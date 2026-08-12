import re

from django.core.exceptions import ValidationError


def normalize_phone(value):
    """Return a stable international-looking phone identifier."""
    value = (value or "").strip()
    if not value:
        return None
    compact = re.sub(r"[\s().-]", "", value)
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"
    prefix = "+" if compact.startswith("+") else ""
    digits = compact[1:] if prefix else compact
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise ValidationError(
            "Saisissez un numéro valide, de préférence avec l’indicatif pays (ex. +223)."
        )
    return f"{prefix}{digits}"
