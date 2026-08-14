from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from accounts.models import User
from companies.models import Company, Membership
from decisions.models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt
from forecasting.models import ForecastJob
from operations.forms import MovementForm, ReceiptForm, SaleForm


class EmptySerializer(serializers.Serializer):
    pass


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "code", "name", "city", "currency", "timezone", "status")


class MembershipSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "company", "role", "role_label", "status", "joined_at")


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class ActiveMembershipTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        user_id = refresh.get("user_id")
        has_access = User.objects.filter(id=user_id, is_active=True).exists() and Membership.objects.filter(
            user_id=user_id,
            status=Membership.Status.ACTIVE,
            company__status=Company.Status.ACTIVE,
        ).exists()
        if not has_access:
            raise AuthenticationFailed(
                "Votre accès aux dépôts est suspendu ou indisponible.",
                code="no_active_membership",
            )
        return super().validate(attrs)


class SaleItemWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity_packages = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, default=0)


class SaleWriteSerializer(serializers.Serializer):
    sale_date = serializers.DateField()
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(choices=SaleForm.PAYMENT_METHODS)
    payment_status = serializers.ChoiceField(choices=SaleForm.PAYMENT_STATUS)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    items = SaleItemWriteSerializer(many=True, allow_empty=False)


class SaleUpdateSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(
        choices=SaleForm.PAYMENT_METHODS, required=False
    )
    payment_status = serializers.ChoiceField(
        choices=SaleForm.PAYMENT_STATUS, required=False
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=500
    )


class ProductWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    brand = serializers.CharField(max_length=120, required=False, allow_blank=True)
    category_id = serializers.UUIDField()
    volume_value = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True, min_value=0
    )
    volume_unit = serializers.ChoiceField(
        choices=("CL", "ML", "L"), required=False, allow_blank=True
    )
    package_type = serializers.ChoiceField(
        choices=("CARTON", "PACK", "CASIER", "UNITE")
    )
    units_per_package = serializers.IntegerField(min_value=1)
    purchase_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    selling_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    minimum_stock = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    reorder_quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    is_active = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if attrs.get("selling_price") is not None and attrs.get("purchase_price") is not None:
            if attrs["selling_price"] < attrs["purchase_price"]:
                raise serializers.ValidationError({"selling_price": "Le prix de vente ne peut pas être inférieur au prix d'achat."})
        if attrs.get("volume_value") and not attrs.get("volume_unit"):
            raise serializers.ValidationError({"volume_unit": "Indiquez l'unité du volume."})
        return attrs


class CustomerWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    customer_type_id = serializers.UUIDField()
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    zone = serializers.CharField(max_length=120, required=False, allow_blank=True, allow_null=True)
    district = serializers.CharField(max_length=120, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True, default="Bamako")
    is_active = serializers.BooleanField(default=True)


class SupplierWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField(default=True)


class MovementWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    movement_type = serializers.ChoiceField(choices=MovementForm.MOVEMENTS)
    movement_date = serializers.DateField()
    quantity_packages = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(min_length=5, max_length=500)


class ReceiptItemWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity_packages = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class ReceiptWriteSerializer(serializers.Serializer):
    receipt_date = serializers.DateField()
    supplier_id = serializers.UUIDField()
    items = ReceiptItemWriteSerializer(many=True, allow_empty=False)


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    remaining_quantity = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = ("id", "product_id", "product_code", "product_name", "quantity_ordered", "quantity_received", "remaining_quantity", "unit_cost")


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = ("id", "order_number", "supplier_id", "supplier_name", "status", "expected_date", "notes", "items", "created_at", "updated_at")


class PurchaseOrderItemWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_code = serializers.CharField(max_length=40, required=False, allow_blank=True)
    product_name = serializers.CharField(max_length=180, required=False, allow_blank=True)
    quantity_ordered = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal("0.01"))
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, default=0)


class PurchaseOrderWriteSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    supplier_name = serializers.CharField(max_length=180, required=False, allow_blank=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    items = PurchaseOrderItemWriteSerializer(many=True, allow_empty=False)


class OrderReceiveLineSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity_packages = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal("0.01"))
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class OrderReceiveSerializer(serializers.Serializer):
    receipt_date = serializers.DateField()
    items = OrderReceiveLineSerializer(many=True, allow_empty=False)


class PurchaseOrderReceiptSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = PurchaseOrderReceipt
        fields = ("id", "order", "order_number", "receipt_id", "receipt_number", "quantity_received", "created_at")


class ForecastJobSerializer(serializers.ModelSerializer):
    error = serializers.SerializerMethodField()

    class Meta:
        model = ForecastJob
        fields = ("id", "product_id", "product_name", "status", "horizon", "model_name", "forecast_id", "forecast_number", "result", "error", "requested_at", "started_at", "completed_at")

    def get_error(self, obj) -> dict | None:
        return {"code": "forecast_failed", "message": "La prévision a échoué. Vous pouvez la relancer."} if obj.status == ForecastJob.Status.FAILED else None


class ForecastJobWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    horizon = serializers.IntegerField(min_value=1, max_value=7, default=7)
