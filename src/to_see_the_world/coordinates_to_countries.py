#!/usr/bin/env python3.11
import configparser
import math
from pathlib import Path

import pandas as pd
from scipy.spatial import KDTree
#from shapely import STRtree
#from shapely.geometry import Point, Polygon

from update_local_data2 import Datasets


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
        df = self.get_geodata(coords)
        df = self.get_closest_admin(df
            ).sort_values(by=['id'], ascending=True)
        print(df)
        return df
        
    def setup_data(self, fname):
        f = self.config.get('path', fname)
        return pd.read_csv(
            f'{self.pwd}/{f}', na_filter = False)
        
    def get_geodata(self, coords):
       # start_ids = coords['id']
#        df1 = self.get_geodata_strtree(coords)
#        complete_ids = list(df1.id.values)
#        missed_ids = [start_ids.index(x) for x in
#            start_ids if x not in complete_ids]
#        if len(missed_ids) == 0:
#            return df1
#        print(f'num missed_ids: {len(missed_ids)}, '
#            'running kdtree')
#        m_ids = [coords['id'][idx] for idx in
#            missed_ids]
#        m_coords = [coords['coords'][idx] for idx in
#            missed_ids]
#        missed_coords = {'id': m_ids,
#            'coords': m_coords}
#        df2 = self.get_geodata_kdtree(
#            missed_coords)
#        df_combined = pd.concat([df1, df2],
#            ignore_index=True)
#        return df_combined
        return self.get_geodata_kdtree(coords)
    
    def clockwise_sort_polygon(self, coords):
        centroids = self.Datasets.get_centroid(
            coords)
        center_x = centroids[1]
        center_y = centroids[0]
        def angle_to_center(coord):
            return (math.atan2(
                coord[1] - center_y, coord[0
                ] - center_x) + 2 * math.pi) % (
                2 * math.pi)
        ans = sorted(coords, 
            key=angle_to_center, reverse=True)
        polygon = Polygon(ans)
        if not polygon.is_valid:
            print('bad', centroids)
        return polygon

    def get_polygons(self):
        df_grouped = self.df_cb_shifted.groupby(
            'fid').apply(
            lambda x: list(zip(x['lat'], x['lon']))
            ).reset_index(name='tuples')
        df_grouped['tup_len'] = \
            df_grouped.tuples.apply(len)
        df_grouped = df_grouped.get(
            df_grouped.tup_len >= 4
            ).reset_index()
        a = self.df_cb_shifted.set_index(
            'fid')['country_code'
            ].to_dict()
        idx_to_fid = df_grouped.to_dict()['fid']
        cc_index_dict = {k:a[v] for k,v in
            idx_to_fid.items()}
        polygons = [self.clockwise_sort_polygon(x
            ) for x in list(df_grouped.tuples.values)]
        return polygons, cc_index_dict, idx_to_fid

    def get_geodata_strtree(self, coords):
        # figure out how to translate the location to the cc
        # have code choose between these two answers 305 762
        # for the spain island in France
        polygons, cc_index_dict, idx_to_fid = \
            self.get_polygons() 
        points = [Point(v) for v in coords['coords']]
        tree = STRtree(points)
        cgi = tree.query(polygons, predicate='contains')
        geo_data = {
            'id': [], 'fid': [], 'country_code': [],
            'og_coord': []}
        coords_dict = {idx:{
            'id': coords['id'][idx],
            'tuple': coords['coords'][idx]
            } for idx,_ in enumerate(coords['id'])} 
        c = dict(zip(cgi[1], cgi[0]))
        for k,v in c.items():
            geo_data['country_code'].append(
                cc_index_dict[v])
            geo_data['id'].append(coords_dict[k]['id'])
            geo_data['fid'].append(idx_to_fid[v])
            geo_data['og_coord'].append(
                coords_dict[k]['tuple'])
        return pd.DataFrame(geo_data)

    def get_geodata_kdtree(self, coords):
        data = list(zip(
            list(self.df_cb_shifted['lat']),
            list(self.df_cb_shifted['lon'])))
        tree = KDTree(data, leafsize=30)
        _, ii = tree.query(coords['coords'], k=1,
            workers=-1)
        geo_data = {
            'id': [], 'fid': [], 'country_code': [],
            'og_coord': []}
        for idx, i in enumerate(ii):
            geo_data['id'].append(coords['id'][idx])
            fid = self.df_cb_shifted.iloc[[
                i]].fid.values[0]
            geo_data['fid'].append(fid)
            cc = self.df_cb_shifted.iloc[[
                i]].country_code.values[0]
            geo_data['country_code'].append(cc)
            geo_data['og_coord'].append(
                coords['coords'][idx])
        return pd.DataFrame(geo_data)
        
    def get_closest_admin(self, df_geo_data):
        geo_data = {
            'id': [],
            'fid': [],
            'country_code': [],
            'og_coord': [],
            'admin_name': [],
            'city': []}
        for cc in set(df_geo_data.country_code):
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
    coords = {
            0:(42.47551552569287, 1.9644517432906565),#ES
            1:(36.17471263921515, -94.23251549603685),# AR, USA
            2:(22.9219, 105.86972), #vietnam
            3:(22.48113, 103.97163), #Lao Cai, Vietnam
            4:(21.68350, 102.10566), #laos
            5:(19.88874, 102.13589), #laos
            6:(22.92331, 105.87171), #china
            7:(21.19285, 101.69193), #china
            8:(22.50781, 103.96374), #Hekou, China 
            9:(22.52989, 103.93700), #Hekou, China
            10:(25.01570, 102.76066)}#Kunming, China
    coords = {'id': [0,1,2,3,4,5,6,7,8,9,10],
            'coords': [(42.47551552569287, 1.9644517432906565),#ES
            (36.17471263921515, -94.23251549603685),# AR, USA
            (22.9219, 105.86972), #vietnam
            (22.48113, 103.97163), #Lao Cai, Vietnam
            (21.68350, 102.10566), #laos
            (19.88874, 102.13589), #laos
            (22.92331, 105.87171), #china
            (21.19285, 101.69193), #china
            (22.50781, 103.96374), #Hekou, China 
            (22.52989, 103.93700), #Hekou, China
            (25.01570, 102.76066)]}#Kunming, China
    CTC = CoordinatesToCountries()
    ans = CTC.run(coords)
    print(ans)
