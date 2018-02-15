#!/usr/bin/python3

from pandas.io import sql
from sqlalchemy import create_engine
import mysql.connector
from mysql.connector import Error
from csv import reader
from pprint import pprint
from collections import defaultdict
import numpy as np
import pandas as pd
from pandas.io import sql
import time
import math
from math import sqrt

# ------------------ config start ---------------------#
MTM_TempFac=200         # Larger the number --> Positive t2m has LARGER influence on melting falling snow (default=200)
MTM_TriangleFac=700     # Larger the number --> Positive t2m AND positive zeroChgt have SMALLER influence on melting (default=500)
# ------------------- config end ----------------------#

csvdir="input_csv"
location="Zagreb"
master = pd.DataFrame()
dflist = []
df = {}

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
          ["extract","mdlhgt","mdlhgt",0], \
          ["extract","mlcape","mlcape",0], \
          ["extract","mslp","mslp",0], \
          ["extract","prec","prec",0], \
          ["extract","t2m","t2m",0], \
          ["extract","t850","t850",0], \
          ["extract","wd","wd",0], \
          ["extract","wspd","wspd",0]] \
#sources = [["cldave","cld",0]]

for i in range(len(sources)):
  filename=str(csvdir) + "/" + sources[i][0] + "_" + str(location) + "_" + sources[i][2]
  varname=str(sources[i][1])
  field=int(sources[i][3])
  df[varname] = pd.read_csv(filename, header=None, usecols=[field], names=[varname], dtype=np.float64)
  dflist.append(df[varname])
  rf = pd.concat(dflist, axis=1)


#add cloumn weather
rf['weather'] = "None"
rf['precpctfinal'] = "None"
rf['snowpct'] = "None"
rf['rainpct'] = "None"
rf['tstormpct'] = "None"
rf['precpctdisp'] = str("None")
rf['snowpctdisp'] = str("None")
rf['tstormpctdisp'] = str("None")


start_time = time.time()

# B) Calculate final precipitation probability
rf.loc[(rf['precpctfinal'] == "None"), 'precpctfinal'] = np.clip((rf['precpct'] + (np.clip((rf['rdrmax'] - 20),0,None)/2) + np.clip((rf['cldave'] - 60),0,None)/4),0,100).apply(lambda x: round(x,0))

# C) Calculate snow probability
rf.loc[(rf['snowpct'] == "None"), 'snowpct'] = np.clip(rf['precpctfinal']*(1 - (np.clip(((np.clip(rf['h0'],0,None).apply(lambda x: round(x,0)) + MTM_TempFac * rf['t2m'])/2),0,None).apply(lambda x: round(x,3))) / MTM_TriangleFac),0,100).apply(lambda x: round(x,0))
rf.loc[(rf['rainpct'] == "None"), 'rainpct'] = np.clip((rf['precpctfinal']-rf['snowpct']),0,100).apply(lambda x: round(x,0))

# D) Calculate tstorm probability

rf.loc[(rf['tstormpct'] == "None") & (rf['rdrmax'] >= 35), 'tstormpct'] = (((rf['upthrpct'])**(0.5))*14+rf['rdrmax']-40+(rf['capeave'])**(0.5)*2-15).apply(lambda x: round(x,0))
rf.loc[(rf['tstormpct'] == "None") & (rf['rdrmax'] < 35), 'tstormpct'] = ((rf['precpctfinal']/100)*((rf['capeave'])**(0.5))*2-15).apply(lambda x: round(x,0))

# E) Limit precipitation, snow and tstorm probabilities into range 1-90 %

rf.loc[(rf['precpctfinal'] < 1), 'precpctdisp'] = '<1%'
rf.loc[(rf['precpctfinal'] > 90), 'precpctdisp'] = '>90%'
rf.loc[(rf['precpctdisp'] == "None"), 'precpctdisp'] = rf['precpctfinal'].astype(str) + '%'

rf.loc[(rf['snowpct'] < 1), 'snowpctdisp'] = '<1%'
rf.loc[(rf['snowpct'] > 90), 'snowpctdisp'] = '>90%'
rf.loc[(rf['snowpctdisp'] == "None"), 'snowpctdisp'] = rf['snowpct'].astype(str) + '%'

rf.loc[(rf['tstormpct'] < 1), 'tstormpctdisp'] = '<1%'
rf.loc[(rf['tstormpct'] > 90), 'tstormpctdisp'] = '>90%'
rf.loc[(rf['tstormpctdisp'] == "None"), 'tstormpctdisp'] = rf['tstormpct'].astype(str) + '%'

# F) Clouds and rain
rf.loc[(rf['precave'] > 4) & (rf['precpct'] > 20) & (rf['cldave'] < 50) & (rf['weather'] == 'None'), 'weather'] = '7.png'
rf.loc[(rf['precave'] > 4) & (rf['precpct'] > 20) & (rf['cldave'] < 85) & (rf['weather'] == 'None'), 'weather'] = '16.png'
rf.loc[(rf['precave'] > 1) & (rf['precpct'] > 20) & (rf['cldave'] < 50) & (rf['weather'] == 'None'), 'weather'] = '6.png'
rf.loc[(rf['precave'] > 1) & (rf['precpct'] > 20) & (rf['cldave'] < 85) & (rf['weather'] == 'None'), 'weather'] = '15.png'
rf.loc[(rf['precave'] > 0) & (rf['precpct'] > 20) & (rf['cldave'] < 50) & (rf['weather'] == 'None'), 'weather'] = '5.png'
rf.loc[(rf['precave'] > 0) & (rf['precpct'] > 20) & (rf['cldave'] < 85) & (rf['weather'] == 'None'), 'weather'] = '14.png'
rf.loc[(rf['precave'] > 4) & (rf['precpct'] > 20) & (rf['weather'] == 'None'), 'weather'] = '25.png'
rf.loc[(rf['precave'] > 1) & (rf['precpct'] > 20) & (rf['weather'] == 'None'), 'weather'] = '24.png'
rf.loc[(rf['precave'] > 0) & (rf['precpct'] > 20) & (rf['weather'] == 'None'), 'weather'] = '23.png'
rf.loc[(rf['cldave'] > 85) & (rf['weather'] == 'None'), 'weather'] = '102.png'
rf.loc[(rf['cldave'] > 50) & (rf['weather'] == 'None'), 'weather'] = '4.png'
rf.loc[(rf['cldave'] > 15) & (rf['weather'] == 'None'), 'weather'] = '3.png'
rf.loc[(rf['cldave'] > 0) & (rf['weather'] == 'None'), 'weather'] = '2.png'
rf.loc[rf['weather'] == 'None', 'weather'] = "1.png"


elapsed_time = time.time() - start_time

print(elapsed_time)
print(rf.to_string())
print(rf.dtypes)