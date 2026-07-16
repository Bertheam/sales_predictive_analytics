import pandas as pd
import plotly.express as px
import streamlit as st

from app.database.session import SessionLocal
from app.ml.models import MODEL_LABELS
from app.services.forecast_service import ForecastService
from app.utils.ui import render_page_header


MAE_HELP = (
    "Erreur absolue moyenne : écart moyen entre les ventes réelles et les "
    "prévisions, exprimé en colis. Plus la valeur est faible, meilleur est "
    "le modèle."
)
RMSE_HELP = (
    "Racine de l'erreur quadratique moyenne : mesure l'erreur en colis en "
    "pénalisant davantage les écarts importants. Plus la valeur est faible, "
    "meilleur est le modèle."
)
MAPE_HELP = (
    "Erreur absolue moyenne en pourcentage : écart moyen relatif entre les "
    "ventes réelles et les prévisions. Les jours sans vente réelle sont "
    "exclus du calcul. Plus la valeur est faible, meilleur est le modèle."
)


def render_ranking(ranking: list[dict]):
    ranking_data = pd.DataFrame(ranking).rename(
        columns={
            "rank": "Rang",
            "label": "Modèle",
            "mae": "MAE",
            "rmse": "RMSE",
            "mape": "MAPE (%)",
        }
    )

    st.dataframe(
        ranking_data[["Rang", "Modèle", "MAE", "RMSE", "MAPE (%)"]],
        column_config={
            "Rang": st.column_config.NumberColumn("Rang", format="%d"),
            "MAE": st.column_config.NumberColumn(
                "MAE",
                help=MAE_HELP,
                format="%.2f",
            ),
            "RMSE": st.column_config.NumberColumn(
                "RMSE",
                help=RMSE_HELP,
                format="%.2f",
            ),
            "MAPE (%)": st.column_config.NumberColumn(
                "MAPE (%)",
                help=MAPE_HELP,
                format="%.2f",
            ),
        },
        hide_index=True,
        width="stretch",
    )


def render_backtest_chart(result: dict):
    test_data = result["test_data"]
    prediction_columns = result["prediction_columns"]
    selected_columns = ["date", "quantity_sold"] + list(
        prediction_columns.values()
    )
    column_labels = {
        "quantity_sold": "Ventes réelles",
        **{
            column: MODEL_LABELS[model]
            for model, column in prediction_columns.items()
        },
    }
    chart_data = test_data[selected_columns].rename(columns=column_labels)
    chart_data = chart_data.melt(
        id_vars="date",
        var_name="Série",
        value_name="Quantité",
    )

    figure = px.line(
        chart_data,
        x="date",
        y="Quantité",
        color="Série",
        labels={
            "date": "Date",
            "Quantité": "Quantité vendue (colis)",
        },
    )
    figure.update_layout(legend_title_text="")
    st.plotly_chart(figure, width="stretch")


def main():
    render_page_header(
        title="Comparaison des modèles",
        description=(
            "Comparez les méthodes de prévision sur une période de test "
            "chronologique et identifiez automatiquement la plus précise."
        ),
        icon="🤖",
        section="Prévoir",
    )

    db = SessionLocal()

    try:
        service = ForecastService(db)
        products = service.get_products()
        date_range = service.get_available_date_range()

        if not products or date_range["min_date"] is None:
            st.warning("Aucune donnée de vente n'est disponible.")
            return

        st.caption(
            "Historique disponible : "
            f"{date_range['min_date'].strftime('%d/%m/%Y')} → "
            f"{date_range['max_date'].strftime('%d/%m/%Y')}"
        )

        product_options = {
            f"{product['name']} ({product['code']})": product["id"]
            for product in products
        }
        product_col, test_col = st.columns([2, 1])

        with product_col:
            selected_product = st.selectbox(
                "Produit",
                options=list(product_options),
            )

        with test_col:
            test_days = st.selectbox(
                "Période de test",
                options=[30, 60, 90],
                index=1,
                format_func=lambda days: f"{days} jours",
            )

        if st.button("Comparer les modèles", type="primary"):
            with st.spinner(
                "Feature engineering, entraînement et backtesting..."
            ):
                result = service.evaluate_product(
                    product_options[selected_product],
                    test_days,
                )

            best_model = result["best_model"]
            best_metrics = result["models"][best_model]

            st.success(
                "Meilleur modèle sur cette période : "
                f"{MODEL_LABELS[best_model]}"
            )

            model_col, mae_col, rmse_col, mape_col = st.columns(4)
            with model_col:
                st.metric("Modèle retenu", MODEL_LABELS[best_model])
            with mae_col:
                st.metric(
                    "MAE",
                    f"{best_metrics['mae']:.2f} colis",
                    help=MAE_HELP,
                )
            with rmse_col:
                st.metric(
                    "RMSE",
                    f"{best_metrics['rmse']:.2f} colis",
                    help=RMSE_HELP,
                )
            with mape_col:
                st.metric(
                    "MAPE",
                    f"{best_metrics['mape']:.2f} %",
                    help=MAPE_HELP,
                )

            st.subheader("Classement automatique")
            render_ranking(result["ranking"])

            st.subheader("Ventes réelles et prédictions")
            test_data = result["test_data"]
            st.caption(
                f"Backtesting du {test_data['date'].min().strftime('%d/%m/%Y')} "
                f"au {test_data['date'].max().strftime('%d/%m/%Y')}. "
                f"{result['excluded_test_stockouts']} jour(s) de rupture "
                "exclus des métriques."
            )
            render_backtest_chart(result)

            with st.expander("Détails du dataset et des ruptures de stock"):
                zero_days = int((result["dataset"]["quantity_sold"] == 0).sum())
                st.write(
                    f"{len(result['dataset'])} jours préparés, dont "
                    f"{zero_days} jours sans vente complétés avec 0."
                )
                st.write(
                    f"{result['training_rows']} jours utilisés pour "
                    f"l'entraînement et {result['test_rows']} pour "
                    "l'évaluation."
                )
                st.write(
                    f"{result['excluded_train_stockouts']} jour(s) de rupture "
                    "exclus de l'entraînement. Le stock disponible correspond "
                    "au stock d'ouverture pour éviter toute fuite de données."
                )
                st.write(
                    "Features : retards J-1/J-7/J-14/J-21/J-28, moyennes "
                    "mobiles 7/14/28 jours, calendrier, météo, périodes "
                    "Ramadan/Tabaski et variables de stock."
                )

    except ValueError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error("Impossible de comparer les modèles.")
        st.exception(exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
