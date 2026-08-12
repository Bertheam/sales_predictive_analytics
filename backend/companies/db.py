from contextlib import contextmanager

from django.conf import settings
from django.db import connection, transaction

from app.database.tenant import normalize_company_id


TENANT_RUNTIME_ROLE = "sales_predictive_tenant_runtime"


def activate_tenant_on_cursor(cursor, company_id) -> str:
    """Bind a verified tenant to the current PostgreSQL transaction."""
    normalized_id = normalize_company_id(company_id)
    if connection.vendor != "postgresql":
        return normalized_id
    if getattr(settings, "TENANT_USE_RUNTIME_ROLE", False):
        cursor.execute(f"SET LOCAL ROLE {TENANT_RUNTIME_ROLE}")
    cursor.execute(
        "SELECT set_config('app.current_company_id', %s, TRUE)",
        [normalized_id],
    )
    return normalized_id


@contextmanager
def tenant_atomic(company_id):
    """Open an atomic Django scope with one explicit PostgreSQL tenant."""
    normalized_id = normalize_company_id(company_id)
    with transaction.atomic():
        previous_company_id = ""
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('app.current_company_id', TRUE)"
                )
                previous_company_id = cursor.fetchone()[0] or ""
                activate_tenant_on_cursor(cursor, normalized_id)
        try:
            yield normalized_id
        except BaseException:
            # The atomic savepoint restores SET LOCAL values after rollback.
            raise
        else:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.current_company_id', %s, TRUE)",
                        [previous_company_id],
                    )
                    if getattr(settings, "TENANT_USE_RUNTIME_ROLE", False):
                        cursor.execute("RESET ROLE")


@contextmanager
def tenant_cursor(company_id):
    """Yield a cursor protected by the shared tenant/RLS context."""
    with tenant_atomic(company_id):
        with connection.cursor() as cursor:
            yield cursor
