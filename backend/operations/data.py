from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import connection
from django.utils import timezone

from companies.db import tenant_cursor


def dict_rows(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def list_categories(company_id):
    if connection.vendor != "postgresql":
        return []
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, code, name
            FROM product_categories
            WHERE company_id = %s AND is_active = TRUE
            ORDER BY name
        """, [str(company_id)])
        return dict_rows(cursor)


def product_catalog(company_id, *, query="", category_id="", status="active"):
    if connection.vendor != "postgresql":
        return [], {"total": 0, "active": 0, "low_stock": 0, "value": 0}
    params = [str(company_id)]
    filters = ["p.company_id = %s"]
    if query:
        filters.append("(p.name ILIKE %s OR p.code ILIKE %s OR COALESCE(p.brand, '') ILIKE %s)")
        search = f"%{query}%"
        params.extend([search, search, search])
    if category_id:
        filters.append("p.category_id = %s")
        params.append(category_id)
    if status == "active":
        filters.append("p.is_active = TRUE AND p.deleted_at IS NULL")
    elif status == "inactive":
        filters.append("p.is_active = FALSE AND p.deleted_at IS NULL")
    elif status == "archived":
        filters.append("p.deleted_at IS NOT NULL")
    where = " AND ".join(filters)
    with tenant_cursor(company_id) as cursor:
        cursor.execute(f"""
            SELECT
                p.id, p.code, p.name, p.brand, p.package_type,
                p.units_per_package, p.purchase_price, p.selling_price,
                p.minimum_stock, p.reorder_quantity, p.is_active, p.deleted_at,
                pc.name AS category_name,
                stock.closing_stock, stock.stock_date,
                CASE
                    WHEN stock.closing_stock IS NULL THEN 'UNTRACKED'
                    WHEN stock.closing_stock <= 0 THEN 'OUT'
                    WHEN stock.closing_stock <= p.minimum_stock THEN 'LOW'
                    ELSE 'OK'
                END AS stock_status
            FROM products p
            JOIN product_categories pc
              ON pc.id = p.category_id AND pc.company_id = p.company_id
            LEFT JOIN LATERAL (
                SELECT ds.closing_stock, ds.stock_date
                FROM daily_stocks ds
                WHERE ds.company_id = p.company_id AND ds.product_id = p.id
                ORDER BY ds.stock_date DESC
                LIMIT 1
            ) stock ON TRUE
            WHERE {where}
            ORDER BY p.is_active DESC, p.name
        """, params)
        products = dict_rows(cursor)
        cursor.execute("""
            WITH latest AS (
                SELECT DISTINCT ON (ds.product_id)
                    ds.product_id, ds.closing_stock
                FROM daily_stocks ds
                WHERE ds.company_id = %s
                ORDER BY ds.product_id, ds.stock_date DESC
            )
            SELECT
                COUNT(p.id) AS total,
                COUNT(p.id) FILTER (WHERE p.is_active) AS active,
                COUNT(p.id) FILTER (
                    WHERE p.is_active AND COALESCE(l.closing_stock, 0) <= p.minimum_stock
                ) AS low_stock,
                COALESCE(SUM(COALESCE(l.closing_stock, 0) * p.purchase_price), 0) AS value
            FROM products p
            LEFT JOIN latest l ON l.product_id = p.id
            WHERE p.company_id = %s
        """, [str(company_id), str(company_id)])
        values = cursor.fetchone()
    return products, {
        "total": values[0], "active": values[1],
        "low_stock": values[2], "value": values[3],
    }


def get_product(company_id, product_id):
    if connection.vendor != "postgresql":
        return None
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, name, brand, category_id, volume_value, volume_unit,
                   package_type, units_per_package, purchase_price, selling_price,
                   minimum_stock, reorder_quantity, is_active
            FROM products
            WHERE company_id = %s AND id = %s AND deleted_at IS NULL
        """, [str(company_id), str(product_id)])
        row = cursor.fetchone()
        if not row:
            return None
        return dict(zip([column[0] for column in cursor.description], row))


def save_product(company_id, cleaned_data, product_id=None, user_id=None):
    values = {
        **cleaned_data,
        "company_id": str(company_id),
        "category_id": str(cleaned_data["category_id"]),
        "user_id": user_id,
    }
    with tenant_cursor(company_id) as cursor:
        cursor.execute(
            "SELECT 1 FROM product_categories WHERE company_id = %s AND id = %s AND is_active = TRUE",
            [str(company_id), values["category_id"]],
        )
        if not cursor.fetchone():
            raise ValueError("La catégorie choisie n’appartient pas à ce dépôt.")
        if product_id:
            cursor.execute("""
                UPDATE products SET
                    name=%(name)s, brand=%(brand)s, category_id=%(category_id)s,
                    volume_value=%(volume_value)s, volume_unit=%(volume_unit)s,
                    package_type=%(package_type)s, units_per_package=%(units_per_package)s,
                    purchase_price=%(purchase_price)s, selling_price=%(selling_price)s,
                    minimum_stock=%(minimum_stock)s,
                    reorder_quantity=%(reorder_quantity)s, is_active=%(is_active)s,
                    updated_at=NOW(), updated_by_user_id=%(user_id)s
                WHERE company_id=%(company_id)s AND id=%(product_id)s
                RETURNING id, code
            """, {**values, "product_id": str(product_id)})
        else:
            cursor.execute("""
                INSERT INTO products (
                    company_id, name, brand, category_id, volume_value, volume_unit,
                    package_type, units_per_package, purchase_price, selling_price,
                    minimum_stock, reorder_quantity, is_active, created_by_user_id,
                    updated_by_user_id
                ) VALUES (
                    %(company_id)s, %(name)s, %(brand)s, %(category_id)s,
                    %(volume_value)s, %(volume_unit)s, %(package_type)s,
                    %(units_per_package)s, %(purchase_price)s, %(selling_price)s,
                    %(minimum_stock)s, %(reorder_quantity)s, %(is_active)s,
                    %(user_id)s, %(user_id)s
                ) RETURNING id, code
            """, values)
        result = cursor.fetchone()
        if not result:
            raise ValueError("Produit introuvable dans ce dépôt.")
        return {"id": result[0], "code": result[1]}


def set_product_archived(company_id, product_id, *, archived, user_id):
    with tenant_cursor(company_id) as cursor:
        if archived:
            cursor.execute("""
                UPDATE products
                SET is_active = FALSE, deleted_at = NOW(),
                    deleted_by_user_id = %s, updated_by_user_id = %s,
                    updated_at = NOW()
                WHERE company_id = %s AND id = %s AND deleted_at IS NULL
                RETURNING id, code, name
            """, [user_id, user_id, str(company_id), str(product_id)])
        else:
            cursor.execute("""
                UPDATE products
                SET is_active = TRUE, deleted_at = NULL,
                    deleted_by_user_id = NULL, updated_by_user_id = %s,
                    updated_at = NOW()
                WHERE company_id = %s AND id = %s AND deleted_at IS NOT NULL
                RETURNING id, code, name
            """, [user_id, str(company_id), str(product_id)])
        row = cursor.fetchone()
        return None if not row else {"id": row[0], "code": row[1], "name": row[2]}


def list_customer_types(company_id):
    if connection.vendor != "postgresql":
        return []
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, code, name FROM customer_types
            WHERE company_id=%s AND is_active=TRUE ORDER BY name
        """, [str(company_id)])
        return dict_rows(cursor)


def customer_catalog(company_id, *, query="", customer_type_id="", status="active"):
    if connection.vendor != "postgresql":
        return [], {"total": 0, "active": 0, "archived": 0, "with_phone": 0}
    params = [str(company_id)]
    filters = ["c.company_id=%s"]
    if query:
        search = f"%{query}%"
        filters.append("(c.name ILIKE %s OR c.code ILIKE %s OR COALESCE(c.phone, '') ILIKE %s OR COALESCE(c.zone, '') ILIKE %s)")
        params.extend([search, search, search, search])
    if customer_type_id:
        filters.append("c.customer_type_id=%s")
        params.append(customer_type_id)
    if status == "active":
        filters.append("c.is_active=TRUE AND c.deleted_at IS NULL")
    elif status == "inactive":
        filters.append("c.is_active=FALSE AND c.deleted_at IS NULL")
    elif status == "archived":
        filters.append("c.deleted_at IS NOT NULL")
    with tenant_cursor(company_id) as cursor:
        cursor.execute(f"""
            SELECT c.id, c.code, c.name, c.customer_type_id, ct.name AS type_name,
                   c.phone, c.zone, c.district, c.city, c.is_active, c.deleted_at,
                   COUNT(s.id) FILTER (WHERE s.deleted_at IS NULL) AS sale_count,
                   COALESCE(SUM(s.total_amount) FILTER (WHERE s.deleted_at IS NULL), 0) AS revenue
            FROM customers c
            JOIN customer_types ct
              ON ct.company_id=c.company_id AND ct.id=c.customer_type_id
            LEFT JOIN sales s ON s.company_id=c.company_id AND s.customer_id=c.id
            WHERE {' AND '.join(filters)}
            GROUP BY c.id, ct.name
            ORDER BY c.deleted_at NULLS FIRST, c.is_active DESC, c.name
        """, params)
        customers = dict_rows(cursor)
        cursor.execute("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE is_active=TRUE AND deleted_at IS NULL),
                   COUNT(*) FILTER (WHERE deleted_at IS NOT NULL),
                   COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(phone, '')), '') IS NOT NULL AND deleted_at IS NULL)
            FROM customers WHERE company_id=%s
        """, [str(company_id)])
        values = cursor.fetchone()
    return customers, {
        "total": values[0], "active": values[1],
        "archived": values[2], "with_phone": values[3],
    }


def get_customer(company_id, customer_id):
    if connection.vendor != "postgresql":
        return None
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, code, name, customer_type_id, phone, zone, district,
                   city, is_active
            FROM customers
            WHERE company_id=%s AND id=%s AND deleted_at IS NULL
        """, [str(company_id), str(customer_id)])
        row = cursor.fetchone()
        return None if not row else dict(zip([column[0] for column in cursor.description], row))


def save_customer(company_id, values, customer_id=None, *, user_id=None):
    payload = {**values, "company_id": str(company_id), "user_id": user_id}
    payload["customer_type_id"] = str(payload["customer_type_id"])
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT 1 FROM customer_types
            WHERE company_id=%s AND id=%s AND is_active=TRUE
        """, [str(company_id), payload["customer_type_id"]])
        if not cursor.fetchone():
            raise ValueError("Le type de client choisi n’appartient pas à ce dépôt.")
        if customer_id:
            cursor.execute("""
                UPDATE customers SET name=%(name)s,
                    customer_type_id=%(customer_type_id)s, phone=%(phone)s,
                    zone=%(zone)s, district=%(district)s, city=%(city)s,
                    is_active=%(is_active)s, updated_at=NOW(),
                    updated_by_user_id=%(user_id)s
                WHERE company_id=%(company_id)s AND id=%(customer_id)s
                  AND deleted_at IS NULL
                RETURNING id, code, name
            """, {**payload, "customer_id": str(customer_id)})
        else:
            cursor.execute("""
                INSERT INTO customers (
                    company_id, name, customer_type_id, phone, zone, district,
                    city, is_active, created_by_user_id, updated_by_user_id
                ) VALUES (
                    %(company_id)s, %(name)s, %(customer_type_id)s, %(phone)s,
                    %(zone)s, %(district)s, %(city)s, %(is_active)s,
                    %(user_id)s, %(user_id)s
                ) RETURNING id, code, name
            """, payload)
        row = cursor.fetchone()
        if not row:
            raise ValueError("Client introuvable dans ce dépôt.")
        return {"id": row[0], "code": row[1], "name": row[2]}


def set_customer_archived(company_id, customer_id, *, archived, user_id):
    with tenant_cursor(company_id) as cursor:
        if archived:
            cursor.execute("""
                UPDATE customers SET is_active=FALSE, deleted_at=NOW(),
                    deleted_by_user_id=%s, updated_by_user_id=%s, updated_at=NOW()
                WHERE company_id=%s AND id=%s AND deleted_at IS NULL
                RETURNING id, code, name
            """, [user_id, user_id, str(company_id), str(customer_id)])
        else:
            cursor.execute("""
                UPDATE customers SET is_active=TRUE, deleted_at=NULL,
                    deleted_by_user_id=NULL, updated_by_user_id=%s, updated_at=NOW()
                WHERE company_id=%s AND id=%s AND deleted_at IS NOT NULL
                RETURNING id, code, name
            """, [user_id, str(company_id), str(customer_id)])
        row = cursor.fetchone()
        return None if not row else {"id": row[0], "code": row[1], "name": row[2]}


def supplier_catalog(company_id, *, query="", status="active"):
    if connection.vendor != "postgresql":
        return [], {"total": 0, "active": 0, "archived": 0, "receipt_count": 0}
    params = [str(company_id)]
    filters = ["s.company_id=%s"]
    if query:
        search = f"%{query}%"
        filters.append("(s.name ILIKE %s OR s.code ILIKE %s OR COALESCE(s.phone, '') ILIKE %s OR COALESCE(s.city, '') ILIKE %s)")
        params.extend([search, search, search, search])
    if status == "active":
        filters.append("s.is_active=TRUE AND s.deleted_at IS NULL")
    elif status == "inactive":
        filters.append("s.is_active=FALSE AND s.deleted_at IS NULL")
    elif status == "archived":
        filters.append("s.deleted_at IS NOT NULL")
    with tenant_cursor(company_id) as cursor:
        cursor.execute(f"""
            SELECT s.id, s.code, s.name, s.phone, s.city, s.is_active, s.deleted_at,
                   COUNT(pr.id) FILTER (WHERE pr.deleted_at IS NULL) AS receipt_count,
                   COALESCE(SUM(pr.total_amount) FILTER (WHERE pr.deleted_at IS NULL), 0) AS purchased_amount
            FROM suppliers s
            LEFT JOIN purchase_receipts pr
              ON pr.company_id=s.company_id AND pr.supplier_id=s.id
            WHERE {' AND '.join(filters)}
            GROUP BY s.id
            ORDER BY s.deleted_at NULLS FIRST, s.is_active DESC, s.name
        """, params)
        suppliers = dict_rows(cursor)
        cursor.execute("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE is_active=TRUE AND deleted_at IS NULL),
                   COUNT(*) FILTER (WHERE deleted_at IS NOT NULL)
            FROM suppliers WHERE company_id=%s
        """, [str(company_id)])
        values = cursor.fetchone()
        cursor.execute("""
            SELECT COUNT(*) FROM purchase_receipts
            WHERE company_id=%s AND deleted_at IS NULL
        """, [str(company_id)])
        receipt_count = cursor.fetchone()[0]
    return suppliers, {
        "total": values[0], "active": values[1],
        "archived": values[2], "receipt_count": receipt_count,
    }


def get_supplier(company_id, supplier_id):
    if connection.vendor != "postgresql":
        return None
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, code, name, phone, city, is_active
            FROM suppliers
            WHERE company_id=%s AND id=%s AND deleted_at IS NULL
        """, [str(company_id), str(supplier_id)])
        row = cursor.fetchone()
        return None if not row else dict(zip([column[0] for column in cursor.description], row))


def save_supplier(company_id, values, supplier_id=None, *, user_id=None):
    payload = {**values, "company_id": str(company_id), "user_id": user_id}
    with tenant_cursor(company_id) as cursor:
        if supplier_id:
            cursor.execute("""
                UPDATE suppliers SET name=%(name)s, phone=%(phone)s,
                    city=%(city)s, is_active=%(is_active)s, updated_at=NOW(),
                    updated_by_user_id=%(user_id)s
                WHERE company_id=%(company_id)s AND id=%(supplier_id)s
                  AND deleted_at IS NULL
                RETURNING id, code, name
            """, {**payload, "supplier_id": str(supplier_id)})
        else:
            cursor.execute("""
                INSERT INTO suppliers (
                    company_id, name, phone, city, is_active,
                    created_by_user_id, updated_by_user_id
                ) VALUES (
                    %(company_id)s, %(name)s, %(phone)s, %(city)s, %(is_active)s,
                    %(user_id)s, %(user_id)s
                ) RETURNING id, code, name
            """, payload)
        row = cursor.fetchone()
        if not row:
            raise ValueError("Fournisseur introuvable dans ce dépôt.")
        return {"id": row[0], "code": row[1], "name": row[2]}


def set_supplier_archived(company_id, supplier_id, *, archived, user_id):
    with tenant_cursor(company_id) as cursor:
        if archived:
            cursor.execute("""
                UPDATE suppliers SET is_active=FALSE, deleted_at=NOW(),
                    deleted_by_user_id=%s, updated_by_user_id=%s, updated_at=NOW()
                WHERE company_id=%s AND id=%s AND deleted_at IS NULL
                RETURNING id, code, name
            """, [user_id, user_id, str(company_id), str(supplier_id)])
        else:
            cursor.execute("""
                UPDATE suppliers SET is_active=TRUE, deleted_at=NULL,
                    deleted_by_user_id=NULL, updated_by_user_id=%s, updated_at=NOW()
                WHERE company_id=%s AND id=%s AND deleted_at IS NOT NULL
                RETURNING id, code, name
            """, [user_id, str(company_id), str(supplier_id)])
        row = cursor.fetchone()
        return None if not row else {"id": row[0], "code": row[1], "name": row[2]}


def stock_overview(company_id, *, query="", stock_status="all"):
    products, summary = product_catalog(company_id, query=query, status="active")
    if stock_status != "all":
        products = [item for item in products if item["stock_status"] == stock_status]
    summary["quantity"] = sum((item["closing_stock"] or 0) for item in products)
    return products, summary


def inventory_history(company_id, *, limit=50):
    if connection.vendor != "postgresql":
        return [], []
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT pr.id, pr.receipt_number, pr.receipt_date, pr.supplier_id,
                   s.name AS supplier_name, pr.total_amount, pr.status,
                   COUNT(pri.id) AS item_count,
                   COALESCE(SUM(pri.quantity_packages), 0) AS quantity
            FROM purchase_receipts pr
            JOIN suppliers s ON s.company_id=pr.company_id AND s.id=pr.supplier_id
            LEFT JOIN purchase_receipt_items pri
              ON pri.company_id=pr.company_id AND pri.purchase_receipt_id=pr.id
            WHERE pr.company_id=%s AND pr.deleted_at IS NULL
            GROUP BY pr.id, s.name
            ORDER BY pr.receipt_date DESC, pr.created_at DESC
            LIMIT %s
        """, [str(company_id), limit])
        receipts = dict_rows(cursor)
        cursor.execute("""
            SELECT sm.id, sm.movement_number, sm.movement_date, p.code,
                   p.name AS product_name, sm.movement_type,
                   CASE sm.movement_type
                     WHEN 'PURCHASE' THEN 'Réception fournisseur'
                     WHEN 'SALE' THEN 'Vente'
                     WHEN 'SALE_RETURN' THEN 'Retour client'
                     WHEN 'PURCHASE_RETURN' THEN 'Retour fournisseur'
                     WHEN 'DAMAGE' THEN 'Casse / dommage'
                     WHEN 'LOSS' THEN 'Perte'
                     WHEN 'ADJUSTMENT_IN' THEN 'Ajustement positif'
                     WHEN 'ADJUSTMENT_OUT' THEN 'Ajustement négatif'
                     WHEN 'INITIAL_STOCK' THEN 'Stock initial'
                     ELSE sm.movement_type
                   END AS movement_label,
                   sm.direction,
                   sm.quantity_packages, sm.reason
            FROM stock_movements sm
            JOIN products p ON p.company_id=sm.company_id AND p.id=sm.product_id
            WHERE sm.company_id=%s
            ORDER BY sm.movement_date DESC, sm.created_at DESC
            LIMIT %s
        """, [str(company_id), limit])
        movements = dict_rows(cursor)
    return receipts, movements


def sales_overview(company_id, *, start_date=None, end_date=None, query=""):
    if connection.vendor != "postgresql":
        return [], {"revenue": 0, "count": 0, "quantity": 0, "average": 0}, None, None
    with tenant_cursor(company_id) as cursor:
        cursor.execute(
            "SELECT MIN(sale_date), MAX(sale_date) FROM sales WHERE company_id = %s AND deleted_at IS NULL",
            [str(company_id)],
        )
        min_date, max_date = cursor.fetchone()
        if not max_date:
            return [], {"revenue": 0, "count": 0, "quantity": 0, "average": 0}, None, None
        end_date = end_date or max_date
        start_date = start_date or max(min_date, end_date - timedelta(days=29))
        params = [str(company_id), start_date, end_date]
        filters = ["s.company_id = %s", "s.deleted_at IS NULL", "s.sale_date BETWEEN %s AND %s"]
        if query:
            filters.append("(s.sale_number ILIKE %s OR COALESCE(c.name, '') ILIKE %s)")
            search = f"%{query}%"
            params.extend([search, search])
        where = " AND ".join(filters)
        cursor.execute(f"""
            SELECT
                s.id, s.sale_number, s.sale_date, s.sale_time,
                COALESCE(c.name, 'Client comptoir') AS customer_name,
                s.payment_method, s.payment_status, s.total_amount,
                COUNT(si.id) AS item_count,
                COALESCE(SUM(si.quantity_packages), 0) AS quantity
            FROM sales s
            LEFT JOIN customers c
              ON c.id = s.customer_id AND c.company_id = s.company_id
            LEFT JOIN sale_items si
              ON si.sale_id = s.id AND si.company_id = s.company_id
            WHERE {where}
            GROUP BY s.id, c.name
            ORDER BY s.sale_date DESC, s.sale_time DESC NULLS LAST
        """, params)
        sales = dict_rows(cursor)
        cursor.execute("""
            SELECT COALESCE(SUM(s.total_amount), 0), COUNT(s.id),
                   COALESCE(SUM(items.quantity), 0), COALESCE(AVG(s.total_amount), 0)
            FROM sales s
            LEFT JOIN LATERAL (
                SELECT SUM(si.quantity_packages) AS quantity
                FROM sale_items si
                WHERE si.company_id = s.company_id AND si.sale_id = s.id
            ) items ON TRUE
            WHERE s.company_id = %s AND s.deleted_at IS NULL AND s.sale_date BETWEEN %s AND %s
        """, [str(company_id), start_date, end_date])
        values = cursor.fetchone()
    return sales, {
        "revenue": values[0], "count": values[1],
        "quantity": values[2], "average": values[3],
    }, start_date, end_date


def sale_detail(company_id, sale_id):
    if connection.vendor != "postgresql":
        return None, []
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT s.id, s.sale_number, s.sale_date, s.sale_time, s.customer_id,
                   COALESCE(c.name, 'Client comptoir') AS customer_name,
                   s.salesperson_name, s.payment_method, s.payment_status,
                   s.subtotal, s.discount_amount, s.total_amount, s.notes
            FROM sales s
            LEFT JOIN customers c
              ON c.id = s.customer_id AND c.company_id = s.company_id
            WHERE s.company_id = %s AND s.id = %s AND s.deleted_at IS NULL
        """, [str(company_id), str(sale_id)])
        row = cursor.fetchone()
        if not row:
            return None, []
        sale = dict(zip([column[0] for column in cursor.description], row))
        cursor.execute("""
            SELECT p.code, p.name, si.quantity_packages, si.units_per_package,
                   si.unit_price, si.discount_amount, si.total_amount, si.gross_margin
            FROM sale_items si
            JOIN products p ON p.id = si.product_id AND p.company_id = si.company_id
            WHERE si.company_id = %s AND si.sale_id = %s
            ORDER BY p.name
        """, [str(company_id), str(sale_id)])
        items = dict_rows(cursor)
    return sale, items


def update_sale_metadata(company_id, sale_id, user_id, values):
    with tenant_cursor(company_id) as cursor:
        customer_id = values.get("customer_id") or None
        if customer_id:
            cursor.execute("SELECT 1 FROM customers WHERE company_id=%s AND id=%s AND deleted_at IS NULL", [str(company_id), customer_id])
            if not cursor.fetchone():
                raise ValueError("Le client choisi n’appartient pas à ce dépôt.")
        cursor.execute("""
            UPDATE sales SET customer_id=%s, payment_method=%s, payment_status=%s,
                notes=%s, updated_by_user_id=%s, updated_at=NOW()
            WHERE company_id=%s AND id=%s AND deleted_at IS NULL
            RETURNING id, sale_number
        """, [customer_id, values["payment_method"], values["payment_status"],
              values.get("notes") or None, user_id, str(company_id), str(sale_id)])
        row = cursor.fetchone()
        return None if not row else {"id": row[0], "number": row[1]}


def cancel_sale(company_id, sale_id, user_id):
    cancellation_date = timezone.localdate()
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, sale_number FROM sales
            WHERE company_id=%s AND id=%s AND deleted_at IS NULL FOR UPDATE
        """, [str(company_id), str(sale_id)])
        sale = cursor.fetchone()
        if not sale:
            return None
        cursor.execute("""
            SELECT p.id, p.code, p.name, p.units_per_package, p.purchase_price,
                   p.selling_price, p.minimum_stock, si.quantity_packages
            FROM sale_items si
            JOIN products p ON p.company_id=si.company_id AND p.id=si.product_id
            WHERE si.company_id=%s AND si.sale_id=%s
            ORDER BY p.id FOR UPDATE OF p
        """, [str(company_id), str(sale_id)])
        lines = dict_rows(cursor)
        for line in lines:
            quantity = Decimal(line.pop("quantity_packages"))
            _apply_stock(cursor, company_id, line, cancellation_date, "SALE_RETURN", "IN", quantity)
            cursor.execute("""
                INSERT INTO stock_movements (
                    company_id, movement_date, product_id, movement_type, quantity_packages,
                    quantity_units, direction, unit_cost, reference_type, reference_id, reason,
                    created_by_user_id, updated_by_user_id
                ) VALUES (%s,%s,%s,'SALE_RETURN',%s,%s,'IN',%s,'SALE_CANCELLATION',%s,%s,%s,%s)
            """, [str(company_id), _operation_timestamp(cancellation_date), line["id"], quantity,
                  quantity * line["units_per_package"], line["purchase_price"], sale[0],
                  f"Annulation vente {sale[1]}", user_id, user_id])
        cursor.execute("""
            UPDATE sales SET deleted_at=NOW(), deleted_by_user_id=%s,
                updated_by_user_id=%s, updated_at=NOW(), payment_status='CANCELLED'
            WHERE company_id=%s AND id=%s
        """, [user_id, user_id, str(company_id), str(sale_id)])
    return {"id": sale[0], "number": sale[1], "returned_lines": len(lines)}


def operational_references(company_id):
    if connection.vendor != "postgresql":
        return {"products": [], "customers": [], "suppliers": []}
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT p.id, p.code, p.name, p.units_per_package, p.purchase_price,
                   p.selling_price, p.minimum_stock,
                   COALESCE(stock.closing_stock, 0) AS current_stock
            FROM products p
            LEFT JOIN LATERAL (
                SELECT closing_stock FROM daily_stocks
                WHERE company_id=p.company_id AND product_id=p.id
                ORDER BY stock_date DESC LIMIT 1
            ) stock ON TRUE
            WHERE p.company_id=%s AND p.is_active=TRUE AND p.deleted_at IS NULL
            ORDER BY p.name
        """, [str(company_id)])
        products = dict_rows(cursor)
        cursor.execute("""
            SELECT id, code, name FROM customers
            WHERE company_id=%s AND is_active=TRUE AND deleted_at IS NULL ORDER BY name
        """, [str(company_id)])
        customers = dict_rows(cursor)
        cursor.execute("""
            SELECT id, code, name FROM suppliers
            WHERE company_id=%s AND is_active=TRUE AND deleted_at IS NULL ORDER BY name
        """, [str(company_id)])
        suppliers = dict_rows(cursor)
    return {"products": products, "customers": customers, "suppliers": suppliers}


def _operation_timestamp(operation_date):
    if operation_date == timezone.localdate():
        return timezone.now()
    return timezone.make_aware(datetime.combine(operation_date, time(12)))


def _get_product(cursor, company_id, product_id):
    cursor.execute("""
        SELECT id, code, name, units_per_package, purchase_price,
               selling_price, minimum_stock
        FROM products
        WHERE company_id=%s AND id=%s AND is_active=TRUE AND deleted_at IS NULL
        FOR UPDATE
    """, [str(company_id), str(product_id)])
    row = cursor.fetchone()
    if not row:
        raise ValueError("Un produit est inconnu, archivé ou inactif.")
    return dict(zip([column[0] for column in cursor.description], row))


def _apply_stock(cursor, company_id, product, operation_date, movement_type, direction, quantity):
    cursor.execute("""
        SELECT id, stock_date, closing_stock
        FROM daily_stocks
        WHERE company_id=%s AND product_id=%s
        ORDER BY stock_date DESC LIMIT 1 FOR UPDATE
    """, [str(company_id), str(product["id"])])
    latest = cursor.fetchone()
    if latest and operation_date < latest[1]:
        raise ValueError(
            f"Une opération plus récente existe déjà au {latest[1]:%d/%m/%Y} pour {product['name']}."
        )
    current = Decimal(latest[2]) if latest else Decimal("0")
    quantity = Decimal(quantity)
    if direction == "OUT" and quantity > current:
        raise ValueError(f"Stock insuffisant pour {product['name']} : {current} colis disponibles.")
    received = quantity if movement_type == "PURCHASE" else Decimal("0")
    sold = quantity if movement_type == "SALE" else Decimal("0")
    damaged = quantity if movement_type == "DAMAGE" else Decimal("0")
    other_in = quantity if direction == "IN" and not received else Decimal("0")
    other_out = quantity if direction == "OUT" and not sold and not damaged else Decimal("0")
    closing = current + quantity * (1 if direction == "IN" else -1)
    if latest and operation_date == latest[1]:
        cursor.execute("""
            UPDATE daily_stocks SET
                quantity_received=quantity_received+%s, quantity_sold=quantity_sold+%s,
                quantity_damaged=quantity_damaged+%s, other_entries=other_entries+%s,
                other_outputs=other_outputs+%s, closing_stock=%s, stockout_flag=%s
            WHERE company_id=%s AND id=%s
        """, [received, sold, damaged, other_in, other_out, closing, closing <= 0, str(company_id), latest[0]])
    else:
        cursor.execute("""
            INSERT INTO daily_stocks (
                company_id, stock_date, product_id, opening_stock, quantity_received,
                quantity_sold, quantity_damaged, other_entries, other_outputs,
                closing_stock, minimum_stock, stockout_flag
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, [str(company_id), operation_date, str(product["id"]), current, received, sold,
              damaged, other_in, other_out, closing, product["minimum_stock"], closing <= 0])
    return current, closing


def _clean_lines(lines, value_fields):
    cleaned, seen = [], set()
    for line in lines:
        product_id = line.get("product_id")
        if not product_id:
            continue
        if product_id in seen:
            raise ValueError("Un produit ne peut apparaître qu’une fois dans la même opération.")
        seen.add(product_id)
        if any(line.get(field) is None for field in value_fields):
            raise ValueError("Une ligne produit est incomplète.")
        cleaned.append(line)
    if not cleaned:
        raise ValueError("Ajoutez au moins une ligne produit complète.")
    return sorted(cleaned, key=lambda item: item["product_id"])


def create_sale(company_id, user_id, header, lines, salesperson_name):
    lines = _clean_lines(lines, ("quantity_packages", "unit_price"))
    with tenant_cursor(company_id) as cursor:
        customer_id = header.get("customer_id") or None
        if customer_id:
            cursor.execute("SELECT 1 FROM customers WHERE company_id=%s AND id=%s AND deleted_at IS NULL", [str(company_id), customer_id])
            if not cursor.fetchone():
                raise ValueError("Le client choisi n’appartient pas à ce dépôt.")
        prepared, subtotal, discount, total = [], Decimal("0"), Decimal("0"), Decimal("0")
        for line in lines:
            product = _get_product(cursor, company_id, line["product_id"])
            quantity, price = Decimal(line["quantity_packages"]), Decimal(line["unit_price"])
            line_discount = Decimal(line.get("discount_amount") or 0)
            gross = quantity * price
            if line_discount > gross:
                raise ValueError(f"La remise dépasse le montant de la ligne {product['name']}.")
            _apply_stock(cursor, company_id, product, header["sale_date"], "SALE", "OUT", quantity)
            prepared.append((product, quantity, price, line_discount, gross - line_discount))
            subtotal += gross
            discount += line_discount
            total += gross - line_discount
        cursor.execute("""
            INSERT INTO sales (
                company_id, sale_date, sale_time, customer_id, salesperson_name,
                payment_method, payment_status, subtotal, discount_amount,
                total_amount, notes, created_by_user_id, updated_by_user_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id, sale_number
        """, [str(company_id), header["sale_date"],
              timezone.localtime(_operation_timestamp(header["sale_date"])).time().replace(tzinfo=None),
              customer_id, salesperson_name, header["payment_method"], header["payment_status"],
              subtotal, discount, total, header.get("notes") or None, user_id, user_id])
        sale_id, number = cursor.fetchone()
        for product, quantity, price, line_discount, line_total in prepared:
            units = quantity * product["units_per_package"]
            margin = line_total - quantity * product["purchase_price"]
            cursor.execute("""
                INSERT INTO sale_items (
                    company_id, sale_id, product_id, quantity_packages, units_per_package,
                    quantity_units, unit_price, discount_amount, total_amount, unit_cost, gross_margin
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, [str(company_id), sale_id, product["id"], quantity, product["units_per_package"],
                  units, price, line_discount, line_total, product["purchase_price"], margin])
            cursor.execute("""
                INSERT INTO stock_movements (
                    company_id, movement_date, product_id, movement_type, quantity_packages,
                    quantity_units, direction, unit_cost, reference_type, reference_id, reason,
                    created_by_user_id, updated_by_user_id
                ) VALUES (%s,%s,%s,'SALE',%s,%s,'OUT',%s,'SALE',%s,%s,%s,%s)
            """, [str(company_id), _operation_timestamp(header["sale_date"]), product["id"], quantity,
                  units, product["purchase_price"], sale_id, f"Vente {number}", user_id, user_id])
    return {"id": sale_id, "number": number, "total": total}


def create_receipt(company_id, user_id, header, lines):
    lines = _clean_lines(lines, ("quantity_packages", "unit_cost"))
    with tenant_cursor(company_id) as cursor:
        cursor.execute("SELECT 1 FROM suppliers WHERE company_id=%s AND id=%s AND deleted_at IS NULL", [str(company_id), header["supplier_id"]])
        if not cursor.fetchone():
            raise ValueError("Le fournisseur choisi n’appartient pas à ce dépôt.")
        cursor.execute("""
            INSERT INTO purchase_receipts (
                company_id, supplier_id, receipt_date, total_amount, status,
                created_by_user_id, updated_by_user_id
            ) VALUES (%s,%s,%s,0,'VALIDATED',%s,%s) RETURNING id, receipt_number
        """, [str(company_id), header["supplier_id"], header["receipt_date"], user_id, user_id])
        receipt_id, number = cursor.fetchone()
        total = Decimal("0")
        for line in lines:
            product = _get_product(cursor, company_id, line["product_id"])
            quantity, cost = Decimal(line["quantity_packages"]), Decimal(line["unit_cost"])
            _apply_stock(cursor, company_id, product, header["receipt_date"], "PURCHASE", "IN", quantity)
            units, line_total = quantity * product["units_per_package"], quantity * cost
            cursor.execute("""
                INSERT INTO purchase_receipt_items (
                    company_id, purchase_receipt_id, product_id, quantity_packages,
                    units_per_package, quantity_units, unit_cost, total_cost
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, [str(company_id), receipt_id, product["id"], quantity, product["units_per_package"], units, cost, line_total])
            cursor.execute("""
                INSERT INTO stock_movements (
                    company_id, movement_date, product_id, movement_type, quantity_packages,
                    quantity_units, direction, unit_cost, reference_type, reference_id, reason,
                    created_by_user_id, updated_by_user_id
                ) VALUES (%s,%s,%s,'PURCHASE',%s,%s,'IN',%s,'PURCHASE_RECEIPT',%s,%s,%s,%s)
            """, [str(company_id), _operation_timestamp(header["receipt_date"]), product["id"], quantity,
                  units, cost, receipt_id, f"Réception {number}", user_id, user_id])
            total += line_total
        cursor.execute("UPDATE purchase_receipts SET total_amount=%s, updated_at=NOW(), updated_by_user_id=%s WHERE company_id=%s AND id=%s", [total, user_id, str(company_id), receipt_id])
    return {"id": receipt_id, "number": number, "total": total}


def receipt_detail(company_id, receipt_id):
    if connection.vendor != "postgresql":
        return None
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, receipt_number, receipt_date, supplier_id, total_amount, status
            FROM purchase_receipts
            WHERE company_id=%s AND id=%s AND deleted_at IS NULL
        """, [str(company_id), str(receipt_id)])
        row = cursor.fetchone()
        return None if not row else dict(zip([column[0] for column in cursor.description], row))


def update_receipt_metadata(company_id, receipt_id, user_id, values):
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT 1 FROM suppliers
            WHERE company_id=%s AND id=%s AND is_active=TRUE AND deleted_at IS NULL
        """, [str(company_id), values["supplier_id"]])
        if not cursor.fetchone():
            raise ValueError("Le fournisseur choisi n’appartient pas à ce dépôt.")
        cursor.execute("""
            UPDATE purchase_receipts
            SET supplier_id=%s, updated_by_user_id=%s, updated_at=NOW()
            WHERE company_id=%s AND id=%s AND deleted_at IS NULL
            RETURNING id, receipt_number
        """, [values["supplier_id"], user_id, str(company_id), str(receipt_id)])
        row = cursor.fetchone()
        return None if not row else {"id": row[0], "number": row[1]}


def cancel_receipt(company_id, receipt_id, user_id):
    cancellation_date = timezone.localdate()
    with tenant_cursor(company_id) as cursor:
        cursor.execute("""
            SELECT id, receipt_number FROM purchase_receipts
            WHERE company_id=%s AND id=%s AND deleted_at IS NULL FOR UPDATE
        """, [str(company_id), str(receipt_id)])
        receipt = cursor.fetchone()
        if not receipt:
            return None
        cursor.execute("""
            SELECT p.id, p.code, p.name, p.units_per_package, p.purchase_price,
                   p.selling_price, p.minimum_stock, pri.quantity_packages, pri.unit_cost
            FROM purchase_receipt_items pri
            JOIN products p ON p.company_id=pri.company_id AND p.id=pri.product_id
            WHERE pri.company_id=%s AND pri.purchase_receipt_id=%s
            ORDER BY p.id FOR UPDATE OF p
        """, [str(company_id), str(receipt_id)])
        lines = dict_rows(cursor)
        for line in lines:
            quantity = Decimal(line.pop("quantity_packages"))
            unit_cost = line.pop("unit_cost")
            _apply_stock(
                cursor, company_id, line, cancellation_date,
                "PURCHASE_RETURN", "OUT", quantity,
            )
            cursor.execute("""
                INSERT INTO stock_movements (
                    company_id, movement_date, product_id, movement_type,
                    quantity_packages, quantity_units, direction, unit_cost,
                    reference_type, reference_id, reason,
                    created_by_user_id, updated_by_user_id
                ) VALUES (%s,%s,%s,'PURCHASE_RETURN',%s,%s,'OUT',%s,
                          'RECEIPT_CANCELLATION',%s,%s,%s,%s)
            """, [str(company_id), _operation_timestamp(cancellation_date), line["id"], quantity,
                  quantity * line["units_per_package"], unit_cost, receipt[0],
                  f"Annulation réception {receipt[1]}", user_id, user_id])
        cursor.execute("""
            UPDATE purchase_receipts
            SET deleted_at=NOW(), deleted_by_user_id=%s, updated_by_user_id=%s,
                updated_at=NOW(), status='CANCELLED'
            WHERE company_id=%s AND id=%s
        """, [user_id, user_id, str(company_id), str(receipt_id)])
    return {"id": receipt[0], "number": receipt[1], "returned_lines": len(lines)}


def create_manual_movement(company_id, user_id, values):
    directions = {"ADJUSTMENT_IN": "IN", "ADJUSTMENT_OUT": "OUT", "DAMAGE": "OUT", "LOSS": "OUT", "SALE_RETURN": "IN", "PURCHASE_RETURN": "OUT"}
    movement_type = values["movement_type"]
    if movement_type not in directions:
        raise ValueError("Type de mouvement non autorisé.")
    with tenant_cursor(company_id) as cursor:
        product = _get_product(cursor, company_id, values["product_id"])
        quantity, direction = Decimal(values["quantity_packages"]), directions[movement_type]
        previous, current = _apply_stock(cursor, company_id, product, values["movement_date"], movement_type, direction, quantity)
        cursor.execute("""
            INSERT INTO stock_movements (
                company_id, movement_date, product_id, movement_type, quantity_packages,
                quantity_units, direction, unit_cost, reference_type, reason,
                created_by_user_id, updated_by_user_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'MANUAL',%s,%s,%s)
            RETURNING id, movement_number
        """, [str(company_id), _operation_timestamp(values["movement_date"]), product["id"], movement_type,
              quantity, quantity * product["units_per_package"], direction, product["purchase_price"],
              values["reason"], user_id, user_id])
        movement_id, number = cursor.fetchone()
    return {"id": movement_id, "number": number, "product": product["name"], "previous": previous, "current": current}
