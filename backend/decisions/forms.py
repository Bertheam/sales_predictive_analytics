from decimal import Decimal

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone


class RestockDraftForm(forms.Form):
    supplier_id = forms.ChoiceField(
        label="Fournisseur",
        required=False,
        choices=(),
        widget=forms.Select(attrs={"class": "form-control", "data-placeholder": "À choisir plus tard"}),
    )
    quantity = forms.DecimalField(
        label="Quantité à préparer (colis)",
        min_value=Decimal("0.01"),
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )

    def __init__(self, *args, suppliers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.suppliers = list(suppliers)
        self.fields["supplier_id"].choices = [("", "À choisir plus tard")] + [
            (str(row["id"]), f"{row['name']} · {row['code']}") for row in self.suppliers
        ]

    def selected_supplier(self):
        supplier_id = self.cleaned_data.get("supplier_id")
        return next((row for row in self.suppliers if str(row["id"]) == supplier_id), None)


class PurchaseOrderCreateForm(forms.Form):
    draft_ids = forms.MultipleChoiceField(
        label="Produits à commander",
        choices=(),
        widget=forms.CheckboxSelectMultiple,
    )
    expected_date = forms.DateField(
        label="Livraison prévue",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    notes = forms.CharField(
        label="Note pour le fournisseur",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    def __init__(self, *args, drafts=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.drafts = list(drafts)
        self.fields["draft_ids"].choices = [
            (
                str(draft.id),
                f"{draft.product_name} · {draft.quantity:g} colis",
            )
            for draft in self.drafts
        ]

    def clean_expected_date(self):
        value = self.cleaned_data.get("expected_date")
        if value and value < timezone.localdate():
            raise forms.ValidationError("La date prévue ne peut pas être passée.")
        return value

    def clean(self):
        cleaned = super().clean()
        selected_ids = set(cleaned.get("draft_ids") or [])
        selected = [draft for draft in self.drafts if str(draft.id) in selected_ids]
        if selected_ids and len(selected) != len(selected_ids):
            raise forms.ValidationError("Un plan sélectionné n’est plus disponible.")
        supplier_ids = {str(draft.supplier_id or "") for draft in selected}
        if "" in supplier_ids:
            raise forms.ValidationError(
                "Choisissez un fournisseur pour chaque produit avant de créer la commande."
            )
        if len(supplier_ids) > 1:
            raise forms.ValidationError(
                "Une commande ne peut concerner qu’un seul fournisseur."
            )
        cleaned["selected_drafts"] = selected
        return cleaned


class PurchaseOrderReceiveForm(forms.Form):
    receipt_date = forms.DateField(
        label="Date de réception",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def __init__(self, *args, items=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.items = [item for item in items if item.remaining_quantity > 0]
        for item in self.items:
            suffix = str(item.id)
            self.fields[f"quantity_{suffix}"] = forms.DecimalField(
                label="Colis reçus",
                min_value=Decimal("0"),
                max_value=item.remaining_quantity,
                max_digits=16,
                decimal_places=2,
                initial=item.remaining_quantity,
                widget=forms.NumberInput(
                    attrs={"class": "form-control", "step": "0.01"}
                ),
            )
            self.fields[f"unit_cost_{suffix}"] = forms.DecimalField(
                label="Coût par colis",
                min_value=Decimal("0"),
                max_digits=14,
                decimal_places=2,
                initial=item.unit_cost,
                widget=forms.NumberInput(
                    attrs={"class": "form-control", "step": "0.01"}
                ),
            )

    def clean_receipt_date(self):
        value = self.cleaned_data["receipt_date"]
        if value > timezone.localdate():
            raise forms.ValidationError("La date de réception ne peut pas être future.")
        return value

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        quantities = [
            cleaned.get(f"quantity_{item.id}") or Decimal("0")
            for item in self.items
        ]
        if not any(quantity > 0 for quantity in quantities):
            raise forms.ValidationError(
                "Renseignez au moins une quantité réellement reçue."
            )
        return cleaned

    def receipt_lines(self):
        lines = []
        for item in self.items:
            quantity = self.cleaned_data[f"quantity_{item.id}"]
            if quantity <= 0:
                continue
            lines.append(
                {
                    "item": item,
                    "product_id": str(item.product_id),
                    "quantity_packages": quantity,
                    "unit_cost": self.cleaned_data[f"unit_cost_{item.id}"],
                }
            )
        return lines


class ManualPurchaseOrderForm(forms.Form):
    supplier_id = forms.ChoiceField(
        label="Fournisseur",
        choices=(),
        widget=forms.Select(
            attrs={"class": "form-control", "data-placeholder": "Choisir un fournisseur"}
        ),
    )
    expected_date = forms.DateField(
        label="Livraison prévue",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    notes = forms.CharField(
        label="Note pour le fournisseur",
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Facultatif"}
        ),
    )

    def __init__(self, *args, suppliers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.suppliers = list(suppliers)
        self.fields["supplier_id"].choices = [("", "Choisir un fournisseur")] + [
            (str(row["id"]), f"{row['code']} · {row['name']}")
            for row in self.suppliers
        ]

    def clean_expected_date(self):
        value = self.cleaned_data.get("expected_date")
        if value and value < timezone.localdate():
            raise forms.ValidationError("La date prévue ne peut pas être passée.")
        return value

    def selected_supplier(self):
        supplier_id = self.cleaned_data["supplier_id"]
        return next(
            (row for row in self.suppliers if str(row["id"]) == supplier_id),
            None,
        )


class ManualPurchaseOrderItemForm(forms.Form):
    product_id = forms.ChoiceField(
        label="Produit",
        choices=(),
        widget=forms.Select(
            attrs={"class": "form-control", "data-placeholder": "Choisir un produit"}
        ),
    )
    quantity_ordered = forms.DecimalField(
        label="Quantité (colis)",
        min_value=Decimal("0.01"),
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
        ),
    )

    def __init__(self, *args, products=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product_id"].choices = [("", "Choisir un produit")] + [
            (str(row["id"]), f"{row['code']} · {row['name']}") for row in products
        ]


class BaseManualPurchaseOrderItemFormSet(BaseFormSet):
    deletion_widget = forms.HiddenInput

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        products = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            if not form.cleaned_data:
                continue
            product_id = form.cleaned_data.get("product_id")
            if product_id:
                products.append(product_id)
        if len(products) != len(set(products)):
            raise forms.ValidationError(
                "Un produit ne peut apparaître qu’une fois dans la commande."
            )


ManualPurchaseOrderItemFormSet = formset_factory(
    ManualPurchaseOrderItemForm,
    formset=BaseManualPurchaseOrderItemFormSet,
    extra=0,
    min_num=1,
    max_num=20,
    can_delete=True,
    validate_min=True,
    validate_max=True,
)
