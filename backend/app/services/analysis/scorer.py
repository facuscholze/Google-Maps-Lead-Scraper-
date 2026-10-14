"""Explainable lead & opportunity scoring (spec §25-29, §63-64).

Every score returns a `breakdown` with human-readable reasons and deltas.
The rules are deterministic and grounded in place + audit evidence only.

Fase 6 (D6.2): cada regla pertenece a una **categoría** y su aporte se puede
ponderar por workspace con `weights` (multiplicador 0..3, default 1.0). Los
umbrales de temperatura también son configurables (default 80/60/40). El
breakdown registra `base_delta`, `weight` y `category` además del `delta`
final, para que la UI muestre exactamente qué se ponderó — nada se inventa.
"""
from __future__ import annotations

from typing import Any

from app.core.enums import (
    LeadTemperature,
    Priority,
    RecommendedAction,
)
from app.services.analysis.types import AuditResult

# Categorías ponderables (D6.2). Cada regla del score pertenece a una.
SCORE_CATEGORIES = (
    "reputation",
    "reviews",
    "website_presence",
    "website_quality",
    "opportunities",
    "phone",
    "email",
)

DEFAULT_THRESHOLDS = (80, 60, 40)  # hot, warm, cold

RULE_WEIGHTS = {"no_cta": 5, "no_contact": 4, "no_mobile": 5, "no_seo": 3}


def resolve_weights(raw: dict[str, Any] | None) -> dict[str, float]:
    """Devuelve un dict completo categoría→peso (default 1.0).

    Ignora claves desconocidas y clampa a 0..3 (el endpoint valida igualmente;
    esto es defensa en profundidad para llamadas directas/pipeline).
    """
    weights = {c: 1.0 for c in SCORE_CATEGORIES}
    if not raw:
        return weights
    for cat in SCORE_CATEGORIES:
        if raw.get(cat) is None:
            continue
        try:
            value = float(raw[cat])
        except (TypeError, ValueError):
            continue
        weights[cat] = min(3.0, max(0.0, value))
    return weights


def temperature_for(score: int, thresholds: tuple[int, int, int] | None = None) -> str:
    hot, warm, cold = thresholds or DEFAULT_THRESHOLDS
    if score >= hot:
        return LeadTemperature.HOT.value
    if score >= warm:
        return LeadTemperature.WARM.value
    if score >= cold:
        return LeadTemperature.COLD.value
    return LeadTemperature.LOW.value


def priority_for(lead_score: int | None, opportunity_score: int | None) -> str:
    lead_score = lead_score or 0
    opportunity_score = opportunity_score or 0
    if lead_score >= 80 and opportunity_score >= 75:
        return Priority.P1.value
    if lead_score >= 65 and opportunity_score >= 60:
        return Priority.P2.value
    if lead_score >= 45 or opportunity_score >= 45:
        return Priority.P3.value
    return Priority.P4.value


class LeadScorer:
    """Computes explainable lead/opportunity scores and the "why this lead" text."""

    def score(
        self,
        *,
        rating: float | None,
        reviews: int,
        website_score: float | None,
        audit: AuditResult | None,
        has_email: bool,
        email_confidence: str | None,
        has_phone: bool,
        has_website: bool,
        business_name: str,
        social_count: int = 0,
        weights: dict[str, float] | None = None,
        thresholds: tuple[int, int, int] | None = None,
    ) -> dict[str, Any]:
        w = resolve_weights(weights)

        def sc(base: float, cat: str) -> int:
            """Puntos finales tras aplicar el peso de la categoría (redondeado)."""
            return int(round(base * w[cat], 0))

        def add(side: list[dict[str, Any]], *, base: float, cat: str, label: str, detail: str) -> int:
            delta = sc(base, cat)
            side.append({
                "delta": delta,
                "base_delta": base,
                "weight": w[cat],
                "category": cat,
                "label": label,
                "detail": detail,
            })
            return delta

        rating = rating or 0.0
        lead_reasons: list[dict[str, Any]] = []
        opp_reasons: list[dict[str, Any]] = []
        lead_score = 0
        opportunity_score = 0

        # --- reputation (0-24) ------------------------------------------------
        if rating >= 4.8:
            lead_score += add(lead_reasons, base=24, cat="reputation", label="Excelente reputación", detail=f"Rating {rating} estrellas")
        elif rating >= 4.5:
            lead_score += add(lead_reasons, base=20, cat="reputation", label="Muy buena reputación", detail=f"Rating {rating} estrellas")
        elif rating >= 4.2:
            lead_score += add(lead_reasons, base=16, cat="reputation", label="Buena reputación", detail=f"Rating {rating} estrellas")
        elif rating >= 4.0:
            lead_score += add(lead_reasons, base=13, cat="reputation", label="Reputación aceptable", detail=f"Rating {rating} estrellas")
        else:
            lead_score += add(lead_reasons, base=7, cat="reputation", label="Reputación media", detail=f"Rating {rating} estrellas")

        # --- social proof / reviews (0-20) ------------------------------------
        if reviews >= 500:
            lead_score += add(lead_reasons, base=20, cat="reviews", label="Muy consolidado", detail=f"{reviews} reseñas")
        elif reviews >= 300:
            lead_score += add(lead_reasons, base=18, cat="reviews", label="Más de 300 reseñas", detail=f"{reviews} reseñas")
        elif reviews >= 150:
            lead_score += add(lead_reasons, base=14, cat="reviews", label="Volumen de reseñas relevante", detail=f"{reviews} reseñas")
        elif reviews >= 100:
            lead_score += add(lead_reasons, base=12, cat="reviews", label="Cien o más reseñas", detail=f"{reviews} reseñas")
        elif reviews >= 50:
            lead_score += add(lead_reasons, base=9, cat="reviews", label="Con reseñas", detail=f"{reviews} reseñas")
        else:
            lead_score += add(lead_reasons, base=3, cat="reviews", label="Pocas reseñas", detail=f"{reviews} reseñas")

        # --- website (0-26) ----------------------------------------------------
        if has_website and website_score is not None:
            lead_score += add(lead_reasons, base=18, cat="website_presence", label="Website activo y auditado", detail=f"Website {website_score:.1f}/10")
            quality = max(2, min(8, round(website_score / 10 * 8)))
            lead_score += add(lead_reasons, base=quality, cat="website_quality", label="Calidad del website", detail=f"Score {website_score:.1f}/10")
            digital_maturity = 6 + round((10 - website_score) * 2)
            opportunity_score += add(opp_reasons, base=digital_maturity, cat="website_quality", label="Oportunidad de mejora web", detail=f"Presencia web con score {website_score:.1f}/10")
        elif has_website:
            lead_score += add(lead_reasons, base=12, cat="website_presence", label="Website activo", detail="Presencia web detectada")
            opportunity_score += add(opp_reasons, base=8, cat="website_presence", label="Presencia web detectable", detail="El negocio tiene website (aún no auditado)")
        else:
            lead_score += add(lead_reasons, base=16, cat="website_presence", label="Potencial para una web nueva", detail="Sin sitio registrado en Google Places")
            opportunity_score += add(opp_reasons, base=30, cat="website_presence", label="Web nueva", detail="No hay sitio registrado; validar si ya tienen uno")

        # --- detected opportunities -------------------------------------------
        if audit and audit.opportunities:
            opp_weight = self._opportunity_weight(audit)
            lead_score += add(lead_reasons, base=10, cat="opportunities", label="Oportunidades de diseño web", detail=f"{len(audit.opportunities)} oportunidad(es) detectadas")
            opportunity_score += add(opp_reasons, base=opp_weight, cat="opportunities", label="Mejoras web detectadas", detail="; ".join(o["title"] for o in audit.opportunities[:3]))

        # --- contactability ----------------------------------------------------
        if has_phone:
            lead_score += add(lead_reasons, base=5, cat="phone", label="Teléfono disponible", detail="Contacto telefónico público")
            opportunity_score += add(opp_reasons, base=4, cat="phone", label="Contacto telefónico", detail="Facilita el primer contacto")
        if has_email:
            conf_points = {"HIGH": 9, "MEDIUM": 7, "LOW": 3}.get(email_confidence or "LOW", 3)
            lead_score += add(lead_reasons, base=conf_points, cat="email", label="Email público encontrado", detail=f"Confianza {email_confidence}")
            opportunity_score += add(opp_reasons, base=conf_points, cat="email", label="Email disponible", detail=f"Confianza {email_confidence}")

        # Web conversion and mobile experience, not invisible automation.
        if audit:
            for dimension in ("conversion", "mobile"):
                if audit.subscores.get(dimension, 10) < 6:
                    opportunity_score += add(opp_reasons, base=6, cat="opportunities", label=f"Mejora web: {dimension}",
                                             detail=f"Subscore {dimension}: {audit.subscores[dimension]}/10")

        lead_score = min(100, lead_score)
        opportunity_score = min(100, opportunity_score)

        from app.services.catalog import recommended_web_service

        recommended_service = recommended_web_service(has_website, website_score)
        temperature = temperature_for(lead_score, thresholds)
        priority = priority_for(lead_score, opportunity_score)
        recommended_action = self._recommended_action(
            temperature=temperature,
            email_confidence=email_confidence,
            has_email=has_email,
            lead_score=lead_score,
            opportunity_score=opportunity_score,
        )
        confidence = self._confidence(audit=audit, has_website=has_website, has_email=has_email)

        return {
            "lead_score": lead_score,
            "opportunity_score": opportunity_score,
            "lead_breakdown": lead_reasons,
            "opportunity_breakdown": opp_reasons,
            "temperature": temperature,
            "priority": priority,
            "recommended_action": recommended_action,
            "recommended_service": recommended_service,
            "confidence": confidence,
            "thresholds": thresholds or DEFAULT_THRESHOLDS,
            "why_this_lead": self._why_this_lead(
                business_name=business_name,
                rating=rating,
                reviews=reviews,
                website_score=website_score,
                audit=audit,
                email_confidence=email_confidence,
                has_website=has_website,
            ),
            "why_now": self._why_now(audit=audit, temperature=temperature),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _opportunity_weight(audit: AuditResult | None) -> int:
        if not audit:
            return 0
        total = 0
        for opportunity in audit.opportunities:
            title = str(opportunity.get("title", ""))
            key = next(
                (rule.key for rule in _RULE_LIST if rule.label.lower() in title.lower()),
                None,
            )
            total += RULE_WEIGHTS.get(key or "", 2)
        return min(40, total * 3)

    @staticmethod
    def _recommend_service(audit: AuditResult | None) -> str:
        from app.services.catalog import recommended_web_service

        return recommended_web_service(bool(audit and audit.extracted.url),
                                       audit.overall_score if audit else None)

    @staticmethod
    def _recommended_action(
        temperature: str,
        email_confidence: str | None,
        has_email: bool,
        lead_score: int,
        opportunity_score: int,
    ) -> str:
        if not has_email:
            if lead_score >= 75 and opportunity_score >= 70:
                return RecommendedAction.REVIEW_FIRST.value
            return RecommendedAction.LOW_PRIORITY.value
        if email_confidence == "HIGH":
            if temperature in (LeadTemperature.HOT.value, LeadTemperature.WARM.value):
                return RecommendedAction.CONTACT_NOW.value
            return RecommendedAction.REVIEW_FIRST.value
        if email_confidence == "MEDIUM":
            if temperature == LeadTemperature.HOT.value:
                return RecommendedAction.REVIEW_FIRST.value
            return RecommendedAction.REVIEW_FIRST.value
        return RecommendedAction.REVIEW_FIRST.value  # LOW confidence → never auto-send

    @staticmethod
    def _confidence(audit: AuditResult | None, has_website: bool, has_email: bool) -> float:
        score = 0.25
        if has_website:
            score += 0.25
        if audit is not None:
            pages = audit.extracted.page_count if audit.extracted else 0
            score += 0.25 if pages >= 2 else 0.1
        if has_email:
            score += 0.2
        return round(min(0.99, score), 2)

    @staticmethod
    def _why_this_lead(
        business_name: str,
        rating: float,
        reviews: int,
        website_score: float | None,
        audit: AuditResult | None,
        email_confidence: str | None,
        has_website: bool,
    ) -> str:
        parts: list[str] = []
        if reviews >= 100 and rating >= 4.0:
            parts.append(
                f"{business_name} cuenta con una reputación sólida en Google, con {reviews} reseñas y {rating} estrellas."
            )
        elif reviews > 0:
            parts.append(
                f"{business_name} tiene presencia en Google con {reviews} reseñas y {rating} estrellas."
            )
        if has_website and website_score is not None:
            parts.append(f"Su website está activo ({website_score:.1f}/10) y presenta sus servicios.")
        elif has_website:
            parts.append("Su website está activo.")
        if audit and audit.opportunities:
            summary = "; ".join(o["title"] for o in audit.opportunities[:3])
            parts.append(
                f"Sin embargo, detectamos oportunidades concretas: {summary.lower()}."
            )
        else:
            parts.append(
                "Conviene validar si necesitan una landing page o un sitio institucional antes de definir el alcance."
            )
        if email_confidence:
            parts.append(
                f"Contamos con un canal de contacto público (email con confianza {email_confidence})."
            )
        return " ".join(parts)

    @staticmethod
    def _why_now(audit: AuditResult | None, temperature: str) -> str:
        if audit and audit.opportunities:
            first = audit.opportunities[0]
            return (
                f"El momento es adecuado: {first['evidence'].lower()} "
                f"Actuar ahora posiciona a AvaScho como el partner que cierra esa brecha antes que la competencia."
            )
        if temperature == LeadTemperature.HOT.value:
            return "El negocio está en su mejor momento digital; se puede explorar una landing para un servicio o campaña."
        return "El negocio podría estar receptivo a mejorar su presencia web; conviene validar con una primera conversación corta."


from app.services.catalog import OPPORTUNITY_RULES as _RULE_LIST  # noqa: E402
