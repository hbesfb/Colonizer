import pyodbc
import sqlalchemy as db
import os
import json
from PIL import Image
from os import path
from sqlalchemy.orm import Session
from sqlalchemy.ext.automap import automap_base
from settings import settings
from hashlib import md5
from datetime import datetime

# settings
fromdate = datetime(2024,10,1)
version='WebApp 2.0'
outpath="/mnt/data/Data/Colonizer/eksport"

config_file = os.environ.get('SETTLEPLATE_CONFIG','production')

if not settings.init(config_file):
	exit(1)
# create database
db_uri = 'mssql+pyodbc://{user}:{password}@{host}:{port}/{dbname}?driver={driver}'.format(**settings['db'])

engine = db.create_engine(db_uri)
connection = engine.connect()
session = Session(engine)
base = automap_base()
base.prepare(autoload_with=engine)
SettlePlate = base.classes.SETTLEPLATE

# start querying
query = session.query(SettlePlate.ID, SettlePlate.Barcode, SettlePlate.ScanDate, SettlePlate.Counts, SettlePlate.Colonies).filter(SettlePlate.Counts >= '0', SettlePlate.Version.like(version))
results = query.all()
for i,row in zip(range(len(results)),results):
	query_t0 = session.query(SettlePlate.ScanDate).filter(db.and_(SettlePlate.Barcode.like(row.Barcode), SettlePlate.Counts == '-1'))
	age = round( (row.ScanDate - query_t0.one().ScanDate).total_seconds() / (60*60) )
	name = md5(row.Barcode.encode()).hexdigest()
	counts = row.Counts
	filename = f"{name}-{age}-{counts}"
	img_path = path.join(outpath,filename+".jpg")
	# check if settleplate has been saved
	if os.path.isfile(img_path):
		print("{}/{} skipped".format(i+1,len(results)))
	else:
		# save image
		imagedata = session.query(SettlePlate.Image).filter(SettlePlate.ID == row.ID).one().Image
		with open(img_path, 'wb') as f:
			f.write(imagedata)
		# convert CFU info to tensorflow annotations
		w,h = img = Image.open(img_path).size
		annotation = []
		for cfu in json.loads(row.Colonies):
			y1,x1,y2,x2 = cfu['bbox']
			annotation.append({
				"x":			round(x1*w),
				"y":			round(y1*h),
				"width":		round((x2-x1)*w),
				"height":	round((y2-y1)*h),
				"label": 	"single_colony"
			})

		with open(path.join(outpath,filename+".json"), 'w') as f:
			f.write(json.dumps(annotation))
		print("{}/{} saved: {}".format(i+1,len(results),filename))