#!/bin/bash
# Provisions the pipeline's application database and a least-privilege role,
# separate from the Airflow metadata database. Runs once, on first container
# start (empty data volume), via the postgres docker-entrypoint-initdb.d hook.
set -euo pipefail

# Application database, owned by the bootstrap (airflow) superuser.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE DATABASE ${CHECKIT_DB};
  CREATE ROLE ${CHECKIT_APP_USER} WITH LOGIN PASSWORD '${CHECKIT_APP_PASSWORD}';
EOSQL

# Least privilege: the app role owns only the dedicated ``checkit`` schema in
# the ``checkit`` database. It has no rights on the Airflow metadata database.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${CHECKIT_DB}" <<-EOSQL
  REVOKE ALL ON SCHEMA public FROM PUBLIC;
  CREATE SCHEMA IF NOT EXISTS checkit AUTHORIZATION ${CHECKIT_APP_USER};
  GRANT CONNECT ON DATABASE ${CHECKIT_DB} TO ${CHECKIT_APP_USER};
  ALTER ROLE ${CHECKIT_APP_USER} IN DATABASE ${CHECKIT_DB} SET search_path = checkit;
EOSQL
