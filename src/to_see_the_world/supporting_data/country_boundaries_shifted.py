#!/usr/bin/env python3
from pathlib import Path

import gpxpy.gpx
import pandas as pd
import pyclipper


class ShiftBoundaries:
    def __init__(self):
        self.pwd = Path.cwd()
     
    def run(self, polygons, offset=-2.0):
        pshift = {}
        for polygon in polygons:
            print(f'Shifting {polygon}')
            if polygon == 'LS' \
                or polygon == 'SM' \
                or polygon == 'VA':
                #Lesotho(LS) is within South Africa (ZA).
                #LS, needs to seperate its shifted border
                #by a greater value than its neighbor,
                #else their two borders are equal.
                #Same is with San Marino (SM) and
                # Vatican City (VA). Their
                #borders are completely within Italy (IT)
                offset = offset * 100
            coords = polygons[polygon]
            solution = []
            for coord in coords:
                solution = self.shift_polygons(
                    coord, offset, solution)
            pshift[polygon] = solution
        return pshift

    def shift_polygons(
        self, coords, offset, solution, min_len=50):
        if len(coords) >= min_len and abs(offset) > 0:
            coords = [[c[1], c[0]] for c in coords]
            subj = pyclipper.scale_to_clipper(coords)
            pco = pyclipper.PyclipperOffset()
            pco.AddPath(
                subj,
                pyclipper.JT_MITER,
                pyclipper.ET_CLOSEDPOLYGON)
            ret = pco.Execute(offset)
            solution.extend(
                pyclipper.scale_from_clipper(ret)[0])
            solution  = [[round(s[0], 9), round(s[1], 9)
                ] for s in solution]
        else:
            solution.extend([[round(coord[1], 9),
                round(coord[0], 9)] for coord in coords])
        return solution

    def get_depth(self, lst):
        d = 0
        for item in lst:
            if isinstance(item, list):
                d = max(self.get_depth(item), d)
        return d + 1
        
    def flatten(self,
        polygons, name_col='country_code'):
        flat = {'lat': [], 'lon': [], name_col: []}
        for polygon in polygons:
            coords = polygons[polygon]
            flat['lat'] += [x[0] for x in coords]
            flat['lon'] += [x[1] for x in coords]
            flat[name_col] += [polygon] * len(coords)
        return flat
        
    def save_csv(self, flat,
        fname='shifted_boundaries.csv'):
        df = pd.DataFrame.from_dict(flat)
        df.to_csv(
            f'{self.pwd}/{fname}',
            index = False)
            
    def save_gpx(self, polygons):
        for polygon in polygons:
            coords = polygons[polygon]
            print(f'Creating gpx file for {polygon}')
            gpx = gpxpy.gpx.GPX()
            gpx_track = gpxpy.gpx.GPXTrack()
            gpx.tracks.append(gpx_track)
            gpx_seg = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_seg)
            for x in coords:
                gpx_seg.points.append(
                    gpxpy.gpx.GPXTrackPoint(
                        latitude = x[0],
                        longitude = x[1]))
            xml = gpx.to_xml()
            f = open(
                f'{self.pwd}/output/{polygon}.gpx', 'w')
            f.write(xml)
            f.close()


if __name__ == "__main__":
    polygons = {
        'square': [[[1, 1], [1, 2], [2,2], [2,1], [1,1]]],
        'triangle': [[[0,0], [1,5], [10, -6], [0,0]]],
        'random': [[[0,0], [4,8], [6,5], [0,0]],
            [[1,1], [3,7], [5,4], [1,1]]]}
    SB = ShiftBoundaries()
    polygons_shifted = SB.run(polygons)
    flat = SB.flatten(polygons_shifted)
    #SB.save_csv(flat)
    #SB.save_gpx(polygons_shifted)