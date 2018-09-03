#!/usr/bin/python2
# -*- coding: utf-8 -*-

from __future__ import print_function
import ephem
from datetime import datetime
from pandas.io import sql
from sqlalchemy import create_engine
import mysql.connector
from mysql.connector import Error
import csv
from csv import reader
from pprint import pprint
from collections import defaultdict
import numpy as np
import pandas as pd
from pandas.io import sql
import time
import math
from math import sqrt
import json
import pdb
import codecs
import sys
import getopt
import glob
import os

pd.options.display.width = 700
pd.options.display.max_columns = 150

# defaults
providersfile = 'tmp/ma/providers.txt'
locfile = 'tmp/ma/locations.txt'
csvdir  = 'tmp/ma/csv/full'
jsondir = 'tmp/ma/json'
verbose = False

options, remainder = getopt.getopt(sys.argv[1:], 'l:c:j:p:v', ['locfile=', 'csvdir=', 'jsondir=', 'providersfile=','verbose', ])
if verbose: print('OPTIONS   :', options)

for opt, arg in options:
    if opt in ('-l', '--locfile'):
        locfile = arg
    elif opt in ('-c', '--csvdir'):
        csvdir = arg
    elif opt in ('-j', '--jsondir'):
        jsondir = arg
    elif opt in ('-p', '--providersfile'):
        providersfile = arg
    elif opt in ('-v', '--verbose'):
        verbose = True

# Read locations file
with open(locfile, 'r') as f:
    reader = csv.reader(f, delimiter=' ', skipinitialspace=True)
    locations_list = list(reader)

with open(providersfile, 'r') as p:
    reader2 = csv.reader(p, delimiter=' ', skipinitialspace=True)
    providers_list = list(reader2)


# Cleaning providers' list
#
# Ovaj dio prvenstveno radimo zato jer
# nam je bitno znati imamo li jedan ili više providera da bi učitali
# pripadajući tuning config (ispod). To je važno jer ako se radi multi
# provider kalkukacija potrebne su nešto drugačije postavke za parametrizaciju
# grmljavine s obzirom da usrednjavanje umanjuje ekstreme (radar, updraft)
#
cleaned_list = []
for prov in providers_list:
    #print (prov[0])
    if os.path.isdir(str(csvdir) + "/" + str(prov[0])):
        cleaned_list.append(prov)
providers_list = cleaned_list
#print (providers_list)


# ------------------ config start ---------------------#

# 1 provider only:
# ------------------------------------------------------
if len(providers_list) == 1:
    print ("Running single provider config tuning")

    # Snow probability:
    MTM_TempFac=200         # Larger the number --> Positive t2m has LARGER influence on melting falling snow (default=200)
    MTM_TriangleFac=750     # Larger the number --> Positive t2m AND positive zeroChgt have SMALLER influence on melting (default=500)
    # Thunderstorm probability:
    TstmMtdThrsh=33         # Minimum radar reflectivity for updraft method (CAPE/PREC below)
    TstmRM_Coeff_U=15       # Updraft coefficient (larger number --> larger thunderstorm probability) (radar method)
    TstmRM_Coeff_R=40       # Radar coefficient (larger number --> smaller thunderstorm probability) (radar method)
    TstmRM_Coeff_C=15       # CAPE coefficient (larger number --> smaller thunderstorm probability (radar method)
    TstmCM_Coeff_C=5        # CAPE coefficient (larger number --> smaller thunderstorm probability (CAPE method)
    # Thunderstorm flag:
    TstmRED_RadThrsh=52     # Radar threshold for red thunderstorm
    TstmYEL_RadThrsh=38     # Radar threshold for yellow thunderstorm
    TstmRED_UpThrsh=30      # Updraft percentage threshold for red thunderstorm
    TstmYEL_UpThrsh=5       # Updraft percentage threshold for yellow thunderstorm
    TstmRED_Probab=60       # Minimum probability threshold for red thunderstorm
    TstmYEL_Probab=25       # Minimum probability threshold for yellow thunderstorm
    TstmYEL_Probab_woRU=50  # Trigger tstm flag even if no radar or updraft condition is met if tstm probability is over this value


# Multi provider:
# ------------------------------------------------------
if len(providers_list) > 1:
    print ("Running multi provider config tuning")

    # Snow probability:
    MTM_TempFac=200         # Larger the number --> Positive t2m has LARGER influence on melting falling snow (default=200)
    MTM_TriangleFac=750     # Larger the number --> Positive t2m AND positive zeroChgt have SMALLER influence on melting (default=500)
    # Thunderstorm probability:
    TstmMtdThrsh=33         # Minimum radar reflectivity for updraft method (CAPE/PREC below)
    TstmRM_Coeff_U=17       # Updraft coefficient (larger number --> larger thunderstorm probability) (radar method)
    TstmRM_Coeff_R=35       # Radar coefficient (larger number --> smaller thunderstorm probability) (radar method)
    TstmRM_Coeff_C=10       # CAPE coefficient (larger number --> smaller thunderstorm probability (radar method)
    TstmCM_Coeff_C=5        # CAPE coefficient (larger number --> smaller thunderstorm probability (CAPE method)
    # Thunderstorm flag:
    TstmRED_RadThrsh=48     # Radar threshold for red thunderstorm
    TstmYEL_RadThrsh=32     # Radar threshold for yellow thunderstorm
    TstmRED_UpThrsh=25      # Updraft percentage threshold for red thunderstorm
    TstmYEL_UpThrsh=3       # Updraft percentage threshold for yellow thunderstorm
    TstmRED_Probab=45       # Minimum probability threshold for red thunderstorm
    TstmYEL_Probab=18       # Minimum probability threshold for yellow thunderstorm
    TstmYEL_Probab_woRU=44  # Trigger tstm flag even if no radar or updraft condition is met if tstm probability is over this value


# ------------------- config end ----------------------#

for loc in locations_list:
    location=loc[0]
    lat=loc[1]
    lon=loc[2]
    height=loc[3]
    altlat=loc[4]
    altlon=loc[5]
    altheight=loc[6]

    if float(altlat) != 0:

        dflist = []
        dflist2 = []
        dflist3 = []
        df = {}
        df2 = {}
        rf2 = {}

        # csv sources list
        # fields:
        # postproc table field name
        # file suffix
        # relevant csv column

        sources = [["matrixstats","cldave","cld",0], \
                ["matrixstats","precave","prec",0], \
                ["matrixstats","precpct","prec",2], \
                ["matrixstats","upthrpct","up",2], \
                ["matrixstats","rdrmax","rdr",0], \
                ["matrixstats","capeave","capep1",0], \
                ["extract","altt2m","altt2m",0], \
                ["extract","capep1","capep1",0], \
                ["extract","cld","cld",0], \
                ["extract","d2m","d2m",0], \
                ["extract","gust","gust",0], \
                ["extract","h0","h0",0], \
                ["extract","h2m","h2m",0], \
                ["extract","mlcape","mlcape",0], \
                ["extract","mslp","mslp",0], \
                ["extract","prec","prec",0], \
                ["extract","t2m","t2m",0], \
                ["extract","t850","t850",0], \
                ["extract","u10","u10",0], \
                ["extract","v10","v10",0]]
        #sources = [["cldave","cld",0]]

        for prov in range(len(providers_list)):
            dflist2 = []
            for i in range(len(sources)):
                filename=str(csvdir) + "/" + str(providers_list[prov][0]) + "/" + sources[i][0] + "_" + str(location) + "_" + sources[i][2]
                varname=str(sources[i][1])
                field=int(sources[i][3])
                if os.path.exists(filename):
                    df2[varname] = pd.read_csv(filename, header=None, usecols=[field], names=[varname], dtype=np.float64)
                    dflist2.append(df2[varname])
                    rf2[prov] = pd.concat(dflist2, axis=1)
                    if verbose: print(filename, varname)
                else:
                    if verbose: print('not found:', filename, varname)
            if verbose: pprint(providers_list[prov][0], width=400)
            if verbose: pprint(rf2[prov])
        df_concat = pd.concat(rf2)
        rf3 = df_concat.groupby(level=1).mean()
        if verbose: pprint(rf3)

        #import dates
        dateparse = lambda x: pd.datetime.strptime(x, '%Y-%m-%d_%H:%M')
        df['date'] = pd.read_csv(csvdir + '/dates', header=None, parse_dates=[0], names=['date'],date_parser=dateparse)
        dflist.append(df['date'])

        #import weekdays
        df['weekday'] = pd.read_csv(csvdir + '/weekdays', header=None, usecols=[0], names=['weekday'])
        dflist.append(df['weekday'])

        #create dates&weekdays table
        rf4 = pd.concat(dflist, axis=1)

        #merge dates&weekdays with data
        rf = pd.concat([rf4, rf3], axis=1, join_axes=[rf4.index])

        # temporary
        rf['location']=location
        rf['lat']=lat
        rf['lon']=lon
        rf['height']=height
        rf['altlat']=altlat
        rf['altlon']=altlon
        rf['altheight']=altheight

        #add cloumn weather
        rf['wspd'] = np.nan
        rf['wd'] = np.nan
        rf['weather'] = np.nan
        rf['precpctfinal'] = np.nan
        rf['snowpct'] = np.nan
        rf['rtspct_ratio'] = np.nan
        rf['rainpct'] = np.nan
        rf['tstormpct'] = np.nan
        rf['precpctdisp'] = np.nan
        rf['snowpctdisp'] = np.nan
        rf['tstormpctdisp'] = np.nan
        rf['h2mdisp'] = np.nan
        rf['tstorm'] = str("-")
        rf['fog'] = str("-")
        #rf['nightsym']=np.nan
        rf['wind'] = np.nan
        rf['winddir'] = np.nan
        rf['wdir'] = np.nan
        rf['rtsratiotmp'] = np.nan
        rf['rtsratio'] = np.nan
        rf['hour'] = np.nan
        rf['ymd'] = np.nan
        rf['daynight'] = np.nan

        rf['winterdone'] = np.nan
        rf['fogdone'] = np.nan
        rf['winddone'] = np.nan
        rf['rtsratiodone'] = np.nan


        start_time = time.time()
        if verbose: pprint(rf)
#        sys.exit()

        # A) Calculate wind speed and direction from U and V vectors
        rf.loc[(rf['wspd'].isnull()), 'wspd'] = (rf['u10'] ** 2 + rf['v10'] ** 2) ** (0.5)
        rf.loc[(rf['wd'].isnull()), 'wd'] = 57.3*np.arctan2(rf['u10'],rf['v10'])+180

        # B) Calculate final precipitation probability
        rf.loc[(rf['precpctfinal'].isnull()), 'precpctfinal'] = np.clip((rf['precpct'] + (np.clip((rf['rdrmax'] - 20),0,None)/2) + np.clip((rf['cldave'] - 60),0,None)/4),0,100).apply(lambda x: round(x,0))


        # C) Calculate snow probability
        #rf.loc[(rf['snowpct'].isnull()), 'snowpct'] = np.clip(rf['precpctfinal']*(1 - (np.clip(((np.clip(rf['h0'],0,None).apply(lambda x: round(x,0)) + MTM_TempFac * rf['t2m'])/2),0,None).apply(lambda x: round(x,3))) / MTM_TriangleFac),0,100).apply(lambda x: round(x,0))
        rf.loc[(rf['snowpct'].isnull()), 'snowpct'] = np.clip(rf['precpctfinal']*(1 - (np.clip(((np.clip(rf['h0'],0,None).apply(lambda x: round(x,0)) + MTM_TempFac * rf['t2m'])/2 - 4*(100-rf['h2m']) ),0,None).apply(lambda x: round(x,3))) / MTM_TriangleFac),0,100).apply(lambda x: round(x,0))
        rf.loc[(rf['rainpct'].isnull()), 'rainpct'] = np.clip((rf['precpctfinal']-rf['snowpct']),0,100).apply(lambda x: round(x,0))

        # D) Calculate tstorm probability
        rf.loc[(rf['tstormpct'].isnull()) & (rf['rdrmax'] >= TstmMtdThrsh), 'tstormpct'] = (((rf['upthrpct'])**(0.5))*TstmRM_Coeff_U+rf['rdrmax']-TstmRM_Coeff_R+(rf['capeave'])**(0.5)*2-TstmRM_Coeff_C).apply(lambda x: round(x,0))
        rf.loc[(rf['tstormpct'].isnull()) & (rf['rdrmax'] < TstmMtdThrsh), 'tstormpct'] = ((rf['precpctfinal']/100)*((rf['capeave'])**(0.5))*2-TstmCM_Coeff_C).apply(lambda x: round(x,0))

        # E) Limit precipitation, snow and tstorm probabilities into range 1-90 %
        intc = ['tstormpct', 'snowpct', 'precpctfinal']
        rf[intc] = rf[intc].applymap(np.int64)

        rf.loc[(rf['precpctfinal'] < 1), 'precpctdisp'] = '<1%'
        rf.loc[(rf['precpctfinal'] > 90), 'precpctdisp'] = '>90%'
        rf.loc[(rf['precpctdisp'].isnull()), 'precpctdisp'] = rf['precpctfinal'].astype(str) + '%'

        #ff[intcols] = ff[intcols].apply(lambda x: pd.Series.round(x, 0))
        #ff[intcols] = ff[intcols].applymap(np.int64)
        #ff = ff.applymap(str)

        rf.loc[(rf['snowpct'] < 1), 'snowpctdisp'] = '<1%'
        rf.loc[(rf['snowpct'] > 90), 'snowpctdisp'] = '>90%'
        rf.loc[(rf['snowpctdisp'].isnull()), 'snowpctdisp'] = rf['snowpct'].astype(str) + '%'

        rf.loc[(rf['tstormpct'] < 1), 'tstormpctdisp'] = '<1%'
        rf.loc[(rf['tstormpct'] > 90), 'tstormpctdisp'] = '>90%'
        rf.loc[(rf['tstormpctdisp'].isnull()), 'tstormpctdisp'] = rf['tstormpct'].astype(str) + '%'

        # F) Clouds and rain
        rf.loc[(rf['precave'] > 4) & (rf['precpct'] > 20) & (rf['cldave'] < 50) & (rf['weather'].isnull()), 'weather'] = '7.png'
        rf.loc[(rf['precave'] > 4) & (rf['precpct'] > 20) & (rf['cldave'] < 85) & (rf['weather'].isnull()), 'weather'] = '16.png'
        rf.loc[(rf['precave'] > 1) & (rf['precpct'] > 20) & (rf['cldave'] < 50) & (rf['weather'].isnull()), 'weather'] = '6.png'
        rf.loc[(rf['precave'] > 1) & (rf['precpct'] > 20) & (rf['cldave'] < 85) & (rf['weather'].isnull()), 'weather'] = '15.png'
        rf.loc[(rf['precave'] > 0) & (rf['precpct'] > 20) & (rf['cldave'] < 50) & (rf['weather'].isnull()), 'weather'] = '5.png'
        rf.loc[(rf['precave'] > 0) & (rf['precpct'] > 20) & (rf['cldave'] < 85) & (rf['weather'].isnull()), 'weather'] = '14.png'
        rf.loc[(rf['precave'] > 4) & (rf['precpct'] > 20) & (rf['weather'].isnull()) , 'weather'] = '25.png'
        rf.loc[(rf['precave'] > 1) & (rf['precpct'] > 20) & (rf['weather'].isnull()) , 'weather'] = '24.png'
        rf.loc[(rf['precave'] > 0) & (rf['precpct'] > 20) & (rf['weather'].isnull()) , 'weather'] = '23.png'
        rf.loc[(rf['cldave'] > 85) & (rf['weather'].isnull()), 'weather'] = '102.png'
        rf.loc[(rf['cldave'] > 50) & (rf['weather'].isnull()), 'weather'] = '4.png'
        rf.loc[(rf['cldave'] > 15) & (rf['weather'].isnull()), 'weather'] = '3.png'
        rf.loc[(rf['cldave'] > 0) & (rf['weather'].isnull()), 'weather'] = '2.png'
        rf.loc[rf['weather'].isnull(), 'weather'] = "1.png"

        # G) Additional T-Storm flag
        rf.loc[(rf['rdrmax'] > TstmRED_RadThrsh) & (rf['upthrpct'] > TstmRED_UpThrsh) & (rf['tstormpct'] > TstmRED_Probab), 'tstorm'] = '202.png'        # grmljavinsko nevrijeme
        rf.loc[(rf['rdrmax'] > TstmYEL_RadThrsh) & (rf['upthrpct'] > TstmYEL_UpThrsh) & (rf['tstormpct'] > TstmYEL_Probab) & (rf['tstorm'] != '202.png'), 'tstorm'] = '201.png'         # grmljavina
        rf.loc[(rf['tstormpct'] > TstmYEL_Probab_woRU) & (rf['tstorm'] != '202.png'), 'tstorm'] = '201.png'         # grmljavina

        # H) Winter weather

        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 2.5 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['cldave']  < 50.0 )  &  (rf['t2m'] < 5.0 )  &  (rf['d2m'] < 2.0), ['winterdone', 'weather']] = ['1', '10.png']     # promjenjivo oblačno, jak snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.5 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['cldave']  < 50.0 )  &  (rf['t2m'] < 5.0 )  &  (rf['d2m'] < 2.0), ['winterdone', 'weather']] = ['1', '9.png' ]     # promjenjivo oblačno, umjeren snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['cldave']  < 50.0 )  &  (rf['t2m'] < 5.0 )  &  (rf['d2m'] < 2.0), ['winterdone', 'weather']] = ['1', '8.png' ]     # promjenjivo oblačno, slab snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 2.5 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['cldave']  < 85.0 )  &  (rf['t2m'] < 5.0 )  &  (rf['d2m'] < 2.0), ['winterdone', 'weather']] = ['1', '19.png']     # pretežno oblačno, jak snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.5 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['cldave']  < 85.0 )  &  (rf['t2m'] < 5.0 )  &  (rf['d2m'] < 2.0), ['winterdone', 'weather']] = ['1', '18.png']     # pretežno oblačno, umjeren snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['cldave']  < 85.0 )  &  (rf['t2m'] < 5.0 )  &  (rf['d2m'] < 2.0), ['winterdone', 'weather']] = ['1', '17.png']     # pretežno oblačno, slab snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 2.5 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['t2m']     <  5.0 )  &  (rf['d2m'] < 2.0),                        ['winterdone', 'weather']] = ['1', '28.png']     # jak snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.5 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['t2m']     <  5.0 )  &  (rf['d2m'] < 2.0),                        ['winterdone', 'weather']] = ['1', '27.png']     # umjeren snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 1.0 )  &  (rf['t2m']     <  5.0 )  &  (rf['d2m'] < 2.0),                        ['winterdone', 'weather']] = ['1', '26.png']     # slab snijeg
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 4.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['cldave']  < 50.0 )  &  (rf['t2m'] < 6.0 )  &  (rf['d2m'] < 3.0), ['winterdone', 'weather']] = ['1', '13.png']     # promjenjivo oblačno, jaka susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 1.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['cldave']  < 50.0 )  &  (rf['t2m'] < 6.0 )  &  (rf['d2m'] < 3.0), ['winterdone', 'weather']] = ['1', '12.png']     # promjenjivo oblačno, umjerena susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['cldave']  < 50.0 )  &  (rf['t2m'] < 6.0 )  &  (rf['d2m'] < 3.0), ['winterdone', 'weather']] = ['1', '11.png']     # promjenjivo oblačno, slaba susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 4.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['cldave']  < 85.0 )  &  (rf['t2m'] < 6.0 )  &  (rf['d2m'] < 3.0), ['winterdone', 'weather']] = ['1', '22.png']     # pretežno oblačno, jaka susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 1.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['cldave']  < 85.0 )  &  (rf['t2m'] < 6.0 )  &  (rf['d2m'] < 3.0), ['winterdone', 'weather']] = ['1', '21.png']     # pretežno oblačno, umjerena susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['cldave']  < 85.0 )  &  (rf['t2m'] < 6.0 )  &  (rf['d2m'] < 3.0), ['winterdone', 'weather']] = ['1', '20.png']     # pretežno oblačno, slaba susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 4.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['t2m']     <  6.0 )  &  (rf['d2m'] < 3.0),                        ['winterdone', 'weather']] = ['1', '31.png']     # jaka susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 1.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['t2m']     <  6.0 )  &  (rf['d2m'] < 3.0),                        ['winterdone', 'weather']] = ['1', '30.png']     # umjerena susnježica
        rf.loc[(rf['winterdone'].isnull()) & (rf['precave'] > 0.0 )  &  (rf['precpctfinal']  > 20.0)  &  ((rf['rainpct']+0.001)/(rf['snowpct']+0.001) < 5.0 )  &  (rf['t2m']     <  6.0 )  &  (rf['d2m'] < 3.0),                        ['winterdone', 'weather']] = ['1', '29.png']     # slaba susnježica

        rf.rtspct_ratio=(rf['rainpct']+0.001)/(rf['snowpct']+0.001)

        with codecs.open("/tmp/rf_prefog.table", "w", encoding='utf-8') as rfprefog_file:
            print(rf.to_string(), file=rfprefog_file)

        # I) Additional fog flag
        # fog="-" po defaultu vec popunjen
        rf.loc[(rf['fogdone'].isnull()) & (rf['precave']  < 0.2) & (rf['h2m'] > 99.0) & (rf['mslp'] > 1010) & (rf['wspd'] < 2.5) & (rf['cldave'] < 101.0) , ['fogdone', 'weather', 'fog']] = ['1', '102.png', '302.png']     # jaka magla, updateamo fog i weather samo ako nije tstorm
        rf.loc[(rf['fogdone'].isnull()) & (rf['precave']  < 0.6) & (rf['h2m'] > 95.0) & (rf['mslp'] > 1005) & (rf['wspd'] < 4.0) & (rf['cldave'] < 101.0) , ['fogdone', 'fog']] =  ['1', '301.png']       # slaba magla , updateamo fog samo ako nije tstorm

        rf.loc[rf['tstorm'] != "-", 'fog'] = '-'

        with codecs.open("/tmp/rf_postfog.table", "w", encoding='utf-8') as rfpostfog_file:
            print(rf.to_string(), file=rfpostfog_file)

        # J) Night symbols (this should be programmed to take in account ACTUAL sun position, but...)

        ephemloc        = ephem.Observer()
        ephemloc.lat    = lat
        ephemloc.lon    = lon
        ephemloc.elevation = float(height)

        def daytime(datetime):
            ephemloc.date=datetime
            next_sunrise    = ephemloc.next_rising(ephem.Sun()).datetime()
            next_sunset     = ephemloc.next_setting(ephem.Sun()).datetime()
            if next_sunset < next_sunrise:
                return 'day'
            else:
                return 'night'

        rf.daynight=rf.date.apply(lambda x: daytime(x))

        def modweather(image):
            #  if daynight == 'day':
            #    return image
            #  else:
            if image == '1.png' :  return  '32.png'
            if image == '2.png' :  return  '33.png'
            if image == '3.png' :  return  '34.png'
            if image == '4.png' :  return  '35.png'
            if image == '5.png' :  return  '37.png'
            if image == '6.png' :  return  '38.png'
            if image == '7.png' :  return  '39.png'
            if image == '8.png' :  return  '40.png'
            if image == '9.png' :  return  '41.png'
            if image == '10.png':  return  '42.png'
            if image == '11.png':  return  '43.png'
            if image == '12.png':  return  '44.png'
            if image == '13.png':  return  '45.png'
            if image == '14.png':  return  '46.png'
            if image == '15.png':  return  '47.png'
            if image == '16.png':  return  '48.png'
            if image == '17.png':  return  '49.png'
            if image == '18.png':  return  '50.png'
            if image == '19.png':  return  '51.png'
            if image == '20.png':  return  '52.png'
            if image == '21.png':  return  '53.png'
            if image == '22.png':  return  '54.png'
            return image


        rf.loc[rf['daynight'] == 'night', 'weather'] = rf['weather'].apply(lambda x: modweather(x))
        # K) Static WIND corrections
        # komentirano

        # L) Wind Codes

        # olujan vjetar
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 337.5 ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'100.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 292.5 ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NW','99.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 247.5 ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'W' ,'98.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 202.5 ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SW','97.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 157.5 ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'S' ,'96.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 112.5 ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SE','95.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 67.5  ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'E' ,'94.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 22.5  ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NE','101.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  <= 22.5  ) & (rf['wspd'] > 15 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'100.png']

        # jak vjetar

        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 337.5 ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'92.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 292.5 ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NW','91.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 247.5 ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'W' ,'90.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 202.5 ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SW','89.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 157.5 ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'S' ,'88.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 112.5 ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SE','87.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 67.5  ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'E' ,'86.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 22.5  ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NE','93.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  <= 22.5  ) & (rf['wspd'] > 10 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'92.png']

        # umjeren vjetar

        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 337.5 ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'84.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 292.5 ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NW','83.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 247.5 ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'W' ,'82.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 202.5 ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SW','81.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 157.5 ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'S' ,'80.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 112.5 ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SE','79.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 67.5  ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'E' ,'78.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 22.5  ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NE','85.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  <= 22.5  ) & (rf['wspd'] > 4 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'84.png']

        # slab vjetar

        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 337.5 ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'77.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 292.5 ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NW','71.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 247.5 ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'W' ,'70.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 202.5 ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SW','69.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 157.5 ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'S' ,'68.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 112.5 ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SE','67.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 67.5  ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'E' ,'66.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 22.5  ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NE','65.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  <= 22.5  ) & (rf['wspd'] >= 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'77.png']

        # tišina ili slab vjetar promjenjiva smjera

        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 337.5 ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 292.5 ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NW','64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 247.5 ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'W' ,'64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 202.5 ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SW','64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 157.5 ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'S' ,'64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 112.5 ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'SE','64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 67.5  ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'E' ,'64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  > 22.5  ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'NE','64.png']
        rf.loc[(rf['winddone'].isnull()) & (rf['wd']  <= 22.5  ) & (rf['wspd'] < 1 ) , ['winddone', 'winddir', 'wind']] =  ['1', 'N' ,'64.png']

        # Reset precipitation amount to 0.0 if weather symbol does not contain precipitation
        rf.loc[(rf['weather'].isin([ '1.png', '2.png', '3.png', '4.png', '102.png', '32.png', '33.png', '34.png', '35.png' ])), 'precave'] = '0.0'

        rf.wspd = rf.wspd.apply(lambda x: round(x,0))
        rf.wdir = rf.wd.apply(lambda x: round(x,0))

        rf.loc[rf['wdir'] == 360, 'wdir'] = 0

        rf.loc[rf['weekday'] == "Monday"   , 'weekday' ] = "Ponedjeljak"
        rf.loc[rf['weekday'] == "Tuesday"  , 'weekday' ] = "Utorak"
        rf.loc[rf['weekday'] == "Wednesday", 'weekday' ] = "Srijeda"
        rf.loc[rf['weekday'] == "Thursday" , 'weekday' ] = "Četvrtak"
        rf.loc[rf['weekday'] == "Friday"   , 'weekday' ] = "Petak"
        rf.loc[rf['weekday'] == "Saturday" , 'weekday' ] = "Subota"
        rf.loc[rf['weekday'] == "Sunday"   , 'weekday' ] = "Nedjelja"

        rf.loc[(rf['rtsratio'].isnull()) & (rf['rtspct_ratio'] >= 999), 'rtsratio' ] = '>999' #rf['rtspct_ratio'].apply(lambda x: round(x,2))
        rf.loc[(rf['rtsratio'].isnull()) & (rf['rtspct_ratio'] >= 100), 'rtsratio' ] = rf['rtspct_ratio'].apply(lambda x: '{:.2f}'.format(round(x,0)))
        rf.loc[(rf['rtsratio'].isnull()) & (rf['rtspct_ratio'] >= 10), 'rtsratio' ] = rf['rtspct_ratio'].apply(lambda x: '{:.2f}'.format(round(x,1)))
        rf.loc[(rf['rtsratio'].isnull()) & (rf['rtspct_ratio'] < 10 ), 'rtsratio' ] = rf['rtspct_ratio'].apply(lambda x: '{:.2f}'.format(round(x,2)))


        # ovo bas nema smisla jer nikad nije -
        #                if [ "$precpctdisp" == "-" ]
        #                then
        #                    rtsratio="-"
        #                fi

        rf.h2m = rf.h2m.apply(lambda x: round(x,1))
        rf.h2mdisp = rf.h2m.apply(lambda x: round(x,0))
        rf.gust = rf.gust.apply(lambda x: round(x,0))

        rf.loc[rf['gust'] < rf['wspd'], 'gust'] = rf['wspd']

        rf.precave = rf.precave.apply(lambda x: round(float(x),1))
        rf.mslp = rf.mslp.apply(lambda x: round(x,0))
        rf.mlcape = rf.mlcape.apply(lambda x: round(x,0))
        rf.h0 = np.clip((rf.h0.apply(lambda x: round(x,0))),0, None)
        rf.t850 = rf.t850.apply(lambda x: round(x,0))
        rf.hour = rf.date.apply(lambda x: x.strftime('%H:%M'))
        rf.ymd = rf.date.apply(lambda x: x.strftime('%Y-%m-%d'))

        #j = (rf.groupby(['ymd','weekday'], as_index=False).apply(lambda x: x[['hour','weather']].to_dict('r')).reset_index().rename(columns={0:'forecast'}).to_json(orient='records'))

        with codecs.open("/tmp/rf.table", "w", encoding='utf-8') as rf_file:
            print(rf.to_string(), file=rf_file)

        #print(rf.to_string())
        a=rf[['location','ymd','weekday','hour','weather','tstorm','fog','wind','wspd','gust','wdir','altt2m','d2m','h2mdisp','precpctdisp','precave','snowpctdisp','tstormpctdisp','mslp','h0','t850','mlcape']]

        with codecs.open("/tmp/rf.table", "w", encoding='utf-8') as a_file:
            print(a.to_string(), file=a_file)

        ff=a.rename(index=str, columns={'altt2m': 'temperature',\
                                    'ymd': 'date',\
                                    'd2m': 'dewpoint',\
                                    'h2mdisp':'humidity',\
                                    'precave':'prec',\
                                    'snowpctdisp':'snowpct',\
                                    'precpctdisp':'precpct',\
                                    'tstormpctdisp': 'tstormpct',\
                                    'h0':'h0m'})

        intcols = ['mlcape', 'wdir', 'mslp', 't850', 'gust', 'h0m', 'wspd',  'temperature', 'dewpoint', 'humidity']
        ff[intcols] = ff[intcols].apply(lambda x: pd.Series.round(x, 0))
        ff[intcols] = ff[intcols].applymap(np.int64)
        ff = ff.applymap(str)

        with codecs.open("/tmp/ff.table", "w", encoding='utf-8') as ff_file:
            print(ff.to_string(), file=ff_file)

        j=ff.groupby(['date', 'weekday'],as_index=False).apply(lambda x: x[['hour','weather','tstorm','fog','wind','wspd','gust','wdir','temperature','dewpoint','humidity','precpct','prec','snowpct','tstormpct','mslp','h0m','t850','mlcape']].to_dict('r')).reset_index().rename(columns={0:'forecast'})


        locations = {}
        for locgrp, locdf in a.groupby('location'):
            #  print('Group: %s' % locgrp)
            #  print('DataFrame description: \n%s\n' % locdf)
            my_dict = {'location': locgrp , 'data': j.to_dict('r')}
            #  for dategrp, datedf in locdf.groupby(['ymd','weekday']):
                #my_dict["data"].append({'date' : dategrp[0], 'weekday' : dategrp[1], 'forecast' : []})
            #  my_dict["data"].append({json.loads(j).astype(str)})

        #my_dict["data"].append(j.to_dict('r'))

        outputfile=str(jsondir) + "/" + str(location) + ".json"
        with open(outputfile, "w") as json_file:
            print(json.dumps(my_dict, indent=2, sort_keys=False), file=json_file)

        elapsed_time = time.time() - start_time

        #print(elapsed_time)
        #print(ff.to_string())
        #print(rf.dtypes)
