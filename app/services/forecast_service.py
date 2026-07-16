from sqlalchemy.orm import Session

from app.ml.dataset_builder import SalesDatasetBuilder
from app.ml.features import (
    add_calendar_features,
    add_lag_features,
    add_stock_features,
    add_time_features,
)
from app.ml.training import compare_models
from app.repositories.product_repository import ProductRepository


class ForecastService:
    """Prépare et évalue les modèles de référence par produit."""

    def __init__(self, db: Session):
        self.product_repository = ProductRepository(db)
        self.dataset_builder = SalesDatasetBuilder(db)

    def get_products(self) -> list[dict]:
        return self.product_repository.get_all_active_products()

    def get_available_date_range(self) -> dict:
        return self.dataset_builder.get_available_date_range()

    def prepare_product_dataset(self, product_id: str):
        dataset = self.dataset_builder.build_product_daily_dataset(product_id)

        if dataset.empty:
            raise ValueError("Aucune donnée disponible pour ce produit.")

        dataset = add_calendar_features(
            dataset,
            self.dataset_builder.get_calendar_features(),
        )
        dataset = add_stock_features(
            dataset,
            self.dataset_builder.get_stock_features(product_id),
        )
        dataset = add_time_features(dataset)
        return add_lag_features(dataset)

    def evaluate_product(
        self,
        product_id: str,
        test_days: int = 60,
    ) -> dict:
        dataset = self.prepare_product_dataset(product_id)
        evaluation = compare_models(dataset, test_days)

        return {
            "dataset": dataset,
            **evaluation,
        }
