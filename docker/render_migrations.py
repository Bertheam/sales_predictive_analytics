"""Apply database migrations once per schema revision on Render.

Free Render services restart after being idle. Running both migration engines on
every wake-up adds a significant delay even when the schema is already current.
This guard fingerprints the migration source files and records only successful
schema revisions in PostgreSQL. A failed migration is never marked as applied.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

import psycopg


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_LOCK_ID = 6_295_601_233_227_825_841
TRACKING_TABLE = "nexastock_schema_releases"


def migration_files() -> list[Path]:
    django_migrations = PROJECT_ROOT.glob("backend/*/migrations/*.py")
    alembic_migrations = (PROJECT_ROOT / "alembic" / "versions").glob("*.py")
    return sorted(
        (
            path
            for path in (*django_migrations, *alembic_migrations)
            if path.name != "__init__.py"
        ),
        key=lambda path: path.relative_to(PROJECT_ROOT).as_posix(),
    )


def schema_fingerprint() -> str:
    digest = hashlib.sha256()
    files = migration_files()
    if not files:
        raise RuntimeError("Aucun fichier de migration Django ou Alembic détecté.")

    # Les versions de Django et des extensions peuvent aussi embarquer leurs
    # propres migrations. Les manifests déclenchent donc une vérification lors
    # d'une mise à jour de dépendances, même si les migrations du projet n'ont
    # pas changé.
    schema_inputs = [
        *files,
        PROJECT_ROOT / "requirements.txt",
        PROJECT_ROOT / "alembic.ini",
    ]
    for path in schema_inputs:
        relative_path = path.relative_to(PROJECT_ROOT).as_posix().encode()
        digest.update(len(relative_path).to_bytes(4, "big"))
        digest.update(relative_path)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_migrations() -> None:
    commands = (
        ("python", "backend/manage.py", "migrate", "--noinput"),
        ("python", "-m", "alembic", "upgrade", "head"),
    )
    for command in commands:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL est requis pour le démarrage Render.")

    fingerprint = schema_fingerprint()
    force = os.environ.get("RENDER_FORCE_MIGRATIONS", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS public.{TRACKING_TABLE} (
                    fingerprint varchar(64) PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                f"SELECT 1 FROM public.{TRACKING_TABLE} WHERE fingerprint = %s",
                (fingerprint,),
            )
            already_applied = cursor.fetchone() is not None

            if already_applied and not force:
                print("Schéma déjà à jour : migrations ignorées.", flush=True)
                return

            print("Nouvelle révision de schéma : application des migrations...", flush=True)
            run_migrations()
            cursor.execute(
                f"""
                INSERT INTO public.{TRACKING_TABLE} (fingerprint)
                VALUES (%s)
                ON CONFLICT (fingerprint) DO NOTHING
                """,
                (fingerprint,),
            )
            print("Migrations appliquées et révision enregistrée.", flush=True)


if __name__ == "__main__":
    main()
