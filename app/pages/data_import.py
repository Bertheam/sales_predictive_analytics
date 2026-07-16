import hashlib
import json

import pandas as pd
import streamlit as st

from app.database.session import SessionLocal
from app.services.data_import_service import DataImportService
from app.utils.ui import render_page_header


IMPORT_LABELS = {
    "SALES": "Ventes",
    "STOCKS": "Stocks journaliers",
    "PRODUCTS": "Produits",
    "CUSTOMERS": "Clients",
}
STATUS_LABELS = {
    "COMPLETED": "🟢 Terminé",
    "PARTIALLY_COMPLETED": "🟠 Partiellement terminé",
    "FAILED": "🔴 Échec",
    "IMPORTING": "🔵 En cours",
    "PENDING": "⚪ En attente",
}


def render_format_help(service: DataImportService, import_type: str) -> None:
    definition = service.get_definitions()[import_type]
    st.info(definition["description"])
    required_col, optional_col, automatic_col = st.columns(3)
    required_col.markdown(
        "**Colonnes obligatoires**\n\n"
        + "\n\n".join(f"- `{column}`" for column in definition["required"])
    )
    optional_col.markdown(
        "**Colonnes facultatives**\n\n"
        + "\n\n".join(f"- `{column}`" for column in definition["optional"])
    )
    automatic_col.markdown(
        "**Calculés automatiquement**\n\n"
        + "\n\n".join(
            f"- `{column}`" for column in definition["automatic"]
        )
    )

    st.download_button(
        "Télécharger le modèle Excel guidé",
        service.get_template(import_type, "XLSX"),
        file_name=f"modele_{import_type.lower()}.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        width="stretch",
    )


def render_analysis(service: DataImportService, analysis: dict) -> None:
    valid_count = len(analysis["valid_rows"])
    invalid_count = len(analysis["invalid_rows"])
    duplicate_count = len(analysis["duplicate_rows"])
    total_col, valid_col, invalid_col, duplicate_col = st.columns(4)
    total_col.metric("Lignes analysées", analysis["total_rows"])
    valid_col.metric("Lignes valides", valid_count)
    invalid_col.metric("Lignes invalides", invalid_count)
    duplicate_col.metric("Doublons ignorés", duplicate_count)

    if analysis["already_imported"]:
        st.error(
            "Ce fichier a déjà été importé. Son empreinte correspond "
            "à un lot terminé."
        )
    elif invalid_count:
        st.warning(
            "Des erreurs ont été détectées. Corrigez le fichier ou "
            "choisissez d'importer uniquement les lignes valides."
        )
    elif not valid_count:
        st.warning("Aucune nouvelle ligne valide à importer.")
    else:
        st.success("Le fichier est valide et peut être importé.")

    st.subheader("Aperçu de validation")
    st.caption("Les 100 premières lignes sont affichées.")
    st.dataframe(
        analysis["preview"],
        column_config={
            "Ligne": st.column_config.NumberColumn(format="%d"),
            "Erreurs": st.column_config.TextColumn(width="large"),
        },
        hide_index=True,
        width="stretch",
    )

    if analysis["already_imported"] or not valid_count:
        return

    import_valid_only = False
    if invalid_count:
        import_valid_only = st.checkbox(
            "Importer uniquement les lignes valides",
            help=(
                "Les lignes invalides seront conservées dans le journal "
                "du lot avec le détail de leurs erreurs."
            ),
        )
    disabled = invalid_count > 0 and not import_valid_only
    if st.button(
        "Confirmer l'import dans PostgreSQL",
        type="primary",
        disabled=disabled,
    ):
        with st.spinner("Import transactionnel en cours..."):
            result = service.execute_import(analysis, import_valid_only)
        st.session_state.pop("data_import_analysis", None)
        st.session_state["data_import_result"] = result
        st.rerun()


def render_new_import(service: DataImportService) -> None:
    import_type = st.selectbox(
        "Type de données",
        options=list(IMPORT_LABELS),
        format_func=lambda value: IMPORT_LABELS[value],
    )
    with st.expander("Format attendu et modèles", expanded=True):
        render_format_help(service, import_type)

    uploaded_file = st.file_uploader(
        "Fichier Excel complété",
        type=["xlsx"],
        help="Taille et contenu contrôlés avant toute écriture en base.",
    )
    if uploaded_file is None:
        return

    content = uploaded_file.getvalue()
    if len(content) > 20 * 1024 * 1024:
        st.error("Le fichier dépasse la taille maximale autorisée de 20 Mo.")
        return
    st.caption(
        f"{uploaded_file.name} · {len(content) / 1024:.1f} Ko"
    )
    if st.button("Analyser et valider le fichier", type="secondary"):
        with st.spinner("Lecture et validation des données..."):
            analysis = service.analyze_file(
                file_name=uploaded_file.name,
                content=content,
                import_type=import_type,
            )
        st.session_state["data_import_analysis"] = analysis

    analysis = st.session_state.get("data_import_analysis")
    if analysis and (
        analysis["file_name"] == uploaded_file.name
        and analysis["import_type"] == import_type
        and analysis["file_hash"] == hashlib.sha256(content).hexdigest()
    ):
        render_analysis(service, analysis)


def history_frame(history: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Lot": row["batch_number"],
                "Fichier": row["file_name"],
                "Type": IMPORT_LABELS.get(row["import_type"], row["import_type"]),
                "Format": row["file_type"],
                "Total": row["total_rows"],
                "Importées": row["valid_rows"],
                "Invalides": row["invalid_rows"],
                "Doublons": row["duplicate_rows"],
                "Statut": STATUS_LABELS.get(row["status"], row["status"]),
                "Date": row["created_at"],
            }
            for row in history
        ]
    )


def render_history(service: DataImportService) -> None:
    history = service.get_history()
    if not history:
        st.info("Aucun lot d'import n'est enregistré.")
        return

    st.dataframe(
        history_frame(history),
        column_config={
            "Date": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Total": st.column_config.NumberColumn(format="%d"),
            "Importées": st.column_config.NumberColumn(format="%d"),
            "Invalides": st.column_config.NumberColumn(format="%d"),
            "Doublons": st.column_config.NumberColumn(format="%d"),
        },
        hide_index=True,
        width="stretch",
    )

    batches_with_errors = [row for row in history if row["recorded_errors"]]
    if not batches_with_errors:
        return
    options = {
        f"{row['batch_number']} · {row['file_name']}": row
        for row in batches_with_errors
    }
    st.subheader("Erreurs d'un lot")
    selected_label = st.selectbox("Lot", list(options))
    errors = service.get_batch_errors(str(options[selected_label]["id"]))
    error_table = pd.DataFrame(
        [
            {
                "Ligne": row["source_row_number"],
                "Erreurs": " · ".join(row["error_messages"]),
                "Données": json.dumps(
                    row["raw_data"], ensure_ascii=False, default=str
                ),
            }
            for row in errors
        ]
    )
    st.dataframe(
        error_table,
        column_config={
            "Erreurs": st.column_config.TextColumn(width="large"),
            "Données": st.column_config.TextColumn(width="large"),
        },
        hide_index=True,
        width="stretch",
    )


def main() -> None:
    render_page_header(
        title="Import des données Excel",
        description=(
            "Alimentez l'application avec des données réelles après contrôle "
            "du format, des doublons et de la cohérence métier."
        ),
        icon="📥",
        section="Opérations",
    )

    result = st.session_state.pop("data_import_result", None)
    if result:
        st.success(
            f"Lot {result['batch_number']} terminé : "
            f"{result['imported_rows']} ligne(s) importée(s), "
            f"{result['duplicate_rows']} doublon(s) ignoré(s)."
        )

    db = SessionLocal()
    try:
        service = DataImportService(db)
        import_tab, history_tab = st.tabs(
            ["Nouvel import", "Historique des imports"]
        )
        with import_tab:
            render_new_import(service)
        with history_tab:
            render_history(service)
    except ValueError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error("Impossible de traiter l'import de données.")
        st.exception(exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
