from uuid import uuid4

from django.db import IntegrityError
from django.test import TestCase, override_settings

from .db import tenant_cursor
from .models import Company


@override_settings(TENANT_USE_RUNTIME_ROLE=True)
class PostgreSQLTenantIsolationTests(TestCase):
    """Exercise PostgreSQL RLS with the restricted runtime role."""

    def setUp(self):
        self.company_a = Company.objects.create(code="rls-a", name="Dépôt RLS A")
        self.company_b = Company.objects.create(code="rls-b", name="Dépôt RLS B")
        self.category_a = uuid4()
        self.category_b = uuid4()
        self._insert_category(self.company_a.id, self.category_a, "A")
        self._insert_category(self.company_b.id, self.category_b, "B")

    @staticmethod
    def _insert_category(company_id, category_id, suffix):
        with tenant_cursor(company_id) as cursor:
            cursor.execute(
                """
                INSERT INTO product_categories (id, company_id, code, name)
                VALUES (%s, %s, %s, %s)
                """,
                [str(category_id), str(company_id), f"CAT-{suffix}", f"Catégorie {suffix}"],
            )

    def test_runtime_role_reads_only_the_active_company(self):
        with tenant_cursor(self.company_a.id) as cursor:
            cursor.execute("SELECT company_id, code FROM product_categories ORDER BY code")
            rows = cursor.fetchall()

        self.assertEqual(rows, [(self.company_a.id, "CAT-A")])

    def test_composite_foreign_key_rejects_a_foreign_category(self):
        with self.assertRaises(IntegrityError):
            with tenant_cursor(self.company_a.id) as cursor:
                cursor.execute(
                    """
                    INSERT INTO products (
                        company_id, code, name, category_id, package_type,
                        units_per_package, selling_price
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        str(self.company_a.id),
                        "PRD-CROSS",
                        "Produit étranger",
                        str(self.category_b),
                        "Carton",
                        12,
                        1000,
                    ],
                )
