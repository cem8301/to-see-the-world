#!/usr/bin/env python3.11
import configparser
from pathlib import Path

import pandas as pd
from scipy.spatial import KDTree


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

    def run(self, coords):
        df = self.get_geodata(coords)
        df = self.get_closest_admin(df
            ).sort_values(by=['idx'], ascending=True)
        return df
        
    def setup_data(self, fname):
        f = self.config.get('path', fname)
        return pd.read_csv(
            f'{self.pwd}/{f}', na_filter = False)
        
    def get_geodata(self, coords):
        data = list(zip(
            list(self.df_cb_shifted['lat']),
            list(self.df_cb_shifted['lon'])))
        tree = KDTree(data, leafsize=30)
        _, ii = tree.query(coords, k=1, workers=-1)
        geo_data = {
            'idx': [], 'country_code': [],
            'closest_boundary_coord': [],
            'og_coord': []}
        for idx, i in enumerate(ii):
            geo_data['idx'].append(idx)
            cc = self.df_cb_shifted.iloc[[
                i]].country_code.values[0]
            geo_data['country_code'].append(cc)
            geo_data['closest_boundary_coord'
                ].append(data[i])
            geo_data['og_coord'].append(coords[idx])
        return pd.DataFrame(geo_data)
        
    def get_closest_admin(self, df_geo_data):
        geo_data = {
           'idx': [],
            'country_code': [],
            'closest_boundary_coord': [],
            'og_coord': [],
            'admin_name': [],
            'city': []}
        for cc in set(df_geo_data.country_code):
            sub_df_gd = df_geo_data.get(
                df_geo_data.country_code == cc)
            sub_df_c = self.df_city.get(
                self.df_city.cc == cc)
            geo_data['idx'] += list(sub_df_gd['idx'])
            geo_data['country_code'] += list(
                sub_df_gd['country_code'])
            cb_coord = list(sub_df_gd[
                'closest_boundary_coord'])
            geo_data['closest_boundary_coord'
                ] += cb_coord
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
    coords = [
            (36.17471263921515, -94.23251549603685),# AR, USA
            (22.9219, 105.86972), #vietnam
            (22.48113, 103.97163), #Lao Cai, Vietnam
            (21.68350, 102.10566), #laos
            (19.88874, 102.13589), #laos
            (22.92331, 105.87171), #china
            (21.19285, 101.69193), #china
            (22.50781, 103.96374), #Hekou, China 
            (22.52989, 103.93700), #Hekou, China
            (25.01570, 102.76066)]*1#Kunming, China
    CTC = CoordinatesToCountries()
    ans = CTC.run(coords)
    print(ans)
    print(ans.get(ans.country_code == 'SI')[['closest_boundary_coord']])
