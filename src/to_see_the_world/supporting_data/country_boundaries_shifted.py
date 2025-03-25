#!/usr/bin/env python3
from pathlib import Path

import gpxpy.gpx
import pandas as pd
import pyclipper


class ShiftBoundaries:
    def __init__(self):
        self.pwd = Path.cwd()
     
    def run(self, polygons, offset=-2.0, min_len=3):
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
                solution.append(self.shift_polygons(
                    coord, offset, min_len))
            pshift[polygon] = solution
        return pshift

    def shift_polygons(
        self, coords, offset, min_len):
        if len(coords) >= min_len and abs(offset) > 0:
            subj = pyclipper.scale_to_clipper(coords)
            pco = pyclipper.PyclipperOffset()
            pco.AddPath(
                subj,
                pyclipper.JT_MITER,
                pyclipper.ET_CLOSEDPOLYGON)
            ret = pco.Execute(offset)
            coords = pyclipper.scale_from_clipper(
                ret)[0]  
        return coords

    def get_depth(self, lst):
        d = 0
        for item in lst:
            if isinstance(item, list):
                d = max(self.get_depth(item), d)
        return d + 1
        
    def flatten(self,
        polygons, name_col='country_code',
        lat_first=True, round_val=9):
        flat = {'lat': [], 'lon': [], name_col: [], 'fid': []}
        fid = 0
        for polygon in polygons:
            coords = polygons[polygon]
            for coord in coords:
                if lat_first:
                    lat = 0
                    lon = 1
                else:
                    lat = 1
                    lon = 0
                flat['lat'] += [round(x[lat], round_val
                    ) for x in coord]
                flat['lon'] += [round(x[lon], round_val
                    ) for x in coord]
                flat[name_col] += [polygon] * len(coord)
                flat['fid'] += [fid] * len(coord)
                fid += 1
        return flat
        
    def save_csv(self, df,
        fname='country_boundaries._shifted.csv'):
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
    print(flat)
    #SB.save_csv(flat)
    #SB.save_gpx(polygons_shifted)
