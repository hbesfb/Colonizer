import traceback
import os
import time
from sqlalchemy import text
from flask_sqlalchemy import SQLAlchemy
from settings import settings

db = SQLAlchemy()

def init_database(app):
	"""
	Initialize the database connection.
	Supports:
	  - MSSQL (via FreeTDS/ODBC + pyodbc)
	  - PostgreSQL (via psycopg2)
	Uses config from settings['db'].
	"""
	global db

	app.logger.info('Connecting to database...')

	sql_info = settings['db']
	db_type = sql_info.get('db_type', '').lower()
	
	#validate required keys
	required_keys = ['host', 'port', 'dbname', 'user', 'password']
	if db_type in ['mssql', 'sqlserver', 'postgres', 'postgresql']:
		missing = [k for k in required_keys if k not in sql_info]
		if missing:
			raise ValueError(f"Missing required DB config keys: {missing}")

	# ------------------------------------------------------------
	# MSSQL (ODBC)
	# ------------------------------------------------------------
	if db_type in ['mssql', 'sqlserver']:
		# Build ODBC string for MSSQL (e.g. using FreeTDS driver)
		odbc_str = (
			f"DRIVER={{{sql_info['driver']}}};"
			f"SERVER={sql_info['host']},{sql_info['port']};"
			f"DATABASE={sql_info['dbname']};"
			f"UID={sql_info['user']};"
			f"PWD={sql_info['password']};"
			f"{sql_info.get('arg', '')}"
		)

		# Mask password in logs
		safe_odbc = odbc_str.replace(sql_info['password'], "***")
		app.logger.info(f"ODBC raw string (password masked): {safe_odbc}")

		encoded = URL.create( "mssql+pyodbc", query={"odbc_connect": odbc_str})
		app.config['SQLALCHEMY_DATABASE_URI'] = str(encoded)
		app.logger.info("Using MSSQL database (ODBC driver / FreeTDS).")

	# ------------------------------------------------------------
	# PostgreSQL
	# ------------------------------------------------------------
	elif db_type in ['postgres', 'postgresql']:
		# Build SQLAlchemy URI for PostgreSQL
		uri = (
			f"postgresql+psycopg2://{sql_info['user']}:{sql_info['password']}@"
			f"{sql_info['host']}:{sql_info['port']}/{sql_info['dbname']}"
			)
		#Mask password in logs
		safe_uri = str(uri).replace(sql_info['password'], "***")
		app.logger.info(f"PostgreSQL URL (password masked): {safe_uri}")

		app.config['SQLALCHEMY_DATABASE_URI'] = uri
		app.logger.info("Using PostgreSQL database (psycopg2 driver).")

		# Initialize SQLAlchemy
		db.init_app(app)

		# Retry logic for PostgreSQL incase DB is not yet ready when app starts
		MAX_RETRIES = 10
		retry_delay = 1
		for attempt in range(1, MAX_RETRIES + 1):
			try:
				with app.app_context():
					db.session.execute(text("SELECT 1"))
				app.logger.info("PostgreSQL database connection initialized successfully.")
				app.logger.info(f"PostgreSQL connection successful on attempt {attempt}")
				break
			except Exception as e:
				app.logger.warning(
					f"PostgreSQL connection failed (attempt {attempt}/{MAX_RETRIES}): {e}"
				)
				time.sleep(retry_delay)
		else:
			app.logger.critical("PostgreSQL unavailable after retries — cannot start")
			raise SystemExit(1)

	# Try initializing for all DB types except PostgreSQL (which has been handled above)
	if db_type not in ['postgres', 'postgresql']:
		try:
			db.init_app(app)
		except Exception as e:
			app.logger.error(f"Could not initialize database: {str(e)}")
			app.logger.error(f"Exception type: {type(e).__name__}")
			app.logger.error(f"Full traceback: {traceback.format_exc()}")
			raise
		
	# ------------------------------------------------------------
	# Kubernetes-specific connection tests to PostgreSQL
	# ------------------------------------------------------------
	config_file = os.environ.get('SETTLEPLATE_CONFIG', 'default')
	if config_file == "kubernetes" and db_type.lower() in ['postgres', 'postgresql']:
		try:
			# Test the database connection within app context
			with app.app_context():
				# Test 1: Check if database engine is available
				try:
					engine = db.engine # db.get_engine() is deprecated in SQLAlchemy 2.x,
					safe_engine_url = str(engine.url).replace(sql_info['password'], "***")
					app.logger.info(f"Database engine available: {safe_engine_url}")
				except Exception as e:
					app.logger.error(f"Database engine not available: {e}")
					raise
			
				# Test 2: Attempt a simple database query
				try:
					result = db.session.execute(db.text('SELECT version()')).scalar()
					app.logger.info(f"Database connection successful. PostgreSQL version: {result}")
				except Exception as e:
					app.logger.error(f"Database connection test failed: {e}")
					raise
			
				# Test 4: Test transaction capability
				try:
					db.session.execute(db.text('SELECT 1')).scalar()
					db.session.commit()
					app.logger.info("Database transaction test successful.")
				except Exception as e:
					app.logger.error(f"Database transaction test failed: {e}")
					db.session.rollback()
					raise

			app.logger.info('Database connection initialized and tested successfully (k3s).')
		
		except Exception as e:
			app.logger.error(f"Database initialization failed: {str(e)}")
			app.logger.error(f"Exception type: {type(e).__name__}")
			app.logger.error(f"Full traceback: {traceback.format_exc()}")
		
			# Log connection details for debugging (without password)
			app.logger.error(f"Connection details - Host: {sql_info['host']}, Port: {sql_info['port']}, "
						f"Database: {sql_info['dbname']}, User: {sql_info['user']}")
			raise	

def create_database(app):
	from webdaemon.model import Settleplate
	with app.app_context():
		db.create_all()

def create_database_cmd():
	from webdaemon.model import Settleplate
	from sqlalchemy.dialects import mssql
	from sqlalchemy.schema import CreateTable
	return CreateTable(Settleplate.__table__).compile(dialect=mssql.dialect())