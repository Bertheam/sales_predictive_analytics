import pandas as pd
import streamlit as st

from app.database.session import SessionLocal
from app.services.ml_quality_service import MLQualityService
from app.utils.ui import render_page_header


STATUS_LABELS = {
    "ACTIVE": "🟢 ACTIVE",
    "EXPIRED": "🟠 EXPIRED",
    "EVALUATED": "🔵 EVALUATED",
}
PERFORMANCE_LABELS = {
    "GOOD": "🟢 Bonne",
    "WATCH": "🟠 À surveiller",
    "POOR": "🔴 Insuffisante",
}
DRIFT_LABELS = {
    "DECLINING": "🔴 En baisse",
    "IMPROVING": "🟢 En amélioration",
    "STABLE": "🔵 Stable",
    "INSUFFICIENT_DATA": "⚪ Données insuffisantes",
}


def history_frame(history: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "N° prévision": row["forecast_number"],
                "Produit": row["product_name"],
                "Catégorie": row["category_name"],
                "Début": row["forecast_start_date"],
                "Fin": row["forecast_end_date"],
                "Modèle": row["model_name"],
                "Statut": STATUS_LABELS.get(row["status"], row["status"]),
                "Prévu": float(row["predicted_quantity"]),
                "Réel": (
                    float(row["actual_quantity"])
                    if row["actual_quantity"] is not None
                    else None
                ),
                "Erreur totale": (
                    float(row["absolute_error"])
                    if row["absolute_error"] is not None
                    else None
                ),
                "MAE": float(row["mae"]) if row["mae"] is not None else None,
                "RMSE": (
                    float(row["rmse"]) if row["rmse"] is not None else None
                ),
                "MAPE (%)": (
                    float(row["mape"]) if row["mape"] is not None else None
                ),
                "Performance": PERFORMANCE_LABELS.get(
                    row["performance_status"],
                    "En attente",
                ),
            }
            for row in history
        ]
    )


def quality_frame(quality: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Produit": row["product_name"],
                "Modèle": row["model_name"],
                "Prévisions évaluées": row["forecast_count"],
                "MAE actuelle": row["mae"],
                "RMSE actuelle": row["rmse"],
                "MAPE (%)": row["mape"],
                "Performance": PERFORMANCE_LABELS.get(
                    row["performance_status"],
                    row["performance_label"],
                ),
                "MAE 30 jours": row["current_mae_30d"],
                "MAE 30 jours précédents": row["previous_mae_30d"],
                "Tendance": DRIFT_LABELS.get(
                    row["drift_status"],
                    row["drift_label"],
                ),
                "Action recommandée": row["action"],
            }
            for row in quality
        ]
    )


def reviews_frame(reviews: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": row["review_date"],
                "Produit": row["product_name"],
                "Période de début": row["period_start_date"],
                "Période de fin": row["period_end_date"],
                "Ancien modèle": row["previous_model"] or "Non déterminé",
                "Modèle recommandé": row["recommended_model"],
                "Décision": (
                    "Changer de modèle"
                    if row["action"] == "CHANGER_MODELE"
                    else "Conserver le modèle"
                ),
            }
            for row in reviews
        ]
    )


def render_overview(data: dict) -> None:
    status_counts = data["status_counts"]
    active_col, expired_col, evaluated_col, review_col = st.columns(4)
    active_col.metric("Prévisions actives", status_counts.get("ACTIVE", 0))
    expired_col.metric("Prévisions expirées", status_counts.get("EXPIRED", 0))
    evaluated_col.metric(
        "Prévisions évaluées",
        status_counts.get("EVALUATED", 0),
    )
    review_col.metric("À réévaluer", data["models_to_review"])

    metric_col1, metric_col2, coverage_col = st.columns(3)
    metric_col1.metric(
        "MAE moyenne",
        f"{data['average_mae']:.2f} colis"
        if data["average_mae"] is not None
        else "En attente",
        help=(
            "Erreur absolue moyenne : écart moyen, en colis, entre la "
            "prévision journalière et la vente réelle. Plus elle est basse, "
            "meilleur est le modèle."
        ),
    )
    metric_col2.metric(
        "MAPE moyenne",
        f"{data['average_mape']:.2f} %"
        if data["average_mape"] is not None
        else "En attente",
        help=(
            "Erreur absolue moyenne en pourcentage. Elle facilite la "
            "comparaison entre produits de volumes différents."
        ),
    )
    coverage = (
        data["evaluated_forecasts"] / data["total_forecasts"]
        if data["total_forecasts"]
        else 0
    )
    coverage_col.metric("Couverture d'évaluation", f"{coverage:.0%}")
    st.progress(
        coverage,
        text=(
            f"{data['evaluated_forecasts']} prévision(s) évaluée(s) "
            f"sur {data['total_forecasts']}"
        ),
    )

    cutoff_date = data["lifecycle"]["cutoff_date"]
    if not data["evaluated_forecasts"]:
        st.info(
            "Aucune prévision n'est encore arrivée à échéance. "
            f"Les ventes réelles disponibles s'arrêtent au "
            f"{cutoff_date:%d/%m/%Y}. Les erreurs seront calculées "
            "automatiquement dès que toute la période prévue sera couverte."
        )

    st.subheader("Qualité actuelle par produit et par modèle")
    quality = quality_frame(data["quality"])
    if quality.empty:
        st.caption(
            "Ce tableau sera alimenté après la première évaluation."
        )
    else:
        st.dataframe(
            quality,
            column_config={
                "MAE actuelle": st.column_config.NumberColumn(format="%.2f"),
                "RMSE actuelle": st.column_config.NumberColumn(format="%.2f"),
                "MAPE (%)": st.column_config.NumberColumn(format="%.2f %%"),
                "MAE 30 jours": st.column_config.NumberColumn(format="%.2f"),
                "MAE 30 jours précédents": (
                    st.column_config.NumberColumn(format="%.2f")
                ),
            },
            hide_index=True,
            width="stretch",
        )


def render_history(history: list[dict]) -> None:
    st.subheader("Historique des prévisions générées")
    if not history:
        st.info("Aucune prévision enregistrée.")
        return

    products = sorted({row["product_name"] for row in history})
    models = sorted({row["model_name"] for row in history if row["model_name"]})
    statuses = ["ACTIVE", "EXPIRED", "EVALUATED"]
    product_col, model_col, status_col = st.columns(3)
    product = product_col.selectbox(
        "Produit",
        ["Tous"] + products,
        key="quality_history_product",
    )
    model = model_col.selectbox(
        "Modèle",
        ["Tous"] + models,
        key="quality_history_model",
    )
    status = status_col.selectbox(
        "Statut",
        ["Tous"] + statuses,
        format_func=lambda value: STATUS_LABELS.get(value, value),
        key="quality_history_status",
    )

    filtered = [
        row
        for row in history
        if (product == "Tous" or row["product_name"] == product)
        and (model == "Tous" or row["model_name"] == model)
        and (status == "Tous" or row["status"] == status)
    ]
    st.caption(f"{len(filtered)} prévision(s) affichée(s).")
    st.dataframe(
        history_frame(filtered),
        column_config={
            "Début": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Fin": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Prévu": st.column_config.NumberColumn(format="%.2f"),
            "Réel": st.column_config.NumberColumn(format="%.2f"),
            "Erreur totale": st.column_config.NumberColumn(format="%.2f"),
            "MAE": st.column_config.NumberColumn(
                format="%.2f",
                help="Erreur absolue moyenne en colis.",
            ),
            "RMSE": st.column_config.NumberColumn(
                format="%.2f",
                help=(
                    "Racine de l'erreur quadratique moyenne. Elle pénalise "
                    "davantage les grandes erreurs."
                ),
            ),
            "MAPE (%)": st.column_config.NumberColumn(
                format="%.2f %%",
                help="Erreur absolue moyenne exprimée en pourcentage.",
            ),
        },
        hide_index=True,
        width="stretch",
    )


def render_reassessment(service: MLQualityService, data: dict) -> None:
    st.subheader("Dérive et réévaluation périodique")
    st.write(
        "Le système compare la MAE des 30 derniers jours aux 30 jours "
        "précédents. Une hausse supérieure à 20 % signale une baisse "
        "de performance."
    )

    quality = quality_frame(data["quality"])
    if quality.empty:
        st.info(
            "La dérive nécessite des prévisions arrivées à échéance. "
            "Vous pouvez toutefois lancer une comparaison complète des "
            "modèles sur l'historique actuel."
        )
    else:
        st.dataframe(quality, hide_index=True, width="stretch")

    all_products = st.checkbox(
        "Réévaluer tous les produits",
        value=False,
        help=(
            "Si cette option est décochée, seuls les produits dont la "
            "performance baisse ou devient insuffisante sont traités."
        ),
    )
    button_label = (
        "Comparer les modèles pour tous les produits"
        if all_products
        else "Réévaluer les modèles signalés"
    )
    if st.button(button_label, type="primary"):
        with st.spinner("Comparaison des modèles en cours..."):
            result = service.run_periodic_reassessment(all_products)
        st.session_state["model_reassessment_result"] = result
        st.rerun()

    result = st.session_state.pop("model_reassessment_result", None)
    if result:
        st.success(
            f"{len(result['successes'])} produit(s) réévalué(s) "
            f"sur {result['requested']}."
        )
        if result["errors"]:
            st.warning(
                f"{len(result['errors'])} produit(s) n'ont pas pu être "
                "réévalués."
            )

    st.subheader("Historique des revues de modèles")
    reviews = reviews_frame(data["reviews"])
    if reviews.empty:
        st.caption("Aucune revue périodique enregistrée.")
    else:
        st.dataframe(
            reviews,
            column_config={
                "Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Période de début": st.column_config.DateColumn(
                    format="DD/MM/YYYY"
                ),
                "Période de fin": st.column_config.DateColumn(
                    format="DD/MM/YYYY"
                ),
            },
            hide_index=True,
            width="stretch",
        )


def main() -> None:
    render_page_header(
        title="Qualité du système prédictif",
        description=(
            "Mesurez la précision après échéance, suivez la dérive et "
            "identifiez les modèles qui doivent être réentraînés."
        ),
        icon="🧪",
        section="Prévoir",
    )

    db = SessionLocal()
    try:
        service = MLQualityService(db)
        data = service.get_dashboard_data()
        cutoff_date = data["lifecycle"]["cutoff_date"]
        if cutoff_date:
            st.caption(
                "Dernière date de vente réelle disponible : "
                f"{cutoff_date:%d/%m/%Y}"
            )

        overview_tab, history_tab, reassessment_tab = st.tabs(
            [
                "Vue qualité",
                "Historique des prévisions",
                "Dérive et réévaluation",
            ]
        )
        with overview_tab:
            render_overview(data)
        with history_tab:
            render_history(data["history"])
        with reassessment_tab:
            render_reassessment(service, data)
    except Exception as exc:
        st.error("Impossible de charger le tableau de bord qualité ML.")
        st.exception(exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
