import streamlit as st
from sqlalchemy import text

from app.database.session import SessionLocal
from app.security.signed_access import require_signed_access
from app.utils.ui import apply_app_style, render_sidebar_brand


st.set_page_config(
    page_title="Pilotage prédictif des ventes",
    page_icon="📊",
    layout="wide",
)

apply_app_style()
render_sidebar_brand()
access = require_signed_access()

try:
    with SessionLocal(access["company_id"]) as tenant_db:
        tenant_name = tenant_db.execute(
            text("SELECT name FROM companies WHERE id = :company_id AND status = 'ACTIVE'"),
            {"company_id": access["company_id"]},
        ).scalar_one_or_none()
except Exception as exc:
    st.error(
        "Le contexte du dépôt technique n'est pas disponible. "
        "Vérifiez les migrations et le dépôt transmis par NexaStock."
    )
    st.exception(exc)
    st.stop()

if not tenant_name:
    st.error("Le dépôt configuré pour Streamlit est introuvable ou inactif.")
    st.stop()

st.sidebar.caption(f"Dépôt analysé : **{tenant_name}**")


dashboard_page = st.Page(
    "pages/dashboard.py",
    title="Tableau de bord",
    icon="📊",
    default=True,
)
forecasts_page = st.Page(
    "pages/forecasts.py",
    title="Comparaison des modèles",
    icon="🤖",
    url_path="previsions",
)
future_forecasts_page = st.Page(
    "pages/future_forecasts.py",
    title="Prévision future",
    icon="🔭",
    url_path="prevision-future",
)
decisions_page = st.Page(
    "pages/decisions.py",
    title="Pilotage métier",
    icon="🎯",
    url_path="pilotage-metier",
)
ml_quality_page = st.Page(
    "pages/ml_quality.py",
    title="Qualité ML",
    icon="🧪",
    url_path="qualite-ml",
)
inventory_page = st.Page(
    "pages/inventory.py",
    title="Stocks et réceptions",
    icon="📦",
    url_path="stocks-receptions",
)
help_page = st.Page(
    "pages/help.py",
    title="Guide d'utilisation",
    icon="❔",
    url_path="guide",
)

navigation = st.navigation(
    {
        "Décider": [dashboard_page, decisions_page],
        "Prévoir": [future_forecasts_page, forecasts_page, ml_quality_page],
        "Opérations": [inventory_page],
        "Aide": [help_page],
    }
)
navigation.run()
