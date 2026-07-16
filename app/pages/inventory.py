from datetime import date

import pandas as pd
import streamlit as st

from app.database.session import SessionLocal
from app.services.inventory_service import InventoryService
from app.utils.ui import render_page_header


DIRECTION_LABELS = {"IN": "🟢 Entrée", "OUT": "🔴 Sortie"}


def render_receipt_form(
    service: InventoryService,
    suppliers: list[dict],
    products: list[dict],
) -> None:
    st.subheader("Nouvelle réception fournisseur")
    st.caption(
        "Le numéro de réception et les mouvements de stock sont générés "
        "automatiquement. Une réception peut contenir plusieurs produits."
    )
    supplier_options = {
        f"{row['name']} ({row['code']})": str(row["id"])
        for row in suppliers
    }
    product_options = {
        f"{row['name']} ({row['code']})": str(row["id"])
        for row in products
    }

    with st.form("receipt_form"):
        supplier_col, date_col = st.columns([2, 1])
        supplier_label = supplier_col.selectbox(
            "Fournisseur",
            list(supplier_options),
        )
        receipt_date = date_col.date_input(
            "Date de réception",
            value=date.today(),
            max_value=date.today(),
        )
        lines = st.data_editor(
            pd.DataFrame(
                [
                    {
                        "Produit": None,
                        "Quantité (colis)": 1.0,
                        "Coût unitaire": 0.0,
                    }
                ]
            ),
            column_config={
                "Produit": st.column_config.SelectboxColumn(
                    options=list(product_options),
                    required=True,
                    width="large",
                ),
                "Quantité (colis)": st.column_config.NumberColumn(
                    min_value=0.01,
                    step=1.0,
                    format="%.2f",
                    required=True,
                ),
                "Coût unitaire": st.column_config.NumberColumn(
                    min_value=0.0,
                    step=100.0,
                    format="%.0f FCFA",
                    required=True,
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key="receipt_lines",
        )
        submitted = st.form_submit_button(
            "Valider la réception",
            type="primary",
        )

    if submitted:
        items = [
            {
                "product_id": product_options.get(row.get("Produit")),
                "quantity_packages": row.get("Quantité (colis)"),
                "unit_cost": row.get("Coût unitaire"),
            }
            for row in lines.to_dict("records")
        ]
        result = service.create_receipt(
            supplier_id=supplier_options[supplier_label],
            receipt_date=receipt_date,
            items=items,
        )
        st.session_state["inventory_receipt_result"] = result
        st.rerun()


def render_movement_form(
    service: InventoryService,
    products: list[dict],
) -> None:
    st.subheader("Mouvement manuel essentiel")
    st.caption(
        "Les sorties sont bloquées si le stock est insuffisant. Toute "
        "opération antidatée avant le dernier stock du produit est refusée."
    )
    movement_types = service.get_movement_types()
    movement_options = {
        config["label"]: key for key, config in movement_types.items()
    }
    product_options = {
        (
            f"{row['name']} ({row['code']}) · "
            f"stock {float(row['current_stock']):.2f}"
        ): str(row["id"])
        for row in products
    }

    with st.form("movement_form"):
        movement_col, product_col = st.columns(2)
        movement_label = movement_col.selectbox(
            "Nature du mouvement",
            list(movement_options),
        )
        product_label = product_col.selectbox(
            "Produit",
            list(product_options),
        )
        date_col, quantity_col = st.columns(2)
        movement_date = date_col.date_input(
            "Date du mouvement",
            value=date.today(),
            max_value=date.today(),
        )
        quantity = quantity_col.number_input(
            "Quantité (colis)",
            min_value=0.01,
            value=1.0,
            step=1.0,
        )
        reason = st.text_area(
            "Motif",
            placeholder="Exemple : casse constatée pendant l'inventaire",
        )
        submitted = st.form_submit_button(
            "Enregistrer le mouvement",
            type="primary",
        )

    if submitted:
        result = service.create_movement(
            product_id=product_options[product_label],
            movement_type=movement_options[movement_label],
            movement_date=movement_date,
            quantity=quantity,
            reason=reason,
        )
        st.session_state["inventory_movement_result"] = result
        st.rerun()


def stock_frame(products: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Code": row["code"],
                "Produit": row["name"],
                "Stock actuel": float(row["current_stock"]),
                "Stock minimum": float(row["minimum_stock"]),
                "Dernier stock": row["last_stock_date"],
                "Statut": (
                    "🔴 Rupture"
                    if float(row["current_stock"]) <= 0
                    else "🟠 Stock faible"
                    if float(row["current_stock"]) <= float(row["minimum_stock"])
                    else "🟢 Disponible"
                ),
            }
            for row in products
        ]
    )


def render_inventory_history(data: dict) -> None:
    total_col, low_col, stockout_col, receipt_col = st.columns(4)
    total_col.metric("Stock total", f"{data['total_stock']:,.2f} colis")
    low_col.metric("Stocks faibles", data["low_stock_count"])
    stockout_col.metric("Ruptures", data["stockout_count"])
    receipt_col.metric("Réceptions affichées", len(data["receipts"]))

    stock_tab, receipt_tab, movement_tab = st.tabs(
        ["Stock actuel", "Historique des réceptions", "Journal des mouvements"]
    )
    with stock_tab:
        stock = stock_frame(data["products"])
        status_filter = st.selectbox(
            "Statut du stock",
            ["Tous", "Disponible", "Stock faible", "Rupture"],
            key="inventory_stock_status",
        )
        if status_filter != "Tous":
            stock = stock[stock["Statut"].str.contains(status_filter)]
        st.dataframe(
            stock,
            column_config={
                "Stock actuel": st.column_config.NumberColumn(format="%.2f"),
                "Stock minimum": st.column_config.NumberColumn(format="%.2f"),
                "Dernier stock": st.column_config.DateColumn(format="DD/MM/YYYY"),
            },
            hide_index=True,
            width="stretch",
        )

    with receipt_tab:
        receipts = pd.DataFrame(
            [
                {
                    "N° réception": row["receipt_number"],
                    "Date": row["receipt_date"],
                    "Fournisseur": row["supplier_name"],
                    "Produits": row["item_count"],
                    "Quantité totale": float(row["total_quantity"]),
                    "Montant total": float(row["total_amount"]),
                    "Statut": row["status"],
                }
                for row in data["receipts"]
            ]
        )
        st.dataframe(
            receipts,
            column_config={
                "Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Quantité totale": st.column_config.NumberColumn(format="%.2f"),
                "Montant total": st.column_config.NumberColumn(format="%.0f FCFA"),
            },
            hide_index=True,
            width="stretch",
        )

    with movement_tab:
        product_names = sorted(
            {row["product_name"] for row in data["movements"]}
        )
        type_names = sorted(
            {row["movement_type"] for row in data["movements"]}
        )
        product_col, type_col = st.columns(2)
        product = product_col.selectbox(
            "Produit",
            ["Tous"] + product_names,
            key="movement_history_product",
        )
        movement_type = type_col.selectbox(
            "Type",
            ["Tous"] + type_names,
            key="movement_history_type",
        )
        filtered = [
            row
            for row in data["movements"]
            if (product == "Tous" or row["product_name"] == product)
            and (
                movement_type == "Tous"
                or row["movement_type"] == movement_type
            )
        ]
        movements = pd.DataFrame(
            [
                {
                    "N° mouvement": row["movement_number"],
                    "Date": row["movement_date"],
                    "Produit": row["product_name"],
                    "Type": row["movement_type"],
                    "Direction": DIRECTION_LABELS[row["direction"]],
                    "Quantité": float(row["quantity_packages"]),
                    "Motif": row["reason"],
                }
                for row in filtered
            ]
        )
        st.dataframe(
            movements,
            column_config={
                "Date": st.column_config.DatetimeColumn(
                    format="DD/MM/YYYY HH:mm"
                ),
                "Quantité": st.column_config.NumberColumn(format="%.2f"),
                "Motif": st.column_config.TextColumn(width="large"),
            },
            hide_index=True,
            width="stretch",
        )


def main() -> None:
    render_page_header(
        title="Stocks et réceptions",
        description=(
            "Enregistrez les réceptions fournisseurs, les corrections de "
            "stock et consultez la traçabilité complète des mouvements."
        ),
        icon="📦",
        section="Opérations",
    )

    receipt_result = st.session_state.pop("inventory_receipt_result", None)
    if receipt_result:
        st.success(
            f"Réception {receipt_result['receipt_number']} enregistrée : "
            f"{receipt_result['total_quantity']:.2f} colis, "
            f"{receipt_result['total_amount']:,.0f} FCFA."
        )
    movement_result = st.session_state.pop("inventory_movement_result", None)
    if movement_result:
        st.success(
            f"Mouvement {movement_result['movement_number']} enregistré. "
            f"Nouveau stock de {movement_result['product_name']} : "
            f"{movement_result['current_stock']:.2f} colis."
        )

    db = SessionLocal()
    try:
        service = InventoryService(db)
        suppliers = service.get_suppliers()
        data = service.get_dashboard_data()
        if not suppliers or not data["products"]:
            st.warning("Les fournisseurs ou produits actifs sont indisponibles.")
            return

        receipt_tab, movement_tab, history_tab = st.tabs(
            ["Nouvelle réception", "Mouvement manuel", "Stock et historique"]
        )
        with receipt_tab:
            render_receipt_form(service, suppliers, data["products"])
        with movement_tab:
            render_movement_form(service, data["products"])
        with history_tab:
            render_inventory_history(data)
    except ValueError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error("Impossible de traiter l'opération de stock.")
        st.exception(exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
