#!/usr/bin/env python3
import csv
import urllib.request
import zipfile

GN_URL = 'http://download.geonames.org/export/dump/'
GN_CITIES500 = 'cities500'
GN_ADMIN1 = 'admin1CodesASCII.txt'
GN_ADMIN2 = 'admin2Codes.txt'

# Schema of the GeoNames Cities with Population > 500
GN_COLUMNS = {
    'geoNameId': 0,
    'name': 1,
    'asciiName': 2,
    'alternateNames': 3,
    'latitude': 4,
    'longitude': 5,
    'featureClass': 6,
    'featureCode': 7,
    'countryCode': 8,
    'cc2': 9,
    'admin1Code': 10,
    'admin2Code': 11,
    'admin3Code': 12,
    'admin4Code': 13,
    'population': 14,
    'elevation': 15,
    'dem': 16,
    'timezone': 17,
    'modificationDate': 18
}

# Schema of the GeoNames Admin 1/2 Codes
ADMIN_COLUMNS = {
    'concatCodes': 0,
    'name': 1,
    'asciiName': 2,
    'geoNameId': 3
}

# Schema of the cities file created by this library
RG_COLUMNS = [
    'lat',
    'lon',
    'name',
    'admin1',
    'admin2',
    'cc'
]

# Name of cities file created by this library
RG_FILE = 'cities500.csv'

# WGS-84 major axis in kms
A = 6378.137

# WGS-84 eccentricity squared
E2 = 0.00669437999014

gn_cities500_url = f'{GN_URL}{GN_CITIES500}.zip'
gn_admin1_url = f'{GN_URL}{GN_ADMIN1}'
gn_admin2_url = f'{GN_URL}{GN_ADMIN2}'

cities500_zipfilename = f'{GN_CITIES500}.zip'
cities500_filename = f'{GN_CITIES500}.txt'

print('Downloading files from Geoname...')
urllib.request.urlretrieve(gn_cities500_url, cities500_zipfilename)
urllib.request.urlretrieve(gn_admin1_url, GN_ADMIN1)
urllib.request.urlretrieve(gn_admin2_url, GN_ADMIN2)


print('Extracting cities500...')
_z = zipfile.ZipFile(open(cities500_zipfilename, 'rb'))
open(cities500_filename, 'wb').write(_z.read(cities500_filename))

print('Loading admin1 codes...')
admin1_map = {}
t_rows = csv.reader(open(GN_ADMIN1, 'rt'), delimiter='\t')
for row in t_rows:
    admin1_map[row[ADMIN_COLUMNS['concatCodes']]] = row[ADMIN_COLUMNS['asciiName']]

print('Loading admin2 codes...')
admin2_map = {}
for row in csv.reader(open(GN_ADMIN2, 'rt'), delimiter='\t'):
    admin2_map[row[ADMIN_COLUMNS['concatCodes']]] = row[ADMIN_COLUMNS['asciiName']]

print('Creating formatted geocoded file...')
writer = csv.DictWriter(open(RG_FILE, 'wt'), fieldnames=RG_COLUMNS)
rows = []
for row in csv.reader(open(cities500_filename, 'rt'), \
        delimiter='\t', quoting=csv.QUOTE_NONE):
    geonameid = row[GN_COLUMNS['geoNameId']]
    lat = row[GN_COLUMNS['latitude']]
    lon = row[GN_COLUMNS['longitude']]
    name = row[GN_COLUMNS['asciiName']]
    cc = row[GN_COLUMNS['countryCode']]

    admin1_c = row[GN_COLUMNS['admin1Code']]
    admin2_c = row[GN_COLUMNS['admin2Code']]

    cc_admin1 = f'{cc}.{admin1_c}'
    cc_admin2 = f'{cc}.{admin1_c}.{admin2_c}'

    admin1 = ''
    admin2 = ''

    if cc_admin1 in admin1_map:
        admin1 = admin1_map[cc_admin1]
    if cc_admin2 in admin2_map:
        admin2 = admin2_map[cc_admin2]

    write_row = {
     'lat':lat,
     'lon':lon,
     'name':name,
     'admin1':admin1,
     'admin2':admin2,
     'cc':cc}
    rows.append(write_row)
    
writer.writeheader()
writer.writerows(rows)


