#!/bin/sh
set -eu

backup_path="${1:-SPA_DB}"
database_url="${NEON_DATABASE_URL:-${DATABASE_URL:-}}"

if [ ! -f "${backup_path}" ]; then
    echo "Backup introuvable : ${backup_path}" >&2
    exit 1
fi

if [ -z "${database_url}" ]; then
    echo "Définissez NEON_DATABASE_URL avec l'URL directe PostgreSQL Neon." >&2
    exit 1
fi

case "${database_url}" in
    *-pooler.*)
        echo "Utilisez l'URL directe Neon, sans '-pooler', pour pg_restore." >&2
        exit 1
        ;;
esac

if ! command -v psql >/dev/null 2>&1 || ! command -v pg_restore >/dev/null 2>&1; then
    echo "psql et pg_restore doivent être disponibles localement." >&2
    exit 1
fi

echo "Validation du backup PostgreSQL..."
pg_restore --list "${backup_path}" >/dev/null

public_table_count="$({
    psql "${database_url}" \
        --no-psqlrc \
        --tuples-only \
        --no-align \
        --set=ON_ERROR_STOP=1 \
        --command="SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public';"
} | tr -d '[:space:]')"

if [ "${public_table_count}" != "0" ]; then
    echo "Restauration refusée : la base cible contient déjà ${public_table_count} table(s) publiques." >&2
    echo "Utilisez une base Neon vide pour éviter tout écrasement de données." >&2
    exit 1
fi

echo "Restauration du schéma..."
pg_restore \
    --dbname="${database_url}" \
    --section=pre-data \
    --exit-on-error \
    --no-owner \
    --no-acl \
    "${backup_path}"

echo "Restauration des données..."
pg_restore \
    --dbname="${database_url}" \
    --section=data \
    --exit-on-error \
    --no-owner \
    --no-acl \
    "${backup_path}"

echo "Restauration des index, contraintes et politiques..."
pg_restore \
    --dbname="${database_url}" \
    --section=post-data \
    --exit-on-error \
    --no-owner \
    --no-acl \
    "${backup_path}"

echo "Contrôle du schéma restauré..."
psql "${database_url}" \
    --no-psqlrc \
    --set=ON_ERROR_STOP=1 \
    --command="
        SELECT
            to_regclass('public.alembic_version') AS alembic_version,
            to_regclass('public.django_migrations') AS django_migrations,
            to_regclass('public.companies') AS companies,
            to_regclass('public.sales') AS sales;
    "

echo "Restauration Neon terminée. La base peut maintenant être reliée à Render."
