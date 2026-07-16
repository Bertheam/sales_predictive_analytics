from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_suppliers(self) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT id, code, name
                FROM suppliers
                WHERE is_active = TRUE
                ORDER BY name
            """)
        )
        return [dict(row) for row in rows.mappings()]

    def get_products(self) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    p.id, p.code, p.name, p.units_per_package,
                    p.purchase_price, p.minimum_stock,
                    COALESCE(stock.closing_stock, 0) AS current_stock,
                    stock.stock_date AS last_stock_date
                FROM products p
                LEFT JOIN LATERAL (
                    SELECT ds.closing_stock, ds.stock_date
                    FROM daily_stocks ds
                    WHERE ds.product_id = p.id
                    ORDER BY ds.stock_date DESC
                    LIMIT 1
                ) stock ON TRUE
                WHERE p.is_active = TRUE
                ORDER BY p.name
            """)
        )
        return [dict(row) for row in rows.mappings()]

    def get_product(self, product_id: str) -> dict | None:
        row = self.db.execute(
            text("""
                SELECT id, code, name, units_per_package,
                       purchase_price, minimum_stock
                FROM products
                WHERE id = :product_id AND is_active = TRUE
            """),
            {"product_id": product_id},
        ).mappings().one_or_none()
        return dict(row) if row else None

    def create_receipt_header(
        self,
        supplier_id: str,
        receipt_date,
    ) -> dict:
        row = self.db.execute(
            text("""
                INSERT INTO purchase_receipts (
                    supplier_id, receipt_date, total_amount, status
                ) VALUES (
                    :supplier_id, :receipt_date, 0, 'VALIDATED'
                )
                RETURNING id, receipt_number
            """),
            {"supplier_id": supplier_id, "receipt_date": receipt_date},
        ).mappings().one()
        return dict(row)

    def add_receipt_item(
        self,
        *,
        receipt_id,
        product: dict,
        quantity: float,
        unit_cost: float,
    ) -> None:
        self.db.execute(
            text("""
                INSERT INTO purchase_receipt_items (
                    purchase_receipt_id, product_id, quantity_packages,
                    units_per_package, quantity_units, unit_cost, total_cost
                ) VALUES (
                    :receipt_id, :product_id, :quantity,
                    :units_per_package, :quantity_units, :unit_cost,
                    :total_cost
                )
            """),
            {
                "receipt_id": receipt_id,
                "product_id": product["id"],
                "quantity": quantity,
                "units_per_package": product["units_per_package"],
                "quantity_units": quantity * product["units_per_package"],
                "unit_cost": unit_cost,
                "total_cost": quantity * unit_cost,
            },
        )

    def update_receipt_total(self, receipt_id, total_amount: float) -> None:
        self.db.execute(
            text("""
                UPDATE purchase_receipts
                SET total_amount = :total_amount, updated_at = NOW()
                WHERE id = :receipt_id
            """),
            {"receipt_id": receipt_id, "total_amount": total_amount},
        )

    def add_movement(
        self,
        *,
        movement_date: datetime,
        product: dict,
        movement_type: str,
        quantity: float,
        direction: str,
        unit_cost: float,
        reference_type: str,
        reference_id=None,
        reason: str,
    ) -> str:
        return self.db.execute(
            text("""
                INSERT INTO stock_movements (
                    movement_date, product_id, movement_type,
                    quantity_packages, quantity_units, direction, unit_cost,
                    reference_type, reference_id, reason
                ) VALUES (
                    :movement_date, :product_id, :movement_type,
                    :quantity, :quantity_units, :direction, :unit_cost,
                    :reference_type, :reference_id, :reason
                )
                RETURNING movement_number
            """),
            {
                "movement_date": movement_date,
                "product_id": product["id"],
                "movement_type": movement_type,
                "quantity": quantity,
                "quantity_units": quantity * product["units_per_package"],
                "direction": direction,
                "unit_cost": unit_cost,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "reason": reason,
            },
        ).scalar_one()

    def apply_daily_stock(
        self,
        *,
        product: dict,
        stock_date,
        movement_type: str,
        direction: str,
        quantity: float,
    ) -> dict:
        latest = self.db.execute(
            text("""
                SELECT id, stock_date, closing_stock
                FROM daily_stocks
                WHERE product_id = :product_id
                ORDER BY stock_date DESC
                LIMIT 1
                FOR UPDATE
            """),
            {"product_id": product["id"]},
        ).mappings().one_or_none()

        if latest and stock_date < latest["stock_date"]:
            raise ValueError(
                f"Une opération existe déjà au {latest['stock_date']:%d/%m/%Y} "
                f"pour {product['name']}."
            )

        current_stock = float(latest["closing_stock"]) if latest else 0.0
        if direction == "OUT" and quantity > current_stock:
            raise ValueError(
                f"Stock insuffisant pour {product['name']} : "
                f"{current_stock:.2f} colis disponibles."
            )

        received = quantity if movement_type == "PURCHASE" else 0.0
        sold = quantity if movement_type == "SALE" else 0.0
        damaged = quantity if movement_type == "DAMAGE" else 0.0
        other_entries = quantity if direction == "IN" and not received else 0.0
        other_outputs = (
            quantity
            if direction == "OUT" and not damaged and not sold
            else 0.0
        )
        closing_stock = current_stock + quantity * (1 if direction == "IN" else -1)

        if latest and stock_date == latest["stock_date"]:
            self.db.execute(
                text("""
                    UPDATE daily_stocks
                    SET quantity_received = quantity_received + :received,
                        quantity_sold = quantity_sold + :sold,
                        quantity_damaged = quantity_damaged + :damaged,
                        other_entries = other_entries + :other_entries,
                        other_outputs = other_outputs + :other_outputs,
                        closing_stock = :closing_stock,
                        stockout_flag = :stockout_flag
                    WHERE id = :stock_id
                """),
                {
                    "received": received,
                    "sold": sold,
                    "damaged": damaged,
                    "other_entries": other_entries,
                    "other_outputs": other_outputs,
                    "closing_stock": closing_stock,
                    "stockout_flag": closing_stock <= 0,
                    "stock_id": latest["id"],
                },
            )
        else:
            self.db.execute(
                text("""
                    INSERT INTO daily_stocks (
                        stock_date, product_id, opening_stock,
                        quantity_received, quantity_sold, quantity_damaged,
                        other_entries, other_outputs, closing_stock,
                        minimum_stock, stockout_flag
                    ) VALUES (
                        :stock_date, :product_id, :opening_stock,
                        :received, :sold, :damaged, :other_entries,
                        :other_outputs, :closing_stock,
                        :minimum_stock, :stockout_flag
                    )
                """),
                {
                    "stock_date": stock_date,
                    "product_id": product["id"],
                    "opening_stock": current_stock,
                    "received": received,
                    "sold": sold,
                    "damaged": damaged,
                    "other_entries": other_entries,
                    "other_outputs": other_outputs,
                    "closing_stock": closing_stock,
                    "minimum_stock": product["minimum_stock"],
                    "stockout_flag": closing_stock <= 0,
                },
            )
        return {
            "previous_stock": current_stock,
            "current_stock": closing_stock,
        }

    def get_receipt_history(self, limit: int = 100) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    pr.id, pr.receipt_number, pr.receipt_date,
                    s.name AS supplier_name, pr.total_amount, pr.status,
                    COUNT(pri.id) AS item_count,
                    COALESCE(SUM(pri.quantity_packages), 0) AS total_quantity
                FROM purchase_receipts pr
                JOIN suppliers s ON s.id = pr.supplier_id
                LEFT JOIN purchase_receipt_items pri
                    ON pri.purchase_receipt_id = pr.id
                GROUP BY pr.id, s.name
                ORDER BY pr.receipt_date DESC, pr.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [dict(row) for row in rows.mappings()]

    def get_movement_history(self, limit: int = 300) -> list[dict]:
        rows = self.db.execute(
            text("""
                SELECT
                    sm.movement_number, sm.movement_date, sm.movement_type,
                    sm.direction, sm.quantity_packages, sm.unit_cost,
                    sm.reference_type, sm.reason,
                    p.code AS product_code, p.name AS product_name
                FROM stock_movements sm
                JOIN products p ON p.id = sm.product_id
                ORDER BY sm.movement_date DESC, sm.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [dict(row) for row in rows.mappings()]
