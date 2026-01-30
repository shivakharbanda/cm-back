#!/usr/bin/env bash
# Quick access to the automation_db PostgreSQL database.
# Usage:
#   ./tools/db.sh              # open interactive psql shell
#   ./tools/db.sh "SQL query"  # run a single query

CONTAINER="automation_postgres"
DB_USER="postgres"
DB_NAME="automation_db"

if [ -z "$1" ]; then
  podman exec -it "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"
else
  podman exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "$1"
fi
