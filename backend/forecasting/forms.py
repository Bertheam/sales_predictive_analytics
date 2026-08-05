from django import forms

from .data import product_choices


class ForecastJobForm(forms.Form):
    product_id = forms.ChoiceField(
        label="Produit",
        choices=(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    horizon = forms.TypedChoiceField(
        label="Horizon",
        choices=((7, "7 jours"),),
        coerce=int,
        initial=7,
        widget=forms.Select(attrs={"class": "form-control", "data-native-select": "true"}),
    )

    def __init__(self, *args, company_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product_id"].choices = product_choices(company_id)
