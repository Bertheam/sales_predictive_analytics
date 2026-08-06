from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Count, DecimalField, Max, Min, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, ExtractIsoWeekDay

from .models import DailyStock, Product, Sale, SaleItem


ZERO = Decimal("0")
MONEY_FIELD = DecimalField(max_digits=24, decimal_places=2)
QUANTITY_FIELD = DecimalField(max_digits=24, decimal_places=2)
PAYMENT_METHOD_LABELS = {
    "CASH": "Espèces",
    "MOBILE_MONEY": "Mobile money",
    "BANK_TRANSFER": "Virement bancaire",
    "CREDIT": "Crédit",
}
PAYMENT_STATUS_LABELS = {
    "PAID": "Payée",
    "PENDING": "En attente",
    "PARTIAL": "Partiellement payée",
    "CANCELLED": "Annulée",
}
WEEKDAY_LABELS = {
    1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi",
    5: "Vendredi", 6: "Samedi", 7: "Dimanche",
}


@dataclass(frozen=True)
class DashboardSnapshot:
    """Backward-compatible payload used by the existing dashboard API."""
    ready: bool = False
    min_date: object | None = None
    max_date: object | None = None
    revenue: Decimal = ZERO
    sales_count: int = 0
    quantity_sold: Decimal = ZERO
    current_stock: Decimal = ZERO
    risk_products: int = 0
    active_products: int = 0


@contextmanager
def tenant_orm_scope(company_id):
    """Set the PostgreSQL RLS context while keeping all data reads in the ORM."""
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_company_id', %s, TRUE)",
                    [str(company_id)],
                )
        yield


def percentage_change(current, previous):
    current = Decimal(str(current or ZERO))
    previous = Decimal(str(previous or ZERO))
    if previous == 0:
        return ZERO if current == 0 else None
    return ((current - previous) / abs(previous) * Decimal("100")).quantize(Decimal("0.1"))


def _period_totals(company_id, start_date, end_date):
    sales = Sale.objects.filter(
        company_id=company_id,
        deleted_at__isnull=True,
        sale_date__range=(start_date, end_date),
    )
    sale_totals = sales.aggregate(
        revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
        transactions=Count("id"),
        last_sale_date=Max("sale_date"),
    )
    quantity = SaleItem.objects.filter(
        company_id=company_id,
        sale__deleted_at__isnull=True,
        sale__sale_date__range=(start_date, end_date),
    ).aggregate(
        quantity=Coalesce(Sum("quantity_packages"), Value(ZERO), output_field=QUANTITY_FIELD)
    )["quantity"]
    transactions = sale_totals["transactions"] or 0
    revenue = sale_totals["revenue"] or ZERO
    return {
        "revenue": revenue,
        "quantity": quantity or ZERO,
        "transactions": transactions,
        "average_basket": revenue / transactions if transactions else ZERO,
        "last_sale_date": sale_totals["last_sale_date"],
    }


def _stock_snapshot(company_id, as_of=None):
    stock_rows = DailyStock.objects.filter(
        company_id=company_id,
        product_id=OuterRef("pk"),
    )
    if as_of:
        stock_rows = stock_rows.filter(stock_date__lte=as_of)
    stock_rows = stock_rows.order_by("-stock_date", "-created_at")
    products = Product.objects.filter(
        company_id=company_id, is_active=True, deleted_at__isnull=True
    ).annotate(
        latest_stock=Subquery(stock_rows.values("closing_stock")[:1]),
        latest_minimum=Subquery(stock_rows.values("minimum_stock")[:1]),
        latest_stockout=Subquery(stock_rows.values("stockout_flag")[:1]),
    )
    total = ZERO
    risk = 0
    tracked = 0
    for product in products.only("id", "minimum_stock"):
        if product.latest_stock is None:
            continue
        tracked += 1
        total += product.latest_stock
        threshold = product.latest_minimum if product.latest_minimum is not None else product.minimum_stock
        if product.latest_stockout or product.latest_stock <= threshold:
            risk += 1
    return {"quantity": total, "risk_products": risk, "tracked_products": tracked}


def _latest_update(company_id):
    candidates = [
        Sale.objects.filter(company_id=company_id).aggregate(value=Max("updated_at"))["value"],
        Product.objects.filter(company_id=company_id).aggregate(value=Max("updated_at"))["value"],
        DailyStock.objects.filter(company_id=company_id).aggregate(value=Max("created_at"))["value"],
    ]
    return max((value for value in candidates if value is not None), default=None)


def get_overview_snapshot(company_id, today):
    start_date = today - timedelta(days=6)
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    with tenant_orm_scope(company_id):
        current = _period_totals(company_id, start_date, today)
        previous = _period_totals(company_id, previous_start, previous_end)
        current_stock = _stock_snapshot(company_id, today)
        previous_stock = _stock_snapshot(company_id, previous_end)
        active_products = Product.objects.filter(
            company_id=company_id, is_active=True, deleted_at__isnull=True
        ).count()
        has_stock = DailyStock.objects.filter(company_id=company_id).exists()
        has_sales = Sale.objects.filter(company_id=company_id, deleted_at__isnull=True).exists()
        last_update = _latest_update(company_id)

    steps = [
        {"label": "Dépôt configuré", "complete": True, "url_name": "companies:edit"},
        {
            "label": "Produits ou stocks ajoutés",
            "complete": active_products > 0 or has_stock,
            "url_name": "operations:products",
        },
        {
            "label": "Premières ventes enregistrées",
            "complete": has_sales,
            "url_name": "operations:sales",
        },
    ]
    completed = sum(step["complete"] for step in steps)
    return {
        "company_configured": True,
        "start_date": start_date,
        "end_date": today,
        "previous_start": previous_start,
        "previous_end": previous_end,
        "last_updated_at": last_update,
        "active_products": active_products,
        "revenue": current["revenue"],
        "sales_count": current["transactions"],
        "quantity_sold": current["quantity"],
        "current_stock": current_stock["quantity"],
        "risk_products": current_stock["risk_products"],
        "revenue_change": percentage_change(current["revenue"], previous["revenue"]),
        "sales_change": percentage_change(current["transactions"], previous["transactions"]),
        "quantity_change": percentage_change(current["quantity"], previous["quantity"]),
        "stock_change": percentage_change(current_stock["quantity"], previous_stock["quantity"]),
        "setup_steps": steps,
        "setup_completed": completed,
        "setup_percent": completed * 100 // len(steps),
    }


def get_dashboard_snapshot(company_id) -> DashboardSnapshot:
    """Keep the historical API contract while using tenant-filtered ORM queries."""
    with tenant_orm_scope(company_id):
        sales = Sale.objects.filter(company_id=company_id, deleted_at__isnull=True)
        bounds = sales.aggregate(min_date=Min("sale_date"), max_date=Max("sale_date"))
        totals = sales.aggregate(
            revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
            sales_count=Count("id"),
        )
        quantity = SaleItem.objects.filter(
            company_id=company_id, sale__deleted_at__isnull=True
        ).aggregate(
            value=Coalesce(Sum("quantity_packages"), Value(ZERO), output_field=QUANTITY_FIELD)
        )["value"]
        stock = _stock_snapshot(company_id)
        active_products = Product.objects.filter(
            company_id=company_id, is_active=True, deleted_at__isnull=True
        ).count()
    return DashboardSnapshot(
        ready=True,
        min_date=bounds["min_date"], max_date=bounds["max_date"],
        revenue=totals["revenue"] or ZERO,
        sales_count=totals["sales_count"] or 0,
        quantity_sold=quantity or ZERO,
        current_stock=stock["quantity"], risk_products=stock["risk_products"],
        active_products=active_products,
    )


def _ranked_rows(queryset, *, label_key, label_map=None, limit=None):
    rows = list(queryset[:limit] if limit else queryset)
    maximum = max((row["revenue"] or ZERO for row in rows), default=ZERO)
    for row in rows:
        raw_label = row.get(label_key)
        row["label"] = (label_map or {}).get(raw_label, raw_label) or "Non renseigné"
        row["revenue"] = row["revenue"] or ZERO
        row["share_percent"] = int(row["revenue"] / maximum * 100) if maximum else 0
    return rows


def _chart_series(company_id, start_date, end_date):
    revenue_rows = Sale.objects.filter(
        company_id=company_id, deleted_at__isnull=True,
        sale_date__range=(start_date, end_date),
    ).values("sale_date").annotate(
        revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD)
    )
    quantity_rows = SaleItem.objects.filter(
        company_id=company_id, sale__deleted_at__isnull=True,
        sale__sale_date__range=(start_date, end_date),
    ).values("sale__sale_date").annotate(
        quantity=Coalesce(Sum("quantity_packages"), Value(ZERO), output_field=QUANTITY_FIELD)
    )
    revenue_by_date = {row["sale_date"]: row["revenue"] for row in revenue_rows}
    quantity_by_date = {row["sale__sale_date"]: row["quantity"] for row in quantity_rows}
    day_count = (end_date - start_date).days + 1
    series = []
    for offset in range(day_count):
        day = start_date + timedelta(days=offset)
        series.append({
            "date": day,
            "revenue": revenue_by_date.get(day, ZERO),
            "quantity": quantity_by_date.get(day, ZERO),
        })
    max_revenue = max((row["revenue"] for row in series), default=ZERO)
    max_quantity = max((row["quantity"] for row in series), default=ZERO)
    divisor = max(day_count - 1, 1)
    for index, row in enumerate(series):
        row["x"] = round(index / divisor * 100, 2)
        row["revenue_y"] = round(90 - (float(row["revenue"] / max_revenue) * 75 if max_revenue else 0), 2)
        row["quantity_y"] = round(90 - (float(row["quantity"] / max_quantity) * 75 if max_quantity else 0), 2)
    return {
        "rows": series,
        "revenue_points": " ".join(f'{row["x"]},{row["revenue_y"]}' for row in series),
        "quantity_points": " ".join(f'{row["x"]},{row["quantity_y"]}' for row in series),
        "has_data": bool(max_revenue or max_quantity),
    }


def get_activity_dashboard(company_id, start_date, end_date):
    duration = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)
    with tenant_orm_scope(company_id):
        current = _period_totals(company_id, start_date, end_date)
        previous = _period_totals(company_id, previous_start, previous_end)
        sales = Sale.objects.filter(
            company_id=company_id, deleted_at__isnull=True,
            sale_date__range=(start_date, end_date),
        )
        items = SaleItem.objects.filter(
            company_id=company_id, sale__deleted_at__isnull=True,
            sale__sale_date__range=(start_date, end_date),
        )
        top_products = _ranked_rows(
            items.values("product_id", "product__name").annotate(
                revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
                quantity=Coalesce(Sum("quantity_packages"), Value(ZERO), output_field=QUANTITY_FIELD),
            ).order_by("-revenue", "product__name"),
            label_key="product__name", limit=5,
        )
        top_categories = _ranked_rows(
            items.values("product__category_id", "product__category__name").annotate(
                revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
                quantity=Coalesce(Sum("quantity_packages"), Value(ZERO), output_field=QUANTITY_FIELD),
            ).order_by("-revenue", "product__category__name"),
            label_key="product__category__name", limit=5,
        )
        top_customers = _ranked_rows(
            sales.values("customer_id", "customer__name").annotate(
                revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
                transactions=Count("id"),
            ).order_by("-revenue", "customer__name"),
            label_key="customer__name", limit=5,
        )
        payment_methods = _ranked_rows(
            sales.values("payment_method").annotate(
                revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
                transactions=Count("id"),
            ).order_by("-revenue"),
            label_key="payment_method", label_map=PAYMENT_METHOD_LABELS,
        )
        payment_statuses = _ranked_rows(
            sales.values("payment_status").annotate(
                revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
                transactions=Count("id"),
            ).order_by("-revenue"),
            label_key="payment_status", label_map=PAYMENT_STATUS_LABELS,
        )
        weekdays = _ranked_rows(
            sales.annotate(weekday=ExtractIsoWeekDay("sale_date")).values("weekday").annotate(
                revenue=Coalesce(Sum("total_amount"), Value(ZERO), output_field=MONEY_FIELD),
                transactions=Count("id"),
            ).order_by("-revenue"),
            label_key="weekday", label_map=WEEKDAY_LABELS,
        )
        chart = _chart_series(company_id, start_date, end_date)
        last_update = _latest_update(company_id)

    metrics = []
    for key, label in (
        ("revenue", "Chiffre d’affaires"),
        ("quantity", "Quantité vendue"),
        ("transactions", "Transactions"),
        ("average_basket", "Panier moyen"),
    ):
        metrics.append({
            "key": key,
            "label": label,
            "value": current[key],
            "change": percentage_change(current[key], previous[key]),
        })
    return {
        "start_date": start_date,
        "end_date": end_date,
        "previous_start": previous_start,
        "previous_end": previous_end,
        "metrics": metrics,
        "chart": chart,
        "top_products": top_products,
        "top_categories": top_categories,
        "top_customers": top_customers,
        "payment_methods": payment_methods,
        "payment_statuses": payment_statuses,
        "weekdays": weekdays,
        "last_updated_at": last_update,
        "has_sales": current["transactions"] > 0,
    }
