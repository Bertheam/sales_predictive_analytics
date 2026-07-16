import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.database.session import SessionLocal
from app.services.future_forecast_service import FutureForecastService
from app.utils.ui import render_page_header


def render_forecast_chart(result: dict):
    history = result["history"]
    forecast = result["forecast"]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history["date"],
            y=history["quantity_sold"],
            name="Historique",
            mode="lines",
            line={"color": "#2563EB"},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["upper_bound"],
            name="Borne haute 95 %",
            mode="lines",
            line={"width": 0},
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["lower_bound"],
            name="Intervalle de confiance 95 %",
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(249, 115, 22, 0.18)",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["predicted_quantity"],
            name="Prévision",
            mode="lines+markers",
            line={"color": "#F97316", "width": 3},
        )
    )
    figure.update_layout(
        xaxis_title="",
        yaxis_title="Quantité (colis)",
        legend_title_text="",
        hovermode="x unified",
    )
    st.plotly_chart(figure, width="stretch")


def render_forecast_table(forecast: pd.DataFrame):
    table = forecast[
        [
            "date",
            "predicted_quantity",
            "lower_bound",
            "upper_bound",
            "stock_available",
            "stock_need",
            "predicted_revenue",
        ]
    ].rename(
        columns={
            "date": "Date",
            "predicted_quantity": "Quantité prévue",
            "lower_bound": "Borne basse",
            "upper_bound": "Borne haute",
            "stock_available": "Stock disponible",
            "stock_need": "Besoin en stock",
            "predicted_revenue": "CA prévu",
        }
    )

    number_column = lambda label: st.column_config.NumberColumn(
        label,
        format="%.2f",
    )
    st.dataframe(
        table,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "Quantité prévue": number_column("Quantité prévue"),
            "Borne basse": number_column("Borne basse"),
            "Borne haute": number_column("Borne haute"),
            "Stock disponible": number_column("Stock disponible"),
            "Besoin en stock": number_column("Besoin en stock"),
            "CA prévu": st.column_config.NumberColumn(
                "CA prévu",
                format="%.0f FCFA",
            ),
        },
        hide_index=True,
        width="stretch",
    )


STATUS_LABELS = {
    "ACTIVE": "🟢 Active",
    "EXPIRED": "🟠 Expirée",
    "EVALUATED": "🔵 Évaluée",
}


def render_generation(service: FutureForecastService, products: list[dict]):
    product_options = {
        f"{product['name']} ({product['code']})": product["id"]
        for product in products
    }
    product_col, horizon_col, test_col = st.columns([2, 1, 1])

    with product_col:
        selected_product = st.selectbox(
            "Produit",
            options=list(product_options),
        )
    with horizon_col:
        horizon = st.selectbox(
            "Horizon",
            options=list(range(1, 8)),
            index=6,
            format_func=lambda days: f"{days} jour(s)",
        )
    with test_col:
        test_days = st.selectbox(
            "Validation du modèle",
            options=[30, 60, 90],
            index=1,
            format_func=lambda days: f"{days} jours",
        )

    st.caption(
        "La génération enregistre automatiquement le modèle, la prévision "
        "et ses résultats journaliers dans PostgreSQL."
    )

    if not st.button("Générer et enregistrer la prévision", type="primary"):
        return

    with st.spinner(
        "Sélection du modèle, réentraînement et prévision itérative..."
    ):
        result = service.generate_and_save(
            product_options[selected_product],
            horizon,
            test_days,
        )

    forecast = result["forecast"]
    st.success(
        f"Prévision {result['forecast_number']} enregistrée avec "
        f"{result['best_model_label']}."
    )

    model_col, quantity_col, stock_col, revenue_col = st.columns(4)
    model_col.metric("Modèle retenu", result["best_model_label"])
    quantity_col.metric(
        "Quantité totale prévue",
        f"{forecast['predicted_quantity'].sum():.2f} colis",
    )
    stock_col.metric(
        "Besoin total en stock",
        f"{forecast['stock_need'].sum():.2f} colis",
    )
    revenue_col.metric(
        "Chiffre d'affaires prévu",
        f"{forecast['predicted_revenue'].sum():,.0f} FCFA",
    )

    st.info(
        f"Intervalle de confiance : {result['confidence_level']:.0%} · "
        f"Stock actuel : {result['current_stock']:.2f} colis"
    )
    st.subheader("Historique et prévision")
    render_forecast_chart(result)
    st.subheader("Prévision et besoin de stock par jour")
    render_forecast_table(forecast)

    with st.expander("Traçabilité et méthode"):
        st.write(f"Run modèle : `{result['run_number']}`")
        st.write(f"Prévision : `{result['forecast_number']}`")
        st.write(
            f"Entraînement hors rupture : "
            f"{result['training_start_date'].strftime('%d/%m/%Y')} → "
            f"{result['training_end_date'].strftime('%d/%m/%Y')} "
            f"({result['training_rows']} jours)."
        )
        st.write(
            f"Ruptures exclues du backtesting : "
            f"{result['excluded_test_stockouts']} jour(s)."
        )
        st.write(
            "Les prédictions J+n sont ajoutées à l'historique avant "
            "le calcul de J+n+1. L'incertitude augmente avec la racine "
            "de l'horizon."
        )


def history_frame(history: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "N° prévision": row["forecast_number"],
                "Produit": row["product_name"],
                "Période": (
                    f"{row['forecast_start_date']:%d/%m/%Y} → "
                    f"{row['forecast_end_date']:%d/%m/%Y}"
                ),
                "Horizon": row["horizon"],
                "Modèle": row["model_name"],
                "Statut": STATUS_LABELS.get(row["status"], row["status"]),
                "Quantité prévue": float(row["predicted_quantity"]),
                "Quantité réelle": (
                    float(row["actual_quantity"])
                    if row["actual_quantity"] is not None
                    else None
                ),
                "MAE": float(row["mae"]) if row["mae"] is not None else None,
                "RMSE": (
                    float(row["rmse"]) if row["rmse"] is not None else None
                ),
                "MAPE (%)": (
                    float(row["mape"]) if row["mape"] is not None else None
                ),
                "Générée le": row["created_at"],
            }
            for row in history
        ]
    )


def render_saved_forecast_detail(
    service: FutureForecastService,
    selected: dict,
):
    results = service.get_forecast_results(str(selected["id"]))
    if not results:
        st.warning("Aucun résultat journalier pour cette prévision.")
        return

    data = pd.DataFrame(results)
    numeric_columns = [
        "predicted_quantity",
        "lower_bound",
        "upper_bound",
        "predicted_revenue",
        "recommended_stock",
        "actual_quantity",
        "absolute_error",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=data["forecast_date"],
            y=data["upper_bound"],
            mode="lines",
            line={"width": 0},
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data["forecast_date"],
            y=data["lower_bound"],
            name="Intervalle de confiance 95 %",
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(249, 115, 22, 0.18)",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data["forecast_date"],
            y=data["predicted_quantity"],
            name="Quantité prévue",
            mode="lines+markers",
            line={"color": "#F97316", "width": 3},
        )
    )
    if data["actual_quantity"].notna().any():
        figure.add_trace(
            go.Scatter(
                x=data["forecast_date"],
                y=data["actual_quantity"],
                name="Vente réelle",
                mode="lines+markers",
                line={"color": "#2563EB", "width": 3},
            )
        )
    figure.update_layout(
        yaxis_title="Quantité (colis)",
        legend_title_text="",
        hovermode="x unified",
    )
    st.plotly_chart(figure, width="stretch")

    table = data.rename(
        columns={
            "forecast_date": "Date",
            "predicted_quantity": "Quantité prévue",
            "lower_bound": "Borne basse",
            "upper_bound": "Borne haute",
            "actual_quantity": "Quantité réelle",
            "absolute_error": "Erreur absolue",
            "recommended_stock": "Stock recommandé",
            "predicted_revenue": "CA prévu",
        }
    )
    st.dataframe(
        table,
        column_config={
            "Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Quantité prévue": st.column_config.NumberColumn(format="%.2f"),
            "Borne basse": st.column_config.NumberColumn(format="%.2f"),
            "Borne haute": st.column_config.NumberColumn(format="%.2f"),
            "Quantité réelle": st.column_config.NumberColumn(format="%.2f"),
            "Erreur absolue": st.column_config.NumberColumn(format="%.2f"),
            "Stock recommandé": st.column_config.NumberColumn(format="%.2f"),
            "CA prévu": st.column_config.NumberColumn(format="%.0f FCFA"),
        },
        column_order=[
            "Date",
            "Quantité prévue",
            "Borne basse",
            "Borne haute",
            "Quantité réelle",
            "Erreur absolue",
            "Stock recommandé",
            "CA prévu",
        ],
        hide_index=True,
        width="stretch",
    )


def render_forecast_history(service: FutureForecastService):
    history = service.get_forecast_history()
    if not history:
        st.info("Aucune prévision n'a encore été enregistrée.")
        return

    products = sorted({row["product_name"] for row in history})
    models = sorted({row["model_name"] for row in history if row["model_name"]})
    product_col, status_col, model_col = st.columns(3)
    product = product_col.selectbox(
        "Produit",
        ["Tous"] + products,
        key="future_history_product",
    )
    status = status_col.selectbox(
        "Statut",
        ["Tous", "ACTIVE", "EXPIRED", "EVALUATED"],
        format_func=lambda value: STATUS_LABELS.get(value, value),
        key="future_history_status",
    )
    model = model_col.selectbox(
        "Modèle",
        ["Tous"] + models,
        key="future_history_model",
    )

    filtered = [
        row
        for row in history
        if (product == "Tous" or row["product_name"] == product)
        and (status == "Tous" or row["status"] == status)
        and (model == "Tous" or row["model_name"] == model)
    ]
    st.caption(f"{len(filtered)} prévision(s) affichée(s).")
    st.dataframe(
        history_frame(filtered),
        column_config={
            "Quantité prévue": st.column_config.NumberColumn(format="%.2f"),
            "Quantité réelle": st.column_config.NumberColumn(format="%.2f"),
            "MAE": st.column_config.NumberColumn(
                format="%.2f",
                help="Erreur absolue moyenne en colis.",
            ),
            "RMSE": st.column_config.NumberColumn(
                format="%.2f",
                help="Mesure qui pénalise davantage les grandes erreurs.",
            ),
            "MAPE (%)": st.column_config.NumberColumn(
                format="%.2f %%",
                help="Erreur absolue moyenne exprimée en pourcentage.",
            ),
            "Générée le": st.column_config.DatetimeColumn(
                format="DD/MM/YYYY HH:mm"
            ),
        },
        hide_index=True,
        width="stretch",
    )

    if not filtered:
        return

    options = {
        (
            f"{row['forecast_number']} · {row['product_name']} · "
            f"{row['forecast_start_date']:%d/%m/%Y} → "
            f"{row['forecast_end_date']:%d/%m/%Y}"
        ): row
        for row in filtered
    }
    st.subheader("Détail d'une prévision")
    selected_label = st.selectbox(
        "Prévision à consulter",
        list(options),
        key="saved_forecast_detail",
    )
    selected = options[selected_label]
    status_value = STATUS_LABELS.get(selected["status"], selected["status"])
    total_col, actual_col, model_metric, status_metric = st.columns(4)
    total_col.metric(
        "Quantité prévue",
        f"{float(selected['predicted_quantity']):.2f} colis",
    )
    actual_col.metric(
        "Quantité réelle",
        (
            f"{float(selected['actual_quantity']):.2f} colis"
            if selected["actual_quantity"] is not None
            else "En attente"
        ),
    )
    model_metric.metric("Modèle", selected["model_name"])
    status_metric.metric("Statut", status_value)
    render_saved_forecast_detail(service, selected)


def main():
    render_page_header(
        title="Prévision future J+1 à J+7",
        description=(
            "Générez de nouvelles prévisions, estimez le besoin de stock et "
            "consultez l'historique complet des résultats enregistrés."
        ),
        icon="🔭",
        section="Prévoir",
    )

    db = SessionLocal()
    try:
        service = FutureForecastService(db)
        products = service.get_products()
        if not products:
            st.warning("Aucun produit actif n'est disponible.")
            return

        generation_tab, history_tab = st.tabs(
            ["Générer une prévision", "Historique des prévisions"]
        )
        with generation_tab:
            render_generation(service, products)
        with history_tab:
            render_forecast_history(service)
    except ValueError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error("Impossible de charger la page des prévisions futures.")
        st.exception(exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
