-- ============================================================
-- 02_schema.sql
-- Schéma principal
-- Base cible : sales_predictions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------
-- Utilisateurs
-- -----------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(200),
    email VARCHAR(200) UNIQUE,
    password_hash TEXT,
    role VARCHAR(50) NOT NULL DEFAULT 'ANALYST',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Référentiels
-- -----------------------------
CREATE TABLE IF NOT EXISTS product_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(180) NOT NULL,
    brand VARCHAR(120),
    category_id UUID NOT NULL REFERENCES product_categories(id),
    volume_value NUMERIC(10,2),
    volume_unit VARCHAR(20),
    package_type VARCHAR(30) NOT NULL,
    units_per_package INTEGER NOT NULL CHECK (units_per_package > 0),
    purchase_price NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    selling_price NUMERIC(14,2) NOT NULL CHECK (selling_price > 0),
    minimum_stock NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (minimum_stock >= 0),
    reorder_quantity NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (reorder_quantity >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(180) NOT NULL,
    customer_type_id UUID NOT NULL REFERENCES customer_types(id),
    phone VARCHAR(50),
    zone VARCHAR(120),
    district VARCHAR(120),
    city VARCHAR(120) NOT NULL DEFAULT 'Bamako',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(180) NOT NULL,
    phone VARCHAR(50),
    city VARCHAR(120),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Imports
-- -----------------------------
CREATE TABLE IF NOT EXISTS import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_number VARCHAR(40) NOT NULL UNIQUE,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    import_type VARCHAR(30) NOT NULL CHECK (import_type IN ('SALES','PRODUCTS','CUSTOMERS','STOCKS','PURCHASES')),
    total_rows INTEGER NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
    valid_rows INTEGER NOT NULL DEFAULT 0 CHECK (valid_rows >= 0),
    invalid_rows INTEGER NOT NULL DEFAULT 0 CHECK (invalid_rows >= 0),
    duplicate_rows INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_rows >= 0),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','VALIDATING','VALIDATED','IMPORTING','COMPLETED','PARTIALLY_COMPLETED','FAILED','CANCELLED')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Ventes
-- -----------------------------
CREATE TABLE IF NOT EXISTS sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sale_number VARCHAR(40) NOT NULL UNIQUE,
    sale_date DATE NOT NULL,
    sale_time TIME,
    customer_id UUID REFERENCES customers(id),
    salesperson_name VARCHAR(180),
    payment_method VARCHAR(30),
    payment_status VARCHAR(30) NOT NULL DEFAULT 'PAID',
    subtotal NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    discount_amount NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    total_amount NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    promotion_applied BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    import_batch_id UUID REFERENCES import_batches(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (discount_amount <= subtotal),
    CHECK (total_amount = subtotal - discount_amount)
);

CREATE TABLE IF NOT EXISTS sale_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sale_id UUID NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    quantity_packages NUMERIC(14,2) NOT NULL CHECK (quantity_packages > 0),
    units_per_package INTEGER NOT NULL CHECK (units_per_package > 0),
    quantity_units NUMERIC(16,2) NOT NULL CHECK (quantity_units > 0),
    unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price > 0),
    discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    total_amount NUMERIC(16,2) NOT NULL CHECK (total_amount >= 0),
    unit_cost NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    gross_margin NUMERIC(16,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Approvisionnements
-- -----------------------------
CREATE TABLE IF NOT EXISTS purchase_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_number VARCHAR(40) NOT NULL UNIQUE,
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    receipt_date DATE NOT NULL,
    total_amount NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    status VARCHAR(30) NOT NULL DEFAULT 'VALIDATED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_receipt_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_receipt_id UUID NOT NULL REFERENCES purchase_receipts(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    quantity_packages NUMERIC(14,2) NOT NULL CHECK (quantity_packages > 0),
    units_per_package INTEGER NOT NULL CHECK (units_per_package > 0),
    quantity_units NUMERIC(16,2) NOT NULL CHECK (quantity_units > 0),
    unit_cost NUMERIC(14,2) NOT NULL CHECK (unit_cost >= 0),
    total_cost NUMERIC(16,2) NOT NULL CHECK (total_cost >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Stocks
-- -----------------------------
CREATE TABLE IF NOT EXISTS stock_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movement_number VARCHAR(50) NOT NULL UNIQUE,
    movement_date TIMESTAMPTZ NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    movement_type VARCHAR(30) NOT NULL CHECK (
        movement_type IN (
            'PURCHASE','SALE','SALE_RETURN','PURCHASE_RETURN',
            'DAMAGE','LOSS','ADJUSTMENT_IN','ADJUSTMENT_OUT','INITIAL_STOCK'
        )
    ),
    quantity_packages NUMERIC(14,2) NOT NULL CHECK (quantity_packages > 0),
    quantity_units NUMERIC(16,2) NOT NULL CHECK (quantity_units > 0),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('IN','OUT')),
    unit_cost NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    reference_type VARCHAR(50),
    reference_id UUID,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_stocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_date DATE NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    opening_stock NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (opening_stock >= 0),
    quantity_received NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (quantity_received >= 0),
    quantity_sold NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (quantity_sold >= 0),
    quantity_damaged NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (quantity_damaged >= 0),
    other_entries NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (other_entries >= 0),
    other_outputs NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (other_outputs >= 0),
    closing_stock NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (closing_stock >= 0),
    minimum_stock NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (minimum_stock >= 0),
    stockout_flag BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(stock_date, product_id)
);

-- -----------------------------
-- Variables calendaires / externes
-- -----------------------------
CREATE TABLE IF NOT EXISTS calendar_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calendar_date DATE NOT NULL UNIQUE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    week_number INTEGER NOT NULL CHECK (week_number BETWEEN 1 AND 53),
    month_number INTEGER NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    quarter_number INTEGER NOT NULL CHECK (quarter_number BETWEEN 1 AND 4),
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    is_public_holiday BOOLEAN NOT NULL DEFAULT FALSE,
    is_ramadan_period BOOLEAN NOT NULL DEFAULT FALSE,
    is_tabaski_period BOOLEAN NOT NULL DEFAULT FALSE,
    is_end_of_month BOOLEAN NOT NULL DEFAULT FALSE,
    is_start_of_month BOOLEAN NOT NULL DEFAULT FALSE,
    temperature_average NUMERIC(5,2),
    rainfall NUMERIC(8,2),
    special_event VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------
-- Machine Learning / Prévisions
-- -----------------------------
CREATE TABLE IF NOT EXISTS model_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_number VARCHAR(40) NOT NULL UNIQUE,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    target_variable VARCHAR(100) NOT NULL,
    forecast_level VARCHAR(30) NOT NULL CHECK (forecast_level IN ('GLOBAL','CATEGORY','PRODUCT')),
    training_start_date DATE NOT NULL,
    training_end_date DATE NOT NULL,
    test_start_date DATE,
    test_end_date DATE,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    mae NUMERIC(18,6),
    rmse NUMERIC(18,6),
    mape NUMERIC(18,6),
    r2_score NUMERIC(18,6),
    training_duration_seconds NUMERIC(18,3),
    status VARCHAR(30) NOT NULL DEFAULT 'COMPLETED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_number VARCHAR(40) NOT NULL UNIQUE,
    forecast_level VARCHAR(30) NOT NULL CHECK (forecast_level IN ('GLOBAL','CATEGORY','PRODUCT')),
    product_id UUID REFERENCES products(id),
    category_id UUID REFERENCES product_categories(id),
    forecast_frequency VARCHAR(20) NOT NULL CHECK (forecast_frequency IN ('DAILY','WEEKLY','MONTHLY')),
    horizon INTEGER NOT NULL CHECK (horizon > 0),
    training_start_date DATE NOT NULL,
    training_end_date DATE NOT NULL,
    forecast_start_date DATE NOT NULL,
    forecast_end_date DATE NOT NULL,
    model_run_id UUID REFERENCES model_runs(id),
    status VARCHAR(30) NOT NULL DEFAULT 'COMPLETED',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (forecast_end_date >= forecast_start_date)
);

CREATE TABLE IF NOT EXISTS forecast_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID NOT NULL REFERENCES forecasts(id) ON DELETE CASCADE,
    forecast_date DATE NOT NULL,
    predicted_quantity NUMERIC(16,2) NOT NULL CHECK (predicted_quantity >= 0),
    lower_bound NUMERIC(16,2) NOT NULL CHECK (lower_bound >= 0),
    upper_bound NUMERIC(16,2) NOT NULL CHECK (upper_bound >= lower_bound),
    predicted_p50 NUMERIC(16,2) CHECK (predicted_p50 >= 0),
    predicted_p80 NUMERIC(16,2) CHECK (predicted_p80 >= predicted_p50),
    predicted_p90 NUMERIC(16,2) CHECK (predicted_p90 >= predicted_p80),
    predicted_revenue NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (predicted_revenue >= 0),
    recommended_stock NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (recommended_stock >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(forecast_id, forecast_date)
);

-- -----------------------------
-- Anomalies
-- -----------------------------
CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anomaly_number VARCHAR(40) NOT NULL UNIQUE,
    anomaly_date TIMESTAMPTZ NOT NULL,
    anomaly_type VARCHAR(50) NOT NULL CHECK (
        anomaly_type IN (
            'ABNORMAL_SALES_INCREASE','ABNORMAL_SALES_DECREASE',
            'UNUSUAL_TRANSACTION','PRICE_INCONSISTENCY','POSSIBLE_DUPLICATE',
            'NEGATIVE_STOCK','STOCKOUT','EXCESS_STOCK',
            'NO_SALES','UNUSUAL_DISCOUNT'
        )
    ),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    product_id UUID REFERENCES products(id),
    sale_id UUID REFERENCES sales(id),
    expected_value NUMERIC(18,2),
    observed_value NUMERIC(18,2),
    deviation_percentage NUMERIC(18,4),
    description TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN',
    detected_by_model VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- -----------------------------
-- Vue analytique pratique
-- -----------------------------
CREATE OR REPLACE VIEW v_sales_analysis AS
SELECT
    s.sale_date,
    s.sale_number,
    s.customer_id,
    c.code AS customer_code,
    c.name AS customer_name,
    ct.name AS customer_type,
    c.zone,
    si.product_id,
    p.code AS product_code,
    p.name AS product_name,
    p.brand,
    pc.name AS category,
    si.quantity_packages,
    si.quantity_units,
    si.unit_price,
    si.discount_amount,
    si.total_amount,
    si.unit_cost,
    si.gross_margin,
    s.promotion_applied,
    s.payment_method,
    s.salesperson_name
FROM sale_items si
JOIN sales s ON s.id = si.sale_id
JOIN products p ON p.id = si.product_id
JOIN product_categories pc ON pc.id = p.category_id
LEFT JOIN customers c ON c.id = s.customer_id
LEFT JOIN customer_types ct ON ct.id = c.customer_type_id;
