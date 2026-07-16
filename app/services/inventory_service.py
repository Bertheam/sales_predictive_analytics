from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.repositories.inventory_repository import InventoryRepository


MOVEMENT_TYPES = {
    "ADJUSTMENT_IN": {
        "label": "Ajustement positif",
        "direction": "IN",
    },
    "ADJUSTMENT_OUT": {
        "label": "Ajustement négatif",
        "direction": "OUT",
    },
    "DAMAGE": {
        "label": "Produit endommagé / casse",
        "direction": "OUT",
    },
    "LOSS": {
        "label": "Perte",
        "direction": "OUT",
    },
    "SALE_RETURN": {
        "label": "Retour client",
        "direction": "IN",
    },
    "PURCHASE_RETURN": {
        "label": "Retour fournisseur",
        "direction": "OUT",
    },
}


class InventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = InventoryRepository(db)

    def get_suppliers(self) -> list[dict]:
        return self.repository.get_suppliers()

    def get_products(self) -> list[dict]:
        return self.repository.get_products()

    def get_movement_types(self) -> dict:
        return MOVEMENT_TYPES

    def create_receipt(
        self,
        *,
        supplier_id: str,
        receipt_date: date,
        items: list[dict],
    ) -> dict:
        if receipt_date > date.today():
            raise ValueError("La date de réception ne peut pas être future.")
        supplier_ids = {
            str(supplier["id"]) for supplier in self.repository.get_suppliers()
        }
        if supplier_id not in supplier_ids:
            raise ValueError("Fournisseur inconnu ou inactif.")

        cleaned_items = []
        seen_products = set()
        for item in items:
            product_id = str(item.get("product_id") or "").strip()
            if not product_id:
                continue
            if product_id in seen_products:
                raise ValueError(
                    "Un produit ne peut apparaître qu'une fois dans la réception."
                )
            seen_products.add(product_id)
            product = self.repository.get_product(product_id)
            if product is None:
                raise ValueError("Un produit est inconnu ou inactif.")
            quantity = self._positive_number(
                item.get("quantity_packages"),
                "La quantité",
            )
            unit_cost = self._non_negative_number(
                item.get("unit_cost"),
                "Le coût unitaire",
            )
            cleaned_items.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "unit_cost": unit_cost,
                }
            )
        if not cleaned_items:
            raise ValueError("Ajoutez au moins une ligne produit valide.")

        cleaned_items.sort(key=lambda item: str(item["product"]["id"]))
        movement_time = datetime.now().time() if receipt_date == date.today() else time(12)
        movement_date = datetime.combine(receipt_date, movement_time)

        try:
            receipt = self.repository.create_receipt_header(
                supplier_id,
                receipt_date,
            )
            total_amount = 0.0
            movements = []
            stock_updates = []
            for item in cleaned_items:
                product = item["product"]
                quantity = item["quantity"]
                unit_cost = item["unit_cost"]
                stock = self.repository.apply_daily_stock(
                    product=product,
                    stock_date=receipt_date,
                    movement_type="PURCHASE",
                    direction="IN",
                    quantity=quantity,
                )
                self.repository.add_receipt_item(
                    receipt_id=receipt["id"],
                    product=product,
                    quantity=quantity,
                    unit_cost=unit_cost,
                )
                movement_number = self.repository.add_movement(
                    movement_date=movement_date,
                    product=product,
                    movement_type="PURCHASE",
                    quantity=quantity,
                    direction="IN",
                    unit_cost=unit_cost,
                    reference_type="PURCHASE_RECEIPT",
                    reference_id=receipt["id"],
                    reason=f"Réception {receipt['receipt_number']}",
                )
                total_amount += quantity * unit_cost
                movements.append(movement_number)
                stock_updates.append(
                    {
                        "product": product["name"],
                        **stock,
                    }
                )
            self.repository.update_receipt_total(
                receipt["id"],
                total_amount,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "receipt_number": receipt["receipt_number"],
            "item_count": len(cleaned_items),
            "total_quantity": sum(item["quantity"] for item in cleaned_items),
            "total_amount": total_amount,
            "movements": movements,
            "stock_updates": stock_updates,
        }

    def create_movement(
        self,
        *,
        product_id: str,
        movement_type: str,
        movement_date: date,
        quantity: float,
        reason: str,
    ) -> dict:
        if movement_type not in MOVEMENT_TYPES:
            raise ValueError("Type de mouvement non autorisé.")
        if movement_date > date.today():
            raise ValueError("La date du mouvement ne peut pas être future.")
        product = self.repository.get_product(product_id)
        if product is None:
            raise ValueError("Produit inconnu ou inactif.")
        quantity = self._positive_number(quantity, "La quantité")
        reason = str(reason or "").strip()
        if len(reason) < 5:
            raise ValueError(
                "Le motif est obligatoire et doit contenir au moins 5 caractères."
            )

        movement = MOVEMENT_TYPES[movement_type]
        movement_time = datetime.now().time() if movement_date == date.today() else time(12)
        timestamp = datetime.combine(movement_date, movement_time)

        try:
            stock = self.repository.apply_daily_stock(
                product=product,
                stock_date=movement_date,
                movement_type=movement_type,
                direction=movement["direction"],
                quantity=quantity,
            )
            movement_number = self.repository.add_movement(
                movement_date=timestamp,
                product=product,
                movement_type=movement_type,
                quantity=quantity,
                direction=movement["direction"],
                unit_cost=float(product["purchase_price"]),
                reference_type="MANUAL",
                reason=reason,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "movement_number": movement_number,
            "movement_label": movement["label"],
            "product_name": product["name"],
            "quantity": quantity,
            **stock,
        }

    def get_dashboard_data(self) -> dict:
        products = self.repository.get_products()
        return {
            "products": products,
            "receipts": self.repository.get_receipt_history(),
            "movements": self.repository.get_movement_history(),
            "total_stock": sum(float(row["current_stock"]) for row in products),
            "stockout_count": sum(float(row["current_stock"]) <= 0 for row in products),
            "low_stock_count": sum(
                float(row["current_stock"]) <= float(row["minimum_stock"])
                for row in products
            ),
        }

    @staticmethod
    def _positive_number(value, label: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{label} doit être numérique.") from None
        if number <= 0:
            raise ValueError(f"{label} doit être supérieure à 0.")
        return number

    @staticmethod
    def _non_negative_number(value, label: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{label} doit être numérique.") from None
        if number < 0:
            raise ValueError(f"{label} ne peut pas être négatif.")
        return number
