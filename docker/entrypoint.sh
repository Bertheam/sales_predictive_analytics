#!/bin/sh
set -eu

if [ "${INITIALIZE_DATABASE:-false}" = "true" ]; then
    export PGPASSWORD="${DB_PASSWORD:?DB_PASSWORD est requis pour initialiser la base}"
    database_has_schema="$({
        psql \
            --host="${DB_HOST}" \
            --port="${DB_PORT}" \
            --username="${DB_USER}" \
            --dbname="${DB_NAME}" \
            --tuples-only \
            --no-align \
            --command="SELECT to_regclass('public.users') IS NOT NULL;"
    } | tr -d '[:space:]')"

    if [ "${database_has_schema}" != "t" ]; then
        echo "Initialisation explicite du schéma PostgreSQL..."
        for sql_file in \
            database_setup/database/02_schema.sql \
            database_setup/database/03_reference_data.sql \
            database_setup/database/04_indexes.sql
        do
            psql \
                --host="${DB_HOST}" \
                --port="${DB_PORT}" \
                --username="${DB_USER}" \
                --dbname="${DB_NAME}" \
                --set=ON_ERROR_STOP=1 \
                --file="${sql_file}"
        done
    else
        echo "Schéma PostgreSQL existant détecté, initialisation ignorée."
    fi
else
    echo "Initialisation SQL désactivée."
fi

echo "Application des migrations Alembic..."
python -m alembic upgrade head

exec "$@"
