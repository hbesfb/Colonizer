#!/usr/bin/env python3
import os
import time
import logging
from flask import Flask
from flask_session import Session
from redis import Redis
from settings import settings, get_secret
from webdaemon.status import servicemonitor
from webdaemon.database import init_database, create_database
from webdaemon.version import __version__
import hwlayer.client as hwclient

# create flask app
app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.logger.info(f'Starting Colonizer v{__version__}')

# Make settings available inside all Jinja templates
@app.context_processor
def inject_settings():
	return dict(settings=settings)

# load settings
# The enviroment sets config file to "kubernetes" in k8s or "production" on the Pi
# if is not set in the enviroment, it defaults to "default"
config_file = os.environ.get('SETTLEPLATE_CONFIG', 'default')
is_k8s = (config_file == "kubernetes")
app.logger.info(f"SETTLEPLATE_CONFIG used: {config_file}")

if not settings.init(config_file, app.logger):
	raise SystemExit(1)

# config
app.config['SECRET_KEY'] = get_secret()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# ------------------------------------------------------
# Redis Connection
# ------------------------------------------------------
def create_redis_client(host, port, password=None):
	"""Create and test a Redis client connection."""
	client = Redis(
		host=host,
		port=port,
		password=password,
		decode_responses=False,
		socket_connect_timeout=5,
		socket_timeout=5,
		retry_on_timeout=True,
		health_check_interval=30,
		max_connections=50
	)
	# Test connection
	client.ping()
	return client

# Redis connection setup
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', '6379'))
redis_password = os.environ.get('REDIS_PASSWORD', None)

app.logger.info(f'Connecting to Redis at {redis_host}:{redis_port}')

# Retry loop for Redis connection
MAX_RETRIES = 10
retry_delay = 1

redis_client = None
for attempt in range(1, MAX_RETRIES + 1):
	try:
		redis_client = create_redis_client(redis_host, redis_port, redis_password)
		app.logger.info(f"Redis connection successful on attempt {attempt}")
		break
	except Exception as e:
		app.logger.warning(f"Redis connection failed (attempt {attempt}/{MAX_RETRIES}): {e}")
		time.sleep(retry_delay)

# If still no Redis after retries → handle based on environment
if redis_client is None:
	if is_k8s: #Explicit fatal failure in Kubernetes 
		app.logger.critical("Redis unavailable in Kubernetes after retries — cannot start")
		raise SystemExit(1)
	else:
		# Local fallback
		app.logger.warning("Retrying fallback to local Redis at localhost:6379")
		try:
			redis_client = create_redis_client("localhost", 6379)
			app.logger.info("Fallback Redis connection successful")
			redis_host, redis_port = "localhost", 6379 # update final host/port used
		except Exception as e:
			app.logger.critical(f"Local Redis connection failed: {e}")
			raise SystemExit(1)

app.logger.info(f"Final Redis connection in use: {redis_host}:{redis_port}")

# ------------------------------------------------------
# Session Configuration
# ------------------------------------------------------
app.logger.info('Setting redis session storage...')
app.config['SESSION_KEY_PREFIX'] = 'colonizer:'  # namespace keys
app.config['SESSION_USE_SIGNER'] = True          # sign cookies for tamper-proofing
app.config['SESSION_COOKIE_NAME'] = 'Colonizer-App'
app.config['SESSION_PERMANENT'] = True           # allow expiry via timeout below
app.config['PERMANENT_SESSION_LIFETIME'] = settings['general']['timeout']

# Set Fask session cookie settings
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Decide other cookie policies based on environment
if config_file == 'kubernetes':
	# In k8s: allow cross-site usage, require HTTPS
	app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
	app.config['SESSION_COOKIE_SECURE'] = True
	app.logger.info("Session cookies set for Kubernetes (SameSite=Lax, Secure=True, HttpOnly=True)")
else:
	# Local dev: strict cookies, no HTTPS requirement
	app.config['SESSION_COOKIE_SAMESITE'] = "Strict" # default is Lax
	app.config['SESSION_COOKIE_SECURE'] = False # flax default
	app.logger.info("Session cookies set for local dev (SameSite=Strict, Secure=False, HttpOnly=True)")

#initialize sessions ensuring app uses the same tested Redis connection
#(In k8s Redis runs in same Pod as Colonizer, so we can use localhost)
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis_client
Session(app)

# Make Redis available to colonizer app
app.redis = redis_client

# ------------------------------------------------------
# Database Initialization #
# ------------------------------------------------------
app.logger.info('initializing database...')
init_database(app)

#we dont use create_database() in k8s, startup script handles settleplate table creation
if not is_k8s:
	create_database(app) # this is indempotent

# ServiceMonitor
app.logger.info('Initializing ServiceMonitor for hardware...')
servicemonitor.init(app)
app.logger.info('ServiceMonitor started')

# ------------------------------------------------------
# Hardware Initialization
# ------------------------------------------------------
app.logger.info('Initializing hardware client...')

# Log the address the client will use
try:
	zmq_addr = hwclient._resolve_address()
	app.logger.info(f"Using ZMQ address: {zmq_addr}")
except Exception as e:
	app.logger.error(f"Could not resolve ZMQ address: {e}")
	zmq_addr = None

# Initialize the hardware client 
try:
	hardware_initialized = hwclient.start_socket()
	if hardware_initialized: 
		app.logger.info("Hardware client initialized successfully") 
	else: app.logger.warning("Hardware client failed to initialize") 
except Exception as e: 
	app.logger.error(f"Hardware client initialization failed: {e}") 
	hardware_initialized = False 

# Expose initialization state to the app
app.hardware_initialized = hardware_initialized

# ------------------------------------------------------
# Health and readiness endpoints 
# ------------------------------------------------------
@app.route('/health')
def health_check():
	"""Health check endpoint for Kubernetes liveness probe"""
	try:
		# Basic app health - check if Flask is responding
		return {
			'status': 'healthy', 
			'Colonizer version': __version__,
			'config': config_file
		}, 200
	except Exception as e:
		app.logger.error(f'Health check failed: {e}')
		return {'status': 'unhealthy', 'error': str(e)}, 500

@app.route('/ready')
def readiness_check():
	"""
	Readiness check endpoint for Kubernetes readiness probe
	This checks if the application is ready to serve traffic 
	"""
	return "ok", 200

@app.route('/deep_ready')
def deep_readiness_check():
	"""
	Deep readiness check for debugging and diagnostics.
	This performs the full dependency check:
	- Redis
	- Hardware (ZMQ)
	- Colonizer version
	- Config
	"""
	checks = []
	all_ready = True
	
	try:
		# Test Redis connection
		if app.redis:
			try:
				app.redis.ping()
				checks.append({'component': 'redis', 'status': 'ok'})
			except Exception as e:
				checks.append({'component': 'redis', 'status': 'failed', 'error': str(e)[:50]})
				all_ready = False
		else:
			checks.append({'component': 'redis', 'status': 'unavailable'})
			all_ready = False
		
		# Test hardware connection, readiness should not fail because of hardware
		if app.hardware_initialized:
			try:
				hw_ready = hwclient.is_ready()
				if hw_ready:
					checks.append({'component': 'hardware', 'status': 'ready'})
				else:
					checks.append({'component': 'hardware', 'status': 'not initialized'})
			except Exception as e:
				checks.append({'component': 'hardware', 'status': 'error', 'error': str(e)[:50]})
		else:
			checks.append({'component': 'hardware', 'status': 'not initialized'})

		# Final readiness status	
		status = 'ready' if all_ready else 'not_ready'
		return {
			'status': status,
			'Colonizer version': __version__,
			'config': config_file,
			'checks': checks
		}, 200 if all_ready else 503
		
	except Exception as e:
		app.logger.error(f'Readiness check failed: {e}')
		return {
			'status': 'not_ready',
			'error': str(e),
			'checks': checks
		}, 503

@app.route('/status')
def service_status():
	"""
	Status endpoint used by the UI to show green/red icons.
	Returns SQL, camera, and storage status from ServiceMonitor.
	"""
	try:
		status = servicemonitor.status

		return {
			"status": "ok",
			"sql": status.get("sql"),
			"camera": status.get("camera"), # <-- hardware readiness already included
			"storage": status.get("storage"),
			"last_update": servicemonitor._lastupdate.isoformat()
		}, 200

	except Exception as e:
		app.logger.error(f"/status endpoint failed: {e}")
		return {"status": "error", "error": str(e)}, 500
	
# -------------------------------
# Setup routes & service checker
# -------------------------------
app.logger.info('Setting up routes...')

# Import all routes to register blueprints
import webdaemon.routes 
app.logger.info('Routes setup complete.')
app.logger.info(f'Colonizer v{__version__} initialization complete')