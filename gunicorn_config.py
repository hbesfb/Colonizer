import os
import multiprocessing

config_file = os.environ.get('SETTLEPLATE_CONFIG', 'default')
is_k8s = config_file == "kubernetes"
path = os.getcwd()
command = f'{path}/venv/bin/gunicorn' #TODO is this used for anything??
pythonpath = path
pidfile = f'{path}/run/colonizer.pid'

accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-") # stdout as default
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-") # stdout as default

# ---------------------------
# User, worker config and bind address
# ---------------------------
if is_k8s:
	user = os.getenv("GUNICORN_USER")
	if not user:
		raise RuntimeError("GUNICORN_USER must be set in Kubernetes deployment")

	port = os.getenv("PORT", "8000")
	bind = f"0.0.0.0:{port}"
	workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
else:
	user = 'colonizer'
	bind = f'unix:{path}/run/colonizer.sock'
	workers = 4

# ---------------------------
# Worker configuration
# ---------------------------
timeout = 30 # Max time (seconds) a worker can take to respond before being killed. Prevents hung requests.
keepalive = 2 #Keep connections alive for 2 seconds

# Recycle workers to prevent memory leaks
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '200'))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', '50'))
#preload_app = True # Load your Flask app before spawning workers

# Additional logging options
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s' 
capture_output = True  # Capture stdout/stderr from app
enable_stdio_inheritance = True  # Inherit stdio from parent

# Graceful handling
graceful_timeout = 30  # Time to wait for graceful worker shutdown

# Set name of master process for clerity in system process lists and logs
proc_name = 'colonizer'