#!/usr/bin/env python3.11
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
        
    def run_country_boundaries(self, shift=False):
        flat = {'lat': [], 'lon': [], 'country_code': []}
        country_polygons = {}
        for cc in self.country_code_converter:
            country_polygons = \
                self.get_country_boundaries(
                cc, country_polygons)

        flat_dict = {'lat': [], 'lon': [],
            'country_code': [], 'border_count': [],
            'fid': []}
        for continent in country_polygons:
            print(continent)
            country_polygons_sub = country_polygons[
                continent]
            flat_dict = self.calculate_flat_dict(
                country_polygons_sub, flat_dict, shift)
            
        df = pd.DataFrame.from_dict(flat_dict)
        indexes = df[df.border_count == 1].sample(
            frac=0.95).index
        df = df.drop(indexes)
        self.save_shifted_boundaries(
            df[['lat', 'lon', 'country_code', 'fid']])
   
    def calculate_flat_dict(self,
        country_polygons_sub,
        flat_dict, shift):
        df = self.calculate_border_count(
            country_polygons_sub)
        if shift:
            noshift_df = df.get(df.bc_fid_avg == 1.0)
            shift_df = df.get(df.bc_fid_avg > 1.0) 
            for k in flat_dict:
                flat_dict[k].extend(
                    list(noshift_df[k].values))  
            agg_shift_df = shift_df.groupby('fid').agg(
                {'coords': list,
                'country_code': 'max',
                'border_count': list}).reset_index()
            for idx, row in agg_shift_df.iterrows():
                 to_shift = {row.country_code: {row.fid: [
                    row.coords]}}
                 polygons_shifted = self.SB.run(
                     to_shift, offset = -100.0)
                 flat_shift = self.SB.flatten(
                     polygons_shifted, round_val=9)
                 flat_shift['border_count'] = \
                     map_border_count(row, flat_shift,
                         country_polygons_sub)
                 for k in flat_dict:
                     flat_dict[k].extend(flat_shift[k])
        else:
            for k in flat_dict:
                flat_dict[k].extend(list(df[k].values))  
        return flat_dict

    def calculate_border_count(self,
        country_polygons):
        flat_og = self.SB.flatten(country_polygons,
            lat_first=False, round_val=9)
        df = pd.DataFrame.from_dict(flat_og)
        df['coords'] = list(zip(df.lat, df.lon))
        df = df.drop_duplicates(
            subset=['coords', 'country_code'])
        vc = df.coords.value_counts()
        df['border_count'] = df.coords.map(vc)
        df['bc_fid_avg'] = df.groupby(
            ['country_code', 'fid'], as_index=False
            )['border_count'].transform('mean') 
        return df
         
    def map_border_count(self, row, flat_shift,
        country_polygons_sub):
        data_other_c = []
        for cc in country_polygons_sub:
            if cc != row.country_code:
                for fid in country_polygons_sub[cc]:
                    nested_list = country_polygons_sub[
                        cc][fid]
                    for coords in nested_list:
                        for (x,y) in coords:
                            data_other_c.append((y,x))
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
            country_boundary_segment_center = int(
                points[idx
                ] + (points[idx + 1] - points[idx])/2)
            dd, ii = self.get_closest_point(
                data_other_c,
                 data[country_boundary_segment_center
                 ])
            if dd > 0.1:
                ocean = 1 # true
            else:
                ocean = 2
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
    
    def get_country_boundaries(
        self, cc, country_polygons={}):
        print(f'Querying for {cc}')
        val = self.country_code_converter[cc]
        url = ("https://services.arcgis.com"
            "/P3ePLMYs2RVChkJx/arcgis/rest"
            "/services/World_Countries/"
            "FeatureServer/0/query?where="
            f"ISO_CC%20%3D%20'{val}'&"
            "outFields=COUNTRY,CONTINENT"
            ",LAND_RANK,FID&outSR=4326&f=json")
        for retry in range(0,4):
            j = requests.get(url, timeout = 60)
            if j.ok:
                j = j.json()
                break
            else:
                print('Trying get_country_data again ' 
                    f'({retry}/5). '
                    f'Status code: {j.status_code}')
        for feature in j['features']:
            #if feature['attributes']['LAND_RANK'] <= 2:
            #    continue
            fid = feature['attributes']['FID']
            coords = feature['geometry']['rings']
            continent = feature[
                'attributes']['CONTINENT']
            country_polygons.setdefault(continent, {})
            country_polygons[continent].setdefault(
                cc, {})
            country_polygons[continent][cc].setdefault(
                fid, []).extend(coords)
        return country_polygons
 
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
        country_codes=[], fids=[]):
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
            if country_codes:
                for cc in country_codes:
                    data.setdefault(cc, {})
                    for fid in set(df.get(
                        df.country_code == cc
                        ).fid.values):
                        #print(fid)
                        lat = df.get(df.fid == fid).lat
                        lon = df.get(df.fid == fid).lon
                        data[cc].setdefault(fid, []).append(
                            list(zip(lat, lon)))
            elif fids:
                data['fid'] = {}
                for fid in fids:
                    lat = df.get(df.fid == fid).lat
                    lon = df.get(df.fid == fid).lon
                    print(f'size of shape: {len(lat)}')
                    data['fid'].setdefault(fid, []).append(
                        list(zip(lat, lon)))
            else:
                print('please supply ccs or fids. exiting')
                exit()
            self.SB.save_gpx(data)
            #coords = [-30.48457889491692,
#                27.61236683325842]
#            ans = df.get(df.lat== coords[0])
#            print(ans)


if __name__ == "__main__":
    D = Datasets()
    #D.run_country_boundaries(shift=False)
    
    #D.run_country_data()
    D.test_country_boundaries_shifted_file(
        country_codes=[],fids=[276.0006])
        