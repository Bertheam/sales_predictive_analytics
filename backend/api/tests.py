from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test import override_settings
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from audit.models import AuditLog
from companies.models import Company, Membership
from companies.db import tenant_cursor
from companies.services import bootstrap_company_references
from decisions.models import PurchaseOrder, PurchaseOrderItem

from .models import IdempotencyRecord


class ApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="api@example.com", password="A-secure-password-2026", full_name="API User"
        )
        self.company = Company.objects.create(code="api-depot", name="Dépôt API")
        Membership.objects.create(
            user=self.user, company=self.company, role=Membership.Role.ADMIN, status=Membership.Status.ACTIVE
        )

    def tearDown(self):
        cache.clear()

    def test_api_rejects_anonymous_requests(self):
        response = self.client.get(reverse("api:me"))
        self.assertIn(response.status_code, (401, 403))

    def test_context_returns_only_selected_company_and_role(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.pk)
        session.save()
        response = self.client.get(reverse("api:context"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company"]["code"], "api-depot")
        self.assertEqual(response.json()["role"], Membership.Role.ADMIN)

    def test_companies_returns_user_memberships(self):
        Company.objects.create(code="other", name="Autre dépôt")
        self.client.force_login(self.user)
        response = self.client.get(reverse("api:companies"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["company"]["code"], "api-depot")

    def test_dashboard_summary_requires_selected_company(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("api:dashboard-summary"))
        self.assertEqual(response.status_code, 400)

    def test_dashboard_summary_uses_selected_company(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.pk)
        session.save()
        response = self.client.get(reverse("api:dashboard-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_id"], str(self.company.pk))

    def test_operational_api_requires_selected_company(self):
        self.client.force_login(self.user)
        for route in ("api:products", "api:stocks", "api:sales"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 400)

    def test_operational_api_is_scoped_to_selected_company(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.pk)
        session.save()
        for route in ("api:products", "api:stocks", "api:sales"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["company_id"], str(self.company.pk))

    def test_authorized_company_header_works_without_browser_session(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID=str(self.company.id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_id"], str(self.company.id))

    def test_explicit_company_header_overrides_browser_session(self):
        second = Company.objects.create(code="api-second", name="Second dépôt")
        Membership.objects.create(
            user=self.user,
            company=second,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID=str(second.id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_id"], str(second.id))

    def test_foreign_company_header_is_rejected_without_fallback(self):
        foreign = Company.objects.create(code="api-foreign", name="Dépôt étranger")
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = str(self.company.id)
        session.save()

        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID=str(foreign.id),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "company_access_denied")

    def test_invalid_company_header_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("api:products"),
            HTTP_X_COMPANY_ID="invalid-company",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_company_context")

    def test_mobile_login_returns_jwt_and_accessible_companies(self):
        response = self.client.post(
            reverse("api:login"),
            {"identifier": self.user.email, "password": "A-secure-password-2026"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())
        self.assertEqual(len(response.json()["companies"]), 1)

    def test_suspended_membership_cannot_obtain_or_refresh_jwt(self):
        membership = Membership.objects.get(user=self.user, company=self.company)
        membership.status = Membership.Status.SUSPENDED
        membership.save(update_fields=["status"])

        response = self.client.post(
            reverse("api:login"),
            {"identifier": self.user.email, "password": "A-secure-password-2026"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "no_active_membership")

        refresh = str(RefreshToken.for_user(self.user))
        response = self.client.post(
            reverse("api:refresh"), {"refresh": refresh},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"login": "2/minute", "sensitive_write": "60/minute"},
    })
    def test_mobile_login_is_rate_limited_by_client_address(self):
        payload = {"identifier": self.user.email, "password": "incorrect"}

        self.assertEqual(self.client.post(reverse("api:login"), payload, content_type="application/json").status_code, 401)
        self.assertEqual(self.client.post(reverse("api:login"), payload, content_type="application/json").status_code, 401)
        response = self.client.post(reverse("api:login"), payload, content_type="application/json")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "throttled")

    @override_settings(REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"login": "10/minute", "sensitive_write": "2/minute"},
    })
    def test_api_mutations_are_rate_limited_per_user(self):
        self.client.force_login(self.user)
        url = reverse("api:stock-movements")
        kwargs = {"content_type": "application/json", "HTTP_X_COMPANY_ID": str(self.company.id)}

        self.assertEqual(self.client.post(url, {}, **kwargs).status_code, 400)
        self.assertEqual(self.client.post(url, {}, **kwargs).status_code, 400)
        response = self.client.post(url, {}, **kwargs)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "throttled")

    def test_bearer_authentication_accesses_profile(self):
        access = str(RefreshToken.for_user(self.user).access_token)
        response = self.client.get(reverse("api:me"), HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], self.user.email)

    def test_viewer_cannot_create_stock_movement(self):
        membership = Membership.objects.get(user=self.user, company=self.company)
        membership.role = Membership.Role.VIEWER
        membership.save(update_fields=["role"])
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("api:stock-movements"), {},
            content_type="application/json", HTTP_X_COMPANY_ID=str(self.company.id),
        )
        self.assertEqual(response.status_code, 403)

    @patch("api.views.create_sale")
    def test_sale_creation_is_idempotent_for_mobile_retries(self, create_sale_mock):
        create_sale_mock.return_value = {
            "id": uuid4(), "number": "VTE-IDEMP-001", "total": Decimal("10000")
        }
        self.client.force_login(self.user)
        payload = {
            "sale_date": str(date.today()), "payment_method": "CASH",
            "payment_status": "PAID",
            "items": [{
                "product_id": str(uuid4()), "quantity_packages": "2",
                "unit_price": "5000", "discount_amount": "0",
            }],
        }
        kwargs = {
            "content_type": "application/json",
            "HTTP_X_COMPANY_ID": str(self.company.id),
            "HTTP_IDEMPOTENCY_KEY": "mobile-sale-2026-0001",
        }

        first = self.client.post(reverse("api:sales"), payload, **kwargs)
        second = self.client.post(reverse("api:sales"), payload, **kwargs)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.headers["Idempotency-Replayed"], "true")
        self.assertEqual(create_sale_mock.call_count, 1)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)

        payload["items"][0]["quantity_packages"] = "3"
        conflict = self.client.post(reverse("api:sales"), payload, **kwargs)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["code"], "idempotency_conflict")

    @patch("api.views.product_catalog")
    def test_product_pagination_and_ordering_are_delegated_to_database(self, catalog):
        catalog.return_value = ([{"id": str(uuid4()), "name": "Cola"}], {"filtered_count": 51})
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("api:products") + "?page=2&page_size=10&ordering=-selling_price",
            HTTP_X_COMPANY_ID=str(self.company.id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["count"], 51)
        catalog.assert_called_once_with(
            self.company.id, query="", status="active",
            ordering="-selling_price", limit=10, offset=10,
        )

    def test_purchase_order_receive_route_is_not_shadowed_and_transitions_are_audited(self):
        order = PurchaseOrder.objects.create(
            company=self.company, order_number="CMD-API-001",
            supplier_id=uuid4(), supplier_name="Fournisseur API",
            created_by=self.user, updated_by=self.user,
        )
        item = PurchaseOrderItem.objects.create(
            order=order, product_id=uuid4(), product_code="PRD-API",
            product_name="Produit API", quantity_ordered=Decimal("5"),
            unit_cost=Decimal("2000"),
        )
        self.client.force_login(self.user)
        headers = {"HTTP_X_COMPANY_ID": str(self.company.id)}

        self.assertEqual(
            self.client.get(reverse("api:purchase-order-receive", args=[order.id]), **headers).status_code,
            405,
        )
        sent = self.client.post(reverse("api:purchase-order-send", args=[order.id]), {}, content_type="application/json", **headers)
        self.assertEqual(sent.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(resource_type="purchase_order", resource_id=str(order.id)).exists())

        with patch("api.views.create_receipt", return_value={
            "id": uuid4(), "number": "REC-API-001", "total": Decimal("4000")
        }):
            received = self.client.post(
                reverse("api:purchase-order-receive", args=[order.id]),
                {"receipt_date": str(date.today()), "items": [{
                    "item_id": str(item.id), "quantity_packages": "2", "unit_cost": "2000",
                }]},
                content_type="application/json", **headers,
            )
        self.assertEqual(received.status_code, 201)
        self.assertTrue(AuditLog.objects.filter(resource_type="purchase_order_receipt").exists())

    def test_p0_catalog_crud_and_stock_detail_routes_are_available(self):
        self.client.force_login(self.user)
        headers = {"HTTP_X_COMPANY_ID": str(self.company.id)}
        category_id = uuid4()
        product_id = uuid4()
        product_payload = {
            "name": "Cola API", "category_id": str(category_id),
            "package_type": "CARTON", "units_per_package": 24,
            "purchase_price": "4000", "selling_price": "5000",
            "minimum_stock": "10", "reorder_quantity": "40",
        }
        product = {
            "id": product_id, "code": "PRD-API-001", **product_payload,
            "brand": "", "volume_value": None, "volume_unit": "",
            "is_active": True,
        }
        with patch("api.views.save_product", return_value={
            "id": product_id, "code": "PRD-API-001",
        }), patch("api.views.get_product", return_value=product), patch(
            "api.views.set_product_archived",
            return_value={"id": product_id, "code": "PRD-API-001", "name": "Cola API"},
        ):
            self.assertEqual(self.client.post(
                reverse("api:products"), product_payload,
                content_type="application/json", **headers,
            ).status_code, 201)
            self.assertEqual(self.client.get(
                reverse("api:product-detail", args=[product_id]), **headers,
            ).status_code, 200)
            self.assertEqual(self.client.patch(
                reverse("api:product-detail", args=[product_id]),
                {"selling_price": "5200"}, content_type="application/json", **headers,
            ).status_code, 200)
            self.assertEqual(self.client.delete(
                reverse("api:product-detail", args=[product_id]), **headers,
            ).status_code, 204)

        customer_id, customer_type_id = uuid4(), uuid4()
        customer_payload = {
            "name": "Boutique API", "customer_type_id": str(customer_type_id),
        }
        customer = {
            "id": customer_id, "code": "CLI-API-001", **customer_payload,
            "phone": None, "zone": None, "district": None,
            "city": "Bamako", "is_active": True,
        }
        with patch("api.views.save_customer", return_value={
            "id": customer_id, "code": "CLI-API-001", "name": "Boutique API",
        }), patch("api.views.get_customer", return_value=customer), patch(
            "api.views.set_customer_archived",
            return_value={"id": customer_id, "code": "CLI-API-001", "name": "Boutique API"},
        ):
            self.assertEqual(self.client.post(
                reverse("api:customers"), customer_payload,
                content_type="application/json", **headers,
            ).status_code, 201)
            self.assertEqual(self.client.patch(
                reverse("api:customer-detail", args=[customer_id]),
                {"phone": "+22370000000"}, content_type="application/json", **headers,
            ).status_code, 200)
            self.assertEqual(self.client.delete(
                reverse("api:customer-detail", args=[customer_id]), **headers,
            ).status_code, 204)

        supplier_id = uuid4()
        supplier = {
            "id": supplier_id, "code": "FRS-API-001", "name": "Fournisseur API",
            "phone": None, "city": "Bamako", "is_active": True,
        }
        with patch("api.views.save_supplier", return_value={
            "id": supplier_id, "code": "FRS-API-001", "name": "Fournisseur API",
        }), patch("api.views.get_supplier", return_value=supplier), patch(
            "api.views.set_supplier_archived",
            return_value={"id": supplier_id, "code": "FRS-API-001", "name": "Fournisseur API"},
        ):
            self.assertEqual(self.client.post(
                reverse("api:suppliers"), {"name": "Fournisseur API"},
                content_type="application/json", **headers,
            ).status_code, 201)
            self.assertEqual(self.client.patch(
                reverse("api:supplier-detail", args=[supplier_id]),
                {"city": "Sikasso"}, content_type="application/json", **headers,
            ).status_code, 200)
            self.assertEqual(self.client.delete(
                reverse("api:supplier-detail", args=[supplier_id]), **headers,
            ).status_code, 204)

        with patch("api.views.stock_detail", return_value={
            "id": product_id, "code": "PRD-API-001", "name": "Cola API",
            "closing_stock": Decimal("35"), "stock_status": "OK",
        }):
            response = self.client.get(
                reverse("api:stock-detail", args=[product_id]), **headers,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["stock_status"], "OK")

    def test_p0_sale_detail_update_and_cancel_routes_are_available(self):
        self.client.force_login(self.user)
        headers = {"HTTP_X_COMPANY_ID": str(self.company.id)}
        sale_id = uuid4()
        sale = {
            "id": sale_id, "sale_number": "VTE-API-001",
            "customer_id": None, "payment_method": "CASH",
            "payment_status": "PAID", "notes": "",
        }
        with patch("api.views.sale_detail", return_value=(sale, [])), patch(
            "api.views.update_sale_metadata",
            return_value={"id": sale_id, "number": "VTE-API-001"},
        ), patch(
            "api.views.cancel_sale",
            return_value={"id": sale_id, "number": "VTE-API-001", "returned_lines": 1},
        ):
            detail = self.client.get(
                reverse("api:sale-detail", args=[sale_id]), **headers,
            )
            updated = self.client.patch(
                reverse("api:sale-detail", args=[sale_id]),
                {"payment_status": "PARTIAL"},
                content_type="application/json", **headers,
            )
            cancelled = self.client.delete(
                reverse("api:sale-detail", args=[sale_id]), **headers,
            )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(cancelled.status_code, 204)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    FORECAST_MAX_DATA_AGE_DAYS=3,
)
class ForecastApiCeleryEndToEndTests(TransactionTestCase):
    """Exécute réellement API → tâche Celery → pipeline ML → persistance."""

    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL

        from app.database import session as app_session

        database = connection.settings_dict
        self._application_session = app_session
        self._application_engine = app_session.engine
        self._test_application_engine = create_engine(
            URL.create(
                "postgresql+psycopg",
                username=database["USER"],
                password=database["PASSWORD"],
                host=database["HOST"],
                port=int(database["PORT"]),
                database=database["NAME"],
            ),
            pool_pre_ping=True,
        )
        app_session._SessionFactory.configure(bind=self._test_application_engine)

        self.user = User.objects.create_user(
            email="forecast-e2e@example.com", password="Forecast-test-2026",
            full_name="Prévision E2E",
        )
        self.company = Company.objects.create(code="forecast-api-e2e", name="Dépôt ML E2E")
        Membership.objects.create(
            user=self.user, company=self.company, role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )
        bootstrap_company_references(self.company.id)
        self.product_id = uuid4()
        self._seed_history()
        self.client.force_login(self.user)

    def tearDown(self):
        self._application_session._SessionFactory.configure(
            bind=self._application_engine
        )
        self._test_application_engine.dispose()
        cache.clear()

    def _fixture_teardown(self):
        """Nettoie aussi les tables SQL métier non gérées par Django."""
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE companies, users, calendar_features RESTART IDENTITY CASCADE"
            )
        cache.clear()

    def _seed_history(self):
        start = date.today() - timedelta(days=159)
        with tenant_cursor(self.company.id) as cursor:
            cursor.execute(
                "SELECT id FROM product_categories WHERE company_id=%s ORDER BY code LIMIT 1",
                [str(self.company.id)],
            )
            category_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO products (
                    id, company_id, code, name, brand, category_id,
                    package_type, units_per_package, purchase_price,
                    selling_price, minimum_stock, reorder_quantity,
                    created_by_user_id, updated_by_user_id
                ) VALUES (%s,%s,'PRD-ML-E2E','Cola ML E2E','NexaStock',%s,
                          'CARTON',24,4000,5000,20,80,%s,%s)
            """, [self.product_id, self.company.id, category_id, self.user.id, self.user.id])

            sales, sale_items, stocks, calendar = [], [], [], []
            for index in range(160):
                day = start + timedelta(days=index)
                sale_id = uuid4()
                quantity = Decimal(str(5 + (index % 7) + (2 if day.weekday() >= 5 else 0)))
                total = quantity * Decimal("5000")
                sales.append((
                    sale_id, self.company.id, f"VTE-ML-{index:04d}", day,
                    total, total, self.user.id, self.user.id,
                ))
                sale_items.append((
                    uuid4(), self.company.id, sale_id, self.product_id,
                    quantity, quantity * 24, total, quantity * Decimal("4000"),
                ))
                stocks.append((
                    uuid4(), self.company.id, day, self.product_id,
                    Decimal("1000"), quantity, Decimal("1000") - quantity,
                ))
                calendar.append((
                    uuid4(), day, day.isoweekday(),
                    day.isocalendar().week, day.month, ((day.month - 1) // 3) + 1,
                    day.weekday() >= 5, Decimal("31.5"), Decimal(str(index % 4)),
                ))
            cursor.executemany("""
                INSERT INTO sales (
                    id, company_id, sale_number, sale_date, sale_time,
                    payment_method, payment_status, subtotal, discount_amount,
                    total_amount, created_by_user_id, updated_by_user_id
                ) VALUES (%s,%s,%s,%s,'10:00','CASH','PAID',%s,0,%s,%s,%s)
            """, sales)
            cursor.executemany("""
                INSERT INTO sale_items (
                    id, company_id, sale_id, product_id, quantity_packages,
                    units_per_package, quantity_units, unit_price,
                    discount_amount, total_amount, unit_cost, gross_margin
                ) VALUES (%s,%s,%s,%s,%s,24,%s,5000,0,%s,4000,%s)
            """, sale_items)
            cursor.executemany("""
                INSERT INTO daily_stocks (
                    id, company_id, stock_date, product_id, opening_stock,
                    quantity_sold, closing_stock, minimum_stock, stockout_flag
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,20,FALSE)
            """, stocks)
            cursor.executemany("""
                INSERT INTO calendar_features (
                    id, calendar_date, day_of_week, week_number,
                    month_number, quarter_number, is_weekend,
                    temperature_average, rainfall
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, calendar)

    def test_forecast_reaches_success_through_real_eager_celery_task(self):
        from config.celery import app as celery_app

        previous_eager = celery_app.conf.task_always_eager
        previous_propagates = celery_app.conf.task_eager_propagates
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True
        try:
            response = self.client.post(
                reverse("api:forecast-jobs"),
                {"product_id": str(self.product_id), "horizon": 3},
                content_type="application/json",
                HTTP_X_COMPANY_ID=str(self.company.id),
                HTTP_IDEMPOTENCY_KEY="forecast-e2e-2026-0001",
            )
        finally:
            celery_app.conf.task_always_eager = previous_eager
            celery_app.conf.task_eager_propagates = previous_propagates

        self.assertEqual(response.status_code, 202, response.content)
        job_id = response.json()["data"]["id"]
        result = self.client.get(
            reverse("api:forecast-job-result", args=[job_id]),
            HTTP_X_COMPANY_ID=str(self.company.id),
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertIn("forecast_id", result.json()["data"])
        self.assertTrue(AuditLog.objects.filter(resource_type="forecast").exists())
