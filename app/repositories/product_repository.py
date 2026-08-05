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
