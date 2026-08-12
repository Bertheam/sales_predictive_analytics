import os
from pathlib import Path
from urllib.parse import quote_plus

from alembic import command
from alembic.config import Config
from django.db import connection
from django.test.runner import DiscoverRunner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FILES = (
    PROJECT_ROOT / "database_setup/database/02_schema.sql",
    PROJECT_ROOT / "database_setup/database/03_reference_data.sql",
    PROJECT_ROOT / "database_setup/database/04_indexes.sql",
)


def _test_database_url() -> str:
    database = connection.settings_dict
    user = quote_plus(str(database.get("USER") or ""))
    password = quote_plus(str(database.get("PASSWORD") or ""))
    host = database.get("HOST") or "localhost"
    port = database.get("PORT") or "5432"
    name = quote_plus(str(database["NAME"]))
    credentials = user
    if password:
        credentials = f"{credentials}:{password}"
    return f"postgresql+psycopg://{credentials}@{host}:{port}/{name}"


class TenantPostgresTestRunner(DiscoverRunner):
    """Build unmanaged business tables only inside Django's test database."""

    def setup_databases(self, **kwargs):
        old_config = super().setup_databases(**kwargs)
        if connection.vendor != "postgresql":
            return old_config
        if not old_config:
            return old_config

        original_names = {
            str(old_name)
            for _, old_name, _ in old_config
            if old_name is not None
        }
        active_name = str(connection.settings_dict["NAME"])
        if active_name in original_names:
            raise RuntimeError(
                "Le schéma métier de test ne peut pas être préparé sur la base courante."
            )

        with connection.cursor() as cursor:
            for sql_file in SCHEMA_FILES:
                cursor.execute(sql_file.read_text(encoding="utf-8"))

        previous_url = os.environ.get("ALEMBIC_DATABASE_URL")
        os.environ["ALEMBIC_DATABASE_URL"] = _test_database_url()
        connection.close()
        try:
            alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
            command.upgrade(alembic_config, "head")
        finally:
            if previous_url is None:
                os.environ.pop("ALEMBIC_DATABASE_URL", None)
            else:
                os.environ["ALEMBIC_DATABASE_URL"] = previous_url
            connection.close()
        return old_config
