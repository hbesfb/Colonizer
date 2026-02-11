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

# ---------------- Verify Redis is reachable ----------------
# In k3s, Redis runs as a sidecar (another container in same pod)
log "waiting for redis..."
for i in {1..10}; do
	# Capture both stdout and stderr
	output=$(redis-cli -h localhost ping 2>&1)

	if [ "$output" = "PONG" ]; then
		log "redis is ready and says: $output"
		break
	fi
	log "redis not ready (error: $output), retrying..."
	sleep 1
done

# ---------------- PostgreSQL preparations ----------------
log "Waiting for PostgreSQL at ${DB_HOST:-postgres-service}:${DB_PORT:-5432}..."
if ! timeout 30 bash -c "until pg_isready -h ${DB_HOST:-postgres-service} -p ${DB_PORT:-5432} >/dev/null 2>&1; do sleep 2; done"; then
	error "PostgreSQL not available"
fi

# create SETTLEPLATE table if it doesn't exist
log "Ensuring SETTLEPLATE table exists..."
PGPASSWORD=${DB_PASSWORD} psql -h ${DB_HOST} -U ${DB_USER} -d colonizer -f migrations/initial_tables.sql \
	|| error "Failed to create or verify SETTLEPLATE table"

# ---------------- Insert test data ----------------
# uncomment if you want test data inserted
# log "Adding some test data..."
# PGPASSWORD=${DB_PASSWORD} psql  -h ${DB_HOST} -U ${DB_USER} -d colonizer -f migrations/003_insert_test_data.sql \
# 	|| error "Failed to insert test data"

# ---------------- Start Gunicorn ----------------
log "Starting Gunicorn..."
cd "$APP_HOME"
exec gunicorn -c gunicorn_config.py webdaemon:app