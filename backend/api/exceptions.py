from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response
    if isinstance(exc, ValidationError):
        response.data = {
            "code": "validation_error",
            "message": "Certaines informations sont incorrectes.",
            "errors": response.data,
        }
    elif not (isinstance(response.data, dict) and "code" in response.data):
        detail = response.data.get("detail", "La requête a échoué.") if isinstance(response.data, dict) else response.data
        response.data = {
            "code": getattr(exc, "default_code", "api_error"),
            "message": str(detail),
        }
    return response
