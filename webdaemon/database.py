from flask_sqlalchemy import SQLAlchemy
from settings import settings

db = SQLAlchemy()

def init_database(app):
	global db
	app.logger.info('Connecting to SQL database...')
	config = 'db_test'
	sql_info = settings['db']
	#if (sql_info['driver'] == "SQLITE"):
	#   app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///{filepath}'.format(**sql_info)
	if (sql_info['driver'] in ["ODBC", "FreeTDS"]):
		app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc://{user}:{password}@{host}:{port}/{dbname}?driver={driver}'.format(**sql_info)
	try:
		db.init_app(app)
	except:
		app.logger.error("Could not initialize database")

def create_database(app):
	from webdaemon.model import Settleplate
	with app.app_context():
		db.create_all()