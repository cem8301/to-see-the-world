#!/usr/bin/env python3
import configparser
from datetime import datetime
import glob
from pathlib import Path
import re

from flatten_dict import flatten
import folium
from folium.plugins import TimestampedGeoJson
import pandas as pd
import polyline
from pretty_html_table import build_table
import requests
import reverse_geocoder as rg
from stravalib import Client
from thefuzz import process, fuzz
from wordcloud import WordCloud, STOPWORDS
import xyzservices.providers as xyz


class Utils:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.pwd = Path.cwd()
        self.col_names = self.config.get(
            'data', 'col_names').split(', ')
        
    def get_local_pickle_files(self):
        pickle_folder = self.config.get(
            'path', 'pickle_folder')
        pickles = glob.glob(
            f'{self.pwd}/{pickle_folder}/*')
        print(f'local pickle files: {pickles}')
        return pickles
    
    def setup_df(self):
        return pd.DataFrame(
            columns = self.col_names)
    
    def create_base(self, pickles):
         df_base = self.setup_df()
         for pickle in pickles:
             df_tmp = pd. read_pickle(pickle)
             df_base = pd.concat(
             [df_base, df_tmp], ignore_index=True)
         return df_base
    
    def get_a_id_list(self, df):
        return list(set(df.get('athlete/id', {0})))

class CountryData:
    def __init__(self, fname_cc, fname_wad):
        self.df_cc = pd.read_csv(fname_cc)
        self.df_wad = pd.read_csv(
            fname_wad).fillna('unknown')
        self.ratio = 70
        
    def get_country_centroids(self):
        return self.df_cc[['name',
                                        'latitude',
                                        'longitude']]

    def get_visited_adm_areas(self, df, country):
        ca = [ca for cas in list(df['country_admin'])
            for ca in cas]
        df_ca = pd.DataFrame(
            ca, columns=['country', 'admin'])
        strings = set(df_ca[
            df_ca.country == country]['admin'])
        return [x for x in strings if x]
     
    def get_adm_areas_remain(
        self, adm_visit, tuple_adm):
        adm_visit.sort()
        tuple_adm.sort()
        list_adm = [x[0] for x in tuple_adm]
        adm_remain = tuple_adm
        visit_official = []
        for visit in adm_visit:
            ans = False
            matches = process.extract(
                visit,
                list_adm,
                scorer=fuzz.ratio)
            if matches:
                first_match = matches[0]
                if first_match[1] >= self.ratio:
                    ans = (first_match[0],
                                dict(tuple_adm)[first_match[0]])
                else:
                    for match in matches:
                        if fuzz.partial_ratio(
                            visit, match[0]) >= self.ratio:
                            ans = (match[0],
                                        dict(tuple_adm)[match[0]])
                            break
            if ans:
                adm_remain = [
                    i for i in adm_remain if i != ans]
                visit_official.append(ans)
            else:
                pass
                #print(f'{visit} has no match')
        return dict(adm_remain), dict(visit_official)
        
    def get_geo(self, df, slice=1):
        dfe = df[['id','coords']].explode(
            'coords').dropna()
        coords_slice = list(dfe.coords)[::slice]
        ids_slice = list(dfe.id)[::slice]
        ta = {}
        tb = {}
        adm_ccs = [(x['cc'], x['admin1'])
            for x in rg.search(coords_slice)]
        for idx, adm_cc in enumerate(adm_ccs):
            t = (adm_cc[0], adm_cc[1])
            if t not in ta.get(ids_slice[idx], []):
                country = self.cc_to_country(
                    adm_cc[0])
                tb.setdefault(ids_slice[idx],[]
                    ).append((country, adm_cc[1]))
                ta.setdefault(ids_slice[idx],[]
                    ).append(t)
        ans = pd.DataFrame(
            tb.items(),
            columns=['id','country_admin'])
        return ans

    def cc_to_country(self, cc):
        try:
            ans = list(self.df_cc[
                self.df_cc.country == cc]['name'])[0]
        except IndexError as ie:
            ans = 'unknown'
            #print(f'{ie}: for {cc}')
        return ans
            
    def get_admin_tracking(self, df, country):
        #NAME,COUNTRY,ISO_CC,ADMINTYPE
        #Badakhshān,Afghanistan,AF,Province
        adm_visit = self.get_visited_adm_areas(
            df, country)
        tot_country_adm = self.df_wad[
            self.df_wad.country.str.contains(
            country)][['name', 'admin_type']]
        tuple_adm = list(zip(
            tot_country_adm.name,
            tot_country_adm.admin_type))
        adm_remain, visit_official =\
            self.get_adm_areas_remain(
            adm_visit, tuple_adm)
        if len(tot_country_adm) == 0:
            #print(country)
            pass
        str_ratio = ''
        for a in set(tot_country_adm['admin_type']):
            num = len([
                n for n in visit_official.values() if n==a])
            den = len(tot_country_adm.get(
                tot_country_adm.admin_type == a))
            str_ratio += (f"{num}/{den} {a}'s\n")
        return (str_ratio,
            list(visit_official.keys()),
            list(adm_remain.keys()))

class StravaData:
    def __init__(
        self, pickles='', http_with_code=''):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.secrets = configparser.ConfigParser()
        self.secrets.read('secrets.ini')
        self.U = Utils()
        self.pickles = pickles
        self.code = \
            self.get_code_from_http_string(
            http_with_code)
        self.col_names = [    
            'map/summary_polyline',
            'coords',
            'id',
            'achievement_count',
            'athlete/id',
            'start_date_local',
            'type',
            'name',
            'distance',
            'total_elevation_gain',
            'elev_high',
            'elev_low',
            'gear_id']
        self.col_names = self.config.get(
            'data', 'col_names').split(', ')
        self.df_base = self.U.create_base(
            self.pickles)
        self.print_df_size_by_a_id(self.df_base)
        fname_cc = self.config.get(
            'path',
            'fname_country_centroids')
        fname_wad = self.config.get(
            'path',
            'fname_world_administrative_divisions')
        self.CD = CountryData(
            fname_cc, fname_wad)
        try:
            self.headers = self.get_headers(
                self.code)
            print('Authorization code was '
                      'succsessful.')
        except:
            print('Authorization code '
                      'incorrect. Fix or proceed with ' 
                      'local data.')
    
    def df_by_a_id(self, df, a_id):
        return df[df['athlete/id'] == a_id]

    def run(self, activity=0, page_count=200):
        if not hasattr(self, "headers"):
            return self.df_base
        code_a_id = self.run_athlete_query()
        final_time = self.get_df_final_time(
            self.df_base, code_a_id)
        df_code = self.U.setup_df()
        if activity:
            df_code, data_end = \
                self.run_activities_query(
                    df_code, code_a_id,
                    final_time, activity)
        for page in range(1, page_count):
            df_code, data_end = \
                self.run_activities_query(
                    df_code, code_a_id,
                    final_time, activity, page=page)
            if data_end:
                if len(df_code) == 0:
                    print(f'{code_a_id}: '
                        'No new rides found')
                    return self.df_base
                else:
                    break
        df_code = self.add_coord_columns(
            df_code)
        df_full = self.clean_df(
            self.df_base, df_code, code_a_id)
        self.save_pickle(df_full, code_a_id)
        self.print_df_size_by_a_id(df_full)
        return df_full
    
    def get_code_from_http_string(
        self, http_with_code):
        m = re.search("code=(.*)&",
            http_with_code)
        if m:
            code = m.group(1)
        else:
            code = ''
        return code
      
    def add_coord_columns(self, df_code):
        df_code['coords'] = df_code[
            'map/summary_polyline'].apply(
            polyline.decode)
        df_geo = self.CD.get_geo(df_code)
        df_code = pd.merge(
            df_code, df_geo, on='id', how='right')
        df_code.coords = \
            df_code.coords.apply(tuple)
        df_code.country_admin = \
            df_code.country_admin.apply(tuple)
        return df_code
        
    def get_df_final_time(self, df, a_id):
        df = self.df_by_a_id(df, a_id)
        try:
            final_time = \
                datetime.strptime(
                    df.get(
                    'start_date_local').sort_values(
                    ascending=False).iat[0],
                    "%Y-%m-%dT%H:%M:%SZ")
            print(f'{a_id}: Final listed time in '
                      f'pickle file {final_time}')
        except:
            final_time = datetime.strptime(
                '2009', "%Y")
            print(f'{a_id}: No pickle file. Final listed '
                      'time is the creation of Strava '
                      f'and is {final_time}')
        return final_time
        
    def print_df_size_by_a_id(self, df):
        msg = ''
        a_ids = self.U.get_a_id_list(df)
        for a_id in a_ids:
            size = len(self.df_by_a_id(df, a_id))
            msg += f'a_id: {a_id}, size: {size}\n'
        print(msg)

    def clean_df(self, df_base, df, code_a_id):
        print(f'{code_a_id}: end of run_query, '
                  'concat df\'s and remove ' 
                  'duplicates')
        len_df = len(
            self.df_by_a_id(df, code_a_id))
        len_dfb = len(
            self.df_by_a_id(df_base, code_a_id))
        print(f'{code_a_id}: length df: {len_df}, '
                  f'{code_a_id}: length df_base: '
                  f'{len_dfb}')
        dfc = pd.concat([df, df_base],
            ignore_index=True).drop_duplicates()
        len_dfc = len(
            self.df_by_a_id(dfc, code_a_id))
        print(
            f'{code_a_id}: length final df: {len_dfc}')
        return dfc
        
    def get_headers(self, code):
         STRAVA_CLIENT_ID = self.secrets.get(
             'strava', 'STRAVA_CLIENT_ID')
         STRAVA_CLIENT_SECRET = \
             self.secrets.get(
             'strava', 'STRAVA_CLIENT_SECRET')
         client = Client()
         access_dict = \
             client.exchange_code_for_token(
                 client_id= STRAVA_CLIENT_ID,
                 client_secret=\
                     STRAVA_CLIENT_SECRET,
                 code= code)
         token = access_dict.get(
             "access_token", '')
         headers = {
             'Authorization':
             "Bearer {0}".format(token)}
         return headers

    def run_athlete_query(self):
        r = requests.get(
            "https://www.strava.com/api/"
            "v3/athlete",
             headers = self.headers).json()
        return r['id']
        
    def run_activities_query(
        self, df, a_id, final_time,
        activity,
        page=0,
        per_page=200):
        data_end = False
        if activity:
            activity_req = f"/{activity}"
        else:
            activity_req =\
                f"?page={page}&per_page={per_page}"
        response = requests.get(
            "https://www.strava.com/api/v3/"
            f"athlete/activities{activity_req}",
            headers = self.headers).json()
        for r in response:
            try:
                code_final_time = \
                    datetime.strptime(
                    r.get('start_date_local'),
                    "%Y-%m-%dT%H:%M:%SZ")
                if code_final_time <= final_time:
                    data_end = True
                    print(f'{a_id}: Data is now ' 
                              'complete. Breaking from '
                              'response loop')
                    break
            except:
                print(f'Issue. Response json: {r}')
            df_r = self.reduce_response(r)
            df = pd.concat([df, df_r],     
                ignore_index=True)
        print(f'{a_id}: Page {page} has ' 
                  f'{len(response)} data points')
        if len(response) == 0:
            print(f'{a_id}: Finished gathering data '
                      f'for page: {page}')
            data_end = True
        return df, data_end

    def reduce_response(self, r):
        r.pop('start_latlng', None)
        r.pop('end_latlng', None)
        df = pd.DataFrame(
            flatten(r, reducer='path'), index=[0])
        df = df[[c for c in df.columns if c in \
            self.col_names]]
        return df

    def save_pickle(self, df, a_id):
        df = self.df_by_a_id(df, a_id)
        folder = self.config.get(
            'path', 'athlete_data_folder')
        fname = f'data_{str(a_id)}.pickle'
        path = Path(folder)
        if not path.exists():
            path.mkdir(parents=True)
        print(f'Saving as {folder}/{fname}')
        df.to_pickle(f'{folder}/{fname}')


class Summary:
    def __init__(self):
        self.U = Utils()
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.pickles = self.U.get_local_pickle_files()
        self.dist_conv = float(
            self.config.get('units', 'dist_conv'))
        self.elev_conv = float(
            self.config.get('units', 'elev_conv'))
        self.dist_label = self.config.get(
            'units', 'dist_label')
        self.elev_label = self.config.get(
            'units', 'elev_label')

    def run(self, s_time_str='', e_time_str=''):
         print('×××××× Summary by Athlete ××××××')
         df = self.U.create_base(self.pickles)
         if s_time_str:
             print(f'Start Time: {s_time_str}')
             df = df.get(
                 df.start_date_local >= s_time_str)
         if e_time_str:
             print(f'End Time: {e_time_str}')
             df = df.get(
                 df.start_date_local <= e_time_str)
         a_ids = self.U.get_a_id_list(df)
         for a_id in a_ids:
             df_a_id = df.get(df['athlete/id'] == a_id)
             dist = round(df_a_id.distance.sum() *
                 self.dist_conv, 0)
             elev = round(
                 df_a_id.total_elevation_gain.sum() *
                 self.elev_conv, 0)
             elev_dist = round(elev/dist, 0)
             country_admin = \
                 df_a_id.country_admin.values.sum()
             countries = list(set(
                 [ca[0] for ca in country_admin]))
             countries.sort()
             admins = list(set(
                 [ca[1] for ca in country_admin]))
             admins.sort()
             print(f'Athlete: {a_id}')
             print(f'    Total Distance: {dist} '
                      f'{self.dist_label}')
             print(f'    Total Elevation Gain: {elev} '
                      f'{self.elev_label}')
             print(f'    Average {self.elev_label}/'
                      f'{self.dist_label}: {elev_dist}')
             print(f'    Countries ({len(countries)}): '    
                      f'{", ".join(countries)}')
             print(f'    Admin Areas: ({len(admins)}): ' 
                      f'{", ".join(admins)}')
             
        
class Map:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.m = folium.Map()
        selection = self.config.get(
            'map', 'tiles').split(', ')
        providers = xyz.flatten()
        for tiles_name in selection:
            tiles = providers[tiles_name]
            folium.TileLayer(
                tiles=tiles.build_url(),
                attr=tiles.html_attribution,
                name=tiles.name,
                show=False
            ).add_to(self.m)
        self.colors = self.config.get(
            'map', 'colors').split(', ')
        self.stroke_width = [
            int(x) for x in self.config.get(
            'map', 'stroke_width').split(', ')]
        self.opacity = [
            int(x) for x in self.config.get(
            'map', 'opacity').split(', ')]
        self.dash_array = [
            int(x) for x in self.config.get(
            'map', 'dash_array').split(', ')]
        self.athlete_count = 0
        self.athlete_ids_list = []
        self.athlete_colors = {}
        self.athlete_stroke_width = {}
        self.athlete_opacity = {}
        self.athlete_dash_array = {}
        self.athlete_lines = {}
        self.font_size = float(
            self.config.get('map', 'font_size'))
        self.dist_conv = float(
            self.config.get('units', 'dist_conv'))
        self.elev_conv = float(
            self.config.get('units', 'elev_conv'))
        self.dist_label = self.config.get(
            'units', 'dist_label')
        self.elev_label = self.config.get(
            'units', 'elev_label')
        self.emoji = self.config._sections[
            'map_emoji']
        fname_cc = self.config.get(
            'path',
            'fname_country_centroids')
        fname_wad = self.config.get(
            'path',
            'fname_world_administrative_divisions')
        self.CD = CountryData(
            fname_cc, fname_wad)
        self.df_c = \
            self.CD.get_country_centroids()
        self.U = Utils()
        self.pickles = self.U.get_local_pickle_files()

    def run(self, http_with_code):
        S = StravaData(self.pickles, http_with_code)
        df = S.run().dropna(
            subset=['map/summary_polyline'])
        a_ids = self.U.get_a_id_list(df)
        print(f'Set up folium map for {len(a_ids)} '
            'athletes')
        for a_id in a_ids:
            self.add_athlete(S.df_by_a_id(df, a_id))
        if len(a_ids) > 0:
            self.create_lines(df, a_ids)
            self.create_athlete_slider(df)
            self.create_country_summaries(df)
            self.add_layer_control()
            self.create_map()
     
    def add_layer_control(self):
        self.m.add_child(folium.LayerControl(
            position='topright',
            collapsed=True,
            autoZIndex=True))

    def create_country_summaries(self, df):
         for _, row in self.df_c.iterrows():
             country = row['name']
             popup = self.get_popup(df, country)
             if len(popup) == 0:
                 continue
             mk = folium.Marker(
                 location=[row.latitude,
                                   row.longitude],
                 icon= folium.features.CustomIcon(
                     icon_image= self.config.get(
                         'map', 'map_icon'),
                     icon_size=(10,10),
                     icon_anchor=(0,0),
                     popup_anchor=(0,0)),
                 popup=folium.Popup(
                     popup,
                     style=(
                        "background-color: white; "                                     "color: #333333; "
                        "font-family: arial; "
                        f"font-size: {self.font_size}px; "
                        "padding: 3px;"
                        "min_width: 6000")))
             self.m.add_child(mk)

    def get_top_words(self, df):
         text = ' '.join(df['name'])
         stopwords = set(STOPWORDS)
         wc = WordCloud(
             max_words=6,
             min_word_length=3,
             collocation_threshold=30,
             stopwords = stopwords
         ).generate(text)
         return ', '.join(wc.words_.keys())
         
    def get_popup(self, df, country):
        popup = {
            'Athlete':[],
            'Number of Rides': [],
            f'Distance ({self.dist_label})':[],
            f'Total Elevation ({self.elev_label})': [],
            'Administrative Areas Ratio':[],
            'Administrative Areas Visited':[],
            'Administrative Areas Remain':[],
            'Top Words!':[]}
        dfc = df[df.country_admin.apply(
            str).str.contains(country)]
        if len(dfc) == 0:
            return ''
        for a_id in self.athlete_ids_list:
            dfa = dfc[dfc['athlete/id']== a_id]
            count = len(dfa)
            if count == 0:
                continue
            dist = round(dfa['distance'].sum(), 1)
            elev = round(
                dfa['total_elevation_gain'].sum(), 0)
            adm_ratio, adm_visit, adm_remain = \
                self.CD.get_admin_tracking(
                dfa, country)
            top_words = self.get_top_words(dfa)
            popup['Athlete'].append(a_id)
            popup['Number of Rides'].append(
                count)
            popup[
                f'Distance ({self.dist_label})'
            ].append(dist)
            popup[
                f'Total Elevation ({self.elev_label})'
            ].append(elev)
            popup['Administrative Areas Ratio'
                ].append(adm_ratio)
            popup['Administrative Areas Visited'
                ].append(adm_visit)
            popup['Administrative Areas Remain'
                ].append(adm_remain)
            popup['Top Words!'].append(top_words)
        dfp = pd.DataFrame(popup)
        tablea = build_table(
            dfp,
            'blue_light',
            padding = '0px 10px 0px 0px',
            font_size= f'{self.font_size}px',
            text_align= 'center')
        tablea = tablea.replace('[',
             '<details><summary>Click to toggle</summary><span>')
        tablea = tablea.replace(']', 
            '</span></details>')
        return (
            f'<h3>{country}</h3>'
            f'{tablea}<br>')
        
    def add_athlete(self, df):
        a_id = list(df.get('athlete/id', '0'))[0]
        ac_print = self.athlete_count +1
        print(f'new athlete line: {a_id}, '
                  f'athlete count: {ac_print}')
        self.athlete_ids_list.append(a_id)
        self.athlete_colors[a_id] = \
            self.colors[self.athlete_count]
        self.athlete_stroke_width[a_id] = \
            self.stroke_width[self.athlete_count]
        self.athlete_opacity[a_id] = \
            self.opacity[self.athlete_count]
        self.athlete_dash_array[a_id] = \
            self.dash_array[self.athlete_count]
        self.athlete_count += 1
        
    def get_emoji(self, the_type):
        if the_type.lower() in self.emoji:
            return self.emoji[the_type.lower()]
        else:
            return self.emoji['other']
     
    def get_link(self, id):
        url = ('https://www.strava.com'
                  f'/activities/{id}')
        return f'<a href="{url}">Strava link</a>'

    def get_athlete_stroke_width(self, a_id):
        return self.athlete_stroke_width[a_id]

    def get_athlete_color(self, a_id):
        return self.athlete_colors[a_id]
        
    def get_athlete_opacity(self, a_id):
        return self.athlete_opacity[a_id]
        
    def get_athlete_dash_array(self, a_id):
        return self.athlete_dash_array[a_id]

    def create_lines(self, df, a_ids):
        df['emoji'] = df['type'].apply(self.get_emoji)
        df['link'] = df['id'].apply(self.get_link)
        df['distance'] = round(df['distance'] * \
            self.dist_conv, 1)
        df['total_elevation_gain'] = round(
            df['total_elevation_gain'] * \
            self.elev_conv, 0)
        df['color'] = df['athlete/id'].apply(
            self.get_athlete_color)
        df['stroke_width'] = df['athlete/id'].apply(
            self.get_athlete_stroke_width)
        df['opacity'] = df['athlete/id'].apply(
            self.get_athlete_opacity)
        df['dash_array'] = df['athlete/id'].apply(
            self.get_athlete_dash_array)
        for a_id in a_ids:
            self.m.add_child(self.create_geo_json(
                df[df['athlete/id']==a_id], a_id))

    def create_athlete_slider(self, df):
        data = []
        for _, row in df.iterrows():
            data.append({
                'color': row['color'],
                'lon': row['coords'][0][1],
                'lat': row['coords'][0][0],
                'times': row['start_date_local']})
        features = [{
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [d['lon'], d['lat']]},
            'properties': {
                'style': {'color' : 'magenta'},
                'icon': 'circle',
                'iconstyle':{
                    'fillOpacity': 0.8,
                    'fillColor': ['green'],
                    'stroke': 'true',
                    'radius': 5},
                'times': [d['times']]}} for d in data]
        gj = {'type': 'FeatureCollection',
                 'name': 'moving',
                 'features': features}
        return TimestampedGeoJson(
            gj,
            period = 'P1D',
            duration = 'P1D',
            max_speed = 30,
            loop = False,
            auto_play = False,
            add_last_point = True
        ).add_to(self.m)

    def get_feature(self, x):
        coords = [(c[1], c[0]) for c in x['coords']]
        start_date_local = datetime. strptime(x['start_date_local'], '%Y-%m-%dT%H:%M:%SZ').strftime('%B %d, %Y')
        return ({
            'type': 'Feature',
            'properties': {
                'stroke': x['color'],
                'stroke-width': x['stroke_width'],
                'stroke-opacity': x['opacity'],
                'dashArray-highlight': '10, 1',
                'dashArray': x['dash_array'],
                'start_date_local': start_date_local,
                'name': x['name'],
                'distance':
                    f"{x['distance']} {self.dist_label}",
                'total_elevation_gain':
                    f"{x['total_elevation_gain']} "
                    f"{self.elev_label}",
                'emoji': x['emoji'],
                'link': x['link'],
                'type': x['type']},
            'geometry': {
                 'type': 'LineString',
                 'coordinates': coords}})

    def create_geo_json(self, df, a_id):
        features = [] 
        for _, row in df.iterrows():
            features.append(self.get_feature(row))
        gj = {'type': 'FeatureCollection',
                 'name': 'strava',
                 'features': features}
        sf = lambda x:{
          'color': x['properties']['stroke'],
          'opacity' : x['properties']['stroke-opacity'],
          'dashArray' : x['properties']['dashArray'],
          'weight': x['properties']['stroke-width']
        }
        hf = lambda x: {
          'color': x['properties']['stroke'],
          'opacity' : x['properties']['stroke-opacity'],
          'dashArray' : x['properties'][
              'dashArray-highlight'],
          'weight': x['properties']['stroke-width']
        }
        return(folium.features.GeoJson(
            gj,
            name = a_id,
            control = True,
            style_function = sf,
            highlight_function = hf,
            popup = \
                folium.features.GeoJsonPopup(
                    fields=[
                        'start_date_local',
                        'name',
                        'emoji',
                        'distance',
                        'total_elevation_gain',
                        'link'],
                    aliases=[
                        'Date: ',
                        'Name: ',
                        'Type: ',
                        'Distance: ', 
                        'Total Elevation Gain: ',
                        'Link: '],
                    style=(
                        "background-color: white; "                                     "color: #333333; "
                        "font-family: arial; "
                        f"font-size: {self.font_size}px; "
                        "padding: 3px;"))))
        
    def create_map(self):
        output_folder = self.config.get(
            'path', 'output_folder')
        a_id_str = '_'.join(
            str(i) for i in self.athlete_ids_list)
        path = Path(output_folder)
        if not path.exists():
            path.mkdir(parents=True)
        print('Saving folium html map as '
                 f'{output_folder}/route_{a_id_str}.html')
        self.m.save(
            f'{output_folder}/route_{a_id_str}.html')
        

if __name__ == "__main__":
     http_with_code = 'https://www.localhost.com/exchange_token?state=&code=8c22a4b1610c76c1deb95c2137eb5d566b85ba91&scope=read,activity:read_all'
     M = Map()
     M.run(http_with_code)
     S = Summary()
     S.run()#s_time_str='2023-05-28')