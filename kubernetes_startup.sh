#!/bin/bash
# script to start app in k8s, will be called in Dockerfile
#
set -euo pipefail # exit if any error occurs

# ---------------- Logging helpers ----------------
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}" >&2; exit 1; }

# ----------------- Confirm we are in k8s env -------------------
if [ "$SETTLEPLATE_CONFIG" != "kubernetes" ];
then
	error "non k8s configuration $SETTLEPLATE_CONFIG detected. This script works only for k8s. exiting..."
fi

# ---------------- Verify Valkey (the Redis-protocol backend in K8s) is reachable ----------------
# In Kubernetes, we ALWAYS use Valkey
HOST="${VALKEY_HOST:-valkey}"
PORT="${VALKEY_PORT:-6379}"
log "waiting for valkey..."

valkey_ready=false
for i in $(seq 1 10); do
	# Capture both stdout and stderr
	if (echo > /dev/tcp/"$HOST"/"$PORT") >/dev/null 2>&1; then
		log "valkey port is open"
		valkey_ready=true
		break
	fi
	log "valkey not ready retrying ($i/10)..."
	sleep 1
done

# Fail hard if valkey is not ready
if [ "$valkey_ready" != true ]; then
	error "valkey never became reachable after ($i/10) retries"
fi
# ---------------- PostgreSQL preparations ----------------
# wait for PostgreSQL to become reachable before Gunicorn starts.
log "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

postgres_ready=false
for i in $(seq 1 10); do
	if (echo > /dev/tcp/"$DB_HOST"/"$DB_PORT") >/dev/null 2>&1; then
		postgres_ready=true
		break
	fi
	log "PostgreSQL not ready yet after ($i/10) retries..."
	sleep 2
done

if [ "$postgres_ready" != true ]; then
	error "PostgreSQL still not available after waiting"
fi

# ---------------- Run migrations: Create SETTLEPLATE table if it doesn't exist (Python psycopg2 migration) ----------------
log "Ensuring SETTLEPLATE table exists..."

python3 - <<'EOF'
import psycopg2
import sys
import time
import os

MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds; delay grows linearly: 2s, 4s, 6s ...

conn = None
last_err = None

for attempt in range(1, MAX_RETRIES + 1):
	try:
		conn = psycopg2.connect(
			host=os.environ["DB_HOST"],
			port=os.environ["DB_PORT"],
			user=os.environ["DB_USER"],
			password=os.environ["DB_PASSWORD"],
			dbname=os.environ["DB_NAME"],
			connect_timeout=5, # fail fast if Postgres doesn't respond in 5s
		)
		break
	except Exception as e:
		last_err = e
		print(f"Postgres connect attempt {attempt}/{MAX_RETRIES} failed: {e}")
		if attempt < MAX_RETRIES:
			time.sleep(RETRY_DELAY * attempt) # backoff before next attempt

if conn is None:
	print(f"Migration failed: could not connect to Postgres after {MAX_RETRIES} attempts: {last_err}")
	sys.exit(1)

try:
	cur = conn.cursor()
	with open("migrations/initial_tables_k8s.sql") as f:
		cur.execute(f.read())
	conn.commit()
	cur.close()
except Exception as e:
	print("Migration failed:", e)
	conn.rollback()
	sys.exit(1)
finally:
	conn.close()
EOF

log "SETTLEPLATE table verified or created successfully"

# ---------------- Insert test data ----------------
# uncomment if you want test data inserted
# log "Adding some test data..."
# PGPASSWORD=${DB_PASSWORD} psql  -h ${DB_HOST} -U ${DB_USER} -d "${DB_NAME}" -f migrations/003_insert_test_data.sql \
# 	|| error "Failed to insert test data"

# ---------------- Start Gunicorn ----------------
log "Starting Gunicorn..."
cd "$APP_HOME"
exec gunicorn -c gunicorn_config.py webdaemon:app