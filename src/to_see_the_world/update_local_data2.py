#!/usr/bin/env python3
import configparser

import pandas as pd
from pathlib import Path
import requests

from supporting_data.country_boundaries_shifted import ShiftBoundaries

    
class Datasets():
    def __init__(self):
        self.pwd = Path.cwd()
        self.config = configparser.ConfigParser()
        self.config.optionxform = str
        self.config.read(f'{self.pwd}/config.ini')
        self.country_code_converter = \
            self.config._sections[
            'country_code_converter']
        self.fname_country_data = self.config.get(
            'path', 'fname_country_data')
        self.fname_shifted_boundaries = \
            self.config.get('path',
            'fname_country_boundaries_shifted')
        self.SB = ShiftBoundaries()
        
    def run_country_boundaries(self):
        flat = {'lat': [], 'lon': [], 'country_code': []}
        island_cc = ['JP', 'PH', 'GB', 'MG',
            'AU', 'AQ', 'TW', 'LK', 'HT', 'DO', 'CU',
            'PG', 'IE', 'NZ', 'SG', 'BH', 'TT',
            'TL', 'JM', 'CY', 'MU', 'FJ', 'KM',
            'SB', 'MT', 'MV', 'CV', 'BN', 'BS',
            'IS', 'VU', 'BB', 'ST', 'WS', 'LC',
            'KI', 'SC', 'GD', 'FM', 'TON', 'VC',
            'AG', 'DM', 'KN', 'MH', 'PW', 'NR', 'TV']
        large_cc = ['DK', 'ID']#['RU', 'DK', 'CA', 'US']
        for cc in self.country_code_converter:
            country_polygons = \
                self.get_country_boundaries(cc)
            flat_cc  = self.shift_country_boundaries(
                country_polygons)
            if cc in island_cc:
                slice = 50
            elif  cc in large_cc:
                slice = 5
            else:
                slice = 1
            for key in flat:
                flat[key] += flat_cc[key][::slice]
        self.save_shifted_boundaries(flat)
       
    def run_country_data(self):
        if Path(f'{self.pwd}/'
            f'{self.fname_shifted_boundaries}'
            ).is_file():
            print(f'{self.fname_shifted_boundaries} '
                'exists')
            country_polygons = pd.read_csv(
                self.fname_shifted_boundaries,
                na_filter = False)
        else:
            print(f'{self.fname_shifted_boundaries} '
                'does not exist. Please run '
                'run_country_boundaries()')
        country_data = self.get_country_data()
        df = pd.DataFrame(country_data
            ).drop_duplicates()
        centroids = self.get_centroids(
            country_polygons)
        df['country_centroid'] = df[
            'country_code'].apply(
            lambda x: centroids[x])
        self.save_country_data(df)
        
    def save_country_data(self, df):
        print(f'Saving {self.fname_country_data}')
        df.to_csv(
            self.fname_country_data,
            header = True,
            index = False,
            columns = ['admin_name',
            'country_name', 'country_code',
            'admin_type', 'country_centroid'])
    
    def get_admin_bnds_count(self):
        url = (
            'https://services1.arcgis.com/0EOqWP'      
            'tpCmgQr2ay/arcgis/rest/services/'
            'World_Admin_Bnds/FeatureServer/0/'
            'query?where=1%3D1&outFields=*'
            '&returnGeometry=false&returnCountOnly'
            '=true&outSR=4326&f=json')
        c = requests.get(url, timeout = 30).json()
        return c['count']
    
    def get_country_data(self):
        data_count = self.get_admin_bnds_count()
        result_record_count = 1000
        data = {
            'admin_name': [],
            'country_name': [],
            'country_code': [],
            'admin_type': []}
        url = (
            'https://services1.arcgis.com/0EOqWPtp' 
            'CmgQr2ay/arcgis/rest/services/'
            'World_Admin_Bnds/FeatureServer/0/'
            'query?where=1%3D1&outFields=NAME,'
            'COUNTRY,ISO_CC,ADMINTYPE&'
            'outSR=4326&f=json')
        result_offsets = list(range(0, data_count,
            result_record_count))
        #result_offsets = [0]
        #result_record_count = 1
        for result_offset in result_offsets:
            print(f'Url data request for {result_offset}')
            url_offset = (
                f'&resultOffset={result_offset}'
                '&resultRecordCount='
                f'{result_record_count}')
            for retry in range(0,4):
                j = requests.get(f'{url}{url_offset}',
                    timeout = 60)
                if j.ok:
                    j = j.json()
                    break
                else:
                    print('Trying get_country_data again ' 
                        f'({retry}/5). '
                        f'Status code: {j.status_code}')
            for feature in j['features']:
                att = feature['attributes']
                admin_name = att['NAME']
                country_name = att['COUNTRY']
                cc = att['ISO_CC']
                admin_type = att['ADMINTYPE']
                geo = feature['geometry']['rings']
                if cc == ' ':
                    continue
                data['admin_name'].append(
                    admin_name)
                data['country_name'].append(
                    country_name)
                data['country_code'].append(cc)
                data['admin_type'].append(admin_type)
        return data

    def get_centroid(self, v):
        ans = [0, 0]
        n = len(v)
        signedArea = 0
        # For all vertices
        for i in range(len(v)):
            x0 = v[i][0]
            y0 = v[i][1]
            x1 = v[(i + 1) % n][0]
            y1 =v[(i + 1) % n][1]
            # Calculate value of A
            # using shoelace formula
            A = (x0 * y1) - (x1 * y0)
            signedArea += A
            # Calculating coordinates of
            # centroid of polygon
            ans[1] += (x0 + x1) * A
            ans[0] += (y0 + y1) * A
        signedArea *= 0.5
        ans[1] = (ans[1]) / (6 * signedArea)
        ans[0] = (ans[0]) / (6 * signedArea)
        return tuple(ans)

    def get_centroids(self, country_polygons):
        centroids = {}
        for cc in country_polygons:
            sub = country_polygons[cc]
            sub.sort(key=len)
            sub.reverse()
            if cc == 'US' or cc == 'MY':
                #ie, Alaska has a longer border
                coords = sub[1]
            else:
                coords = sub[0]
            centroids[cc] = self.get_centroid(coords)
        return centroids
    
    def get_country_boundaries(self, cc):
        val = self.country_code_converter[cc]
        url = ("https://services.arcgis.com"
            "/P3ePLMYs2RVChkJx/arcgis/rest"
            "/services/World_Countries/"
            "FeatureServer/0/query?where="
            f"ISO_CC%20%3D%20'{val}'&"
            "outFields=ISO_CC,COUNTRY"
            ",LAND_RANK&outSR=4326&f=json")
        for retry in range(0,4):
            j = requests.get(url, timeout = 60)
            if j.ok:
                j = j.json()
                break
            else:
                print('Trying get_country_data again ' 
                    f'({retry}/5). '
                    f'Status code: {j.status_code}')
        country_polygons = {}
        for feature in j['features']:
            if feature['attributes']['LAND_RANK'] <= 2:
                continue
            #cc = feature['attributes']['ISO_CC']
            coords = feature['geometry']['rings']
            country_polygons.setdefault(cc, []
                ).extend(coords)
        return country_polygons
        
    def shift_country_boundaries(self,
        country_polygons):
        polygons_shifted = self.SB.run(
            country_polygons, offset=-2.0)
        return self.SB.flatten(polygons_shifted)
        
    def save_shifted_boundaries(self, flat):
        print(
            f'Saving {self.fname_shifted_boundaries}')
        self.SB.save_csv(flat,     
            fname = self.fname_shifted_boundaries)
            
    def test_country_data_file(self):
        if Path(
            f'{self.pwd}/'
            f'{self.fname_country_data}').is_file():
            print(f'{self.fname_country_data} exists')
            df = pd.read_csv(
                self.fname_country_data,
                na_filter = False)
                
    def test_country_boundaries_shifted_file(self,
        country_codes):
        print(f'{self.pwd}/'
            f'{self.fname_shifted_boundaries}')
        if Path(f'{self.pwd}/'
            f'{self.fname_shifted_boundaries}'
            ).is_file():
            print(f'{self.fname_shifted_boundaries} '
                'exists')
            df = pd.read_csv(
                self.fname_shifted_boundaries,
                na_filter = False)
            data = {}
            for cc in country_codes:
                data[cc] = list(zip(
                    df.get(df.country_code == cc).lat,
                    df.get(df.country_code == cc).lon)) 
            self.SB.save_gpx(data)
            coords = [-30.48457889491692,
                27.61236683325842]
            ans = df.get(df.lat== coords[0])
            print(ans)


if __name__ == "__main__":
    D = Datasets()
    D.run_country_boundaries()
    #D.run_country_data()
    #D.test_country_boundaries_shifted_file(['VN','CN'])
