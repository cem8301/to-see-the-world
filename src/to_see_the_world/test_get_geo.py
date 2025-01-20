#!/usr/bin/env python3
import configparser
from pathlib import Path
from time import time

import pandas as pd

from update_local_data2 import Datasets
from coordinates_to_countries import CoordinatesToCountries
from to_see_the_world import CountryData, Utils, Summary

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 2000)
pd.set_option('display.float_format', '{:20,.20f}'.format)
pd.set_option('display.max_colwidth', None)


class TestGetGeo():
    def __init__(self):
        self.pwd = Path.cwd()
        config = configparser.ConfigParser()
        config.read(f'{self.pwd}/config.ini')
        fname_country_boundaries_shifted = \
            config.get(
            'path', 'fname_country_boundaries_shifted')
        self.df_cbs = pd.read_csv(
             fname_country_boundaries_shifted,
             na_filter = False)
        fname_country_data = config.get(
            'path', 'fname_country_data')
        self.CD = CountryData(fname_country_data)
        self.U = Utils()
        self.Sm = Summary()
        
        # Using Jacob's data between 2017-2024
        # Below is a list of every expected border 
        # crossing verified from his data
        self.ans = {
            969217846: 'CH,LI,AT',
            972228442: 'AT,DE',
            975224137: 'DE,AT',
            975224174: 'DE,CZ',
            983225238: 'CZ,PL',
            992259989: 'PL,SK',
            992258897: 'SK,HU',
            999795712: 'HU,AT',
            1002142028: 'AT,SI',
            1002141170: 'SI,HR',
            1006590929: 'HR,BA',
            1020833686: 'BA,RS',
            1026530098: 'RS,ME',
            1036212543: 'ME,RS',
            1036212126: 'RS,MK',
            1042546544: 'MK,AL',
            1054888756: 'AL,GR',
            1090980729: 'JO,PS',
            1100451555: 'IL,PS',
            1143621514: 'EG,SD',
            1154679820: 'SD,ET',
            1277417244: 'ET,KE',
            1313426853: 'KE,UG',
            1332850759: 'UG,RW',
            1353196261: 'RW,BI',
            1366071804: 'BI,TZ',
            1410312683: 'TZ,MZ',
            1430002910: 'MZ,MW',
            1434221854: 'MW,ZM',
            1445999233: 'ZM,ZW,BW',
            1458008121: 'BW,NA',
            1480927778: 'NA,ZA',
            1518380934: 'ZA,LS',
            1532906341: 'LS,ZA',
            1539179780: 'ZA,SZ',
            1542224198: 'SZ,ZA',
            1641423681: 'ES,AD',
            1642648271: 'AD,FR',
            1656622954: 'FR,MC,IT',
            1660818664: 'IT,CH,FR', 
            1663262537: 'FR,CH',
            1680847046: 'FR,BE,LU',
            1681220129: 'LU,BE',
            1685951904: 'BE,FR',
            1763259489: 'GB,IE',
            1803017418: 'NL,DE',
            1808153082: 'DE,DK',
            1815109443: 'SE,NO',
            1838268321: 'NO,SE',
            1853760694: 'SE,FI',
            1855658555: 'FI,NO',
            1867144862: 'NO,FI',
            1899410507: 'EE,LV',
            1902479018: 'LV,LT',
            1910402844: 'LT,PL',
            1917601912: 'PL,UA',
            1922621058: 'UA,MD',
            1927860955: 'MD,RO',
            1938874675: 'RO,BG',
            1947497006: 'BG,TR',
            1989387244: 'TR,AZ',
            1992580159: 'AZ,TR',
            1997830471: 'TR,GE,AM',
            2008312891: 'AM,GE',
            2192652170: 'GE,RU',
            2192652308: 'GE,RU',
            2198713647: 'GE,AZ',
            2209924726: 'AZ,RU',
            2222213119: 'RU,KZ',
            2231316989: 'KZ,UZ',
            2258834992: 'UZ,TJ',
            2557723116: 'US,CA',
            2645200132: 'CA,US',
            2685598168: 'CA,US',
            2925282682: 'TL,ID',
            2989356207: 'MY,BN',
            2989569335: 'BN,MY',
            3004084481: 'MY,ID',
            3070557998: 'SG,MY',
            3084556359: 'MY,TH',
            3115698710: 'TH,KH',
            3127902620: 'KH,VN',
            3155945975: 'VN,LA',
            3163671165: 'LA,TH',
            7250241840: 'US,CA',
            9703455717: 'CA,US',
            8237455383: 'US,MX',
            9858671260: 'IN,NP',
            10309615568: 'NP,IN',
            10429522218: 'IN,BD',
            10523118593: 'BD,IN',
            11054021860: 'IN,PK',
            11251366756: 'CN,KG',
            11297313300: 'KG,UZ',
            11445621051: 'UZ,TJ',
            11766938334: 'TJ,KG',
            11949415280: 'KG,KZ',
            12015174767: 'KZ,KG',
            12210639728: 'KG,KZ',
            12262976789: 'KZ,CN',
            12723522793: 'CN,VN',
            13098612540: 'VN,LA',
            13227992363: 'LA,TH'
        }
        
    def run(self, a_ids=[], output_geo= False):
        pickle = f'{self.pwd}/test_get_geo.pickle'
        df  = pd. read_pickle(pickle)
        df = df.get(df['coords'].str.len() != 0)
        if a_ids:
            df = df.get(df.id.isin(a_ids))
            
        start = time()
        df = self.get_geo(df, 20)
        end = time()
        
        df.coords =df.coords_simple
        missed = self.get_missed(df)
        num_calc_bc = len(df.get(
            df.border_crossings > 1))
        calc_bad = self.get_calc_bad(df)
        
        print(
            f'Elapsed time: {round(end - start, 2)} sec')
        print(
            f'Number of expected BC: {len(self.ans)}')
        print('Number of calculated BC: '             
            f'{num_calc_bc}')  
        print(f'Missed BC: {len(missed)}')
        for m in missed:
            print(f'{m}, {missed[m]}')
        print(f'Extra BCs: {len(calc_bad)}')
        for c in calc_bad:
            print(f'{c}, {calc_bad[c]}')
        
        if output_geo:
            print('Output Geo requested. Look in the '
                'output folder for gpx files -->')
            for a_id in a_ids:
                df_aid = df.get(df.id == a_id)
                D = Datasets()
                ccs = df_aid.country_code.values[0
                    ].split(',')
                if a_id in self.ans:
                    ccs.extend(self.ans[a_id].split(','))
                    ccs = list(set(ccs))
                D.test_country_boundaries_shifted_file(
                    ccs)
                fname=f'{a_id}_test_get_geo.gpx'
                self.Sm.save_gpx(
                     df_aid, elevations=False,
                     fname=fname)
                print('Closest Country Boundary '
                    'Coordinates:')
                cbc = list(df_aid.closest_boundary_coord.values[0])
                points = list(df_aid.coords.values[0])
                for idx, c in enumerate(cbc):
                    point = points[idx]
                    self.get_closeby_boundaries(c, point)

    def get_closeby_boundaries(self, c, point):
        delta = 0.00001
        data = self.df_cbs.get(
            self.df_cbs.lat + delta >= c[0]).get(
            self.df_cbs.lat - delta <= c[0]).get(
            self.df_cbs.lon + delta >= c[1]).get(
            self.df_cbs.lon - delta <= c[1])
        track = {}
        for _, row in data.iterrows():
            r = self.U.get_distance_from_coords(
                [row.lat, row.lon], point, 10)
            print(f'country: {row.country_code}, '
                f'lat: {row.lat}, lon: {row.lon}, dist: {r}')
            track[row.country_code] = r
        print('Closest Country: '
            f'{min(track, key=track.get)}')
        
    def get_missed(self, df):
        missed = {}
        for a in self.ans:
            if a in df.id.values:
                if self.ans[a] != df.get(df.id == a
                    ).country_code.values[0]:
                    calc_value = df.get(df.id == a
                        ).country_code.values[0]
                    link = self.get_strava_activity_link(a)
                    missed[link] = (
                        f'A: {self.ans[a]}, B: {calc_value}')
        return missed

    def get_calc_bad(self, df):
        calc_bad = {}
        for val in df.get(df.border_crossings > 1).id:
            if int(val) not in self.ans.keys():
                link = self.get_strava_activity_link(val)
                calc_bad[link] = df.get(df.id == val
                    ).country_code.values[0]
        return calc_bad

    def get_strava_activity_link(self, i):
        return f'https://www.strava.com/activities/{i}'
    
    def get_border_crossings(self, df):
        return df.country_code.str.split(','
            ).apply(lambda x: len(x))
    
    def get_geo(self, df, slice=1):
            df['coords_simple'] = df['coords'].apply(
                lambda x: x[::slice] + [x[-1]])
            df_explode = df[['id', 'coords_simple']
                ].explode('coords_simple').dropna()
            coords_slice = list(
                df_explode.coords_simple)
            print('Finding coordinate meta data for '
                f'{len(coords_slice)} points')
            CTC = CoordinatesToCountries()
            df_slice = CTC.run(coords_slice)
            df_slice['id'] = list(df_explode.id)
            df_slice = df_slice.groupby('id').agg(
                {'country_code': 
                     lambda x: ','.join(list(
                     dict.fromkeys(x))),
                 'admin_name': ','.join,
                 'closest_boundary_coord':
                     lambda x: x}
                 ).reset_index()
            df = pd.merge(
                df, df_slice[['id', 'country_code',
                'admin_name', 'closest_boundary_coord'
                ]], on='id', how='right')
            df.coords_simple = \
                df.coords_simple.apply(tuple)
            df.coords= \
                df.coords.apply(tuple)
            #df, dbg = edit_borders(df, debug=True)
            df['border_crossings'] = \
                self.get_border_crossings(df)
            df['country_name'] = \
                df.country_code.apply(lambda x:
                self.CD.country_code_to_country_name(
                x))
            return df
    
    def edit_borders(self, df, debug=False):
            df = df.sort_values(by='start_date_local')
            if df.shape[0] <= 3:
                return df
            ids = list(df.id.values)
            debug_data = {}
            df['border_crossings'] = \
                self.get_border_crossings(df)
            bc_gt_1= list(df.get(
                df.border_crossings > 1).id.values)
            for idx, i in enumerate(ids):
                if i not in bc_gt_1:
                    continue
                prev_id = ids[idx - 1]
                cur_id = i
                next_id = ids[idx + 1]
                prev_cc = self.U.get_cc(df, prev_id)
                cur_cc = self.U.get_cc(df, cur_id)
                next_cc = self.U.get_cc(df, next_id)
                bc = df.get(df.id == cur_id
                    ).border_crossings.values[0]
                prev_dist = self.U.get_distance(
                    df, prev_id, cur_id)
                next_dist = self.U.get_distance(
                    df, cur_id, next_id)
                if debug:
                    debug_data[cur_id] = {
                        'prev_cc': prev_cc,
                        'cur_cc_og': cur_cc,
                        'next_cc': next_cc,
                        'bc': bc,
                        'prev_id': prev_id,
                        'cur_id': cur_id,
                        'next_id': next_id,
                        'prev_dist': prev_dist,
                        'next_dist': next_dist}
                if len(cur_cc) == 1:
                # Skipping, odd data
                    continue
                if bc == 2 or bc == 3 and \
                    len(cur_cc) == 2:
                    if prev_cc == next_cc:
                    # Check for in and out of one country
                    # No border crossing.
                    # Set current cur_cc to prev_cc
                        df.loc[df.id == cur_id, 'country_code'
                            ] = ','.join(prev_cc)
                        if cur_id in debug_data:
                            debug_data[cur_id].update(
                                {'edit': 'A, no bc'})
                    elif prev_cc[-1] == cur_cc[0] and \
                        cur_cc[1] == next_cc[0]:
                    # A border was crossed,
                    # cur_cc is valid
                        if debug_data:
                            debug_data[cur_id].update(
                                {'edit': 'B'})
                        pass
                    elif prev_cc[-1] in cur_cc and \
                        prev_dist < 5 and next_dist > 5:
                    # The prev point is a valid comparison,
                    # but the next point is not. Data is
                    # incomplete, but a border was
                    # likely crossed, cur_cc is valid
                        if debug_data:
                            debug_data[cur_id].update(
                                {'edit': 'B2'})
                        pass
                    elif prev_dist > 5 and next_dist < 5 \
                        and next_cc[0] in cur_cc:
                    # The next point is a valid comparison,
                    # but the prev point is not. Data is
                    # incomplete, but a border was
                    # likely crossed, cur_cc is valid
                        if debug_data:
                            debug_data[cur_id].update(
                                {'edit': 'B3'})
                        pass
                    else:
                    # Inconclusive,
                    # set cur_cc to prev_cc
                        df.loc[df.id == cur_id, 'country_code'
                            ] = ','.join(prev_cc)
                        if debug_data:
                            debug_data[cur_id].update(
                                {'edit': 'C, no bc'})
                elif bc == 3 and len(cur_cc) == 3:
                    if prev_cc[-1] == cur_cc[0]:
                    # A country was crossed.
                    # cur_cc is valid
                        if debug_data:
                            debug_data[cur_id].update(
                                {'edit': 'D'})
                        pass
                    else:
                    # Inconclusive.
                    # Set cur_cc to prev_cc
                        df.loc[df.id == cur_id, 'country_code'
                            ] = ','.join(prev_cc)
                        if debug_data:
                            debug_data[cur_id].update(
                                {'edit': 'E, no bc'})
                else:
                # bc > 3, the data very likely bad.
                # Set cur_cc to prev_cc
                    df.loc[df.id == cur_id, 'country_code'
                        ] = ','.join(prev_cc)
                    if debug_data:
                        debug_data[cur_id].update(
                            {'edit': 'F, no bc'})
            return df, debug_data

if __name__ == "__main__":
    TGG = TestGetGeo()
    #TGG.get_closeby_boundaries(
#        c=[46.690248, 15.643147],
#        point=[46.69027, 15.64220])
    TGG.run(
        a_ids=[969217846], output_geo=True
        )
