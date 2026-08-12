from decimal import Decimal

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone


class ProductForm(forms.Form):
    PACKAGE_CHOICES = (
        ("CARTON", "Carton"),
        ("PACK", "Pack"),
        ("CASIER", "Casier"),
        ("UNITE", "Unité"),
    )
    VOLUME_CHOICES = (("CL", "cl"), ("ML", "ml"), ("L", "L"))

    name = forms.CharField(label="Nom du produit", max_length=180)
    brand = forms.CharField(label="Marque", max_length=120, required=False)
    category_id = forms.ChoiceField(label="Catégorie", choices=())
    volume_value = forms.DecimalField(
        label="Volume", required=False, min_value=0, max_digits=10, decimal_places=2
    )
    volume_unit = forms.ChoiceField(
        label="Unité du volume", required=False, choices=(("", "—"), *VOLUME_CHOICES)
    )
    package_type = forms.ChoiceField(label="Conditionnement", choices=PACKAGE_CHOICES)
    units_per_package = forms.IntegerField(label="Unités par colis", min_value=1)
    purchase_price = forms.DecimalField(
        label="Prix d’achat du colis", min_value=0, max_digits=14, decimal_places=2
    )
    selling_price = forms.DecimalField(
        label="Prix de vente du colis", min_value=0.01, max_digits=14, decimal_places=2
    )
    minimum_stock = forms.DecimalField(
        label="Seuil minimum", min_value=0, max_digits=14, decimal_places=2
    )
    reorder_quantity = forms.DecimalField(
        label="Quantité de réapprovisionnement", min_value=0, max_digits=14, decimal_places=2
    )
    is_active = forms.BooleanField(label="Produit actif", required=False, initial=True)

    def __init__(self, *args, categories=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category_id"].choices = [
            (str(category["id"]), category["name"]) for category in categories
        ]
        self.fields["category_id"].widget.attrs["data-enhanced-select"] = "true"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("volume_value") and not cleaned.get("volume_unit"):
            self.add_error("volume_unit", "Choisissez l’unité correspondant au volume.")
        if cleaned.get("selling_price") and cleaned.get("purchase_price"):
            if cleaned["selling_price"] < cleaned["purchase_price"]:
                self.add_error(
                    "selling_price",
                    "Le prix de vente est inférieur au prix d’achat. Vérifiez la marge.",
                )
        return cleaned


class StyledForm(forms.Form):
    def apply_style(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = "".join(character for character in phone if character.isdigit())
        if phone and len(digits) < 8:
            raise forms.ValidationError("Renseignez un numéro contenant au moins 8 chiffres.")
        return phone or None


class DataImportUploadForm(StyledForm):
    IMPORT_CHOICES = (
        ("SALES", "Ventes"),
        ("STOCKS", "Stocks journaliers"),
        ("PRODUCTS", "Produits"),
        ("CUSTOMERS", "Clients"),
    )
    MAX_FILE_SIZE = 20 * 1024 * 1024

    import_type = forms.ChoiceField(
        label="Données à importer",
        choices=IMPORT_CHOICES,
    )
    excel_file = forms.FileField(
        label="Fichier Excel",
        help_text="Format XLSX uniquement · 20 Mo maximum.",
        widget=forms.FileInput(attrs={"accept": ".xlsx"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_style()

    def clean_excel_file(self):
        uploaded_file = self.cleaned_data["excel_file"]
        if not uploaded_file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Choisissez un fichier Excel au format XLSX.")
        if uploaded_file.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError("Ce fichier dépasse la taille maximale de 20 Mo.")
        return uploaded_file


class CustomerForm(StyledForm):
    name = forms.CharField(label="Nom du client", max_length=180)
    customer_type_id = forms.ChoiceField(label="Type de client", choices=())
    phone = forms.CharField(
        label="Téléphone", max_length=50, required=False,
        help_text="Le numéro doit être unique dans ce dépôt.",
    )
    zone = forms.CharField(label="Zone commerciale", max_length=120, required=False)
    district = forms.CharField(label="Quartier", max_length=120, required=False)
    city = forms.CharField(label="Ville", max_length=120, initial="Bamako")
    is_active = forms.BooleanField(label="Client actif", required=False, initial=True)

    def __init__(self, *args, customer_types=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_type_id"].choices = [
            (str(row["id"]), row["name"]) for row in customer_types
        ]
        self.apply_style()


class SupplierForm(StyledForm):
    name = forms.CharField(label="Nom du fournisseur", max_length=180)
    phone = forms.CharField(label="Téléphone", max_length=50, required=False)
    city = forms.CharField(label="Ville", max_length=120, required=False, initial="Bamako")
    is_active = forms.BooleanField(label="Fournisseur actif", required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_style()


class SaleForm(StyledForm):
    PAYMENT_METHODS = (
        ("CASH", "Espèces"), ("MOBILE_MONEY", "Mobile Money"),
        ("BANK_TRANSFER", "Virement"), ("CREDIT", "Crédit"),
    )
    PAYMENT_STATUS = (("PAID", "Payée"), ("UNPAID", "À payer"), ("PARTIAL", "Partielle"))

    sale_date = forms.DateField(label="Date de vente", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    customer_id = forms.ChoiceField(label="Client", required=False, choices=())
    payment_method = forms.ChoiceField(label="Mode de paiement", choices=PAYMENT_METHODS)
    payment_status = forms.ChoiceField(label="Statut du paiement", choices=PAYMENT_STATUS)
    notes = forms.CharField(label="Notes", required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, customers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_id"].choices = [("", "Client comptoir"), *[(str(row["id"]), f"{row['code']} · {row['name']}") for row in customers]]
        self.apply_style()

    def clean_sale_date(self):
        value = self.cleaned_data["sale_date"]
        if value > timezone.localdate():
            raise forms.ValidationError("La date de vente ne peut pas être future.")
        return value


class SaleEditForm(StyledForm):
    customer_id = forms.ChoiceField(label="Client", required=False, choices=())
    payment_method = forms.ChoiceField(label="Mode de paiement", choices=SaleForm.PAYMENT_METHODS)
    payment_status = forms.ChoiceField(label="Statut du paiement", choices=SaleForm.PAYMENT_STATUS)
    notes = forms.CharField(label="Notes", required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, customers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_id"].choices = [("", "Client comptoir"), *[(str(row["id"]), f"{row['code']} · {row['name']}") for row in customers]]
        self.apply_style()


class SaleItemForm(StyledForm):
    product_id = forms.ChoiceField(label="Produit", required=False, choices=())
    quantity_packages = forms.DecimalField(label="Colis", required=False, min_value=Decimal("0.01"), max_digits=14, decimal_places=2)
    unit_price = forms.DecimalField(label="Prix/colis", required=False, min_value=Decimal("0.01"), max_digits=14, decimal_places=2)
    discount_amount = forms.DecimalField(label="Remise", required=False, min_value=0, max_digits=14, decimal_places=2, initial=0)

    def __init__(self, *args, products=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product_id"].choices = [("", "Choisir un produit"), *[(str(row["id"]), f"{row['code']} · {row['name']} · stock {row['current_stock']}") for row in products]]
        self.apply_style()

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product_id")
        values = (cleaned.get("quantity_packages"), cleaned.get("unit_price"))
        if product and not all(value is not None for value in values):
            raise forms.ValidationError("Renseignez la quantité et le prix de cette ligne.")
        if not product and any(value is not None for value in values):
            raise forms.ValidationError("Choisissez le produit correspondant à cette ligne.")
        return cleaned


class ReceiptForm(StyledForm):
    receipt_date = forms.DateField(label="Date de réception", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    supplier_id = forms.ChoiceField(label="Fournisseur", choices=())

    def __init__(self, *args, suppliers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier_id"].choices = [(str(row["id"]), f"{row['code']} · {row['name']}") for row in suppliers]
        self.apply_style()

    def clean_receipt_date(self):
        value = self.cleaned_data["receipt_date"]
        if value > timezone.localdate():
            raise forms.ValidationError("La date de réception ne peut pas être future.")
        return value


class ReceiptEditForm(StyledForm):
    supplier_id = forms.ChoiceField(label="Fournisseur", choices=())

    def __init__(self, *args, suppliers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier_id"].choices = [
            (str(row["id"]), f"{row['code']} · {row['name']}") for row in suppliers
        ]
        self.apply_style()


class ReceiptItemForm(StyledForm):
    product_id = forms.ChoiceField(label="Produit", required=False, choices=())
    quantity_packages = forms.DecimalField(label="Colis reçus", required=False, min_value=Decimal("0.01"), max_digits=14, decimal_places=2)
    unit_cost = forms.DecimalField(label="Coût/colis", required=False, min_value=0, max_digits=14, decimal_places=2)

    def __init__(self, *args, products=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product_id"].choices = [("", "Choisir un produit"), *[(str(row["id"]), f"{row['code']} · {row['name']}") for row in products]]
        self.apply_style()

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product_id")
        values = (cleaned.get("quantity_packages"), cleaned.get("unit_cost"))
        if product and not all(value is not None for value in values):
            raise forms.ValidationError("Renseignez la quantité et le coût de cette ligne.")
        if not product and any(value is not None for value in values):
            raise forms.ValidationError("Choisissez le produit correspondant à cette ligne.")
        return cleaned


class MovementForm(StyledForm):
    MOVEMENTS = (
        ("ADJUSTMENT_IN", "Ajustement positif"), ("ADJUSTMENT_OUT", "Ajustement négatif"),
        ("DAMAGE", "Casse / produit endommagé"), ("LOSS", "Perte"),
        ("SALE_RETURN", "Retour client"), ("PURCHASE_RETURN", "Retour fournisseur"),
    )
    product_id = forms.ChoiceField(label="Produit", choices=())
    movement_type = forms.ChoiceField(label="Type de mouvement", choices=MOVEMENTS)
    movement_date = forms.DateField(label="Date", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    quantity_packages = forms.DecimalField(label="Quantité en colis", min_value=Decimal("0.01"), max_digits=14, decimal_places=2)
    reason = forms.CharField(label="Motif", min_length=5, max_length=500, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, products=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product_id"].choices = [(str(row["id"]), f"{row['code']} · {row['name']} · stock {row['current_stock']}") for row in products]
        self.apply_style()

    def clean_movement_date(self):
        value = self.cleaned_data["movement_date"]
        if value > timezone.localdate():
            raise forms.ValidationError("La date du mouvement ne peut pas être future.")
        return value


class BaseDynamicItemFormSet(BaseFormSet):
    deletion_widget = forms.HiddenInput


SaleItemFormSet = formset_factory(
    SaleItemForm,
    formset=BaseDynamicItemFormSet,
    extra=0,
    min_num=1,
    max_num=20,
    can_delete=True,
    validate_min=True,
    validate_max=True,
)
ReceiptItemFormSet = formset_factory(
    ReceiptItemForm,
    formset=BaseDynamicItemFormSet,
    extra=0,
    min_num=1,
    max_num=20,
    can_delete=True,
    validate_min=True,
    validate_max=True,
)
