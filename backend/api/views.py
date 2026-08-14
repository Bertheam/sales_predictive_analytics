from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import OpenApiParameter, extend_schema

from audit.models import AuditLog
from audit.services import record_audit
from companies.models import Company, Membership
from dashboard.data import get_dashboard_snapshot
from decisions.models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt
from forecasting.data import get_product_freshness
from forecasting.models import ForecastJob
from forecasting.tasks import generate_product_forecast
from operations.data import (
    cancel_sale, create_manual_movement, create_receipt, create_sale,
    customer_catalog, get_customer, get_product, get_supplier,
    inventory_history, operational_references, product_catalog, receipt_detail,
    sale_detail, sales_overview, save_customer, save_product, save_supplier,
    set_customer_archived, set_product_archived, set_supplier_archived,
    stock_detail, stock_overview, supplier_catalog, update_sale_metadata,
)
from operations.receipts import render_sale_document

from .idempotency import idempotent
from .pagination import MobilePagination
from .permissions import CompanyRolePermission, FORECAST_ROLES
from .serializers import (
    ActiveMembershipTokenRefreshSerializer, CustomerWriteSerializer,
    EmptySerializer, ForecastJobSerializer,
    ForecastJobWriteSerializer, LoginSerializer, MembershipSerializer,
    MovementWriteSerializer, OrderReceiveSerializer, ProductWriteSerializer,
    PurchaseOrderReceiptSerializer, PurchaseOrderSerializer,
    PurchaseOrderWriteSerializer, ReceiptWriteSerializer, SaleUpdateSerializer,
    SaleWriteSerializer, SupplierWriteSerializer,
)
from .tenant import require_api_company
from .throttling import LoginRateThrottle


@extend_schema(parameters=[
    OpenApiParameter(
        name="X-Company-ID", type=str, location=OpenApiParameter.HEADER,
        required=True,
        description="Identifiant UUID du dépôt actif. L'utilisateur doit y posséder une adhésion active.",
    ),
    OpenApiParameter(
        name="Idempotency-Key", type=str, location=OpenApiParameter.HEADER,
        required=False,
        description="Clé unique recommandée pour rejouer sans doublon une mutation mobile (POST, PATCH ou DELETE).",
    ),
])
class CompanyAPIView(APIView):
    permission_classes = [CompanyRolePermission]

    def initial(self, request, *args, **kwargs):
        self.format_kwarg = self.get_format_suffix(**kwargs)
        neg = self.perform_content_negotiation(request)
        request.accepted_renderer, request.accepted_media_type = neg
        version, scheme = self.determine_version(request, *args, **kwargs)
        request.version, request.versioning_scheme = version, scheme
        self.perform_authentication(request)
        _, error = require_api_company(request)
        if error:
            from rest_framework.exceptions import APIException
            exc = APIException(error.data.get("detail"), code=error.data.get("code"))
            exc.status_code = error.status_code
            exc.detail = error.data
            raise exc
        self.check_permissions(request)
        self.check_throttles(request)

    def paginate(self, request, rows):
        paginator = MobilePagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response(page)
        response.data["company_id"] = str(request.company.id)
        return response


class LoginView(APIView):
    serializer_class = LoginSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, username=serializer.validated_data["identifier"], password=serializer.validated_data["password"])
        if not user:
            return Response({"code": "invalid_credentials", "message": "Identifiant ou mot de passe incorrect."}, status=401)
        memberships = Membership.objects.select_related("company").filter(user=user, status=Membership.Status.ACTIVE, company__status=Company.Status.ACTIVE)
        if not memberships.exists():
            return Response({
                "code": "no_active_membership",
                "message": "Votre accès aux dépôts est suspendu ou indisponible.",
            }, status=403)
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token), "refresh": str(refresh),
            "access_expires_in": int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
            "user": {"id": user.id, "email": user.email, "phone": user.phone, "full_name": user.full_name},
            "companies": MembershipSerializer(memberships, many=True).data,
        })


class ActiveMembershipTokenRefreshView(TokenRefreshView):
    serializer_class = ActiveMembershipTokenRefreshSerializer


class LogoutView(APIView):
    serializer_class = EmptySerializer
    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except Exception:
            raise ValidationError({"refresh": ["Jeton refresh invalide."]})
        return Response(status=204)


class MeView(APIView):
    serializer_class = EmptySerializer
    def get(self, request):
        return Response({"id": request.user.id, "email": request.user.email, "phone": request.user.phone, "full_name": request.user.full_name})


class CompanyListView(APIView):
    serializer_class = MembershipSerializer
    def get(self, request):
        qs = Membership.objects.select_related("company").filter(user=request.user, status=Membership.Status.ACTIVE, company__status=Company.Status.ACTIVE)
        return Response(MembershipSerializer(qs, many=True).data)


class ContextView(CompanyAPIView):
    serializer_class = EmptySerializer
    def get(self, request):
        return Response({"user": {"id": request.user.id, "email": request.user.email}, "company": {"id": request.company.id, "code": request.company.code, "name": request.company.name}, "role": request.membership.role})


class DashboardSummaryView(CompanyAPIView):
    serializer_class = EmptySerializer
    def get(self, request):
        snapshot = get_dashboard_snapshot(request.company.id)
        return Response({"company_id": str(request.company.id), "ready": snapshot.ready, "period": {"start": snapshot.min_date, "end": snapshot.max_date}, "revenue": snapshot.revenue, "sales_count": snapshot.sales_count, "quantity_sold": snapshot.quantity_sold, "current_stock": snapshot.current_stock, "risk_products": snapshot.risk_products, "active_products": snapshot.active_products})


class ProductListView(CompanyAPIView):
    serializer_class = ProductWriteSerializer
    @extend_schema(operation_id="products_list")
    def get(self, request):
        state = request.query_params.get("status", "active")
        if state not in {"all", "active", "inactive"}: raise ValidationError({"status": ["Filtre invalide."]})
        ordering = request.query_params.get("ordering", "name")
        if ordering.lstrip("-") not in {"name", "code", "selling_price"}: raise ValidationError({"ordering": ["Tri invalide."]})
        _, page_size, offset = MobilePagination.database_page(request)
        rows, summary = product_catalog(
            request.company.id, query=request.query_params.get("q", "")[:100],
            status=state, ordering=ordering, limit=page_size, offset=offset,
        )
        return MobilePagination.database_response(
            request, rows, summary["filtered_count"], company_id=request.company.id
        )

    @idempotent
    def post(self, request):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = {"brand": "", "volume_value": None, "volume_unit": "", **serializer.validated_data}
        try:
            result = save_product(request.company.id, values, user_id=request.user.id)
        except (ValueError, IntegrityError) as exc:
            raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="product", resource_id=result["id"], description=f"Création API du produit {result['code']}.")
        return Response({"data": result}, status=201)


class ProductDetailView(CompanyAPIView):
    serializer_class = ProductWriteSerializer

    def get_object(self, request, product_id):
        product = get_product(request.company.id, product_id)
        if not product:
            raise NotFound("Produit introuvable.")
        return product

    @extend_schema(operation_id="products_retrieve")
    def get(self, request, product_id):
        return Response({"data": self.get_object(request, product_id)})

    @idempotent
    def patch(self, request, product_id):
        current = self.get_object(request, product_id)
        serializer = ProductWriteSerializer(data={**current, **request.data})
        serializer.is_valid(raise_exception=True)
        try:
            result = save_product(request.company.id, serializer.validated_data, product_id, user_id=request.user.id)
        except (ValueError, IntegrityError) as exc:
            raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.UPDATE, resource_type="product", resource_id=result["id"], description=f"Modification API du produit {result['code']}.")
        return Response({"data": result})

    @idempotent
    def delete(self, request, product_id):
        result = set_product_archived(request.company.id, product_id, archived=True, user_id=request.user.id)
        if not result:
            raise NotFound("Produit introuvable.")
        record_audit(request, action=AuditLog.Action.DELETE, resource_type="product", resource_id=result["id"], description=f"Archivage API du produit {result['code']}.", metadata={"logical_deletion": True})
        return Response(status=204)


class CustomerListView(CompanyAPIView):
    serializer_class = CustomerWriteSerializer

    @extend_schema(operation_id="customers_list")
    def get(self, request):
        state = request.query_params.get("status", "active")
        if state not in {"all", "active", "inactive"}: raise ValidationError({"status": ["Filtre invalide."]})
        ordering = request.query_params.get("ordering", "name")
        if ordering.lstrip("-") not in {"name", "code", "city"}: raise ValidationError({"ordering": ["Tri invalide."]})
        _, page_size, offset = MobilePagination.database_page(request)
        rows, summary = customer_catalog(request.company.id, query=request.query_params.get("q", "")[:100], status=state, ordering=ordering, limit=page_size, offset=offset)
        return MobilePagination.database_response(request, rows, summary["filtered_count"], company_id=request.company.id)

    @idempotent
    def post(self, request):
        serializer = CustomerWriteSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        values = {"phone": None, "zone": None, "district": None, "city": "", "is_active": True, **serializer.validated_data}
        try: result = save_customer(request.company.id, values, user_id=request.user.id)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="customer", resource_id=result["id"], description=f"Création API du client {result['code']}.")
        return Response({"data": result}, status=201)


class CustomerDetailView(CompanyAPIView):
    serializer_class = CustomerWriteSerializer
    def get_object(self, request, customer_id):
        row = get_customer(request.company.id, customer_id)
        if not row: raise NotFound("Client introuvable.")
        return row
    @extend_schema(operation_id="customers_retrieve")
    def get(self, request, customer_id): return Response({"data": self.get_object(request, customer_id)})
    @idempotent
    def patch(self, request, customer_id):
        serializer = CustomerWriteSerializer(data={**self.get_object(request, customer_id), **request.data}); serializer.is_valid(raise_exception=True)
        try: result = save_customer(request.company.id, serializer.validated_data, customer_id, user_id=request.user.id)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.UPDATE, resource_type="customer", resource_id=result["id"], description=f"Modification API du client {result['code']}.")
        return Response({"data": result})
    @idempotent
    def delete(self, request, customer_id):
        result = set_customer_archived(request.company.id, customer_id, archived=True, user_id=request.user.id)
        if not result: raise NotFound("Client introuvable.")
        record_audit(request, action=AuditLog.Action.DELETE, resource_type="customer", resource_id=result["id"], description=f"Archivage API du client {result['code']}.", metadata={"logical_deletion": True})
        return Response(status=204)


class SupplierListView(CompanyAPIView):
    serializer_class = SupplierWriteSerializer
    @extend_schema(operation_id="suppliers_list")
    def get(self, request):
        state = request.query_params.get("status", "active")
        if state not in {"all", "active", "inactive"}: raise ValidationError({"status": ["Filtre invalide."]})
        ordering = request.query_params.get("ordering", "name")
        if ordering.lstrip("-") not in {"name", "code", "city"}: raise ValidationError({"ordering": ["Tri invalide."]})
        _, page_size, offset = MobilePagination.database_page(request)
        rows, summary = supplier_catalog(request.company.id, query=request.query_params.get("q", "")[:100], status=state, ordering=ordering, limit=page_size, offset=offset)
        return MobilePagination.database_response(request, rows, summary["filtered_count"], company_id=request.company.id)
    @idempotent
    def post(self, request):
        serializer = SupplierWriteSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        values = {"phone": None, "city": None, "is_active": True, **serializer.validated_data}
        try: result = save_supplier(request.company.id, values, user_id=request.user.id)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="supplier", resource_id=result["id"], description=f"Création API du fournisseur {result['code']}.")
        return Response({"data": result}, status=201)


class SupplierDetailView(CompanyAPIView):
    serializer_class = SupplierWriteSerializer
    def get_object(self, request, supplier_id):
        row = get_supplier(request.company.id, supplier_id)
        if not row: raise NotFound("Fournisseur introuvable.")
        return row
    @extend_schema(operation_id="suppliers_retrieve")
    def get(self, request, supplier_id): return Response({"data": self.get_object(request, supplier_id)})
    @idempotent
    def patch(self, request, supplier_id):
        serializer = SupplierWriteSerializer(data={**self.get_object(request, supplier_id), **request.data}); serializer.is_valid(raise_exception=True)
        try: result = save_supplier(request.company.id, serializer.validated_data, supplier_id, user_id=request.user.id)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.UPDATE, resource_type="supplier", resource_id=result["id"], description=f"Modification API du fournisseur {result['code']}.")
        return Response({"data": result})
    @idempotent
    def delete(self, request, supplier_id):
        result = set_supplier_archived(request.company.id, supplier_id, archived=True, user_id=request.user.id)
        if not result: raise NotFound("Fournisseur introuvable.")
        record_audit(request, action=AuditLog.Action.DELETE, resource_type="supplier", resource_id=result["id"], description=f"Archivage API du fournisseur {result['code']}.", metadata={"logical_deletion": True})
        return Response(status=204)


class StockListView(CompanyAPIView):
    serializer_class = EmptySerializer
    @extend_schema(operation_id="stocks_list")
    def get(self, request):
        state = request.query_params.get("status", "all")
        if state not in {"all", "OK", "LOW", "OUT", "UNTRACKED"}: raise ValidationError({"status": ["Filtre invalide."]})
        ordering = request.query_params.get("ordering", "name")
        if ordering.lstrip("-") not in {"name", "code", "stock"}: raise ValidationError({"ordering": ["Tri invalide."]})
        _, page_size, offset = MobilePagination.database_page(request)
        rows, summary = stock_overview(request.company.id, query=request.query_params.get("q", "")[:100], stock_status=state, ordering=ordering, limit=page_size, offset=offset)
        return MobilePagination.database_response(request, rows, summary["filtered_count"], company_id=request.company.id)


class StockDetailView(CompanyAPIView):
    serializer_class = EmptySerializer
    @extend_schema(operation_id="stocks_retrieve")
    def get(self, request, product_id):
        row = stock_detail(request.company.id, product_id)
        if not row: raise NotFound("Stock introuvable.")
        return Response({"data": row})


class SaleListView(CompanyAPIView):
    serializer_class = SaleWriteSerializer
    @extend_schema(operation_id="sales_list")
    def get(self, request):
        ordering = request.query_params.get("ordering", "-date")
        if ordering.lstrip("-") not in {"date", "sale_number", "total", "customer"}: raise ValidationError({"ordering": ["Tri invalide."]})
        _, page_size, offset = MobilePagination.database_page(request)
        rows, summary, _, _ = sales_overview(
            request.company.id, query=request.query_params.get("q", "")[:100],
            ordering=ordering, limit=page_size, offset=offset,
        )
        return MobilePagination.database_response(
            request, rows, summary["filtered_count"], company_id=request.company.id
        )

    @idempotent
    def post(self, request):
        serializer = SaleWriteSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data); lines = values.pop("items")
        try: result = create_sale(request.company.id, request.user.id, values, lines, request.user.full_name or request.user.login_identifier)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"items": [str(exc)]})
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="sale", resource_id=result["id"], description=f"Création API de la vente {result['number']}.", metadata={"total": str(result["total"])})
        return Response({"data": {"id": result["id"], "number": result["number"], "total": result["total"]}}, status=201)


class SaleDetailView(CompanyAPIView):
    serializer_class = SaleUpdateSerializer
    def get_object(self, request, sale_id):
        sale, items = sale_detail(request.company.id, sale_id)
        if not sale: raise NotFound("Vente introuvable.")
        return sale, items
    @extend_schema(operation_id="sales_retrieve")
    def get(self, request, sale_id):
        sale, items = self.get_object(request, sale_id)
        sale["items"] = items
        return Response({"data": sale})

    @idempotent
    def patch(self, request, sale_id):
        sale, _ = self.get_object(request, sale_id)
        serializer = SaleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = {
            "customer_id": sale["customer_id"],
            "payment_method": sale["payment_method"],
            "payment_status": sale["payment_status"],
            "notes": sale["notes"],
            **serializer.validated_data,
        }
        try: result = update_sale_metadata(request.company.id, sale_id, request.user.id, values)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.UPDATE, resource_type="sale", resource_id=result["id"], description=f"Modification API de la vente {result['number']}.")
        return Response({"data": result})

    @idempotent
    def delete(self, request, sale_id):
        result = cancel_sale(request.company.id, sale_id, request.user.id)
        if not result: raise NotFound("Vente introuvable.")
        record_audit(request, action=AuditLog.Action.DELETE, resource_type="sale", resource_id=result["id"], description=f"Annulation API de la vente {result['number']} et retour du stock.", metadata={"logical_deletion": True, "returned_lines": result["returned_lines"]})
        return Response(status=204)


class SaleReceiptView(CompanyAPIView):
    serializer_class = EmptySerializer
    def get(self, request, sale_id):
        from django.http import HttpResponse
        sale, items = sale_detail(request.company.id, sale_id)
        if not sale:
            raise NotFound("Vente introuvable.")
        response = HttpResponse(
            render_sale_document(sale, items, request.company),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="recu-{sale["sale_number"]}.pdf"'
        return response


class MovementListView(CompanyAPIView):
    serializer_class = MovementWriteSerializer
    def get(self, request):
        _, rows = inventory_history(request.company.id, limit=100)
        return self.paginate(request, rows)
    @idempotent
    def post(self, request):
        serializer = MovementWriteSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        try: result = create_manual_movement(request.company.id, request.user.id, serializer.validated_data)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"non_field_errors": [str(exc)]})
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="stock_movement", resource_id=result["id"], description=f"Création API du mouvement {result['number']}.")
        return Response({"data": result}, status=201)


class ReceiptListView(CompanyAPIView):
    serializer_class = ReceiptWriteSerializer
    @extend_schema(operation_id="receipts_list")
    def get(self, request):
        rows, _ = inventory_history(request.company.id, limit=100)
        return self.paginate(request, rows)
    @idempotent
    def post(self, request):
        serializer = ReceiptWriteSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data); lines = values.pop("items")
        try: result = create_receipt(request.company.id, request.user.id, values, lines)
        except (ValueError, IntegrityError) as exc: raise ValidationError({"items": [str(exc)]})
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="purchase_receipt", resource_id=result["id"], description=f"Création API de la réception {result['number']}.")
        return Response({"data": result}, status=201)


class ReceiptDetailView(CompanyAPIView):
    serializer_class = EmptySerializer
    @extend_schema(operation_id="receipts_retrieve")
    def get(self, request, receipt_id):
        row = receipt_detail(request.company.id, receipt_id)
        if not row: raise NotFound("Réception introuvable.")
        return Response({"data": row})


class PurchaseOrderListView(CompanyAPIView):
    serializer_class = PurchaseOrderSerializer
    @extend_schema(operation_id="purchase_orders_list")
    def get(self, request):
        qs = PurchaseOrder.objects.filter(company=request.company).prefetch_related("items")
        state = request.query_params.get("status")
        if state: qs = qs.filter(status=state)
        paginator = MobilePagination(); page = paginator.paginate_queryset(qs, request, self)
        return paginator.get_paginated_response(PurchaseOrderSerializer(page, many=True).data)
    @idempotent
    def post(self, request):
        serializer = PurchaseOrderWriteSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        data = serializer.validated_data; items = data.pop("items")
        references = operational_references(request.company.id)
        suppliers = {str(row["id"]): row for row in references["suppliers"]}
        products = {str(row["id"]): row for row in references["products"]}
        supplier = suppliers.get(str(data["supplier_id"]))
        if not supplier:
            raise ValidationError({"supplier_id": ["Fournisseur introuvable dans ce dépôt."]})
        data["supplier_name"] = supplier["name"]
        prepared_items = []
        for line in items:
            product = products.get(str(line["product_id"]))
            if not product:
                raise ValidationError({"items": ["Un produit est introuvable dans ce dépôt."]})
            prepared_items.append({**line, "product_code": product["code"], "product_name": product["name"]})
        with transaction.atomic():
            order = PurchaseOrder.objects.create(company=request.company, order_number=PurchaseOrder.new_number(), created_by=request.user, updated_by=request.user, **data)
            PurchaseOrderItem.objects.bulk_create([PurchaseOrderItem(order=order, **line) for line in prepared_items])
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="purchase_order", resource_id=order.id, description=f"Création API de la commande {order.order_number}.")
        return Response({"data": PurchaseOrderSerializer(order).data}, status=201)


class PurchaseOrderDetailView(CompanyAPIView):
    serializer_class = PurchaseOrderSerializer
    def get_object(self, request, order_id, lock=False):
        qs = PurchaseOrder.objects.filter(company=request.company).prefetch_related("items")
        if lock: qs = qs.select_for_update()
        return get_object_or_404(qs, id=order_id)
    @extend_schema(operation_id="purchase_orders_retrieve")
    def get(self, request, order_id): return Response({"data": PurchaseOrderSerializer(self.get_object(request, order_id)).data})


class PurchaseOrderActionView(PurchaseOrderDetailView):
    http_method_names = ["post", "options"]
    @idempotent
    def post(self, request, order_id, action):
        with transaction.atomic():
            order = self.get_object(request, order_id, lock=True)
            if action == "send" and order.status == PurchaseOrder.Status.DRAFT:
                order.status, order.sent_at = PurchaseOrder.Status.SENT, timezone.now()
            elif action == "cancel" and order.status not in {PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED} and order.received_quantity == 0:
                order.status, order.cancelled_at = PurchaseOrder.Status.CANCELLED, timezone.now()
            else: raise ValidationError({"status": ["Transition de commande interdite."]})
            order.updated_by = request.user; order.save()
        record_audit(
            request,
            action=AuditLog.Action.DELETE if action == "cancel" else AuditLog.Action.UPDATE,
            resource_type="purchase_order", resource_id=order.id,
            description=(
                f"Annulation API de la commande {order.order_number}."
                if action == "cancel"
                else f"Commande {order.order_number} marquée envoyée via l'API."
            ),
            metadata={"logical_deletion": action == "cancel"},
        )
        return Response({"data": PurchaseOrderSerializer(order).data})


class PurchaseOrderReceiveView(PurchaseOrderDetailView):
    serializer_class = OrderReceiveSerializer
    http_method_names = ["post", "options"]
    @idempotent
    def post(self, request, order_id):
        serializer = OrderReceiveSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            order = self.get_object(request, order_id, lock=True)
            if order.status in {PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED}: raise ValidationError({"status": ["Cette commande ne peut plus être réceptionnée."]})
            locked = {str(i.id): i for i in PurchaseOrderItem.objects.select_for_update().filter(order=order)}
            lines = []
            for line in serializer.validated_data["items"]:
                item = locked.get(str(line["item_id"]))
                if not item: raise ValidationError({"items": ["Une ligne n'appartient pas à cette commande."]})
                if line["quantity_packages"] > item.remaining_quantity: raise ValidationError({"items": ["Une quantité dépasse le reliquat."]})
                lines.append({"product_id": str(item.product_id), "quantity_packages": line["quantity_packages"], "unit_cost": line["unit_cost"]})
            receipt = create_receipt(request.company.id, request.user.id, {"supplier_id": str(order.supplier_id), "receipt_date": serializer.validated_data["receipt_date"]}, lines)
            total = Decimal("0")
            for source, line in zip(serializer.validated_data["items"], lines):
                item = locked[str(source["item_id"])]; item.quantity_received += line["quantity_packages"]; item.unit_cost = line["unit_cost"]; item.save(); total += line["quantity_packages"]
            order.status = PurchaseOrder.Status.PARTIALLY_RECEIVED if any(i.remaining_quantity > 0 for i in locked.values()) else PurchaseOrder.Status.RECEIVED
            order.received_at = timezone.now() if order.status == PurchaseOrder.Status.RECEIVED else None; order.updated_by = request.user; order.save()
            PurchaseOrderReceipt.objects.create(order=order, receipt_id=receipt["id"], receipt_number=receipt["number"], quantity_received=total, created_by=request.user)
        record_audit(request, action=AuditLog.Action.CREATE, resource_type="purchase_order_receipt", resource_id=receipt["id"], description=f"Réception API {receipt['number']} liée à la commande {order.order_number}.", metadata={"order_id": str(order.id), "quantity": str(total)})
        return Response({"data": receipt}, status=201)


class PurchaseOrderReceiptListView(CompanyAPIView):
    serializer_class = PurchaseOrderReceiptSerializer
    def get(self, request):
        qs = PurchaseOrderReceipt.objects.filter(order__company=request.company).select_related("order")
        paginator = MobilePagination(); page = paginator.paginate_queryset(qs, request, self)
        return paginator.get_paginated_response(PurchaseOrderReceiptSerializer(page, many=True).data)


class ForecastJobListView(CompanyAPIView):
    serializer_class = ForecastJobSerializer
    write_roles = FORECAST_ROLES
    @extend_schema(operation_id="forecast_jobs_list")
    def get(self, request):
        qs = ForecastJob.objects.filter(company=request.company).select_related("requested_by")
        paginator = MobilePagination(); page = paginator.paginate_queryset(qs, request, self)
        return paginator.get_paginated_response(ForecastJobSerializer(page, many=True).data)
    @idempotent
    def post(self, request):
        serializer = ForecastJobWriteSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        fresh = get_product_freshness(request.company.id, serializer.validated_data["product_id"])
        if not fresh.get("exists"): raise ValidationError({"product_id": ["Produit introuvable dans ce dépôt."]})
        if fresh.get("last_sale_date") is None or fresh["age_days"] > settings.FORECAST_MAX_DATA_AGE_DAYS: raise ValidationError({"product_id": ["Les ventes de ce produit ne sont pas assez récentes."]})
        try: job = ForecastJob.objects.create(company=request.company, product_id=serializer.validated_data["product_id"], product_name=fresh["product_name"], requested_by=request.user, horizon=serializer.validated_data["horizon"])
        except IntegrityError: raise ValidationError({"product_id": ["Une prévision est déjà active pour ce produit."]})
        try:
            task = generate_product_forecast.delay(str(job.id)); job.celery_task_id = task.id; job.save(update_fields=["celery_task_id"])
        except Exception:
            job.delete(); raise ValidationError({"non_field_errors": ["Le moteur de traitements est indisponible."]})
        return Response({"data": ForecastJobSerializer(job).data, "status_url": request.build_absolute_uri(f"{job.id}/")}, status=202)


class ForecastJobDetailView(CompanyAPIView):
    serializer_class = ForecastJobSerializer
    def get_object(self, request, job_id): return get_object_or_404(ForecastJob, company=request.company, id=job_id)
    @extend_schema(operation_id="forecast_jobs_retrieve")
    def get(self, request, job_id): return Response({"data": ForecastJobSerializer(self.get_object(request, job_id)).data})


class ForecastJobResultView(ForecastJobDetailView):
    serializer_class = ForecastJobSerializer
    def get(self, request, job_id):
        job = self.get_object(request, job_id)
        if job.status != ForecastJob.Status.SUCCESS: return Response({"code": "forecast_not_ready", "message": "La prévision n'est pas encore disponible.", "status": job.status}, status=409)
        return Response({"data": job.result})


class ForecastJobRetryView(ForecastJobDetailView):
    serializer_class = EmptySerializer
    write_roles = FORECAST_ROLES
    http_method_names = ["post", "options"]
    @idempotent
    def post(self, request, job_id):
        job = self.get_object(request, job_id)
        if job.status != ForecastJob.Status.FAILED: raise ValidationError({"status": ["Seul un job en échec peut être relancé."]})
        job.status = ForecastJob.Status.QUEUED; job.error_message = ""; job.completed_at = None; job.save()
        task = generate_product_forecast.delay(str(job.id)); job.celery_task_id = task.id; job.save(update_fields=["celery_task_id"])
        return Response({"data": ForecastJobSerializer(job).data}, status=202)
