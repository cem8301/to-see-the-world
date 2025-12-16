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
        df = self.get_geodata_kdtree(coords)
        fids = set(list(df['fid'].explode()))
        df = self.check_polygon(df, fids)
        df = self.fix_outliers(df)
        df = self.get_closest_admin(df
            ).sort_values(by=['id'], ascending=True)
        return df
        
    def setup_data(self, fname):
        f = self.config.get('path', fname)
        return pd.read_csv(
            f'{self.pwd}/{f}', na_filter = False)

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
        return pd.DataFrame(geo_data)
        
    def points_in_polygon(self, points, poly):
        """
        Checks if a set of points are inside a given
        polygon using the ray casting algorithm.
        Args:
            points (list of tuples): List of (x, y)
            coordinates of points to check.
            poly (list of tuples): List of (x, y)
            coordinates of the polygon vertices.
        Returns:
            ans (list of tuples): points that are in the
            polygon
        """
        # 1. Convert inputs to numpy arrays for
        # efficient computation
        x = np.array([point[0] for point in points])
        y = np.array([point[1] for point in points])
        # 2. Extract polygon vertices (using wrap
        # -around for edges)
        poly_x = np.array([p[0] for p in poly])
        poly_y = np.array([p[1] for p in poly])
        # 3. Initialize results and vertex count
        n = len(poly)
        # The 'inside' array tracks how many
        # intersections were found for each point
        # We use boolean type and flip its state 
        # when an odd number of intersections is
        # counted
        inside = np.zeros(len(x), dtype=np.bool_)
        # 4. Iterate over each edge of the polygon
        for i in range(n):
            p1x, p1y = poly_x[i], poly_y[i]
            p2x, p2y = poly_x[(i + 1) % n], poly_y[
                (i + 1) % n]
            # 5. The core logic of the ray casting
            # algorithm:
            # Check if the ray cast horizontally from
            # the point intersects the edge [1]
            # Check if the edge crosses the point's 
            # y-height (y lies between p1y and p2y)
            condition1 = (p1y <= y) & (p2y > y)
            condition2 = (p2y <= y) & (p1y > y)
            # Check if the intersection point of the
            # edge is to the right of the point [1]
            den = p2y - p1y
            if den == 0:
                intersect_x = p1x
            else:
                intersect_x = (p2x - p1x) * (y - p1y
                    ) / den + p1x
            condition3 = x < intersect_x
            # If all conditions are met for a specific
            # point and edge, flip the 'inside' state 
            # for that point [1]
            # An even number of flips means outside;
            # an odd number means inside
            mask = (condition1 | condition2
                ) & condition3
            inside[mask] = ~inside[mask]
        ans = [point for idx, point in enumerate(
            points) if inside[idx]]
        return ans

    def check_polygon(self, df, fids, by_fid=True):
        #fids = set(list(df['fid'].explode()))
        df['fid'] = df['fid'].apply(lambda x: x[0
            ] if isinstance(x, list) and len(x) == 1 else x)
        df['country_code'] = df['country_code'
            ].apply(lambda x: x[0
            ] if isinstance(x, list) and len(x) == 1 else x)
        for fid in fids:
            cc = self.df_cb_shifted.get(
                self.df_cb_shifted.fid == fid
                )['country_code'].values[0]
            poly = list(self.df_cb_shifted.get(
                self.df_cb_shifted.fid == fid
                ).apply(lambda row: [row['lat'],
                row['lon']], axis=1))
            dfb = df[df['fid'].apply(
                lambda x: isinstance(x, list))]
            if len(dfb) == 0:
                continue
            if by_fid:
                point = list(dfb[dfb['fid'].apply(
                    lambda x: fid in x)]['og_coord'])
            else:
                point = list(dfb[dfb['country_code'].apply(
                    lambda x: cc in x)]['og_coord'])
            inside = self.points_in_polygon(
                    point, poly)
            df.loc[df.og_coord.isin(inside), 'fid'] = fid
            df.loc[df.og_coord.isin(inside
                ), 'country_code'] = cc
        return df
        
    def fix_outliers(self, df):
        is_list_mask = df['country_code'].apply(
            lambda x: isinstance(x, list))
        fids = []
        # Check all other polygons from the
        # same country_code. Solves issue when
        # the closest point is next to an enclave
        ccs = set(list(df[is_list_mask][
            'country_code'].explode()))
        for cc in ccs:
            df_sub = df.get(df.country_code == cc)
            fids.extend(list(set(list(
                df_sub['fid'].explode()))))
        df = self.check_polygon(
            df, fids, by_fid=False)
        # drop any extra outliers
        df = df[df['country_code'].apply(type) != list]
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
        'id': [0,1,2,3,4,5,6,7,8,9,10,11,12,13]*mult,
        'coords': [
            (22.61900,88.86807), #IN
            (47.16299, -114.099606),#MT, US
            (32.80309, -114.48798), #AZ, US
            (42.4755, 1.9644517),#ES
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
