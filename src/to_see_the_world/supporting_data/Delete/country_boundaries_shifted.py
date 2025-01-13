#!/usr/bin/env python3
import configparser
import json
from pathlib import Path

import gpxpy.gpx
import pyclipper
import pandas as pd


class ShiftBoundaries:
    def __init__(self):
        self.pwd = Path.cwd().parent
        self.config = configparser.ConfigParser()
        self.config.read(
            f'{self.pwd}/config.ini')
        
    def run(self,
        fname_cb_shifted=
        'fname_country_boundaries_shifted',
        fname_cb='fname_country_boundaries'):
        fname_cb_shifted = \
            self.config.get('path', fname_cb_shifted)
        fname_cb = self.config.get('path', fname_cb)
        if Path(f'{self.pwd}/{fname_cb_shifted}'
            ).exists():
            print(f'{fname_cb_shifted} already exists')
        else:
            print(f'Creating {fname_cb_shifted}')
            polygons = self.get_country_polygons(
                fname_cb)
            self.shift_polygons(
                polygons,
                fname_cb_shifted)
        return pd.read_csv(
            f'{self.pwd}/{fname_cb_shifted}')
       
    def get_country_polygons(self,
        fname_country_boundaries):
        fbc = \
            f'{self.pwd}/{fname_country_boundaries}'
        f = open(fbc, "r")
        polygons = json.loads(f.read())['features']
        f.close()
        return polygons
    
    def shift_polygons(self,
        polygons,
        fname_shifted_countries):
        pshift = {
            'lat': [],
            'lon': [],
            'country_code': [], 
            'country_name': []}
        for x in range(0, len(polygons)):
            # Only concerned about main country body
            # ie no islands
            country = polygons[x]
            name = country['properties']['ADMIN']
            cc = country['properties']['ISO_A2']
            if cc in ['AG', 'AU', 'AQ', 'BB', 'BS', 'CU', 'CV',
                         'KM', 'DM', 'FJ', 'GD', 'IS', 'JM',
                         'JP', 'KI', 'MG', 'MT', 'MV', 'MH',
                         'MU', 'FM', 'NR', 'NZ', 'PH', 'PW',
                         'KN', 'LC', 'VC', 'WS', 'ST', 'SC',
                         'SG', 'SB', 'LK', 'TW', 'TO', 'TT',
                         'TV', 'VU', '-']:
                print(f'Skipping the island: {cc}')
                continue
            coords = max(
                [c[0] for c in country['geometry'][
                'coordinates']],
                key = len)
            print(f'Country code: {cc}, '
                f'Coordinate Count: {len(coords)}')
            coords = [(t[1], t[0]) for t in coords]
            subj = pyclipper.scale_to_clipper(coords)
            pco = pyclipper.PyclipperOffset()
            pco.AddPath(
                subj,
                pyclipper.JT_ROUND,
                pyclipper.ET_CLOSEDPOLYGON)
            ret = pco.Execute(-10.0)
            solution = pyclipper.scale_from_clipper(
                ret)[0]
            pshift['lat'] += [s[0] for s in solution]
            pshift['lon'] += [s[1] for s in solution]
            pshift['country_code'] += [cc] * len(solution)
            pshift['country_name'] += [name] * \
                len(solution)
        df = pd.DataFrame.from_dict(pshift)
        print(f'Saving {fname_shifted_countries}')
        df.to_csv(
            f'{self.pwd}/{fname_shifted_countries}',
            sep = ',', index = True)

    def save_gpx(
        self,
        country_codes=[],
        fname_cb_shifted=
        'fname_country_boundaries_shifted'):
        fname_cb_shifted = \
            self.config.get('path', fname_cb_shifted)
        df = pd.read_csv(
            f'{self.pwd}/{fname_cb_shifted}')
        for cc in country_codes:
            df_sub =df.get(df.country_code == cc)
            print(f'Creating gpx file for {cc}')
            gpx = gpxpy.gpx.GPX()
            gpx_track = gpxpy.gpx.GPXTrack()
            gpx.tracks.append(gpx_track)
            gpx_seg = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_seg)
            lst = list(zip(
                list(df_sub['lat']), list(df_sub['lon'])))
            for x in lst:
                gpx_seg.points.append(
                    gpxpy.gpx.GPXTrackPoint(
                        latitude = x[0],
                        longitude = x[1]))
            xml = gpx.to_xml()
            f = open(
                f'{self.pwd}/output/{cc}.gpx', 'w')
            f.write(xml)
            f.close()


if __name__ == "__main__":
    SB = ShiftBoundaries()
    SB.run()
    #SB.save_gpx(country_codes=['AF', 'TJ'])