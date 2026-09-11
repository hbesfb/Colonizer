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
# In k3s, Valkey runs as (separate deployment?/operator?)
# In Kubernetes, we ALWAYS use Valkey
HOST="${VALKEY_HOST:-valkey}"
PORT="${VALKEY_PORT:-6379}"
log "waiting for valkey..."

valkey_ready=false
for i in {1..10}; do
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
	error "valkey never became reachable after 10 attempts"
fi
# ---------------- PostgreSQL preparations ----------------
# wait for PostgreSQL to become reachable before Gunicorn starts.
log "Waiting for PostgreSQL at ${DB_HOST:-postgres-service}:${DB_PORT:-5432}..."
if ! timeout 30 bash -c "until pg_isready -h ${DB_HOST:-postgres-service} -p ${DB_PORT:-5432} >/dev/null 2>&1; do sleep 2; done"; then
	error "PostgreSQL not available"
fi

# create SETTLEPLATE table if it doesn't exist
log "Ensuring SETTLEPLATE table exists..."

if PGPASSWORD="${DB_PASSWORD}" \
	psql -h "${DB_HOST}" -U "${DB_USER}" -d "${DB_NAME}" \
		-f migrations/initial_tables_k8s.sql; then
	log "SETTLEPLATE table verified or created successfully"
else
	error "Failed to create or verify SETTLEPLATE table"
fi

# ---------------- Insert test data ----------------
# uncomment if you want test data inserted
# log "Adding some test data..."
# PGPASSWORD=${DB_PASSWORD} psql  -h ${DB_HOST} -U ${DB_USER} -d "${DB_NAME}" -f migrations/003_insert_test_data.sql \
# 	|| error "Failed to insert test data"

# ---------------- Start Gunicorn ----------------
log "Starting Gunicorn..."
cd "$APP_HOME"
exec gunicorn -c gunicorn_config.py webdaemon:app