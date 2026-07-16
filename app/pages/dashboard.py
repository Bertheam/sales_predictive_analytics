import pandas as pd
import plotly.express as px
import streamlit as st

from app.database.session import SessionLocal
from app.services.dashboard_service import DashboardService
from app.utils.ui import render_page_header


def main():
    render_page_header(
        title="Tableau de bord des ventes",
        description=(
            "Analysez l'activité commerciale, les produits performants et les "
            "tendances sur la période de votre choix."
        ),
        icon="📊",
        section="Décider",
    )

    db = SessionLocal()

    try:
        service = DashboardService(db)
        date_range = service.get_available_date_range()

        min_date = date_range["min_date"]
        max_date = date_range["max_date"]

        if min_date is None or max_date is None:
            st.warning("Aucune vente n'est disponible pour le moment.")
            return

        st.caption(
            "Données disponibles du "
            f"{min_date.strftime('%d/%m/%Y')} au "
            f"{max_date.strftime('%d/%m/%Y')}"
        )

        st.subheader("Période d'analyse")

        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            start_date = st.date_input(
                "Date de début",
                value=min_date,
                min_value=min_date,
                max_value=max_date,
            )

        with filter_col2:
            end_date = st.date_input(
                "Date de fin",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
            )

        if start_date > end_date:
            st.error(
                "La date de début doit être inférieure "
                "ou égale à la date de fin."
            )
            return

        st.info(
            "Période analysée : "
            f"{start_date.strftime('%d/%m/%Y')} → "
            f"{end_date.strftime('%d/%m/%Y')}"
        )

        statistics = service.get_statistics(start_date, end_date)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Chiffre d'affaires",
                f"{statistics['total_revenue']:,.0f} FCFA",
            )

        with col2:
            st.metric(
                "Nombre de ventes",
                f"{statistics['total_sales']:,}",
            )

        with col3:
            st.metric(
                "Clients actifs sur la période",
                f"{statistics['active_customers']:,}",
            )

        col4, col5, col6 = st.columns(3)

        with col4:
            st.metric(
                "Produits vendus sur la période",
                f"{statistics['sold_products']:,}",
            )

        with col5:
            st.metric(
                "Quantité vendue",
                f"{statistics['total_quantity_sold']:,.0f} colis",
            )

        with col6:
            st.metric(
                "Anomalies détectées",
                f"{statistics['total_anomalies']:,}",
            )

        analysis = service.get_dashboard_analysis(start_date, end_date)

        st.subheader("Évolution du chiffre d'affaires")

        revenue_df = pd.DataFrame(analysis["revenue_evolution"])

        if not revenue_df.empty:
            revenue_figure = px.line(
                revenue_df,
                x="date",
                y="revenue",
                labels={
                    "date": "Date",
                    "revenue": "Chiffre d'affaires",
                },
            )
            revenue_figure.update_layout(
                xaxis_title="",
                yaxis_title="FCFA",
            )
            st.plotly_chart(revenue_figure, width="stretch")
        else:
            st.info("Aucune donnée disponible pour cette période.")

        product_col, category_col = st.columns(2)

        with product_col:
            st.subheader("Top 10 des produits")

            top_products_df = pd.DataFrame(analysis["top_products"])

            if not top_products_df.empty:
                products_figure = px.bar(
                    top_products_df,
                    x="quantity_sold",
                    y="product_name",
                    orientation="h",
                    labels={
                        "quantity_sold": "Quantité vendue",
                        "product_name": "Produit",
                    },
                )
                products_figure.update_layout(
                    yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(products_figure, width="stretch")
            else:
                st.info("Aucun produit vendu pour cette période.")

        with category_col:
            st.subheader("Ventes par catégorie")

            category_df = pd.DataFrame(analysis["sales_by_category"])

            if not category_df.empty:
                category_figure = px.pie(
                    category_df,
                    names="category_name",
                    values="revenue",
                )
                st.plotly_chart(category_figure, width="stretch")
            else:
                st.info("Aucune vente par catégorie pour cette période.")

        st.subheader("Chiffre d'affaires par type de client")

        customer_type_df = pd.DataFrame(
            analysis["sales_by_customer_type"]
        )

        if not customer_type_df.empty:
            customer_type_figure = px.bar(
                customer_type_df,
                x="customer_type",
                y="revenue",
                labels={
                    "customer_type": "Type de client",
                    "revenue": "Chiffre d'affaires",
                },
            )
            st.plotly_chart(customer_type_figure, width="stretch")
        else:
            st.info("Aucune vente par type de client pour cette période.")

    except Exception as exc:
        st.error("Impossible de se connecter à la base de données.")
        st.exception(exc)

    finally:
        db.close()


if __name__ == "__main__":
    main()
