from sqlalchemy import text
from sqlalchemy.orm import Session


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db
        self.company_id = str(db.info["company_id"])

    def get_all_active_products(self) -> list[dict]:
        query = text("""
            SELECT id, code, name
            FROM products
            WHERE company_id = :company_id
              AND is_active = TRUE
              AND deleted_at IS NULL
            ORDER BY name
        """)

        return [
            {
                "id": str(row.id),
                "code": row.code,
                "name": row.name,
            }
            for row in self.db.execute(query, {"company_id": self.company_id})
        ]

    def get_by_id(self, product_id: str) -> dict:
        query = text("""
            SELECT id, code, name, selling_price
            FROM products
            WHERE id = :product_id
              AND company_id = :company_id
              AND is_active = TRUE
              AND deleted_at IS NULL
        """)
        row = self.db.execute(query, {
            "product_id": product_id,
            "company_id": self.company_id,
        }).one_or_none()

        if row is None:
            raise ValueError("Produit introuvable ou inactif.")

        return {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "selling_price": float(row.selling_price),
        }

    def get_stock_snapshot(self, product_id: str) -> dict:
        row = self.db.execute(
            text("""
                SELECT
                    COALESCE(stock.closing_stock, 0) AS current_stock,
                    COALESCE(p.minimum_stock, 0) AS minimum_stock,
                    stock.stock_date
                FROM products p
                LEFT JOIN LATERAL (
                    SELECT ds.closing_stock, ds.stock_date
                    FROM daily_stocks ds
                    WHERE ds.product_id = p.id
                      AND ds.company_id = :company_id
                    ORDER BY ds.stock_date DESC
                    LIMIT 1
                ) stock ON TRUE
                WHERE p.id = :product_id
                  AND p.company_id = :company_id
                  AND p.is_active = TRUE
                  AND p.deleted_at IS NULL
            """),
            {"product_id": product_id, "company_id": self.company_id},
        ).mappings().one_or_none()
        if row is None:
            raise ValueError("Produit introuvable ou inactif.")
        return {
            "current_stock": float(row["current_stock"]),
            "minimum_stock": float(row["minimum_stock"]),
            "stock_date": row["stock_date"],
        }
