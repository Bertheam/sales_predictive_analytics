from dataclasses import dataclass
from decimal import Decimal

from django.db import connection, transaction


@dataclass(frozen=True)
class DashboardSnapshot:
    ready: bool = False
    min_date: object | None = None
    max_date: object | None = None
    revenue: Decimal = Decimal("0")
    sales_count: int = 0
    quantity_sold: Decimal = Decimal("0")
    current_stock: Decimal = Decimal("0")
    risk_products: int = 0
    active_products: int = 0


def get_dashboard_snapshot(company_id) -> DashboardSnapshot:
    if connection.vendor != "postgresql":
        return DashboardSnapshot()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_company_id', %s, TRUE)",
            [str(company_id)],
        )
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'sales'
                  AND column_name = 'company_id'
            )
        """)
        if not cursor.fetchone()[0]:
            return DashboardSnapshot()

        cursor.execute("""
            SELECT
                MIN(s.sale_date),
                MAX(s.sale_date),
                COALESCE(SUM(s.total_amount), 0),
                COUNT(s.id),
                COALESCE((
                    SELECT SUM(si.quantity_packages)
                    FROM sale_items si
                    WHERE si.company_id = %s
                ), 0)
            FROM sales s
            WHERE s.company_id = %s
        """, [str(company_id), str(company_id)])
        min_date, max_date, revenue, sales_count, quantity_sold = cursor.fetchone()

        cursor.execute("""
            WITH latest AS (
                SELECT DISTINCT ON (ds.product_id)
                    ds.product_id, ds.closing_stock, ds.minimum_stock,
                    ds.stockout_flag
                FROM daily_stocks ds
                WHERE ds.company_id = %s
                ORDER BY ds.product_id, ds.stock_date DESC
            )
            SELECT
                COALESCE(SUM(closing_stock), 0),
                COUNT(*) FILTER (
                    WHERE stockout_flag = TRUE OR closing_stock <= minimum_stock
                )
            FROM latest
        """, [str(company_id)])
        current_stock, risk_products = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*) FROM products WHERE company_id = %s AND is_active = TRUE",
            [str(company_id)],
        )
        active_products = cursor.fetchone()[0]

    return DashboardSnapshot(
        ready=True,
        min_date=min_date,
        max_date=max_date,
        revenue=revenue,
        sales_count=sales_count,
        quantity_sold=quantity_sold,
        current_stock=current_stock,
        risk_products=risk_products,
        active_products=active_products,
    )
