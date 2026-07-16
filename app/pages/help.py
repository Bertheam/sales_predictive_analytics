import streamlit as st

from app.utils.ui import guide_card, render_page_header


def main() -> None:
    render_page_header(
        title="Guide d'utilisation",
        description=(
            "Retrouvez le parcours conseillé, la signification des indicateurs "
            "et les bonnes pratiques pour exploiter les prévisions."
        ),
        icon="❔",
        section="Aide",
    )

    st.subheader("Parcours recommandé")
    first, second, third = st.columns(3)
    with first:
        guide_card(
            "1 · Alimenter",
            "Importez les ventes, produits, clients et stocks avec les modèles "
            "Excel guidés, puis corrigez les éventuelles erreurs signalées.",
        )
    with second:
        guide_card(
            "2 · Prévoir",
            "Comparez les modèles si nécessaire, puis générez une prévision "
            "future de 1 à 7 jours pour les produits actifs.",
        )
    with third:
        guide_card(
            "3 · Décider",
            "Consultez le pilotage métier pour prioriser les commandes, puis "
            "enregistrez les réceptions et mouvements de stock.",
        )

    st.subheader("Où effectuer chaque action ?")
    st.markdown(
        """
        - **Tableau de bord** : analyser les ventes réalisées sur une période.
        - **Pilotage métier** : voir les risques, alertes et quantités à commander.
        - **Prévision future** : produire et retrouver les prévisions J+1 à J+7.
        - **Comparaison des modèles** : vérifier quel algorithme est le plus précis.
        - **Qualité prédictive** : suivre les erreurs et la dérive dans le temps.
        - **Stocks et réceptions** : saisir les entrées, pertes, casses et ajustements.
        - **Import Excel** : charger de nouvelles données de manière contrôlée.
        """
    )

    st.subheader("Comprendre les indicateurs")
    with st.expander("MAE, RMSE et MAPE"):
        st.markdown(
            """
            - **MAE** : erreur moyenne en colis. Plus elle est faible, mieux c'est.
            - **RMSE** : erreur qui pénalise davantage les gros écarts.
            - **MAPE** : erreur moyenne exprimée en pourcentage.

            Pour une décision quotidienne, privilégiez le classement par **MAE**
            et utilisez la RMSE pour repérer les modèles qui font parfois de très
            grosses erreurs.
            """
        )
    with st.expander("Stock de sécurité et quantité recommandée"):
        st.write(
            "La quantité recommandée couvre la demande prévisionnelle haute et "
            "le stock de sécurité, après déduction du stock actuellement disponible."
        )
    with st.expander("Statut d'une prévision"):
        st.markdown(
            """
            - **Active** : la période prévue n'est pas encore terminée.
            - **Expirée** : la période est terminée mais l'évaluation reste à faire.
            - **Évaluée** : les ventes réelles ont été comparées aux prévisions.
            """
        )

    st.info(
        "Une vente faible pendant une rupture de stock ne représente pas forcément "
        "une demande faible. Le moteur exclut ces jours lorsque c'est nécessaire."
    )


if __name__ == "__main__":
    main()

