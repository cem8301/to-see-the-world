#!/usr/bin/env python3.13
import configparser
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import KDTree

from update_local_data2 import Datasets

import time


class CoordinatesToCountries:
    def __init__(self,
        fname_country_data='fname_country_data',
        fname_cb_shifted=
        'fname_country_boundaries_shifted',
        fname_cities='fname_cities500'):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.pwd = Path.cwd()
        self.df_cb_shifted = \
            self.setup_data(fname_cb_shifted)
        self.df_city = self.setup_data(fname_cities)
        self.Datasets = Datasets()

    def run(self, coords):
        st = time.time()
        #df = self.get_geodata_kdtree(coords)
        #df.to_pickle(f'{self.pwd}/kdtree.pickle')
        df = pd.read_pickle(f'{self.pwd}/kdtree.pickle')
        et = time.time()
        print('get_geodata_kdtree: ', et-st)
        st = time.time()
        st = time.time()
        df = self.check_polygon(df)
        #df.to_pickle(f'{self.pwd}/check_polygon.pickle')
        #df = pd.read_pickle(f'{self.pwd}/check_polygon.pickle')
        et = time.time()
        print('check_polygon: ', et-st)
        
     
       
        l= list(df.get(df.country_code.astype(str).str.len()< 3)['fid'].values)
        
        print(df.get(df.country_code.astype(str).str.len()< 3))
        print(len(l))
        print(df)
        v=[]
        for i in l:
           if isinstance(i, list):
               for j in i:
                   if j not in v:
                       v.append(float(j))
           else:
               if i not in v:
                   v.append(float(i))
        print(v)
           
        b=[]
        for x in list(df.country_code):
            if len(x) > 1:
                if x not in b:
                    b.append(x)
        print(b)
        
        exit()
        
        df = self.get_closest_admin(df
            ).sort_values(by=['id'], ascending=True)
        et = time.time()
        print('get_closest_admin: ', et-st)
        return df
        
    def setup_data(self, fname):
        f = self.config.get('path', fname)
        return pd.read_csv(
            f'{self.pwd}/{f}', na_filter = False)

    def get_geodata_kdtree_og(self, coords):
        tott = 0
        data = list(zip(
            list(self.df_cb_shifted['lat']),
            list(self.df_cb_shifted['lon'])))
        tree = KDTree(data, leafsize=30)
        _, ii = tree.query(coords['coords'], k=2,
            workers=-1)
        geo_data = {
            'id': [], 'fid': [], 'country_code': [],
            'og_coord': []}
        polies = {}
        for idx, i in enumerate(ii):
            geo_data['id'].append(coords['id'][idx])
            og_coord = coords['coords'][idx]
            cc = 0
            fid = 0
            for ix in i:
                cc_test = self.df_cb_shifted.iloc[[ix]
                    ].country_code.values[0]
                fid = self.df_cb_shifted.iloc[[
                    ix]].fid.values[0]
                if fid in polies:
                    poly = polies[fid]
                else:
                    poly = list(self.df_cb_shifted.get(
                        self.df_cb_shifted.fid == fid
                        ).apply(lambda row: [row['lat'],
                        row['lon']], axis=1))
                    polies[fid] = poly
                st = time.time()
                ans = self.is_point_in_polygon(
                    og_coord, poly)
                et = time.time()
                tott += et-st
                if ans:
                    cc = cc_test
                    continue
            geo_data['fid'].append(fid)
            geo_data['country_code'].append(cc)
            geo_data['og_coord'].append(og_coord)
        print('is_point_in_polygon: ', tott)
        return pd.DataFrame(geo_data)

    def get_geodata_kdtree(self, coords):
        tott = 0
        data = list(zip(
            list(self.df_cb_shifted['lat']),
            list(self.df_cb_shifted['lon'])))
        tree = KDTree(data, leafsize=30)
        _, ii = tree.query(coords['coords'], k=2,
            workers=-1)
        geo_data = {
            'id': [], 'og_coord': [], 'fid': [],
            'country_code': []}
        for idx, i in enumerate(ii):
            cc = []
            fid = []
            geo_data['id'].append(coords['id'][idx])
            og_coord = coords['coords'][idx]
            for ix in i:
                cc_ans = self.df_cb_shifted.iloc[[ix]
                    ].country_code.values[0]
                if cc_ans not in cc:
                    cc.append(cc_ans)
                fid_ans = self.df_cb_shifted.iloc[[
                    ix]].fid.values[0]
                if fid_ans not in fid:
                    fid.append(fid_ans)
            geo_data['fid'].append(fid)
            geo_data['country_code'].append(cc)
            geo_data['og_coord'].append(og_coord)
        print('is_point_in_polygon: ', tott)
        return pd.DataFrame(geo_data)
        
    def is_point_in_polygon_og(self, point, polygon):
        x, y = point
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y) and y <= max(
                p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    x_intersection = (y - p1y) * (p2x - p1x
                        ) / (p2y - p1y) + p1x
                else:
                    x_intersection = p1x
                if p1x == p2x or x <= x_intersection:
                    inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    # Source - https://stackoverflow.com/a
    # Posted by user3274748, modified by community. See post 'Timeline' for change history
    # Retrieved 2025-11-29, License - CC BY-SA 4.0
    def is_point_in_polygon(self,points, poly):
        x = np.array([point[0] for point in points])
        y = np.array([point[1] for point in points])
        n = len(poly)
        inside = np.zeros(len(x), np.bool_)
        p2x = 0.0
        p2y = 0.0
        xints = 0.0
        p1x,p1y = poly[0]
        for i in range(n+1):
            p2x,p2y = poly[i % n]
            idx = np.nonzero((y > min(p1y,p2y)) & (y <= max(p1y,p2y)) & (x <= max(p1x,p2x)))[0]
            if p1y != p2y:
                xints = (y[idx]-p1y)*(p2x-p1x)/(p2y-p1y
                    )+p1x
            if p1x == p2x:
                inside[idx] = ~inside[idx]
            else:
                if isinstance(x[idx], list) \
                    and isinstance(xints, list):
                    if len(x[idx]) == 0 and len(xints) > 1:
                        pass
                        print('h')
                    else:
                        idxx = idx[x[idx] <= xints]
                        inside[idxx] = ~inside[idxx]
                else:
                     pass
                     print('i')
            p1x,p1y = p2x,p2y
        ans = [point for idx, point in enumerate(
            points) if inside[idx]]
        print(len(points), len(ans))
        return ans

    def check_polygon(self, df):
        fids = set(list(df['fid'].explode()))
        df['fid'] = df['fid'].apply(lambda x: x[0
            ] if isinstance(x, list) and len(x) == 1 else x)
        df['country_code'] = df['country_code'
            ].apply(lambda x: x[0
            ] if isinstance(x, list) and len(x) == 1 else x)
        for fid in fids:
            poly = list(self.df_cb_shifted.get(
                self.df_cb_shifted.fid == fid
                ).apply(lambda row: [row['lat'],
                row['lon']], axis=1))
            dfb = df[df['fid'].apply(
                lambda x: isinstance(x, list))]
            point = list(dfb[dfb['fid'].apply(
                lambda x: fid in x)]['og_coord'])
            inside = self.is_point_in_polygon(
                    point, poly)
            df.loc[df.og_coord.isin(inside), 'fid'] = fid
            cc = self.df_cb_shifted.get(
                self.df_cb_shifted.fid == fid
                )['country_code'].values[0]
            df.loc[df.og_coord.isin(inside
                ), 'country_code'] = cc
        return df
        
    def get_closest_admin(self, df_geo_data):
        geo_data = {
            'id': [],
            'fid': [],
            'country_code': [],
            'og_coord': [],
            'admin_name': [],
            'city': []}
        for cc in set(df_geo_data.country_code):
            if not cc:
                continue
            sub_df_gd = df_geo_data.get(
                df_geo_data.country_code == cc)
            sub_df_c = self.df_city.get(
                self.df_city.cc == cc)
            geo_data['id'] += list(sub_df_gd['id'])
            geo_data['fid'] += list(sub_df_gd['fid'])
            geo_data['country_code'] += list(
                sub_df_gd['country_code'])
            og_coord = list(sub_df_gd[
                'og_coord'])
            geo_data['og_coord'
                ] += og_coord
            data = list(zip(
                list(sub_df_c['lat']),
                list(sub_df_c['lon'])))
            tree = KDTree(data, leafsize=30)
            _, ii = tree.query(og_coord, k=1,
                workers=-1)
            for i in ii:
                geo_data['admin_name'].append(
                    sub_df_c.iloc[[i]].admin1.values[0])
                geo_data['city'].append(
                    sub_df_c.iloc[[i]].name.values[0])
        return pd.DataFrame(geo_data)



if __name__ == "__main__":
    mult = 1
    coords = {
        'id': [0,1,2,3,4,5,6,7,8,9,10]*mult,
        'coords': [(42.4755, 1.9644517),#ES
            (36.17471, -94.2325154),# AR, USA
            (22.9219, 105.86972),  #vietnam
            (22.48113, 103.97163), #Lao Cai, Vietnam
            (21.68350, 102.10566), #laos
            (19.88874, 102.13589), #laos
            (22.92331, 105.87171), #china
            (21.19285, 101.69193), #china
            (22.50781, 103.96374), #Hekou, China 
            (22.52989, 103.93700), #Hekou, China
            (25.01570, 102.76066)]*mult}#Kunming, China
    CTC = CoordinatesToCountries()
    ans = CTC.run(coords)
    print(ans)
