from dataclasses import dataclass

from django.utils import timezone

from .models import ProductModelChampion


@dataclass(frozen=True)
class ChampionDecision:
    model_key: str
    model_label: str
    metrics: dict
    challenger: dict | None
    decision: str
    reason: str
    improvement_percentage: float | None


def decide_champion(current, evaluation: dict, minimum_improvement: float) -> ChampionDecision:
    """Choisit un modèle stable à partir du backtesting le plus récent."""
    ranking = evaluation["ranking"]
    best = ranking[0]

    if current is None:
        selected = best
        decision = ProductModelChampion.Decision.INSTALLED
        reason = "Première évaluation : la méthode la plus fiable a été installée."
        improvement = None
    else:
        current_row = next(
            (row for row in ranking if row["model"] == current.model_key), None
        )
        if current_row is None:
            selected = best
            decision = ProductModelChampion.Decision.REPLACED
            reason = "L’ancienne méthode n’est plus adaptée à ce profil de ventes."
            improvement = None
        elif best["model"] == current.model_key:
            selected = current_row
            decision = ProductModelChampion.Decision.RETAINED
            reason = "Cette méthode reste la plus fiable sur les ventes récentes."
            improvement = 0.0
        else:
            current_mae = float(current_row["mae"])
            improvement = (
                ((current_mae - float(best["mae"])) / current_mae) * 100
                if current_mae > 0
                else 0.0
            )
            if improvement >= minimum_improvement:
                selected = best
                decision = ProductModelChampion.Decision.REPLACED
                reason = (
                    f"La nouvelle méthode améliore la précision de {improvement:.1f} %."
                )
            else:
                selected = current_row
                decision = ProductModelChampion.Decision.RETAINED
                reason = (
                    "Le gain du challenger est trop faible pour justifier un changement."
                )

    challenger = next(
        (row for row in ranking if row["model"] != selected["model"]), None
    )
    return ChampionDecision(
        model_key=selected["model"],
        model_label=selected["label"],
        metrics=evaluation["models"][selected["model"]],
        challenger=challenger,
        decision=decision,
        reason=reason,
        improvement_percentage=improvement,
    )


def persist_champion(*, company, product_id, product_name, decision):
    now = timezone.now()
    existing = ProductModelChampion.objects.filter(
        company=company, product_id=product_id
    ).first()
    champion_since = (
        existing.champion_since
        if existing and existing.model_key == decision.model_key
        else now
    )
    challenger = decision.challenger or {}
    champion, _ = ProductModelChampion.objects.update_or_create(
        company=company,
        product_id=product_id,
        defaults={
            "product_name": product_name,
            "model_key": decision.model_key,
            "model_label": decision.model_label,
            "mae": decision.metrics.get("mae"),
            "rmse": decision.metrics.get("rmse"),
            "mape": decision.metrics.get("mape"),
            "wape": decision.metrics.get("wape"),
            "bias": decision.metrics.get("bias"),
            "challenger_key": challenger.get("model", ""),
            "challenger_label": challenger.get("label", ""),
            "challenger_mae": challenger.get("mae"),
            "improvement_percentage": decision.improvement_percentage,
            "last_decision": decision.decision,
            "decision_reason": decision.reason,
            "champion_since": champion_since,
            "last_evaluated_at": now,
        },
    )
    return champion
