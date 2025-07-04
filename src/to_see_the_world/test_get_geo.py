#!/usr/bin/env python3.11
import configparser
from pathlib import Path
from time import time

import pandas as pd

from update_local_data2 import Datasets
from coordinates_to_countries import CoordinatesToCountries
from to_see_the_world import CountryData, Utils, Summary

pd.set_option('display.max_rows', None)
#pd.set_option('display.max_columns', None)
#pd.set_option('display.width', 2000)
#pd.set_option('display.float_format', '{:20,.20f}'.format)
#pd.set_option('display.max_colwidth', None)


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
            #975224137: 'DE,AT',
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
            1090981171: 'IL,PS',
            #1100451555: 'PS,IL',
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
        df  = pd.read_pickle(pickle)
        df = df.get(df['coords'].str.len() != 0)
        if a_ids:
            df = df.get(df.id.isin(a_ids))
            
        start = time()
        df = self.get_geo(df, slice=5)
        end = time()
        
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
                ccs = df_aid.country_code.values
                if len(ccs) > 0:
                    ccs = ccs[0].split(',')
                if a_id in self.ans:
                    ccs.extend(self.ans[a_id].split(','))
                    ccs = list(set(ccs))
                D.test_country_boundaries_shifted_file(
                    ccs)
                fname = f'{a_id}_test_get_geo.gpx'
                self.Sm.save_gpx(
                     df_aid, elevations=False,
                     fname=fname)

    def test(self):
        delta = 0.00001
        track = []
        self.df_cbs = self.df_cbs.get(
            self.df_cbs.country_code == 'JP')
        print(len(self.df_cbs))
        self.df_cbs['coords'] = \
            list(zip(self.df_cbs.lat, self.df_cbs.lon))
        df = self.df_cbs[['coords', 'country_code']]
            
        df['data_count'] = df.coords.map(df.coords.value_counts())
        print(len(df.get(df.data_count > 1).data_count.values))
        ans = df.groupby('country_code', as_index=False)['data_count'].mean()
        print(ans.get(ans.data_count==1))
        
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
            f'{min(track, key=track.get)}, point: {point}')
        
    def get_missed(self, df):
        missed = {}
        for x in self.ans:
            if x in df.id.values:
                A = ','.join(sorted(self.ans[x].split(',')))
                B = ','.join(sorted(df.get(df.id == x
                        ).country_code.values[0].split(',')))
                if A != B:
                    link = self.get_strava_activity_link(x)
                    missed[link] = (
                        f'A: {A}, B: {B}')
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

    def check_border_crossings(self, df):
        bc = {}
        for i in sorted(list(set(df.id))):
            dfa = df.get(df.id == i)
            num_bc = len(dfa.groupby(
                [dfa['country_code'].ne(
                dfa['country_code'].shift()
                ).cumsum(), 'country_code']
                ).size())
            bc[i] = num_bc
        return bc

    def country_code_to_country_name(self, cc):
        ans = ''
        cc_list = cc.split(',')
        for c in cc_list:
            if len(ans) > 0:
                ans += ','
            ans +=  list(self.CD.df_country_data.get(
                self.CD.df_country_data.country_code \
                == c)['country_name'])[0]
        return ans 
    
    def get_geo(self, df, slice=1):
        df_explode = df[['id', 'coords']].explode(
            'coords').dropna()
        coords_slice = {'id': list(df_explode.id.values
            )[::slice], 'coords': list(df_explode['coords'
            ].values)[::slice]} 
        print('Finding coordinate meta data for '
            f'{len(coords_slice["id"])} points')
        CTC = CoordinatesToCountries()
        df_slice = CTC.run(coords_slice)
        border_crossings = self.check_border_crossings(df_slice)
        df_slice['border_crossings'] = \
            df_slice.id.apply(
            lambda x: border_crossings[x])
        df_slice = df_slice.drop_duplicates(
            subset=['id', 'country_code', 'admin_name'])
        df_slice = df_slice.groupby('id').agg(
            {'country_code':
                 lambda x: ','.join(list(dict.fromkeys(x))),
             'admin_name': ','.join,
             'border_crossings': 'mean'}).reset_index()
        df = pd.merge(
            df, df_slice[['id',
            'country_code', 'admin_name',
            'border_crossings']], on='id', how='right')
        #df.coords = df.coords.apply(tuple)
        df['country_name'] = df.country_code.apply(
            lambda x: \
            self.country_code_to_country_name(x))
        return df


if __name__ == "__main__":
    TGG = TestGetGeo()
    #TGG.get_closeby_boundaries(
#        c=[46.690248, 15.643147],
#        point=[46.69027, 15.64220])
    TGG.run(
        #a_ids=[10497533128], output_geo=True
        )
    #TGG.test()
