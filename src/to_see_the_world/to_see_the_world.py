#!/usr/bin/env python3
from ast import literal_eval
import configparser
from datetime import datetime
import glob
from math import radians, sin, cos, acos
from pathlib import Path
import re
import time

from flatten_dict import flatten
import folium
from folium.plugins import TimestampedGeoJson
import gpxpy.gpx
import pandas as pd
import polyline
from pretty_html_table import build_table
import requests
from stravalib import Client
from thefuzz import process, fuzz
from wordcloud import WordCloud, STOPWORDS
import xyzservices.providers as xyz

from coordinates_to_countries import CoordinatesToCountries


class Utils:
    def __init__(self):
        self.pwd = Path.cwd()
        self.config = configparser.ConfigParser()
        self.config.read(f'{self.pwd}/config.ini')
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
        
    def get_cc(self, df, id):
        return df.get(df.id == id
            ).country_code.values[0].split(',')
        
    def limit_time(self, time_str, df, start=True):
        if time_str:
            if start:
                 print(f'Start Time: {time_str}')
                 df = df.get(
                     df.start_date_local >= time_str)
            else:
                print(f'End Time: {time_str}')
                df = df.get(
                     df.start_date_local <= time_str)
        return df
    
    def get_distance(self, df, ida, idb):
        coordsa = df.get(df.id == ida
            ).coords.values[0]
        coordsb = df.get(df.id == idb
            ).coords.values[0]
        lata = radians(coordsa[-1][0])
        lona = radians(coordsa[-1][1])
        latb = radians(coordsb[0][0])
        lonb = radians(coordsb[0][1])
        mean_radius_earth = float(self.config.get(
            'units', 'mean_radius_earth'))
        dist = mean_radius_earth * \
            acos(sin(lata) * sin(latb) + \
            cos(lata) * cos(latb) * cos(lona - lonb))
        return round(dist, 2)
    
    def encode(self, msg):
        ans = ''
        i = 0
        while (i <= len(msg) - 1):
            count = 1
            ch = msg[i]
            j = i
            while (j < len(msg) - 1):
                if (msg[j] == msg[j + 1]):
                    count += 1
                    j += 1
                else:
                    break
            ans = f'{ans} {count}:{ch}'
            i = j + 1
        return ans

class CountryData:
    def __init__(self, fname_country_data):
        # Namibia (NA) is read as NaN
        self.U = Utils()
        self.df_country_data = pd.read_csv(
            fname_country_data, na_filter = False)
        self.ratio = 70

    def get_country_centroids(self):
        df_cd = self.df_country_data
        df_cd['country_centroid'] = \
            df_cd.country_centroid.apply(
            lambda x: literal_eval(str(x)))
        return self.df_country_data[[
            'country_code',
            'country_name',
            'country_centroid']].drop_duplicates()

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
        df_explode = df[['id', 'coords']].explode(
            'coords').dropna()
        coords_slice = list(df_explode.coords)[::slice]
        print('Finding coordinate meta data for '
            f'{len(coords_slice)} points')
        CTC = CoordinatesToCountries()
        df_slice = CTC.run(coords_slice)
        df_slice['id'] = list(df_explode.id)[::slice]
        border_crossings = \
            self.check_border_crossings(df_slice)
        df_slice['border_crossings'] = \
            df_slice.id.apply(
            lambda x: border_crossings[x])
        df_slice = df_slice.drop_duplicates(
            subset=['id', 'country_code', 'admin_name'])
        df_slice = df_slice.groupby('id').agg(
            {'country_code': 
                 lambda x: ','.join(list(dict.fromkeys(x))),
             'admin_name': ','.join,
             'border_crossings': 'mean'}).reset_index()
        df = pd.merge(
            df, df_slice[['id',
            'country_code', 'admin_name',
            'border_crossings']], on='id', how='right')
        df.coords = \
            df.coords.apply(tuple)
        df = self.edit_borders(df)
        df['country_name'] = df.country_code.apply(
            lambda x: \
            self.country_code_to_country_name(x))
        return df

    def edit_borders(self, df):
        df = df.sort_values(by='start_date_local')
        df_a = df.get(df.border_crossings > 1)
        ids = list(df.id.values)
        a_ids = list(df_a.id.values)
        if df.shape[0] <= 3:
            return df
        for idx, i in enumerate(ids):
            if i not in a_ids:
                continue
            prev_id = ids[idx - 1]
            cur_id = i
            next_id = ids[idx + 1]
            prev_cc = self.U.get_cc(df, prev_id)
            cur_cc = self.U.get_cc(df, cur_id)
            next_cc = self.U.get_cc(df, next_id)
            bc = df.get(df.id == cur_id
                ).border_crossings.values[0]
            len_next_cc = len(next_cc)
            if len(cur_cc) == 1:
                # Skipping, odd data
                continue
            if len_next_cc == 1:
                if bc == 2:
                    # Check for standard border crossing
                    if prev_cc == next_cc:
                        # No border crossing.
                        # Set current cur_cc to prev_cc
                        df.loc[df.id == cur_id, 'country_code'
                            ] = ','.join(prev_cc)
                    elif cur_cc[0] in prev_cc and \
                        cur_cc[1] == next_cc[0]:
                        # A border was crossed,
                        # cur_cc is valid
                        pass
                    else:
                        # Inconclusive,
                        # set cur_cc to prev_cc
                        df.loc[df.id == cur_id, 'country_code'
                            ] = prev_cc
                elif bc == 3:
                    # Check for country crossing,
                    # note: cannot currently check for
                    # re-entering the original country
                    if prev_cc == cur_cc[0] \
                        and len(cur_cc) == 3:
                        # A country was crossed.
                        # cur_cc is valid
                        pass
                    else:
                        # Inconclusive.
                        # Set cur_cc to prev_cc
                        df.loc[df.id == cur_id, 'country_code'
                            ] = ','.join(prev_cc)
                else:
                    # bc > 3, the data very likely bad.
                    # Set cur_cc to prev_cc
                    df.loc[df.id == cur_id, 'country_code'
                        ] = ','.join(prev_cc)
            elif len_next_cc == 2:
                if cur_cc[0] in prev_cc and \
                    cur_cc[1] == next_cc[0]:
                    # A country was crossed.
                    # cur_cc is valid
                    pass
                else:
                    # Inconclusive,
                    # set cur_cc to prev_cc
                    df.loc[df.id == cur_id, 'country_code'
                        ] = ','.join(prev_cc)
            else:
                # len(next_cc) > 1. There is likely
                # some bad data. Set cur_cc to prev_cc  
                df.loc[df.id == cur_id, 'country_code'
                    ] = ','.join(prev_cc)
        return df
        
    def check_border_crossings(self, df):
        bc = {}
        for i in sorted(list(set(df.id))):
            dfa = df.get(df.id == i)
            num_bc = len(dfa.groupby(
                [dfa['country_code'].ne(
                dfa['country_code'].shift()
                ).cumsum(), 'country_code']
                ).size())
            bc[i] = num_bc
        return bc
    
    def country_code_to_country_name(self, cc):
        ans = ''
        cc_list = cc.split(',')
        for c in cc_list:
            if len(ans) > 0:
                ans += ','
            ans +=  list(self.df_country_data.get(
                self.df_country_data.country_code \
                == c)['country_name'])[0]
        return ans
            
    def get_admin_tracking(self, df, cc):
        adm_visit = list(df.admin_name.values)
        tot_country_adm = self.df_country_data.get(
            self.df_country_data.country_code == cc)[[
                'admin_name', 'admin_type']]
        tuple_adm = list(zip(
            tot_country_adm.admin_name,
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
        self.pwd = Path.cwd()
        self.config = configparser.ConfigParser()
        self.config.read(f'{self.pwd}/config.ini')
        self.secrets = configparser.ConfigParser()
        self.secrets.read(f'{self.pwd}/secrets.ini')
        self.U = Utils()
        self.pickles = pickles
        self.code = \
            self.get_code_from_http_string(
            http_with_code)
        self.col_names = self.config.get(
            'data', 'col_names').split(', ')
        self.df_base = self.U.create_base(
            self.pickles)
        self.print_df_size_by_a_id(self.df_base)
        fname_country_data = self.config.get(
            'path',
            'fname_country_data')
        self.CD = CountryData(
            f'{self.pwd}/{fname_country_data}')
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

    def run(self, activity=0, page_count=200,
        s_time_str='', e_time_str=''):
        if not hasattr(self, "headers"):
            return self.df_base
        code_a_id = self.run_athlete_query()
        final_time = self.get_df_final_time(
            self.df_base, code_a_id)
        df = self.U.setup_df()
        if activity:
            df, data_end = \
                self.run_activities_query(
                    df, code_a_id,
                    final_time, activity=activity)
        else:
            for page in range(1, page_count):
                df, data_end = \
                    self.run_activities_query(
                        df, code_a_id,
                        final_time, activity, page=page,
                        s_time_str=s_time_str,
                        e_time_str=e_time_str)
                if data_end:
                    if len(df) == 0:
                        print(f'{code_a_id}: '
                            'No new rides found')
                        return self.df_base
                    else:
                        break
        df = self.add_coord_columns(df)
        df = self.clean_df(
            self.df_base, df, code_a_id)
        self.save_pickle(df, code_a_id)
        self.print_df_size_by_a_id(df)
        return df
    
    def get_code_from_http_string(
        self, http_with_code):
        m = re.search("code=(.*)&",
            http_with_code)
        if m:
            code = m.group(1)
        else:
            code = ''
        return code
      
    def add_coord_columns(self, df):
        df['coords'] = df[
            'map/summary_polyline'].apply(
            polyline.decode)
        return self.CD.get_geo(df, slice=2)
        
    def get_df_final_time(self, df, a_id,):
        strava_create_time = datetime.strptime(
            '2009', "%Y")
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
            final_time = strava_create_time
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
        self, df, a_id, final_time, activity, page=0,
        per_page=200, s_time_str='', e_time_str=''):
        data_end = False
        if activity:
            activity_req = ('activities'
                f'/{activity}?include_all_efforts=false')
        else:
            activity_req = (
                f'athlete/activities?page={page}&'
                f'per_page={per_page}')
            if s_time_str:
                s_time_linux = datetime.timestamp(
                    datetime.strptime(
                    s_time_str, '%Y-%m-%d'))
                activity_req += f'&after={s_time_linux}'
            if e_time_str:
                e_time_linux = datetime.timestamp(
                    datetime.strptime(
                    e_time_str, '%Y-%m-%d'))
                activity_req += f'&before={e_time_linux}'
        req = ('https://www.strava.com/api/v3/'
            f'{activity_req}')
        response = requests.get(req,
            headers = self.headers,
            timeout=180).json()
        if 'message' in str(response):
            print(f'Issue. Response json: {response}')
        if activity:
            response = [response]
        for r in response:
            try:
                code_final_time = \
                    datetime.strptime(
                    r.get('start_date_local'),
                    '%Y-%m-%dT%H:%M:%SZ')
                if code_final_time <= final_time:
                    data_end = True
                    print(f'{a_id}: Data is now ' 
                              'complete. Breaking from '
                              'response loop')
                    break
            except:
                print(f'Error, response was: {r}')
            df_r = self.reduce_response(r)
            df = pd.concat([df, df_r],     
                ignore_index=True)
        print(f'{a_id}: Page {page} has ' 
                  f'{len(response)} data points')
        if len(response) < per_page:
            print(f'{a_id}: Finished gathering data '
                      f'for page: {page}')
            data_end = True
        return df, data_end

    def reduce_response(self, r):
        r.pop('start_latlng', None)
        r.pop('end_latlng', None)
        r.pop('available_zones', None)
        r.pop('stats_visibility', None)
        r.pop('segment_efforts', None)
        r.pop('splits_metric', None)
        r.pop('laps', None)
        r.pop('splits_standard', None)
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
        self.pwd = Path.cwd()
        self.config = configparser.ConfigParser()
        self.config.read(f'{self.pwd}/config.ini')
        self.pickles = self.U.get_local_pickle_files()
        self.dist_conv = float(
            self.config.get('units', 'dist_conv'))
        self.elev_conv = float(
            self.config.get('units', 'elev_conv'))
        self.dist_label = self.config.get(
            'units', 'dist_label')
        self.elev_label = self.config.get(
            'units', 'elev_label')
        self.sec_to_hr = float(self.config.get(
            'units', 'sec_to_hr'))
        self.full_day_hrs = float(
            self.config.get('data', 'full_day_hrs'))
        self.otd_url = self.config.get('api', 'otd_url')
        self.pwd = Path.cwd()

    def run(self,
        s_time_str='',
        e_time_str='',
        activity=0,
        gpx=False,
        elevations=False):
         print('×××××× Summary by Athlete ××××××')
         df = self.U.create_base(self.pickles)
         df = self.U.limit_time(
             s_time_str, df, start=True)
         df = self.U.limit_time(
             e_time_str, df, start=False)
         units = self.config.get('units', 'dist_label')
         if activity:
             print(
                 f'Limit summary to activity: {activity}')
             df = df.get(df.id == activity)
         a_ids = self.U.get_a_id_list(df)
         for a_id in a_ids:
             df_a_id = df.get(df['athlete/id'] == a_id)
             dist = round(df_a_id.distance.sum() *
                 self.dist_conv, 0)
             elev = round(
                 df_a_id.total_elevation_gain.sum() *
                 self.elev_conv, 0)
             elev_dist = round(elev/dist, 0)
             moving_time = round(
                 df_a_id.moving_time.sum() *
                 self.sec_to_hr, 1)
             avg_speed = round(dist/moving_time, 1)
             num_activities = len(df_a_id)
             num_full_day = \
                 len(df_a_id.get(df_a_id.moving_time 
                     >= self.full_day_hrs/self.sec_to_hr))
             origin, furthest_point, fp_dist = \
                 self.get_furthest_point(df_a_id)
             countries = list(set(','.join(
                 df_a_id.country_name.values.tolist()
                 ).split(',')))
             admin_names = list(set(','.join(
                 df_a_id.admin_name.values.tolist()
                 ).split(',')))
             countries.sort()
             admin_names.sort()
             print(f'Athlete: {a_id}')
             print(f'    Total Distance: {dist} '
                      f'{self.dist_label}')
             print(f'    Total Elevation Gain: {elev} '
                      f'{self.elev_label}')
             print(f'    Average Elevation: {elev_dist} '
                      f'{self.elev_label}/{self.dist_label}')
             print(f'    Moving Time: {moving_time} hrs')
             print(f'    Average Speed: {avg_speed} '
                      f'{self.dist_label}/hr')
             print('    Number of Activities: '
                      f'{num_activities}')
             print('    Number of Full Days'
                      f'(>{self.full_day_hrs} hrs): ' 
                      f'{num_full_day}')
             print('    Furthest Point From First Ride:')
             print(f'        Origin: {origin}')
             print('        Furthest Point: '
                 f'{furthest_point}')
             print(f'        Distance: {fp_dist} {units}')
             print(f'    Countries ({len(countries)}): '    
                      f'{", ".join(countries)}')
             print('     Admin Areas: '
                      f'({len(admin_names)}): ' 
                      f'{", ".join(admin_names)}')
             if gpx:
                 fname = f'{a_id}_{"_".join(countries)}.gpx'
                 self.save_gpx(
                     df, elevations, fname=fname)
              
    def add_elevations(self, lst, elevations):
        if elevations:
            elevations = self.get_elevations(lst)
        else:
            print('All elevation data set to 0.')
            elevations = len(lst) * [0]
        lst = [x + (elevations[
            idx],) for idx, x in enumerate(lst)]
        return lst
    
    def get_elevations(self, lst, req_limit=100):
        elevations = []
        wait_time =round(len(lst)/req_limit + 0.49)
        print('Adding elevation data to gpx. '
            f'Limited to {req_limit} requests per '
            f'second. There are {len(lst)} requests. ' 
            f'Please wait for {wait_time} requests.')
        for i in range(0, len(lst), req_limit):
            time.sleep(0.8)
            coords = pd.DataFrame(
                lst[i: i + req_limit],
                columns=['lat', 'long'])
            coords_str = coords.to_string(
                col_space=1, index=False, header=False)
            coords_str = ",".join(
                coords_str.replace('\n', '|').split())
            req_data = {"locations": coords_str,
                                 "interpolation": "bilinear"}
            r = requests.post(
                self.otd_url, data=req_data, timeout=10)
            if r.json()['status'] == 'OK':
                results = r.json()['results']
                elevations += [
                    res['elevation'] for res in results]
                print(f'Request: {i}:{i + req_limit}')
            else:
                e = r.json()['error']
                print(f'Error in add_elevation: {e}. '
                    'Adding "0"s instead')
                elevations += len(i) * [0]
        return elevations

    def save_gpx(self, df, elevations, fname='out'):
        print(f'Saving gpx file as: {fname}')
        df = df.sort_values(['start_date_local'],
            ascending = True)
        gpx = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)
        gpx_seg = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_seg)
        lst = sum(df["coords"].apply(
            lambda x: [i for i in x]), [])
        lst = self.add_elevations(lst, elevations)
        for x in lst:
            gpx_seg.points.append(
                gpxpy.gpx.GPXTrackPoint(
                latitude = x[0],
                longitude = x[1],
                elevation = x[2]))
        xml = gpx.to_xml()
        f = open(f'{self.pwd}/output/{fname}', 'w')
        f.write(xml)
        f.close()
        
    def get_furthest_point(self, df):
        df = df.sort_values(['start_date_local'],
            ascending = True)
        A = df.iloc[0]
        dists = {}
        for b_id in df.id.values:
            dists[b_id] = self.U.get_distance(
                df, A.id, b_id)
        max_id = max(dists, key=dists.get)
        max_dist = dists[max_id]
        B = df.get(df.id == max_id)
        origin = (
            f'{A["name"]} ({A["admin_name"]}, '
            f'{A["country_name"]})')
        furthest_point = (
            f'{B.name.values[0]} '
            f'({B.admin_name.values[0]}, '
            f'{B.country_name.values[0]})')
        return origin, furthest_point, max_dist
  

class Map:
    def __init__(self):
        self.pwd = Path.cwd()
        self.config = configparser.ConfigParser()
        self.config.read(f'{self.pwd}/config.ini')
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
        self.sec_to_hr = float(self.config.get(
            'units', 'sec_to_hr'))
        self.emoji = self.config._sections[
            'map_emoji']
        self.country_flag = self.config._sections[
            'country_flag']
        fname_country_data = self.config.get(
            'path', 'fname_country_data')
        self.CD = CountryData(
            f'{self.pwd}/{fname_country_data}')
        self.U = Utils()
        self.pickles = self.U.get_local_pickle_files()

    def run(self, http_with_code,
        s_time_str='', e_time_str='', activity=0):
        S = StravaData(self.pickles, http_with_code)
        df = S.run(
            s_time_str=s_time_str,
            e_time_str=e_time_str,
            activity=activity).dropna(
            subset=['map/summary_polyline'])
        df = self.U.limit_time(
             s_time_str, df, start=True)
        df = self.U.limit_time(
             e_time_str, df, start=False)
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
         df_cc = self.CD.get_country_centroids()
         for _, row in df_cc.iterrows():
             cc = row['country_code']
             country_name = row['country_name']
             if pd.isna(cc):
                 continue
             popup = self.get_popup(
                 df, cc, country_name)
             if len(popup) == 0:
                 continue
             mk = folium.Marker(
                 location = row.country_centroid,
                 icon = folium.features.CustomIcon(
                     icon_image = self.config.get(
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
         
    def get_popup(self, df, cc, name):
        popup = {
            'Athlete':[],
            'Number of Rides': [],
            f'Distance ({self.dist_label})':[],
            f'Elevation ({self.elev_label})': [],
            'Moving Time (hrs)': [],
            'Administrative Areas Ratio':[],
            'Administrative Areas Visited':[],
            'Administrative Areas Remain':[],
            'Top Words!':[]}
        dfc = df[df.country_code.apply(
            str).str.contains(cc)]
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
            moving_time = round(
                dfa['moving_time_hrs'].sum(), 1)
            adm_ratio, adm_visit, adm_remain = \
                self.CD.get_admin_tracking(dfa, cc)
            top_words = self.get_top_words(dfa)
            popup['Athlete'].append(a_id)
            popup['Number of Rides'].append(
                count)
            popup[
                f'Distance ({self.dist_label})'
            ].append(dist)
            popup[
                f'Elevation ({self.elev_label})'
            ].append(elev)
            popup['Moving Time (hrs)'].append(
                moving_time)
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
            f'<h3>{name}</h3>'
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
    
    def get_country_flag(self, cc):
         emojis = ''
         for c in cc.lower().split(','):
             if c.strip() in self.country_flag:
                 emojis += self.country_flag[c.strip()]
         return emojis
     
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
        df['emoji'] = df['type'].apply(self.get_emoji) +\
            df['country_code'].apply(
            self.get_country_flag)
        df['link'] = df['id'].apply(self.get_link)
        df['distance'] = round(df['distance'] * \
            self.dist_conv, 1)
        df['total_elevation_gain'] = round(
            df['total_elevation_gain'] * \
            self.elev_conv, 0)
        df['moving_time_hrs'] = round(
            df['moving_time'].astype(float) * \
            self.sec_to_hr, 1)
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
                'moving_time_hrs':
                    f"{x['moving_time_hrs']} hrs",
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
                        'moving_time_hrs',
                        'link'],
                    aliases=[
                        'Date: ',
                        'Name: ',
                        'Type: ',
                        'Distance: ', 
                        'Total Elevation Gain: ',
                        'Moving Time: ',
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
     http_with_code = 'https://www.localhost.com/exchange_token?state=&code=64c479b5ff053a2ce3df7b9af2a7c648c6d10417&scope=read,activity:read_all'
     M = Map()
     M.run(
         http_with_code,
         #s_time_str='2024-01-01',
         #e_time_str='2024-08-06',
         #activity=11725858841
     )
     Sm = Summary()
     Sm.run(
         #s_time_str='2023-05-28',
         #e_time_str='2018-12-14',
         #activity=11725858841,
         #gpx=True,
         #elevations=True
         )