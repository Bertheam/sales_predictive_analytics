import hashlib
import json
from functools import wraps

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from rest_framework.response import Response

from .models import IdempotencyRecord


def _json_value(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _request_hash(request):
    payload = json.dumps(
        request.data, cls=DjangoJSONEncoder, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def idempotent(view_method):
    """Rejoue la première réponse pour une même mutation mobile.

    La clé reste facultative pour préserver les clients web existants. Dès
    qu'elle est fournie, le contrat est strict et inclut utilisateur, dépôt,
    méthode et route.
    """

    @wraps(view_method)
    def wrapper(self, request, *args, **kwargs):
        key = (request.headers.get("Idempotency-Key") or "").strip()
        if not key:
            return view_method(self, request, *args, **kwargs)
        if len(key) > 128 or any(character.isspace() for character in key):
            return Response({
                "code": "invalid_idempotency_key",
                "message": "Idempotency-Key doit être une valeur non vide de 128 caractères maximum, sans espace.",
            }, status=400)

        scope = {
            "key": key,
            "user": request.user,
            "company": request.company,
            "method": request.method,
            "path": request.path,
        }
        digest = _request_hash(request)
        record, created = IdempotencyRecord.objects.get_or_create(
            **scope, defaults={"request_hash": digest}
        )

        if not created:
            if record is None or record.expires_at <= timezone.now():
                if record:
                    record.delete()
                return wrapper(self, request, *args, **kwargs)
            if record.request_hash != digest:
                return Response({
                    "code": "idempotency_conflict",
                    "message": "Cette clé a déjà été utilisée avec un contenu différent.",
                }, status=409)
            if record.status == IdempotencyRecord.Status.COMPLETED:
                response = Response(record.response_body, status=record.response_status)
                for name, value in record.response_headers.items():
                    response[name] = value
                response["Idempotency-Replayed"] = "true"
                return response
            return Response({
                "code": "idempotency_in_progress",
                "message": "Une requête identique est déjà en cours de traitement.",
            }, status=409)

        try:
            response = view_method(self, request, *args, **kwargs)
        except Exception:
            record.delete()
            raise
        if isinstance(response, Response) and response.status_code < 500:
            record.status = IdempotencyRecord.Status.COMPLETED
            record.response_status = response.status_code
            record.response_body = _json_value(response.data)
            record.response_headers = {
                name: value for name, value in response.items()
                if name.lower() in {"location"}
            }
            record.save(update_fields=(
                "status", "response_status", "response_body",
                "response_headers", "updated_at",
            ))
            response["Idempotency-Replayed"] = "false"
        else:
            record.delete()
        return response

    return wrapper
