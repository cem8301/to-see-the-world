#!/usr/bin/env python3
import configparser
from pathlib import Path

import pandas as pd
from scipy.spatial import KDTree


class CoordinatesToCountries:
    def __init__(self,
        fname_cb_shifted=
        'fname_country_boundaries_shifted',
        fname_cities='fname_cities500'):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.pwd = Path.cwd()
        fname_cb_shifted = \
            self.config.get('path', fname_cb_shifted)
        fc = self.config.get('path', fname_cities)
        self.df_country = pd.read_csv(
            f'{self.pwd}/{fname_cb_shifted}')
        self.df_city = pd.read_csv(f'{self.pwd}/{fc}')

    def run(self, coords):
        df = self.get_geodata(coords)
        df = self.get_closest_admin(df
            ).sort_values(by=['idx'], ascending=True)
        return df
        
    def get_geodata(self, coords):
        data = list(zip(
            list(self.df_country['lat']),
            list(self.df_country['lon'])))
        tree = KDTree(data, leafsize=30)
        _, ii = tree.query(coords, k=1, workers=-1)
        geo_data = {
            'idx': [], 'cc': [], 'country': [], 'coord': []}
        for idx, i in enumerate(ii):
            geo_data['idx'].append(idx)
            cc = self.df_country.iloc[[
                i]].country_code.values[0]
            name = self.df_country.iloc[[
                i]].country_name.values[0]
            geo_data['cc'].append(cc)
            geo_data['country'].append(name)
            geo_data['coord'].append(data[i])
        return pd.DataFrame(geo_data)
        
    def get_closest_admin(self, df_geo_data):
        geo_data = {
           'idx': [],
            'cc': [],
            'country': [],
            'coord': [],
            'admin': [],
            'city': []}
        for cc in set(df_geo_data.cc):
            sub_df_gd = df_geo_data.get(
                df_geo_data.cc == cc)
            sub_df_c = self.df_city.get(
                self.df_city.cc == cc)
            geo_data['idx'] += list(sub_df_gd['idx'])
            geo_data['cc'] += list(sub_df_gd['cc'])
            geo_data['country'] += list(
                sub_df_gd['country'])
            coord = list(sub_df_gd['coord'])
            geo_data['coord'] += coord
            data = list(zip(
                list(sub_df_c['lat']),
                list(sub_df_c['lon'])))
            tree = KDTree(data, leafsize=30)
            _, ii = tree.query(coord, k=1, workers=-1)
            for i in ii:
                geo_data['admin'].append(
                    sub_df_c.iloc[[i]].admin1.values[0])
                geo_data['city'].append(
                    sub_df_c.iloc[[i]].name.values[0])
        return pd.DataFrame(geo_data)



if __name__ == "__main__":
    ans = ['CN','LA','LA','VN','CN','CN','CN']
    coords = [
            (21.19285, 101.69193), #china
            (21.68350, 102.10566), #laos
            (19.88874, 102.13589), #laos
            (22.48113, 103.97163), #Lao Cai, Vietnam
            (22.50781, 103.96374), #Hekou, China 
            (22.52989, 103.93700), #Hekou, China
            (25.01570, 102.76066)]*1#Kunming, China
    CTC = CoordinatesToCountries()
    ans = CTC.run(coords)
    print(ans)
