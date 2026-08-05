from decimal import Decimal

from django import forms


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
