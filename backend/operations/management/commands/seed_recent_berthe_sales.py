import math
import random
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from companies.models import Company, Membership
from operations.data import create_receipt, create_sale, operational_references


SEED_PREFIX = "NEXA-BERTHE"


class Command(BaseCommand):
    help = (
        "Prolonge de manière déterministe les ventes du dépôt Berthe KLB "
        "jusqu'à une date récente, sans dupliquer les lignes existantes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="depot-berthe-klb")
        parser.add_argument("--company-name", default="DEPOT BERTHE KLB")
        parser.add_argument("--source-company-code", default="depot-historique")
        parser.add_argument("--end-date", type=date.fromisoformat, default=None)
        parser.add_argument("--seed", type=int, default=20260806)
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirme l'écriture dans la base locale.",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Autorise explicitement l'exécution lorsque DEBUG=False.",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Ajoutez --confirm pour autoriser l'alimentation de la base.")
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError(
                "Commande bloquée hors environnement DEBUG. "
                "Utilisez --allow-production uniquement si vous savez pourquoi."
            )

        company = Company.objects.filter(code=options["company_code"]).first()
        if company is None:
            company = Company.objects.filter(name__iexact=options["company_name"]).first()
        if company is None:
            raise CommandError(
                f"Dépôt introuvable : code={options['company_code']} / "
                f"nom={options['company_name']}."
            )

        membership = (
            Membership.objects.filter(
                company=company,
                status=Membership.Status.ACTIVE,
                role__in=[Membership.Role.OWNER, Membership.Role.ADMIN],
            )
            .select_related("user")
            .order_by("role", "created_at")
            .first()
        )
        if membership is None:
            raise CommandError("Aucun propriétaire ou administrateur actif n'est rattaché au dépôt.")

        source = Company.objects.filter(code=options["source_company_code"]).first()
        if source and not self._has_sales(company.id):
            cloned = self._bootstrap_history(source.id, company.id)
            self.stdout.write(
                f"Historique de départ copié depuis {source.name} : "
                f"{cloned['sales']} ventes et {cloned['items']} lignes produit."
            )

        references = operational_references(company.id)
        products = references["products"]
        customers = references["customers"]
        suppliers = references["suppliers"]
        if not products:
            raise CommandError("Le dépôt ne contient aucun produit actif.")
        if not suppliers:
            raise CommandError("Ajoutez au moins un fournisseur avant d'exécuter le seeder.")

        end_date = options["end_date"] or timezone.localdate()
        start_date, existing_references, averages = self._seed_context(company.id)
        if start_date is None:
            raise CommandError("Le dépôt ne contient pas d'historique à prolonger.")
        if start_date > end_date:
            start_date = end_date

        rows = self._build_rows(
            products=products,
            customers=customers,
            start_date=start_date,
            end_date=end_date,
            averages=averages,
            seed=options["seed"],
        )
        pending = [row for row in rows if row["sale_reference"] not in existing_references]
        if not pending:
            self.stdout.write(self.style.SUCCESS(
                f"Aucune écriture : les ventes {start_date:%d/%m/%Y} → "
                f"{end_date:%d/%m/%Y} existent déjà pour {company.name}."
            ))
            return

        quantities = defaultdict(Decimal)
        for row in pending:
            quantities[row["product_id"]] += row["quantity_packages"]
        receipt_lines = []
        for product in products:
            needed = quantities[product["id"]] + Decimal(product["minimum_stock"]) * 2
            deficit = max(Decimal("0"), needed - Decimal(product["current_stock"]))
            if deficit:
                receipt_lines.append({
                    "product_id": str(product["id"]),
                    "quantity_packages": Decimal(math.ceil(deficit / 10) * 10),
                    "unit_cost": Decimal(product["purchase_price"]),
                })

        grouped = defaultdict(list)
        for row in pending:
            grouped[row["sale_reference"]].append(row)

        with transaction.atomic():
            if receipt_lines:
                create_receipt(
                    company.id,
                    membership.user_id,
                    {"supplier_id": str(suppliers[0]["id"]), "receipt_date": start_date},
                    receipt_lines,
                )

            created_sales = 0
            created_lines = 0
            for sale_reference in sorted(grouped):
                items = grouped[sale_reference]
                first = items[0]
                result = create_sale(
                    company.id,
                    membership.user_id,
                    {
                        "sale_date": first["sale_date"],
                        "customer_id": first["customer_id"],
                        "payment_method": first["payment_method"],
                        "payment_status": "PAID",
                        "notes": f"Jeu récent déterministe · {sale_reference}",
                    },
                    [
                        {
                            "product_id": str(row["product_id"]),
                            "quantity_packages": row["quantity_packages"],
                            "unit_price": row["unit_price"],
                            "discount_amount": Decimal("0"),
                        }
                        for row in items
                    ],
                    "Équipe dépôt Berthe KLB",
                )
                self._set_external_reference(company.id, result["id"], sale_reference)
                created_sales += 1
                created_lines += len(items)

        self.stdout.write(self.style.SUCCESS(
            f"{company.name} alimenté du {start_date:%d/%m/%Y} au "
            f"{end_date:%d/%m/%Y} : {created_sales} ventes, "
            f"{created_lines} lignes produit et {len(receipt_lines)} lignes de réception."
        ))

    @staticmethod
    def _has_sales(company_id):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM sales WHERE company_id = %s)",
                [str(company_id)],
            )
            return cursor.fetchone()[0]

    @staticmethod
    def _bootstrap_history(source_id, target_id):
        """Copie le socle analytique sans déplacer ni modifier le dépôt source."""
        source_id, target_id = str(source_id), str(target_id)
        with transaction.atomic(), connection.cursor() as cursor:
            # Harmoniser d'abord les quelques référentiels éventuellement créés
            # manuellement dans le dépôt cible, puis compléter le catalogue.
            cursor.execute("""
                UPDATE product_categories target
                SET code = source.code, description = source.description,
                    is_active = source.is_active, updated_at = NOW()
                FROM product_categories source
                WHERE source.company_id = %s AND target.company_id = %s
                  AND LOWER(TRIM(target.name)) = LOWER(TRIM(source.name))
            """, [source_id, target_id])
            cursor.execute("""
                INSERT INTO product_categories (
                    company_id, code, name, description, is_active
                )
                SELECT %s, code, name, description, is_active
                FROM product_categories WHERE company_id = %s
                ON CONFLICT DO NOTHING
            """, [target_id, source_id])
            cursor.execute("""
                UPDATE customer_types target
                SET code = source.code, is_active = source.is_active, updated_at = NOW()
                FROM customer_types source
                WHERE source.company_id = %s AND target.company_id = %s
                  AND LOWER(TRIM(target.name)) = LOWER(TRIM(source.name))
            """, [source_id, target_id])
            cursor.execute("""
                INSERT INTO customer_types (company_id, code, name, is_active)
                SELECT %s, code, name, is_active
                FROM customer_types WHERE company_id = %s
                ON CONFLICT DO NOTHING
            """, [target_id, source_id])
            cursor.execute("""
                UPDATE products target
                SET code = source.code, brand = source.brand,
                    category_id = target_category.id,
                    volume_value = source.volume_value, volume_unit = source.volume_unit,
                    package_type = source.package_type,
                    units_per_package = source.units_per_package,
                    purchase_price = source.purchase_price,
                    selling_price = source.selling_price,
                    minimum_stock = source.minimum_stock,
                    reorder_quantity = source.reorder_quantity,
                    is_active = source.is_active, updated_at = NOW()
                FROM products source
                JOIN product_categories source_category
                  ON source_category.id = source.category_id
                 AND source_category.company_id = source.company_id
                JOIN product_categories target_category
                  ON target_category.company_id = %s
                 AND target_category.code = source_category.code
                WHERE source.company_id = %s AND target.company_id = %s
                  AND LOWER(TRIM(target.name)) = LOWER(TRIM(source.name))
                  AND LOWER(TRIM(COALESCE(target.brand, ''))) = LOWER(TRIM(COALESCE(source.brand, '')))
                  AND target.volume_value IS NOT DISTINCT FROM source.volume_value
                  AND LOWER(TRIM(COALESCE(target.volume_unit, ''))) = LOWER(TRIM(COALESCE(source.volume_unit, '')))
                  AND LOWER(TRIM(target.package_type)) = LOWER(TRIM(source.package_type))
            """, [target_id, source_id, target_id])
            cursor.execute("""
                INSERT INTO products (
                    company_id, code, name, brand, category_id, volume_value,
                    volume_unit, package_type, units_per_package, purchase_price,
                    selling_price, minimum_stock, reorder_quantity, is_active
                )
                SELECT %s, source.code, source.name, source.brand, target_category.id,
                       source.volume_value, source.volume_unit, source.package_type,
                       source.units_per_package, source.purchase_price,
                       source.selling_price, source.minimum_stock,
                       source.reorder_quantity, source.is_active
                FROM products source
                JOIN product_categories source_category
                  ON source_category.id = source.category_id
                 AND source_category.company_id = source.company_id
                JOIN product_categories target_category
                  ON target_category.company_id = %s
                 AND target_category.code = source_category.code
                WHERE source.company_id = %s
                ON CONFLICT DO NOTHING
            """, [target_id, target_id, source_id])
            cursor.execute("""
                INSERT INTO suppliers (company_id, code, name, phone, city, is_active)
                SELECT %s, code, name, phone, city, is_active
                FROM suppliers WHERE company_id = %s
                ON CONFLICT DO NOTHING
            """, [target_id, source_id])
            cursor.execute("""
                INSERT INTO customers (
                    company_id, code, name, customer_type_id, phone,
                    zone, district, city, is_active
                )
                SELECT %s, source.code, source.name, target_type.id, source.phone,
                       source.zone, source.district, source.city, source.is_active
                FROM customers source
                JOIN customer_types source_type
                  ON source_type.id = source.customer_type_id
                 AND source_type.company_id = source.company_id
                JOIN customer_types target_type
                  ON target_type.company_id = %s AND target_type.code = source_type.code
                WHERE source.company_id = %s
                ON CONFLICT DO NOTHING
            """, [target_id, target_id, source_id])
            cursor.execute("""
                INSERT INTO sales (
                    company_id, external_reference, sale_date, sale_time,
                    customer_id, salesperson_name, payment_method, payment_status,
                    subtotal, discount_amount, total_amount, promotion_applied, notes
                )
                SELECT %s, 'HIST-' || source.sale_number, source.sale_date,
                       source.sale_time, target_customer.id, source.salesperson_name,
                       source.payment_method, source.payment_status, source.subtotal,
                       source.discount_amount, source.total_amount,
                       source.promotion_applied, 'Historique de démonstration copié'
                FROM sales source
                LEFT JOIN customers source_customer
                  ON source_customer.id = source.customer_id
                 AND source_customer.company_id = source.company_id
                LEFT JOIN customers target_customer
                  ON target_customer.company_id = %s
                 AND target_customer.code = source_customer.code
                WHERE source.company_id = %s AND source.deleted_at IS NULL
                ON CONFLICT (company_id, external_reference) DO NOTHING
            """, [target_id, target_id, source_id])
            sales_count = cursor.rowcount
            cursor.execute("""
                INSERT INTO sale_items (
                    company_id, sale_id, product_id, quantity_packages,
                    units_per_package, quantity_units, unit_price,
                    discount_amount, total_amount, unit_cost, gross_margin
                )
                SELECT %s, target_sale.id, target_product.id,
                       source_item.quantity_packages, source_item.units_per_package,
                       source_item.quantity_units, source_item.unit_price,
                       source_item.discount_amount, source_item.total_amount,
                       source_item.unit_cost, source_item.gross_margin
                FROM sale_items source_item
                JOIN sales source_sale
                  ON source_sale.id = source_item.sale_id
                 AND source_sale.company_id = source_item.company_id
                JOIN sales target_sale
                  ON target_sale.company_id = %s
                 AND target_sale.external_reference = 'HIST-' || source_sale.sale_number
                JOIN products source_product
                  ON source_product.id = source_item.product_id
                 AND source_product.company_id = source_item.company_id
                JOIN products target_product
                  ON target_product.company_id = %s
                 AND target_product.code = source_product.code
                WHERE source_item.company_id = %s
                  AND NOT EXISTS (
                    SELECT 1 FROM sale_items existing
                    WHERE existing.company_id = %s
                      AND existing.sale_id = target_sale.id
                      AND existing.product_id = target_product.id
                  )
            """, [target_id, target_id, target_id, source_id, target_id])
            item_count = cursor.rowcount
            cursor.execute("""
                INSERT INTO daily_stocks (
                    company_id, stock_date, product_id, opening_stock,
                    quantity_received, quantity_sold, quantity_damaged,
                    other_entries, other_outputs, closing_stock,
                    minimum_stock, stockout_flag
                )
                SELECT %s, source_stock.stock_date, target_product.id,
                       source_stock.opening_stock, source_stock.quantity_received,
                       source_stock.quantity_sold, source_stock.quantity_damaged,
                       source_stock.other_entries, source_stock.other_outputs,
                       source_stock.closing_stock, source_stock.minimum_stock,
                       source_stock.stockout_flag
                FROM daily_stocks source_stock
                JOIN products source_product
                  ON source_product.id = source_stock.product_id
                 AND source_product.company_id = source_stock.company_id
                JOIN products target_product
                  ON target_product.company_id = %s
                 AND target_product.code = source_product.code
                WHERE source_stock.company_id = %s
                ON CONFLICT (company_id, stock_date, product_id) DO NOTHING
            """, [target_id, target_id, source_id])
        return {"sales": sales_count, "items": item_count}

    @staticmethod
    def _seed_context(company_id):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_company_id', %s, TRUE)",
                [str(company_id)],
            )
            cursor.execute(
                """
                SELECT MIN(sale_date)
                FROM sales
                WHERE company_id = %s AND external_reference LIKE %s
                """,
                [str(company_id), f"{SEED_PREFIX}-%"],
            )
            seeded_start = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT GREATEST(
                    (SELECT MAX(sale_date) FROM sales WHERE company_id = %s AND deleted_at IS NULL),
                    (SELECT MAX(stock_date) FROM daily_stocks WHERE company_id = %s)
                )
                """,
                [str(company_id), str(company_id)],
            )
            latest_date = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT external_reference
                FROM sales
                WHERE company_id = %s AND external_reference LIKE %s
                """,
                [str(company_id), f"{SEED_PREFIX}-%"],
            )
            existing = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT p.id, COALESCE(AVG(d.quantity), 4)
                FROM products p
                LEFT JOIN (
                    SELECT si.product_id, s.sale_date, SUM(si.quantity_packages) AS quantity
                    FROM sale_items si
                    JOIN sales s ON s.company_id = si.company_id AND s.id = si.sale_id
                    WHERE si.company_id = %s AND s.deleted_at IS NULL
                      AND s.sale_date >= COALESCE(%s::date, CURRENT_DATE) - 27
                    GROUP BY si.product_id, s.sale_date
                ) d ON d.product_id = p.id
                WHERE p.company_id = %s AND p.is_active = TRUE AND p.deleted_at IS NULL
                GROUP BY p.id
                """,
                [str(company_id), latest_date, str(company_id)],
            )
            averages = {row[0]: max(float(row[1]), 1.0) for row in cursor.fetchall()}
        start_date = seeded_start or (latest_date + timedelta(days=1) if latest_date else None)
        return start_date, existing, averages

    @staticmethod
    def _set_external_reference(company_id, sale_id, reference):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_company_id', %s, TRUE)",
                [str(company_id)],
            )
            cursor.execute(
                """
                UPDATE sales SET external_reference = %s
                WHERE company_id = %s AND id = %s
                """,
                [reference, str(company_id), str(sale_id)],
            )

    @staticmethod
    def _build_rows(*, products, customers, start_date, end_date, averages, seed):
        rows = []
        current = start_date
        product_groups = [products[index:index + 5] for index in range(0, len(products), 5)]
        while current <= end_date:
            weekend_factor = 1.16 if current.weekday() >= 5 else 1.0
            month_factor = 1.04 if current.month in {7, 8} else 1.0
            for group_index, group in enumerate(product_groups, start=1):
                reference = f"{SEED_PREFIX}-{current:%Y%m%d}-G{group_index:02d}"
                customer = customers[(current.toordinal() + group_index) % len(customers)] if customers else None
                for product_index, product in enumerate(group):
                    rng = random.Random(seed + current.toordinal() * 101 + group_index * 17 + product_index)
                    expected = averages.get(product["id"], 4.0) * weekend_factor * month_factor
                    quantity = max(1, int(round(rng.gauss(expected, max(1.0, expected * 0.18)))))
                    rows.append({
                        "sale_reference": reference,
                        "sale_date": current,
                        "sale_time": f"{9 + (group_index % 8):02d}:{(group_index * 7) % 60:02d}",
                        "customer_id": str(customer["id"]) if customer else None,
                        "customer_code": customer["code"] if customer else "",
                        "product_id": product["id"],
                        "product_code": product["code"],
                        "quantity_packages": Decimal(quantity),
                        "unit_price": Decimal(product["selling_price"]),
                        "discount_amount": Decimal("0"),
                        "payment_method": "CASH" if group_index % 3 else "MOBILE_MONEY",
                        "payment_status": "PAID",
                        "salesperson_name": "Équipe dépôt Berthe KLB",
                        "notes": "Jeu récent de démonstration NexaStock",
                    })
            current += timedelta(days=1)
        return rows
