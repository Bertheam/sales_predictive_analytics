-- ============================================================
-- 04_indexes.sql
-- Index utiles pour analyses et prévisions
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_customer_id ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);

CREATE INDEX IF NOT EXISTS idx_stock_movements_product_date
    ON stock_movements(product_id, movement_date);

CREATE INDEX IF NOT EXISTS idx_daily_stocks_product_date
    ON daily_stocks(product_id, stock_date);

CREATE INDEX IF NOT EXISTS idx_purchase_receipts_date
    ON purchase_receipts(receipt_date);

CREATE INDEX IF NOT EXISTS idx_purchase_receipt_items_product
    ON purchase_receipt_items(product_id);

CREATE INDEX IF NOT EXISTS idx_calendar_features_date
    ON calendar_features(calendar_date);

CREATE INDEX IF NOT EXISTS idx_forecasts_product
    ON forecasts(product_id);

CREATE INDEX IF NOT EXISTS idx_forecast_results_forecast_date
    ON forecast_results(forecast_id, forecast_date);

CREATE INDEX IF NOT EXISTS idx_anomalies_date
    ON anomalies(anomaly_date);

CREATE INDEX IF NOT EXISTS idx_anomalies_product
    ON anomalies(product_id);

CREATE INDEX IF NOT EXISTS idx_products_category
    ON products(category_id);

CREATE INDEX IF NOT EXISTS idx_customers_type
    ON customers(customer_type_id);
