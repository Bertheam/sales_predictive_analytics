"""
Génère un jeu synthétique cohérent sur 24 mois pour un dépôt de boissons.

Prérequis:
    pip install psycopg[binary] faker numpy pandas python-dotenv

Variables d'environnement possibles:
    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=sales_predictions
    DB_USER=postgres
    DB_PASSWORD=postgres

Le script:
- crée 100 clients
- crée les variables calendaires
- initialise les stocks
- génère des approvisionnements
- génère des ventes avec saisonnalité
- crée les mouvements de stock
- calcule les stocks quotidiens
- injecte quelques anomalies cohérentes
"""

import os
import math
import random
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta

import numpy as np
import psycopg
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("fr_FR")
Faker.seed(SEED)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "sales_predictions"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

END_DATE = date.today() - timedelta(days=1)
START_DATE = END_DATE - timedelta(days=730)

ZONES = [
    ("ACI 2000", "Hamdallaye"),
    ("Bamako-Coura", "Centre"),
    ("Badalabougou", "Commune V"),
    ("Faladié", "Commune VI"),
    ("Kalaban Coura", "Commune V"),
    ("Magnambougou", "Commune VI"),
    ("Sogoniko", "Commune VI"),
    ("Lafiabougou", "Commune IV"),
    ("Sébénikoro", "Commune IV"),
    ("Niamakoro", "Commune VI"),
    ("Kati", "Kati"),
    ("Banankabougou", "Commune VI"),
]

SALESPERSONS = [
    "Moussa Traoré", "Aïssata Diarra", "Oumar Coulibaly",
    "Fatoumata Koné", "Ibrahim Diallo"
]

PAYMENT_METHODS = ["CASH", "MOBILE_MONEY", "BANK_TRANSFER", "CREDIT"]

CUSTOMER_TYPE_WEIGHTS = {
    "BOUTIQUE": 0.34,
    "RESTAURANT": 0.13,
    "HOTEL": 0.07,
    "BAR": 0.10,
    "SUPERMARCHE": 0.05,
    "REVENDEUR": 0.15,
    "PARTICULIER": 0.10,
    "ENTREPRISE": 0.06,
}


def daterange(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def season_factor(d: date) -> float:
    """Approximation de la saisonnalité de la demande."""
    # Mars à juin : période chaude, demande plus forte.
    month_factor = {
        1: 0.90, 2: 0.95, 3: 1.15, 4: 1.28,
        5: 1.35, 6: 1.25, 7: 1.05, 8: 0.92,
        9: 0.95, 10: 1.02, 11: 1.05, 12: 1.18
    }[d.month]
    weekday_factor = 1.18 if d.weekday() in (4, 5) else (0.82 if d.weekday() == 6 else 1.0)
    return month_factor * weekday_factor


def temperature_for_date(d: date) -> float:
    seasonal = {
        1: 25, 2: 28, 3: 32, 4: 35, 5: 34, 6: 31,
        7: 28, 8: 27, 9: 28, 10: 30, 11: 29, 12: 26
    }[d.month]
    return round(float(np.random.normal(seasonal, 2.2)), 1)


def rainfall_for_date(d: date) -> float:
    if d.month in (6, 7, 8, 9):
        return round(max(0.0, float(np.random.gamma(1.4, 5.5))), 1)
    return round(max(0.0, float(np.random.gamma(0.2, 1.0))), 1)


def is_approx_ramadan(d: date) -> bool:
    # Simulation pour données synthétiques: fenêtres approximatives et non normatives.
    periods = [
        (date(2025, 3, 1), date(2025, 3, 30)),
        (date(2026, 2, 18), date(2026, 3, 19)),
    ]
    return any(start <= d <= end for start, end in periods)


def is_approx_tabaski(d: date) -> bool:
    periods = [
        (date(2025, 6, 5), date(2025, 6, 8)),
        (date(2026, 5, 26), date(2026, 5, 29)),
    ]
    return any(start <= d <= end for start, end in periods)


def fetch_dicts(cur, query):
    cur.execute(query)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main():
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            print("Connexion PostgreSQL OK.")

            # Nettoyage des données synthétiques transactionnelles.
            cur.execute("""
                TRUNCATE TABLE
                    anomalies,
                    forecast_results,
                    forecasts,
                    model_runs,
                    daily_stocks,
                    stock_movements,
                    purchase_receipt_items,
                    purchase_receipts,
                    sale_items,
                    sales,
                    import_batches,
                    calendar_features,
                    customers
                RESTART IDENTITY CASCADE;
            """)

            # Récupération référentiels.
            customer_types = fetch_dicts(cur, "SELECT id, code FROM customer_types ORDER BY code")
            products = fetch_dicts(cur, """
                SELECT id, code, name, category_id, units_per_package, purchase_price,
                       selling_price, minimum_stock, reorder_quantity
                FROM products
                WHERE is_active = TRUE
                ORDER BY code
            """)
            suppliers = fetch_dicts(cur, "SELECT id, code FROM suppliers WHERE is_active = TRUE ORDER BY code")

            # -----------------------------
            # Clients
            # -----------------------------
            type_codes = list(CUSTOMER_TYPE_WEIGHTS.keys())
            type_probs = [CUSTOMER_TYPE_WEIGHTS[c] for c in type_codes]
            type_map = {x["code"]: x["id"] for x in customer_types}

            customers = []
            for i in range(1, 101):
                ctype = np.random.choice(type_codes, p=type_probs)
                zone, district = random.choice(ZONES)
                business_prefix = {
                    "BOUTIQUE": "Boutique",
                    "RESTAURANT": "Restaurant",
                    "HOTEL": "Hôtel",
                    "BAR": "Bar",
                    "SUPERMARCHE": "Supermarché",
                    "REVENDEUR": "Établissements",
                    "PARTICULIER": "",
                    "ENTREPRISE": "Entreprise",
                }[ctype]
                if ctype == "PARTICULIER":
                    name = fake.name()
                else:
                    name = f"{business_prefix} {fake.last_name()} {random.choice(['Services','Commerce','Distribution','Plus','Express','Market'])}"

                code = f"CLI-{i:06d}"
                phone = f"+223{random.randint(60000000, 99999999)}"
                cur.execute("""
                    INSERT INTO customers
                    (code, name, customer_type_id, phone, zone, district, city)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (code, name, type_map[ctype], phone, zone, district, "Bamako"))
                customer_id = cur.fetchone()[0]
                customers.append({"id": customer_id, "type": ctype, "code": code})

            # -----------------------------
            # Calendrier
            # -----------------------------
            calendar = {}
            for d in daterange(START_DATE, END_DATE):
                temp = temperature_for_date(d)
                rain = rainfall_for_date(d)
                weekend = d.weekday() in (5, 6)
                ramadan = is_approx_ramadan(d)
                tabaski = is_approx_tabaski(d)
                special_event = None
                if ramadan:
                    special_event = "RAMADAN"
                elif tabaski:
                    special_event = "TABASKI"

                cur.execute("""
                    INSERT INTO calendar_features
                    (calendar_date, day_of_week, week_number, month_number, quarter_number,
                     is_weekend, is_public_holiday, is_ramadan_period, is_tabaski_period,
                     is_end_of_month, is_start_of_month, temperature_average, rainfall, special_event)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    d, d.isoweekday(), d.isocalendar().week, d.month, ((d.month - 1) // 3) + 1,
                    weekend, False, ramadan, tabaski,
                    (d + timedelta(days=1)).month != d.month,
                    d.day == 1, temp, rain, special_event
                ))
                calendar[d] = {"temp": temp, "rain": rain, "ramadan": ramadan, "tabaski": tabaski}

            # -----------------------------
            # Stocks initiaux
            # -----------------------------
            current_stock = {}
            opening_stock_for_day = {}
            movement_seq = 1

            for p in products:
                initial = int(max(float(p["minimum_stock"]) * random.uniform(2.5, 5.0), 120))
                current_stock[p["id"]] = float(initial)
                cur.execute("""
                    INSERT INTO stock_movements
                    (movement_number, movement_date, product_id, movement_type,
                     quantity_packages, quantity_units, direction, unit_cost,
                     reference_type, reason)
                    VALUES (%s,%s,%s,'INITIAL_STOCK',%s,%s,'IN',%s,'SYSTEM','Stock initial synthétique')
                """, (
                    f"MVT-{movement_seq:09d}",
                    datetime.combine(START_DATE, time(7, 0)),
                    p["id"],
                    initial,
                    initial * p["units_per_package"],
                    p["purchase_price"]
                ))
                movement_seq += 1

            # Import batch synthétique.
            cur.execute("SELECT id FROM users WHERE username='admin' LIMIT 1")
            admin_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO import_batches
                (batch_number, file_name, file_type, import_type, total_rows, valid_rows,
                 invalid_rows, duplicate_rows, status, started_at, completed_at, created_by)
                VALUES ('IMP-SYNTH-000001','synthetic_sales_24_months.csv','CSV','SALES',
                        0,0,0,0,'COMPLETED',NOW(),NOW(),%s)
                RETURNING id
            """, (admin_id,))
            import_batch_id = cur.fetchone()[0]

            sale_seq = 1
            receipt_seq = 1
            anomaly_candidates = []

            # Popularité produit: quelques références dominent.
            popularity = np.array([
                1.35 if i < 8 else 1.0 if i < 20 else 0.72
                for i in range(len(products))
            ], dtype=float)
            popularity = popularity / popularity.sum()

            # -----------------------------
            # Boucle quotidienne
            # -----------------------------
            for d in daterange(START_DATE, END_DATE):
                opening = dict(current_stock)
                daily_received = defaultdict(float)
                daily_sold = defaultdict(float)
                daily_damaged = defaultdict(float)
                daily_other_in = defaultdict(float)
                daily_other_out = defaultdict(float)

                # Réapprovisionnement automatique lorsque stock bas.
                products_to_restock = []
                for p in products:
                    if current_stock[p["id"]] <= float(p["minimum_stock"]) * random.uniform(1.0, 1.5):
                        products_to_restock.append(p)

                if products_to_restock:
                    supplier = random.choice(suppliers)
                    receipt_number = f"REC-{receipt_seq:07d}"
                    cur.execute("""
                        INSERT INTO purchase_receipts
                        (receipt_number, supplier_id, receipt_date, total_amount, status)
                        VALUES (%s,%s,%s,0,'VALIDATED')
                        RETURNING id
                    """, (receipt_number, supplier["id"], d))
                    receipt_id = cur.fetchone()[0]
                    receipt_total = 0.0

                    for p in products_to_restock:
                        qty = int(max(float(p["reorder_quantity"]) * random.uniform(0.8, 1.4), 30))
                        cost = float(p["purchase_price"]) * random.uniform(0.98, 1.04)
                        total_cost = qty * cost
                        receipt_total += total_cost

                        cur.execute("""
                            INSERT INTO purchase_receipt_items
                            (purchase_receipt_id, product_id, quantity_packages, units_per_package,
                             quantity_units, unit_cost, total_cost)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """, (
                            receipt_id, p["id"], qty, p["units_per_package"],
                            qty * p["units_per_package"], round(cost, 2), round(total_cost, 2)
                        ))

                        cur.execute("""
                            INSERT INTO stock_movements
                            (movement_number, movement_date, product_id, movement_type,
                             quantity_packages, quantity_units, direction, unit_cost,
                             reference_type, reference_id, reason)
                            VALUES (%s,%s,%s,'PURCHASE',%s,%s,'IN',%s,'PURCHASE_RECEIPT',%s,%s)
                        """, (
                            f"MVT-{movement_seq:09d}",
                            datetime.combine(d, time(8, random.randint(0, 45))),
                            p["id"], qty, qty * p["units_per_package"],
                            round(cost, 2), receipt_id, f"Réception {receipt_number}"
                        ))
                        movement_seq += 1
                        current_stock[p["id"]] += qty
                        daily_received[p["id"]] += qty

                    cur.execute(
                        "UPDATE purchase_receipts SET total_amount=%s WHERE id=%s",
                        (round(receipt_total, 2), receipt_id)
                    )
                    receipt_seq += 1

                # Nombre de ventes du jour.
                sf = season_factor(d)
                temp_boost = 1.0 + max(calendar[d]["temp"] - 30, 0) * 0.018
                event_boost = 1.12 if calendar[d]["ramadan"] else 1.20 if calendar[d]["tabaski"] else 1.0
                expected_sales = 18 * sf * temp_boost * event_boost
                num_sales = max(3, int(np.random.poisson(expected_sales)))

                for _ in range(num_sales):
                    customer = random.choice(customers)
                    sale_number = f"VTE-{sale_seq:09d}"
                    sale_dt = datetime.combine(
                        d,
                        time(random.randint(8, 19), random.randint(0, 59))
                    )
                    promotion = random.random() < 0.09
                    payment_method = random.choices(
                        PAYMENT_METHODS, weights=[0.50, 0.28, 0.12, 0.10], k=1
                    )[0]
                    salesperson = random.choice(SALESPERSONS)

                    cur.execute("""
                        INSERT INTO sales
                        (sale_number, sale_date, sale_time, customer_id, salesperson_name,
                         payment_method, payment_status, subtotal, discount_amount,
                         total_amount, promotion_applied, import_batch_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,0,0,0,%s,%s)
                        RETURNING id
                    """, (
                        sale_number, d, sale_dt.time(), customer["id"], salesperson,
                        payment_method, "PAID" if payment_method != "CREDIT" else "PENDING",
                        promotion, import_batch_id
                    ))
                    sale_id = cur.fetchone()[0]

                    item_count = random.choices([1, 2, 3, 4], weights=[0.46, 0.33, 0.16, 0.05], k=1)[0]
                    chosen_indexes = np.random.choice(
                        len(products), size=item_count, replace=False, p=popularity
                    )

                    subtotal = 0.0
                    sale_discount = 0.0
                    created_items = 0

                    for idx in chosen_indexes:
                        p = products[int(idx)]
                        available = int(current_stock[p["id"]])
                        if available <= 0:
                            continue

                        # Quantités selon type client.
                        qty_mult = {
                            "REVENDEUR": 2.7,
                            "SUPERMARCHE": 2.2,
                            "HOTEL": 1.5,
                            "RESTAURANT": 1.3,
                            "BAR": 1.4,
                            "ENTREPRISE": 1.2,
                            "BOUTIQUE": 1.0,
                            "PARTICULIER": 0.45,
                        }[customer["type"]]

                        base_qty = max(1, int(np.random.gamma(1.8, 2.2) * qty_mult))
                        qty = min(base_qty, available)
                        if qty <= 0:
                            continue

                        price = float(p["selling_price"])
                        # Légères variations de prix au fil du temps.
                        month_index = ((d.year - START_DATE.year) * 12 + d.month - START_DATE.month)
                        price *= 1 + 0.0025 * max(month_index, 0)
                        price = round(price, -1)

                        item_subtotal = qty * price
                        discount = 0.0
                        if promotion:
                            discount = round(item_subtotal * random.uniform(0.02, 0.08), 2)

                        total = item_subtotal - discount
                        unit_cost = float(p["purchase_price"])
                        margin = total - qty * unit_cost

                        cur.execute("""
                            INSERT INTO sale_items
                            (sale_id, product_id, quantity_packages, units_per_package,
                             quantity_units, unit_price, discount_amount, total_amount,
                             unit_cost, gross_margin)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """, (
                            sale_id, p["id"], qty, p["units_per_package"],
                            qty * p["units_per_package"], price, discount,
                            round(total, 2), unit_cost, round(margin, 2)
                        ))

                        cur.execute("""
                            INSERT INTO stock_movements
                            (movement_number, movement_date, product_id, movement_type,
                             quantity_packages, quantity_units, direction, unit_cost,
                             reference_type, reference_id, reason)
                            VALUES (%s,%s,%s,'SALE',%s,%s,'OUT',%s,'SALE',%s,%s)
                        """, (
                            f"MVT-{movement_seq:09d}", sale_dt, p["id"], qty,
                            qty * p["units_per_package"], unit_cost,
                            sale_id, f"Vente {sale_number}"
                        ))
                        movement_seq += 1

                        current_stock[p["id"]] -= qty
                        daily_sold[p["id"]] += qty
                        subtotal += item_subtotal
                        sale_discount += discount
                        created_items += 1

                        # Candidate d'anomalie : grosse transaction.
                        if qty >= 25:
                            anomaly_candidates.append((d, p["id"], sale_id, qty))

                    if created_items == 0:
                        cur.execute("DELETE FROM sales WHERE id=%s", (sale_id,))
                    else:
                        cur.execute("""
                            UPDATE sales
                            SET subtotal=%s, discount_amount=%s, total_amount=%s
                            WHERE id=%s
                        """, (
                            round(subtotal, 2),
                            round(sale_discount, 2),
                            round(subtotal - sale_discount, 2),
                            sale_id
                        ))
                        sale_seq += 1

                # Dégâts aléatoires.
                if random.random() < 0.18:
                    p = random.choice(products)
                    available = int(current_stock[p["id"]])
                    if available > 2:
                        qty = random.randint(1, min(3, available))
                        current_stock[p["id"]] -= qty
                        daily_damaged[p["id"]] += qty
                        cur.execute("""
                            INSERT INTO stock_movements
                            (movement_number, movement_date, product_id, movement_type,
                             quantity_packages, quantity_units, direction, unit_cost,
                             reference_type, reason)
                            VALUES (%s,%s,%s,'DAMAGE',%s,%s,'OUT',%s,'SYSTEM','Casse ou produit endommagé')
                        """, (
                            f"MVT-{movement_seq:09d}",
                            datetime.combine(d, time(18, 30)),
                            p["id"], qty, qty * p["units_per_package"],
                            p["purchase_price"]
                        ))
                        movement_seq += 1

                # Snapshot quotidien.
                for p in products:
                    pid = p["id"]
                    cur.execute("""
                        INSERT INTO daily_stocks
                        (stock_date, product_id, opening_stock, quantity_received,
                         quantity_sold, quantity_damaged, other_entries, other_outputs,
                         closing_stock, minimum_stock, stockout_flag)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        d, pid, round(opening.get(pid, 0), 2),
                        round(daily_received[pid], 2),
                        round(daily_sold[pid], 2),
                        round(daily_damaged[pid], 2),
                        round(daily_other_in[pid], 2),
                        round(daily_other_out[pid], 2),
                        round(current_stock[pid], 2),
                        p["minimum_stock"],
                        current_stock[pid] <= 0
                    ))

            # -----------------------------
            # Anomalies synthétiques
            # -----------------------------
            anomaly_seq = 1

            # Transactions inhabituellement importantes.
            for d, product_id, sale_id, qty in anomaly_candidates[:80]:
                cur.execute("""
                    INSERT INTO anomalies
                    (anomaly_number, anomaly_date, anomaly_type, severity,
                     product_id, sale_id, expected_value, observed_value,
                     deviation_percentage, description, status, detected_by_model)
                    VALUES (%s,%s,'UNUSUAL_TRANSACTION','HIGH',%s,%s,%s,%s,%s,%s,'OPEN','SyntheticRuleEngine')
                """, (
                    f"ANO-{anomaly_seq:07d}",
                    datetime.combine(d, time(12, 0)),
                    product_id, sale_id, 10, qty,
                    round(((qty - 10) / 10) * 100, 2),
                    f"Transaction inhabituellement élevée : {qty} colis."
                ))
                anomaly_seq += 1

            # Ruptures / stocks très bas.
            cur.execute("""
                SELECT ds.stock_date, ds.product_id, ds.closing_stock, ds.minimum_stock
                FROM daily_stocks ds
                WHERE ds.closing_stock <= ds.minimum_stock * 0.25
                ORDER BY ds.stock_date
                LIMIT 70
            """)
            for stock_date, product_id, closing_stock, minimum_stock in cur.fetchall():
                severity = "CRITICAL" if float(closing_stock) <= 0 else "HIGH"
                cur.execute("""
                    INSERT INTO anomalies
                    (anomaly_number, anomaly_date, anomaly_type, severity,
                     product_id, expected_value, observed_value,
                     deviation_percentage, description, status, detected_by_model)
                    VALUES (%s,%s,'STOCKOUT',%s,%s,%s,%s,%s,%s,'OPEN','SyntheticRuleEngine')
                """, (
                    f"ANO-{anomaly_seq:07d}",
                    datetime.combine(stock_date, time(19, 0)),
                    severity, product_id,
                    minimum_stock, closing_stock,
                    round(((float(closing_stock) - float(minimum_stock)) / max(float(minimum_stock), 1)) * 100, 2),
                    "Stock inférieur au seuil critique."
                ))
                anomaly_seq += 1

            # Mise à jour batch import.
            cur.execute("SELECT COUNT(*) FROM sale_items")
            sale_item_count = cur.fetchone()[0]
            cur.execute("""
                UPDATE import_batches
                SET total_rows=%s, valid_rows=%s
                WHERE id=%s
            """, (sale_item_count, sale_item_count, import_batch_id))

            conn.commit()

            # Résumé
            counts = {}
            for table in [
                "customers", "calendar_features", "sales", "sale_items",
                "purchase_receipts", "purchase_receipt_items",
                "stock_movements", "daily_stocks", "anomalies"
            ]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]

            print("\nGénération terminée.")
            for table, count in counts.items():
                print(f"{table:28s}: {count:,}")


if __name__ == "__main__":
    main()
