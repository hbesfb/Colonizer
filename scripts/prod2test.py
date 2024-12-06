#!/usr/bin/env python3
import os
import pyodbc
from datetime import datetime, timedelta
from configparser import ConfigParser
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import Session
from sqlalchemy.ext.automap import automap_base

# readonly database
def db_ro(*args, **kwargs):
	print('Readonly DB!')
	return

# create database
def get_db(inifile_path):
	settings = ConfigParser()
	settings.read(inifile_path)
	sql_info = {
		'filepath' : settings['db']['filepath'],
		'driver'   : settings['db']['driver'],
		'host'     : settings['db']['hostname'],
		'port'     : settings['db']['port'],
		'user'     : settings['db']['user'],
		'password' : settings['db']['password'],
		'dbname'   : settings['db']['name'],
		'args'     : settings['db']['arg'],
		'table'    : settings['db']['table']
	}
	if (sql_info['driver'] == "SQLITE"):
		db_uri = 'sqlite:///{filepath}'.format(**sql_info)
	elif (sql_info['driver'] in ["ODBC", "FreeTDS"]):
		db_uri = 'mssql+pyodbc://{user}:{password}@{host}:{port}/{dbname}?driver={driver}'.format(**sql_info)
	db =  create_engine(db_uri) #, echo=True)
	return db

# setup test session
print('Connecting to test DB ...')
test_base = automap_base()
test_engine = get_db('./settleplate-test.ini')
test_base.prepare(test_engine, reflect=True)
test_obj = test_base.classes.SETTLEPLATE
test_session = Session(test_engine, autoflush=False, autocommit=False)

# setup readonly production session
print('Connectiong to production DB ...')
prod_base = automap_base()
prod_engine = get_db('./settleplate-prod.ini')
prod_base.prepare(prod_engine, reflect=True)
prod_obj = prod_base.classes.SETTLEPLATE
prod_session = Session(prod_engine, autoflush=False, autocommit=False)
prod_session.flush = db_ro

# find settleplates registered last 31 days
to_date = datetime.now()
from_date = to_date - timedelta(days=31)

# query database
print('Querying database ...')
query = prod_session.query(prod_obj)
query = query.filter(and_(prod_obj.ScanDate >= from_date, prod_obj.ScanDate <= to_date))
results = query.all()
print('%d settleplates found'%len(results))
#copy settleplates
for old_obj in results:
	# test if ID already in test DB
	dT = timedelta(seconds=0.5)
	if test_session.query(test_obj.ID).filter(and_(test_obj.ScanDate >= old_obj.ScanDate - dT, test_obj.ScanDate <= old_obj.ScanDate + dT)).scalar() is not None:
		print('  Skip: %d'%old_obj.ID)
		continue
	print('  Copy: %d'%old_obj.ID)
	# else copy it over
	params = old_obj.__dict__.copy()
	params.pop('_sa_instance_state')
	params.pop('ID')
	params['Exported'] = False
	new_obj = test_obj(**params)
	test_session.add(new_obj)
	test_session.flush()

#
if input('Commit to test_database? (y/n): ') == 'y':
	test_session.commit()
	print('Done')
else:
	print('Aborted!')

