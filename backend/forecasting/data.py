from django.db import connection
from django.utils import timezone

from companies.db import tenant_cursor


def product_choices(company_id):
    if connection.vendor != "postgresql":
        return []
    with tenant_cursor(company_id) as cursor:
        cursor.execute(
            """
            SELECT id, name, code
            FROM products
            WHERE company_id = %s AND is_active = TRUE AND deleted_at IS NULL
            ORDER BY name
            """,
            [str(company_id)],
        )
        return [
            (str(product_id), f"{name} · {code}")
            for product_id, name, code in cursor.fetchall()
        ]


def get_product_freshness(company_id, product_id):
    """Return the latest usable sale date for one company-owned product."""
    if connection.vendor != "postgresql":
        return {"exists": False, "last_sale_date": None, "age_days": None}
    with tenant_cursor(company_id) as cursor:
        cursor.execute(
            """
            SELECT p.name, MAX(s.sale_date)
            FROM products p
            LEFT JOIN sale_items si
              ON si.company_id = p.company_id AND si.product_id = p.id
            LEFT JOIN sales s
              ON s.company_id = si.company_id
             AND s.id = si.sale_id
             AND s.deleted_at IS NULL
            WHERE p.company_id = %s
              AND p.id = %s
              AND p.is_active = TRUE
              AND p.deleted_at IS NULL
            GROUP BY p.id, p.name
            """,
            [str(company_id), str(product_id)],
        )
        row = cursor.fetchone()
    if not row:
        return {"exists": False, "last_sale_date": None, "age_days": None}
    product_name, last_sale_date = row
    age_days = max((timezone.localdate() - last_sale_date).days, 0) if last_sale_date else None
    return {
        "exists": True,
        "product_name": product_name,
        "last_sale_date": last_sale_date,
        "age_days": age_days,
    }


def get_products_freshness(company_id):
    """Return sale freshness for every active product in one company query."""
    if connection.vendor != "postgresql":
        return {}
    with tenant_cursor(company_id) as cursor:
        cursor.execute(
            """
            SELECT p.id, p.name, MAX(s.sale_date)
            FROM products p
            LEFT JOIN sale_items si
              ON si.company_id = p.company_id AND si.product_id = p.id
            LEFT JOIN sales s
              ON s.company_id = si.company_id
             AND s.id = si.sale_id
             AND s.deleted_at IS NULL
            WHERE p.company_id = %s
              AND p.is_active = TRUE
              AND p.deleted_at IS NULL
            GROUP BY p.id, p.name
            ORDER BY p.name
            """,
            [str(company_id)],
        )
        rows = cursor.fetchall()
    today = timezone.localdate()
    return {
        str(product_id): {
            "exists": True,
            "product_name": product_name,
            "last_sale_date": last_sale_date,
            "age_days": max((today - last_sale_date).days, 0) if last_sale_date else None,
        }
        for product_id, product_name, last_sale_date in rows
    }


def get_company_freshness(company_id):
    """Return a compact freshness indicator for the page header."""
    if connection.vendor != "postgresql":
        return {"last_sale_date": None, "age_days": None}
    with tenant_cursor(company_id) as cursor:
        cursor.execute(
            """
            SELECT MAX(sale_date)
            FROM sales
            WHERE company_id = %s AND deleted_at IS NULL
            """,
            [str(company_id)],
        )
        last_sale_date = cursor.fetchone()[0]
    age_days = max((timezone.localdate() - last_sale_date).days, 0) if last_sale_date else None
    return {"last_sale_date": last_sale_date, "age_days": age_days}
