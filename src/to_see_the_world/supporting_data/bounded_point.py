#!/usr/bin/env python3.11
import pandas as pd
from scipy.spatial import KDTree

class BoundedPoint:
    def __init__(self):
        pass
        
    def run(self, coords):
        #boundary_data = {'A': [(0,0), (0,5), (5,5), (5,0)],
#                        'B': [(0,5), (5,5), (5,10), (0,10)],
#                        'C': [(5,0), (10,0), (10,5), (5,5)],
#                        'D': [(5,5), (10,5), (10,10), (5,10)]}
        bd = {
            'lat': [0,0,5,5,0,5,5,0,5,10,10,5,5,10,10,5],
            'lon': [0,5,5,0,5,5,10,10,0,0,5,5,5,5,10,10],
            'cc': ['A','A','A','A','B','B','B','B','C','C','C','C','D','D','D','D']}
        bd_df = pd.DataFrame(bd)
        df = self.get_geodata_kdtree(bd_df, coords)
        return df
                
    def get_geodata_kdtree(self, bd, coords):
        data = list(zip(
            list(bd['lat']),
            list(bd['lon'])))
        tree = KDTree(data, leafsize=30)
        _, ii = tree.query(coords['coords'], k=2,
            workers=-1)
        geo_data = {'id': [], 'cc': [], 'og_coord': []}
        for idx, i in enumerate(ii):
            geo_data['id'].append(coords['id'][idx])
            og_coord = coords['coords'][idx]
            cc = 0
            for ix in i:
                cc_test = bd.iloc[[ix]].cc.values[0]
                poly = list(bd.get(bd.cc == cc_test
                    ).apply(lambda row: [row['lat'],
                    row['lon']], axis=1))
                if self.is_point_in_polygon(
                    og_coord, poly):
                    cc = cc_test
            geo_data['cc'].append(cc)
            geo_data['og_coord'].append(og_coord)
        return pd.DataFrame(geo_data)

    def is_point_in_polygon(self, point, polygon):
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

        
if __name__ == "__main__":
    coords = {'id': [0,1,2,3],
                     'coords': [(1,1),(8,8),(2,9),(2,6)],
                     'Ans': ['A', 'D', 'B', 'B']}
    BP = BoundedPoint()
    ans = BP.run(coords)
    print(ans)