import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


class ImportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_reference_maps(self) -> dict:
        def mapping(query: str) -> dict:
            rows = self.db.execute(text(query)).mappings()
            return {row["code"]: dict(row) for row in rows}

        return {
            "products": mapping(
                "SELECT id, code, name, units_per_package, purchase_price, "
                "minimum_stock FROM products"
            ),
            "categories": mapping("SELECT id, code FROM product_categories"),
            "customers": mapping("SELECT id, code FROM customers"),
            "customer_types": mapping("SELECT id, code FROM customer_types"),
        }

    def get_existing_keys(self, import_type: str) -> set | dict:
        if import_type == "SALES":
            return set(
                self.db.execute(
                    text("""
                        SELECT external_reference AS value
                        FROM sales
                        WHERE external_reference IS NOT NULL
                        UNION
                        SELECT sale_number AS value
                        FROM sales
                    """)
                ).scalars()
            )
        if import_type == "PRODUCTS":
            rows = self.db.execute(
                text("""
                    SELECT
                        LOWER(TRIM(name)) AS name,
                        LOWER(TRIM(COALESCE(brand, ''))) AS brand,
                        COALESCE(volume_value, -1) AS volume_value,
                        LOWER(TRIM(COALESCE(volume_unit, ''))) AS volume_unit,
                        LOWER(TRIM(package_type)) AS package_type
                    FROM products
                """)
            )
            return {
                (
                    row.name,
                    row.brand,
                    float(row.volume_value),
                    row.volume_unit,
                    row.package_type,
                )
                for row in rows
            }
        if import_type == "CUSTOMERS":
            rows = list(
                self.db.execute(
                    text("""
                        SELECT
                            LOWER(TRIM(name)) AS name,
                            LOWER(TRIM(COALESCE(district, ''))) AS district,
                            LOWER(TRIM(COALESCE(city, 'Bamako'))) AS city,
                            NULLIF(
                                REGEXP_REPLACE(phone, '[^0-9]', '', 'g'),
                                ''
                            ) AS phone
                        FROM customers
                    """)
                )
            )
            return {
                "phones": {row.phone for row in rows if row.phone},
                "identities": {
                    (row.name, row.district, row.city) for row in rows
                },
            }
        if import_type == "STOCKS":
            rows = self.db.execute(
                text("""
                    SELECT ds.stock_date, p.code AS product_code
                    FROM daily_stocks ds
                    JOIN products p ON p.id = ds.product_id
                """)
            ).mappings()
            return {(row["stock_date"], row["product_code"]) for row in rows}
        raise ValueError(f"Type d'import non pris en charge : {import_type}")

    def file_was_imported(self, file_hash: str, import_type: str) -> bool:
        return bool(
            self.db.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM import_batches
                        WHERE file_hash = :file_hash
                          AND import_type = :import_type
                          AND status IN ('COMPLETED', 'PARTIALLY_COMPLETED')
                    )
                """),
                {"file_hash": file_hash, "import_type": import_type},
            ).scalar_one()
        )

    def create_batch(
        self,
        *,
        file_name: str,
        file_type: str,
        import_type: str,
        file_hash: str,
        total_rows: int,
        valid_rows: int,
        invalid_rows: int,
        duplicate_rows: int,
    ) -> tuple[str, str]:
        batch_number = (
            f"IMP-{datetime.now():%Y%m%d%H%M%S}-"
            f"{uuid4().hex[:6].upper()}"
        )
        batch_id = self.db.execute(
            text("""
                INSERT INTO import_batches (
                    batch_number, file_name, file_type, import_type,
                    file_hash, total_rows, valid_rows, invalid_rows,
                    duplicate_rows, status, started_at
                ) VALUES (
                    :batch_number, :file_name, :file_type, :import_type,
                    :file_hash, :total_rows, :valid_rows, :invalid_rows,
                    :duplicate_rows, 'IMPORTING', NOW()
                )
                RETURNING id
            """),
            {
                "batch_number": batch_number,
                "file_name": file_name,
                "file_type": file_type,
                "import_type": import_type,
                "file_hash": file_hash,
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "duplicate_rows": duplicate_rows,
            },
        ).scalar_one()
        return str(batch_id), batch_number

    def save_errors(self, batch_id: str, invalid_rows: list[dict]) -> None:
        query = text("""
            INSERT INTO import_batch_errors (
                import_batch_id, source_row_number, raw_data, error_messages
            ) VALUES (
                :batch_id, :row_number, CAST(:raw_data AS JSONB),
                CAST(:errors AS JSONB)
            )
        """)
        for row in invalid_rows:
            self.db.execute(
                query,
                {
                    "batch_id": batch_id,
                    "row_number": row["_row_number"],
                    "raw_data": json.dumps(
                        {
                            key: value
                            for key, value in row.items()
                            if not key.startswith("_")
                        },
                        default=str,
                    ),
                    "errors": json.dumps(row["_errors"], ensure_ascii=False),
                },
            )

    def import_rows(
        self,
        import_type: str,
        rows: list[dict],
        batch_id: str,
    ) -> int:
        handlers = {
            "SALES": self._import_sales,
            "STOCKS": self._import_stocks,
            "PRODUCTS": self._import_products,
            "CUSTOMERS": self._import_customers,
        }
        return handlers[import_type](rows, batch_id)

    def complete_batch(
        self,
        batch_id: str,
        imported_rows: int,
        invalid_rows: int,
    ) -> None:
        status = "COMPLETED" if invalid_rows == 0 else "PARTIALLY_COMPLETED"
        self.db.execute(
            text("""
                UPDATE import_batches
                SET status = :status,
                    valid_rows = :imported_rows,
                    completed_at = NOW()
                WHERE id = :batch_id
            """),
            {
                "batch_id": batch_id,
                "status": status,
                "imported_rows": imported_rows,
            },
        )

    def get_history(self) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    ib.id, ib.batch_number, ib.file_name, ib.file_type,
                    ib.import_type, ib.total_rows, ib.valid_rows,
                    ib.invalid_rows, ib.duplicate_rows, ib.status,
                    ib.started_at, ib.completed_at, ib.created_at,
                    COUNT(ibe.id) AS recorded_errors
                FROM import_batches ib
                LEFT JOIN import_batch_errors ibe
                    ON ibe.import_batch_id = ib.id
                GROUP BY ib.id
                ORDER BY ib.created_at DESC
                LIMIT 100
            """)
        )
        return [dict(row) for row in rows.mappings()]

    def get_batch_errors(self, batch_id: str) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT source_row_number, raw_data, error_messages
                FROM import_batch_errors
                WHERE import_batch_id = :batch_id
                ORDER BY source_row_number
            """),
            {"batch_id": batch_id},
        )
        return [dict(row) for row in rows.mappings()]

    def _import_products(self, rows: list[dict], batch_id: str) -> int:
        query = text("""
            INSERT INTO products (
                name, brand, category_id, volume_value, volume_unit,
                package_type, units_per_package, purchase_price,
                selling_price, minimum_stock, reorder_quantity
            ) VALUES (
                :name, :brand, :category_id, :volume_value,
                :volume_unit, :package_type, :units_per_package,
                :purchase_price, :selling_price, :minimum_stock,
                :reorder_quantity
            )
        """)
        for row in rows:
            self.db.execute(query, row)
        return len(rows)

    def _import_customers(self, rows: list[dict], batch_id: str) -> int:
        query = text("""
            INSERT INTO customers (
                name, customer_type_id, phone, zone, district, city
            ) VALUES (
                :name, :customer_type_id, :phone, :zone, :district,
                :city
            )
        """)
        for row in rows:
            self.db.execute(query, row)
        return len(rows)

    def _import_stocks(self, rows: list[dict], batch_id: str) -> int:
        query = text("""
            INSERT INTO daily_stocks (
                stock_date, product_id, opening_stock, quantity_received,
                quantity_sold, quantity_damaged, other_entries, other_outputs,
                closing_stock, minimum_stock, stockout_flag
            ) VALUES (
                :stock_date, :product_id, :opening_stock, :quantity_received,
                :quantity_sold, :quantity_damaged, :other_entries,
                :other_outputs, :closing_stock, :minimum_stock, :stockout_flag
            )
        """)
        for row in rows:
            self.db.execute(query, row)
        return len(rows)

    def _import_sales(self, rows: list[dict], batch_id: str) -> int:
        from app.repositories.inventory_repository import InventoryRepository

        inventory_repository = InventoryRepository(self.db)
        grouped = {}
        for row in rows:
            grouped.setdefault(row["sale_reference"], []).append(row)

        sale_query = text("""
            INSERT INTO sales (
                external_reference, sale_date, sale_time, customer_id,
                salesperson_name, payment_method, payment_status, subtotal,
                discount_amount, total_amount, promotion_applied, notes,
                import_batch_id
            ) VALUES (
                :external_reference, :sale_date, :sale_time, :customer_id,
                :salesperson_name, :payment_method, :payment_status,
                :subtotal, :discount_amount, :total_amount,
                :promotion_applied, :notes, :batch_id
            ) RETURNING id
        """)
        item_query = text("""
            INSERT INTO sale_items (
                sale_id, product_id, quantity_packages, units_per_package,
                quantity_units, unit_price, discount_amount, total_amount,
                unit_cost, gross_margin
            ) VALUES (
                :sale_id, :product_id, :quantity_packages,
                :units_per_package, :quantity_units, :unit_price,
                :discount_amount, :total_amount, :unit_cost, :gross_margin
            )
        """)
        movement_query = text("""
            INSERT INTO stock_movements (
                movement_number, movement_date, product_id, movement_type,
                quantity_packages, quantity_units, direction, unit_cost,
                reference_type, reference_id, reason
            ) VALUES (
                :movement_number, :movement_date, :product_id, 'SALE',
                :quantity_packages, :quantity_units, 'OUT', :unit_cost,
                'SALE', :sale_id, :reason
            )
        """)

        for sale_reference, items in grouped.items():
            first = items[0]
            subtotal = sum(item["line_subtotal"] for item in items)
            discount = sum(item["discount_amount"] for item in items)
            sale_id = self.db.execute(
                sale_query,
                {
                    **first,
                    "subtotal": subtotal,
                    "discount_amount": discount,
                    "total_amount": subtotal - discount,
                    "batch_id": batch_id,
                },
            ).scalar_one()
            for item in items:
                total = item["line_subtotal"] - item["discount_amount"]
                quantity_units = (
                    item["quantity_packages"] * item["units_per_package"]
                )
                self.db.execute(
                    item_query,
                    {
                        **item,
                        "sale_id": sale_id,
                        "quantity_units": quantity_units,
                        "total_amount": total,
                        "gross_margin": (
                            total
                            - item["quantity_packages"] * item["unit_cost"]
                        ),
                    },
                )
                movement_date = datetime.combine(
                    item["sale_date"],
                    item["sale_time"] or datetime.min.time(),
                )
                self.db.execute(
                    movement_query,
                    {
                        **item,
                        "sale_id": sale_id,
                        "quantity_units": quantity_units,
                        "movement_date": movement_date,
                        "movement_number": (
                            f"MVT-IMP-{uuid4().hex[:16].upper()}"
                        ),
                        "reason": f"Vente importée {sale_reference}",
                    },
                )
                inventory_repository.apply_daily_stock(
                    product={
                        "id": item["product_id"],
                        "name": item["product_name"],
                        "minimum_stock": item["minimum_stock"],
                    },
                    stock_date=item["sale_date"],
                    movement_type="SALE",
                    direction="OUT",
                    quantity=item["quantity_packages"],
                )
        return len(rows)
