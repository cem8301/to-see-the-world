#!/usr/bin/env python3
import configparser
from time import time

import pandas as pd
from pathlib import Path
import requests
from scipy.spatial import KDTree

from supporting_data.country_boundaries_shifted import ShiftBoundaries

    
class Datasets():
    def __init__(self):
        self.pwd = Path.cwd()
        self.config = configparser.ConfigParser()
        self.config.optionxform = str
        self.config.read(f'{self.pwd}/config.ini')
        self.country_code_converter = \
            self.config._sections[
            'country_code_converter']
        self.fname_country_data = self.config.get(
            'path', 'fname_country_data')
        self.fname_shifted_boundaries = \
            self.config.get('path',
            'fname_country_boundaries_shifted')
        self.SB = ShiftBoundaries()
        
    def run_country_boundaries(self):
        flat = {'lat': [], 'lon': [], 'country_code': []}
        country_polygons = {}
        continent_groups = {}
        for cc in self.country_code_converter:
            cb, continents = \
                self.get_country_boundaries(cc)
            country_polygons.update(cb)
            for continent in continents.split(','):
                continent_groups.setdefault(
                    continent, []).append(cc)
        
        flat_dict = {'lat': [], 'lon': [],
            'country_code': [], 'border_count': []}
        for continent in continent_groups:
            print(continent)
            ccs = continent_groups[continent]
            country_polygons_sub = {
                cc: country_polygons[cc] for cc in ccs
                if cc in country_polygons}
            flat_dict = self.calculate_flat_dict(
                country_polygons,
                country_polygons_sub, flat_dict)
            
        df = pd.DataFrame.from_dict(flat_dict)
        h = df.get(df.border_count == 1).iloc[::50]
        g = df.get(df.border_count > 1)
        df = pd.concat([h, g], ignore_index = True)
        self.save_shifted_boundaries(
            df[['lat', 'lon', 'country_code']])
   
    def calculate_flat_dict(self,
        country_polygons,
        country_polygons_sub, flat_dict):
        shift_df, noshift_df = self.calculate_shift_df(
            country_polygons_sub)
        agg_shift_df = shift_df.groupby('fid').agg(
            {'coords': list,
            'country_code': 'max',
            'border_count': list}).reset_index()
        for k in flat_dict:
            flat_dict[k].extend(
                list(noshift_df[k].values))
        for idx, row in agg_shift_df.iterrows():
             to_shift = {row.country_code: [row.coords]}
             polygons_shifted = self.SB.run(
                 to_shift, offset = -100.0)
             flat_shift = self.SB.flatten(
                 polygons_shifted, round_val=9)
             flat_shift['border_count'] = \
                 self.map_border_count(row, flat_shift,
                     country_polygons_sub)
             for k in flat_dict:
                 flat_dict[k].extend(flat_shift[k])
        return flat_dict

    def calculate_shift_df(self, country_polygons):
        flat_og = self.SB.flatten(
            country_polygons,
            lat_first=False, round_val=9)
        df = pd.DataFrame.from_dict(flat_og)
        df['coords'] = list(zip(df.lat, df.lon))
        df = df.drop_duplicates(
            subset=['coords', 'country_code'])
        vc = df.coords.value_counts()
        df['border_count'] = df.coords.map(vc)
        df_mean = df.groupby(['country_code', 'fid'],
            as_index=False)['border_count'].mean()
        shift_df = df.get(df.fid.isin(list(
            df_mean.get(df_mean.border_count > 1
            )['fid'].values)))
        noshift_df = df.get(df.fid.isin(list(
            df_mean.get(df_mean.border_count == 1
            )['fid'].values)))
        return shift_df, noshift_df
         
    def map_border_count(self, row, flat_shift,
        country_polygons_sub):
        data_other_c = [x for k,v in 
            country_polygons_sub.items() if k != 
            row.country_code for x in v]
        data_other_c = [(y,x) for nested_list in \
            data_other_c for (x,y) in nested_list]
        data = list(zip(
            flat_shift['lat'], flat_shift['lon']))
        a = row.border_count
        b = a[1::] + [a[0]]
        diff = [x - y for x, y in zip(a, b)]
        res = [idx for idx, val in enumerate(diff
            ) if abs(val) == 1]
        # Remove two points right next to each other
        res = [r for r in res if r+1 not in res] 
        border_count = []
        points = [0]
        for r in res:
            point =  row.coords[r]
            _, ii = self.get_closest_point(data, point)
            points.append(ii)
        points.append(len(flat_shift['lat']))
        points.sort()
        for idx in range(0, len(points) - 1):
            country_boundary_segment_center = int(points[idx
                ] + (points[idx + 1] - points[idx])/2)
            dd, ii = self.get_closest_point(data_other_c,
                data[country_boundary_segment_center])
            if dd > 0.1:
                ocean = 1 # true
            else:
                ocean = 2
            #print(row.country_code, ocean, data[country_boundary_segment_center], dd, ii)
            border_count.extend(
                (points[idx + 1] - points[idx]) * [ocean])
        return border_count
     
    def get_closest_point(self, data, point):
        tree = KDTree(data, leafsize=30)
        dd, ii = tree.query(point, k=1, workers=-1)
        return dd, ii
     
    def run_country_data(self):
        if Path(f'{self.pwd}/'
            f'{self.fname_shifted_boundaries}'
            ).is_file():
            print(f'{self.fname_shifted_boundaries} '
                'exists')
            country_polygons = pd.read_csv(
                self.fname_shifted_boundaries,
                na_filter = False)
        else:
            print(f'{self.fname_shifted_boundaries} '
                'does not exist. Please run '
                'run_country_boundaries()')
        country_data = self.get_country_data()
        df = pd.DataFrame(country_data
            ).drop_duplicates()
        centroids = self.get_centroids(
            country_polygons)
        df['country_centroid'] = df[
            'country_code'].apply(
            lambda x: centroids[x])
        self.save_country_data(df)
        
    def save_country_data(self, df):
        print(f'Saving {self.fname_country_data}')
        df.to_csv(
            self.fname_country_data,
            header = True,
            index = False,
            columns = ['admin_name',
            'country_name', 'country_code',
            'admin_type', 'country_centroid'])
    
    def get_admin_bnds_count(self):
        url = (
            'https://services1.arcgis.com/0EOqWP'      
            'tpCmgQr2ay/arcgis/rest/services/'
            'World_Admin_Bnds/FeatureServer/0/'
            'query?where=1%3D1&outFields=*'
            '&returnGeometry=false&returnCountOnly'
            '=true&outSR=4326&f=json')
        c = requests.get(url, timeout = 30).json()
        return c['count']
    
    def get_country_data(self):
        data_count = self.get_admin_bnds_count()
        result_record_count = 1000
        data = {
            'admin_name': [],
            'country_name': [],
            'country_code': [],
            'admin_type': []}
        url = (
            'https://services1.arcgis.com/0EOqWPtp' 
            'CmgQr2ay/arcgis/rest/services/'
            'World_Admin_Bnds/FeatureServer/0/'
            'query?where=1%3D1&outFields=NAME,'
            'COUNTRY,ISO_CC,ADMINTYPE&'
            'outSR=4326&f=json')
        result_offsets = list(range(0, data_count,
            result_record_count))
        #result_offsets = [0]
        #result_record_count = 1
        for result_offset in result_offsets:
            print(f'Url data request for {result_offset}')
            url_offset = (
                f'&resultOffset={result_offset}'
                '&resultRecordCount='
                f'{result_record_count}')
            for retry in range(0,4):
                j = requests.get(f'{url}{url_offset}',
                    timeout = 60)
                if j.ok:
                    j = j.json()
                    break
                else:
                    print('Trying get_country_data again ' 
                        f'({retry}/5). '
                        f'Status code: {j.status_code}')
            for feature in j['features']:
                att = feature['attributes']
                admin_name = att['NAME']
                country_name = att['COUNTRY']
                cc = att['ISO_CC']
                admin_type = att['ADMINTYPE']
                geo = feature['geometry']['rings']
                if cc == ' ':
                    continue
                data['admin_name'].append(
                    admin_name)
                data['country_name'].append(
                    country_name)
                data['country_code'].append(cc)
                data['admin_type'].append(admin_type)
        return data

    def get_centroid(self, v):
        ans = [0, 0]
        n = len(v)
        signedArea = 0
        # For all vertices
        for i in range(len(v)):
            x0 = v[i][0]
            y0 = v[i][1]
            x1 = v[(i + 1) % n][0]
            y1 =v[(i + 1) % n][1]
            # Calculate value of A
            # using shoelace formula
            A = (x0 * y1) - (x1 * y0)
            signedArea += A
            # Calculating coordinates of
            # centroid of polygon
            ans[1] += (x0 + x1) * A
            ans[0] += (y0 + y1) * A
        signedArea *= 0.5
        ans[1] = (ans[1]) / (6 * signedArea)
        ans[0] = (ans[0]) / (6 * signedArea)
        return tuple(ans)

    def get_centroids(self, country_polygons):
        centroids = {}
        for cc in country_polygons:
            sub = country_polygons[cc]
            sub.sort(key=len)
            sub.reverse()
            if cc == 'US' or cc == 'MY':
                #ie, Alaska has a longer border
                coords = sub[1]
            else:
                coords = sub[0]
            centroids[cc] = self.get_centroid(coords)
        return centroids
    
    def get_country_boundaries(self, cc):
        print(f'Querying for {cc}')
        val = self.country_code_converter[cc]
        url = ("https://services.arcgis.com"
            "/P3ePLMYs2RVChkJx/arcgis/rest"
            "/services/World_Countries/"
            "FeatureServer/0/query?where="
            f"ISO_CC%20%3D%20'{val}'&"
            "outFields=COUNTRY,CONTINENT"
            ",LAND_RANK&outSR=4326&f=json")
        for retry in range(0,4):
            j = requests.get(url, timeout = 60)
            if j.ok:
                j = j.json()
                break
            else:
                print('Trying get_country_data again ' 
                    f'({retry}/5). '
                    f'Status code: {j.status_code}')
        country_polygons = {}
        continents = []
        for feature in j['features']:
            if feature['attributes']['LAND_RANK'] <= 2:
                continue
            coords = feature['geometry']['rings']
            country_polygons.setdefault(cc, []
                ).extend(coords)
            continents.append(feature['attributes'
                ]['CONTINENT'])
        continent = ','.join(list(set(continents)))
        return country_polygons, continent
        
    def save_shifted_boundaries(self, flat):
        print(
            f'Saving {self.fname_shifted_boundaries}')
        self.SB.save_csv(flat,     
            fname = self.fname_shifted_boundaries)
            
    def test_country_data_file(self):
        if Path(
            f'{self.pwd}/'
            f'{self.fname_country_data}').is_file():
            print(f'{self.fname_country_data} exists')
            df = pd.read_csv(
                self.fname_country_data,
                na_filter = False)
                
    def test_country_boundaries_shifted_file(self,
        country_codes):
        print(f'{self.pwd}/'
            f'{self.fname_shifted_boundaries}')
        if Path(f'{self.pwd}/'
            f'{self.fname_shifted_boundaries}'
            ).is_file():
            print(f'{self.fname_shifted_boundaries} '
                'exists')
            df = pd.read_csv(
                self.fname_shifted_boundaries,
                na_filter = False)
            data = {}
            for cc in country_codes:
                data[cc] = list(zip(
                    df.get(df.country_code == cc).lat,
                    df.get(df.country_code == cc).lon)) 
            self.SB.save_gpx(data)
            coords = [-30.48457889491692,
                27.61236683325842]
            ans = df.get(df.lat== coords[0])
            print(ans)


if __name__ == "__main__":
    D = Datasets()
    D.run_country_boundaries()
    #D.run_country_data()
    #D.test_country_boundaries_shifted_file(['VN','KH'])
