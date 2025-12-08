#!/usr/bin/env python3
import os
import logging
from redis import Redis, ConnectionError as RedisConnectionError
from flask import Flask
from flask_session import Session
from settings import settings, get_secret
from webdaemon.status import servicemonitor
from webdaemon.database import init_database
from webdaemon.version import __version__

# create flask app
app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.logger.info(f'Starting Colonizer v{__version__}')

# load settings
config_file = os.environ.get('SETTLEPLATE_CONFIG', 'default')
app.logger.info(f"SETTLEPLATE_CONFIG used: {config_file}")
if not settings.init(config_file, app):
	raise SystemExit(1)

# config
app.config['SECRET_KEY'] = get_secret()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

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

try:
	redis_client = create_redis_client(redis_host, redis_port, redis_password)
	app.logger.info('Redis connection successful')

except (RedisConnectionError, Exception) as e:
	app.logger.error(f'Failed to connect to Redis at {redis_host}:{redis_port}: {e}')
	
	# In non k8s fallback to localhost:6379 if we haven't tried it yet
	if not (redis_host == 'localhost' and redis_port == 6379):
		app.logger.critical('Redis unavailable in Kubernetes - cannot start')
		raise SystemExit(1)
	
	# In non k8s fallback to localhost if not already used:
	if redis_host != 'localhost' or redis_port != 6379:
		app.logger.info('Attempting fallback to local Redis at localhost:6379...')
		try:
			redis_client = create_redis_client('localhost', 6379)
			app.logger.info('Fallback Redis connection successful')
		except (RedisConnectionError, Exception) as fallback_error:
			app.logger.critical(f'All Redis connections failed: {fallback_error}')
			raise SystemExit(1)
	else:
		app.logger.critical('Local Redis connection failed')
		raise SystemExit(1)

# Session behavior
app.logger.info('Setting redis session storage...')
app.config['SESSION_KEY_PREFIX'] = 'colonizer:'  # namespace keys
app.config['SESSION_USE_SIGNER'] = True          # sign cookies for tamper-proofing
app.config['SESSION_COOKIE_NAME'] = 'Colonizer-App'
app.config['SESSION_PERMANENT'] = True           # allow expiry via timeout below
app.config['PERMANENT_SESSION_LIFETIME'] = settings['general']['timeout']

# Decide cookie policy based on environment
if config_file == 'kubernetes':
	# In k8s: allow cross-site usage, require HTTPS
	app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
	app.config['SESSION_COOKIE_SECURE'] = True
	app.config['SESSION_COOKIE_HTTPONLY'] = True
	app.logger.info("Session cookies set for Kubernetes (SameSite=Lax, Secure=True, HttpOnly=True)")
else:
	# Local dev: strict cookies, no HTTPS requirement
	app.config['SESSION_COOKIE_SAMESITE'] = "Strict"
	app.config['SESSION_COOKIE_SECURE'] = False
	app.config['SESSION_COOKIE_HTTPONLY'] = True
	app.logger.info("Session cookies set for local dev (SameSite=Strict, Secure=False, HttpOnly=True)")

#initialize sessions ensuring app uses the same tested Redis connection
#(In k8s Redis runs in same Pod as Colonizer, so we can use localhost)
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis_client
Session(app)

# Make Redis available to colonizer app
app.redis = redis_client

app.logger.info('initializing database...')
init_database(app)

# ServiceMonitor
app.logger.info('Initializing ServiceMonitor for hardware...')
servicemonitor.init(app)

# -------------------------------
# Hardware/ZMQ client initialization
# -------------------------------
app.logger.info('Initializing hardware client...')
hw_client = None

def get_zmq_address(config):
	"""Determine ZMQ address based on configuration."""
	if config == 'kubernetes':
		# In k3s cluster - use service DNS name
		cluster_addr = os.environ.get('CLUSTER_ZMQ_ADDR')
		if not cluster_addr:
			app.logger.error('CLUSTER_ZMQ_ADDR not set for kubernetes config')
			return None
		
		if cluster_addr.startswith("tcp://"):
			return cluster_addr
		else:
			# Assume it's just a hostname and add tcp:// plus the default port
			return f"tcp://{cluster_addr}:3117"
	else:
		# Non-kubernetes config
		local_addr = os.environ.get('LOCAL_ZMQ_ADDR', 'localhost')
		if local_addr.startswith("tcp://"):
			return local_addr
		else:
			return f"tcp://{local_addr}:3117"

# Determine ZMQ address based on configuration
try:
	import hwlayer.client as hwclient
	app.logger.info(f'Hardware setup for config: {config_file}')
	
	zmq_addr = get_zmq_address(config_file)

	if zmq_addr:
		app.logger.info(f'Using ZMQ address: {zmq_addr}')
		os.environ["CLUSTER_ZMQ_ADDR"] = zmq_addr
		hw_client = hwclient.start_socket(zmq_addr)
		app.logger.info("Hardware client initialized successfully")
	else:
		app.logger.warning("No ZMQ address configured for hardware")

except ImportError as e:
	app.logger.error(f'Failed to import hwlayer.client: {e}')
except Exception as e:
	app.logger.error(f'Hardware client initialization failed: {e}')
	

# Make hardware client available to the app
app.hw_client = hw_client

# Health and readiness endpoints
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
	
	This checks if the application is ready to serve traffic by verifying
	dependencies like Redis and hardware connections.
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
		
		# Test hardware connection
		if hw_client:
			try:
				import hwlayer.client as hwclient
				hw_ready = hwclient.check_ready()
				if hw_ready:
					checks.append({'component': 'hardware', 'status': 'ready'})
				else:
					checks.append({'component': 'hardware', 'status': 'not_ready'})
					all_ready = False
			except Exception as e:
				checks.append({'component': 'hardware', 'status': 'error', 'error': str(e)[:50]})
				all_ready = False
		else:
			checks.append({'component': 'hardware', 'status': 'unavailable'})
			# Not failing readiness if hardware is optional
		
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

# -------------------------------
# Setup routes & service checker
# -------------------------------
app.logger.info('Setting up routes...')

# Import all routes to register blueprints
import webdaemon.routes 
app.logger.info('Routes setup complete.')
app.logger.info(f'Colonizer v{__version__} initialization complete')