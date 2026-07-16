-- ============================================================
-- 01_create_database.sql
-- Crée la base PostgreSQL du projet d'analyse prédictive.
-- À exécuter connecté à une base existante (ex: postgres).
-- ============================================================

SELECT 'CREATE DATABASE sales_predictions
        WITH OWNER = CURRENT_USER
             ENCODING = ''UTF8''
             TEMPLATE = template0'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'sales_predictions'
)\gexec

\connect sales_predictions

CREATE EXTENSION IF NOT EXISTS pgcrypto;
