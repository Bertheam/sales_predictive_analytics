import pandas as pd
import streamlit as st

from app.database.session import SessionLocal
from app.services.decision_service import DecisionService
from app.utils.ui import render_page_header


RISK_ICONS = {
    "CRITIQUE": "🔴 CRITIQUE",
    "ÉLEVÉ": "🟠 ÉLEVÉ",
    "MOYEN": "🟡 MOYEN",
    "FAIBLE": "🟢 FAIBLE",
}
SEVERITY_LABELS = {
    "CRITICAL": "🔴 CRITIQUE",
    "HIGH": "🟠 ÉLEVÉE",
    "MEDIUM": "🟡 MOYENNE",
    "LOW": "🔵 FAIBLE",
}


def recommendation_frame(recommendations: list[dict]) -> pd.DataFrame:
    rows = []
    for index, item in enumerate(recommendations, start=1):
        rows.append(
            {
                "Priorité": index,
                "Produit": item["product_name"],
                "Catégorie": item["category_name"],
                "Stock actuel": item["current_stock"],
                "Demande prévue": item["predicted_quantity"],
                "Stock de sécurité": item["safety_stock"],
                "Quantité à commander": item["recommended_order"],
                "Risque": RISK_ICONS[item["risk_level"]],
                "Tendance (%)": item["trend_percentage"],
            }
        )
    return pd.DataFrame(rows)


def render_recommendation_table(
    recommendations: list[dict],
    *,
    limit: int | None = None,
):
    data = recommendation_frame(recommendations)
    if limit is not None:
        data = data.head(limit)

    if data.empty:
        st.info("Aucune recommandation n'est disponible.")
        return

    st.dataframe(
        data,
        column_config={
            "Priorité": st.column_config.NumberColumn(format="%d"),
            "Stock actuel": st.column_config.NumberColumn(format="%.2f"),
            "Demande prévue": st.column_config.NumberColumn(format="%.2f"),
            "Stock de sécurité": st.column_config.NumberColumn(format="%.2f"),
            "Quantité à commander": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "Tendance (%)": st.column_config.NumberColumn(format="%+.1f %%"),
        },
        hide_index=True,
        width="stretch",
    )


def render_global_view(
    service: DecisionService,
    recommendations: list[dict],
):
    summary = service.get_summary(recommendations)
    revenue_col, demand_col, risk_col, restock_col = st.columns(4)

    with revenue_col:
        st.metric(
            "CA prévisionnel",
            f"{summary['predicted_revenue']:,.0f} FCFA",
        )
    with demand_col:
        st.metric(
            "Demande prévue",
            f"{summary['predicted_quantity']:,.2f} colis",
        )
    with risk_col:
        st.metric("Produits à risque", summary["products_at_risk"])
    with restock_col:
        st.metric(
            "Produits à réapprovisionner",
            summary["products_to_restock"],
        )

    coverage = (
        summary["forecasted_products"] / summary["active_products"]
        if summary["active_products"]
        else 0
    )
    st.progress(
        coverage,
        text=(
            f"Couverture des prévisions : "
            f"{summary['forecasted_products']} / "
            f"{summary['active_products']} produits"
        ),
    )

    if summary["forecasted_products"] < summary["active_products"]:
        st.warning(
            "La vue globale est partielle. Générez les prévisions manquantes "
            "pour couvrir tous les produits actifs."
        )
        if st.button(
            "Générer les prévisions manquantes",
            type="primary",
        ):
            with st.spinner(
                "Génération et enregistrement des prévisions manquantes..."
            ):
                generation = service.generate_missing_forecasts()
            st.session_state["forecast_generation_result"] = generation
            st.rerun()

    st.subheader("Priorités de réapprovisionnement")
    priorities = [
        item for item in recommendations if item["recommended_order"] > 0
    ]
    render_recommendation_table(priorities, limit=10)


def render_stock_recommendations(recommendations: list[dict]):
    st.subheader("Recommandations par produit")
    st.caption(
        "Quantité à commander = demande prévue + stock de sécurité − stock "
        "actuel. Le stock de sécurité combine statistiquement les marges "
        "journalières à 95 %."
    )

    category_options = sorted(
        {item["category_name"] for item in recommendations}
    )
    risk_options = ["CRITIQUE", "ÉLEVÉ", "MOYEN", "FAIBLE"]
    category_col, risk_col = st.columns(2)
    with category_col:
        selected_category = st.selectbox(
            "Catégorie",
            options=["Toutes"] + category_options,
            key="recommendation_category",
        )
    with risk_col:
        selected_risk = st.selectbox(
            "Niveau de risque",
            options=["Tous"] + risk_options,
            key="recommendation_risk",
        )

    filtered = [
        item
        for item in recommendations
        if (
            selected_category == "Toutes"
            or item["category_name"] == selected_category
        )
        and (selected_risk == "Tous" or item["risk_level"] == selected_risk)
    ]
    render_recommendation_table(filtered)


def render_alert_center(alerts: list[dict]):
    st.subheader("Centre d'alertes")

    if not alerts:
        st.info("Aucune alerte n'est disponible.")
        return

    min_date = min(alert["date"] for alert in alerts)
    max_date = max(alert["date"] for alert in alerts)
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input(
            "Date de début",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="alert_start_date",
        )
    with date_col2:
        end_date = st.date_input(
            "Date de fin",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="alert_end_date",
        )

    products = sorted({alert["product_name"] for alert in alerts})
    categories = sorted({alert["category_name"] for alert in alerts})
    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    alert_types = sorted({alert["alert_type"] for alert in alerts})
    statuses = sorted({alert["status"] for alert in alerts})

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        product = st.selectbox(
            "Produit",
            options=["Tous"] + products,
            key="alert_product",
        )
        severity = st.selectbox(
            "Sévérité",
            options=["Toutes"] + severities,
            key="alert_severity",
        )
    with filter_col2:
        category = st.selectbox(
            "Catégorie",
            options=["Toutes"] + categories,
            key="alert_category",
        )
        status = st.selectbox(
            "Statut",
            options=["Tous"] + statuses,
            key="alert_status",
        )
    with filter_col3:
        alert_type = st.selectbox(
            "Type d'alerte",
            options=["Tous"] + alert_types,
            key="alert_type",
        )

    filtered = [
        alert
        for alert in alerts
        if start_date <= alert["date"] <= end_date
        and (product == "Tous" or alert["product_name"] == product)
        and (category == "Toutes" or alert["category_name"] == category)
        and (severity == "Toutes" or alert["severity"] == severity)
        and (status == "Tous" or alert["status"] == status)
        and (alert_type == "Tous" or alert["alert_type"] == alert_type)
    ]

    table = pd.DataFrame(
        [
            {
                "Date": alert["date"],
                "Sévérité": SEVERITY_LABELS.get(
                    alert["severity"],
                    alert["severity"],
                ),
                "Type": alert["alert_type"],
                "Produit": alert["product_name"],
                "Catégorie": alert["category_name"],
                "Statut": "OUVERTE" if alert["status"] == "OPEN" else alert["status"],
                "Message": alert["message"],
            }
            for alert in filtered
        ]
    )

    st.caption(f"{len(filtered)} alerte(s) affichée(s) sur {len(alerts)}.")
    st.dataframe(
        table,
        column_config={
            "Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Message": st.column_config.TextColumn(width="large"),
        },
        hide_index=True,
        width="stretch",
    )


def main():
    render_page_header(
        title="Pilotage métier",
        description=(
            "Transformez les prévisions en priorités de réapprovisionnement "
            "et en alertes directement exploitables."
        ),
        icon="🎯",
        section="Décider",
    )

    db = SessionLocal()
    try:
        service = DecisionService(db)
        recommendations = service.get_recommendations()
        alerts = service.get_alerts(recommendations)

        generation = st.session_state.pop(
            "forecast_generation_result",
            None,
        )
        if generation:
            st.success(
                f"{len(generation['successes'])} prévision(s) générée(s) "
                f"sur {generation['requested']}."
            )
            if generation["errors"]:
                st.warning(
                    f"{len(generation['errors'])} produit(s) n'ont pas pu "
                    "être traités."
                )

        global_tab, stock_tab, alert_tab = st.tabs(
            [
                "Vue globale",
                "Recommandations de stock",
                "Centre d'alertes",
            ]
        )
        with global_tab:
            render_global_view(service, recommendations)
        with stock_tab:
            render_stock_recommendations(recommendations)
        with alert_tab:
            render_alert_center(alerts)

    except Exception as exc:
        st.error("Impossible de charger le pilotage métier.")
        st.exception(exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
