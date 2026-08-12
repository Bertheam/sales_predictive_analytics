import base64
import hashlib
import hmac
import json
import time
from uuid import UUID

import streamlit as st
from sqlalchemy import text

from app.config.settings import settings


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _verify(token: str) -> dict:
    try:
        encoded_payload, supplied_signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Jeton d’accès mal formé.") from exc

    expected_signature = base64.urlsafe_b64encode(
        hmac.new(
            settings.STREAMLIT_SIGNING_KEY.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii").rstrip("=")
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise ValueError("Signature du jeton invalide.")

    payload = json.loads(_decode(encoded_payload))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Ce lien d’accès a expiré.")
    payload["company_id"] = str(UUID(payload["company_id"]))
    try:
        payload["user_id"] = str(int(payload["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Utilisateur absent du jeton.") from exc
    return payload


def signed_access_is_authorized(db, access: dict) -> bool:
    """Recheck membership so a revoked short-lived link stops working."""
    if not settings.STREAMLIT_REQUIRE_SIGNED_ACCESS:
        return True
    return bool(
        db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM accounts_user user_account
                    WHERE user_account.id = CAST(:user_id AS BIGINT)
                      AND user_account.is_active = TRUE
                      AND (
                          user_account.is_superuser = TRUE
                          OR EXISTS (
                              SELECT 1
                              FROM company_memberships membership
                              WHERE membership.user_id = user_account.id
                                AND membership.company_id = CAST(:company_id AS UUID)
                                AND membership.status = 'ACTIVE'
                          )
                      )
                )
                """
            ),
            {
                "user_id": access["user_id"],
                "company_id": access["company_id"],
            },
        ).scalar_one()
    )


def require_signed_access() -> dict:
    """Authenticate the browser before any tenant database session is opened."""
    if not settings.STREAMLIT_REQUIRE_SIGNED_ACCESS:
        return {"company_id": settings.company_id, "user_id": "local"}

    if not settings.STREAMLIT_SIGNING_KEY:
        st.error("Le laboratoire n’est pas configuré pour l’accès sécurisé.")
        st.stop()

    token = st.query_params.get("access")
    if token:
        try:
            st.session_state["signed_access"] = _verify(token)
            st.query_params.clear()
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            st.session_state.pop("signed_access", None)
            st.error("Ce lien d’accès est invalide ou a expiré. Revenez dans NexaStock.")
            st.stop()

    access = st.session_state.get("signed_access")
    if not access:
        st.error("Accès réservé aux utilisateurs connectés à NexaStock.")
        st.info("Ouvrez le laboratoire depuis le bouton disponible dans l’application web.")
        st.stop()
    return access
