"""Explainable lead & opportunity scoring (spec §25-29, §63-64).

Every score returns a `breakdown` with human-readable reasons and deltas.
The rules are deterministic and grounded in place + audit evidence only.
"""
from __future__ import annotations

from typing import Any

from app.core.enums import (
    LeadTemperature,
    Priority,
    RecommendedAction,
)
from app.services.analysis.types import AuditResult
from app.services.catalog import SERVICE_ORDER

RULE_WEIGHTS = {"no_booking": 5, "no_whatsapp": 4, "has_form_no_followup": 3, "no_chat": 2}


def temperature_for(score: int) -> str:
    if score >= 80:
        return LeadTemperature.HOT.value
    if score >= 60:
        return LeadTemperature.WARM.value
    if score >= 40:
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
    ) -> dict[str, Any]:
        rating = rating or 0.0
        lead_reasons: list[dict[str, Any]] = []
        opp_reasons: list[dict[str, Any]] = []
        lead_score = 0
        opportunity_score = 0

        # --- reputation (0-24) ------------------------------------------------
        if rating >= 4.8:
            lead_score += 24
            lead_reasons.append({"delta": 24, "label": "Excelente reputación", "detail": f"Rating {rating} estrellas"})
        elif rating >= 4.5:
            lead_score += 20
            lead_reasons.append({"delta": 20, "label": "Muy buena reputación", "detail": f"Rating {rating} estrellas"})
        elif rating >= 4.2:
            lead_score += 16
            lead_reasons.append({"delta": 16, "label": "Buena reputación", "detail": f"Rating {rating} estrellas"})
        elif rating >= 4.0:
            lead_score += 13
            lead_reasons.append({"delta": 13, "label": "Reputación aceptable", "detail": f"Rating {rating} estrellas"})
        else:
            lead_score += 7
            lead_reasons.append({"delta": 7, "label": "Reputación media", "detail": f"Rating {rating} estrellas"})

        # --- social proof / reviews (0-20) ------------------------------------
        if reviews >= 500:
            lead_score += 20
            lead_reasons.append({"delta": 20, "label": "Muy consolidado", "detail": f"{reviews} reseñas"})
        elif reviews >= 300:
            lead_score += 18
            lead_reasons.append({"delta": 18, "label": "Más de 300 reseñas", "detail": f"{reviews} reseñas"})
        elif reviews >= 150:
            lead_score += 14
            lead_reasons.append({"delta": 14, "label": "Volumen de reseñas relevante", "detail": f"{reviews} reseñas"})
        elif reviews >= 100:
            lead_score += 12
            lead_reasons.append({"delta": 12, "label": "Cien o más reseñas", "detail": f"{reviews} reseñas"})
        elif reviews >= 50:
            lead_score += 9
            lead_reasons.append({"delta": 9, "label": "Con reseñas", "detail": f"{reviews} reseñas"})
        else:
            lead_score += 3
            lead_reasons.append({"delta": 3, "label": "Pocas reseñas", "detail": f"{reviews} reseñas"})

        # --- website (0-26) ----------------------------------------------------
        if has_website and website_score is not None:
            lead_score += 18
            lead_reasons.append({"delta": 18, "label": "Website activo y auditado", "detail": f"Website {website_score:.1f}/10"})
            quality = max(2, min(8, round(website_score / 10 * 8)))
            lead_score += quality
            lead_reasons.append({"delta": quality, "label": "Calidad del website", "detail": f"Score {website_score:.1f}/10"})
            digital_maturity = 6 + round((website_score or 0) * 0.8)
            opportunity_score += digital_maturity
            opp_reasons.append({"delta": digital_maturity, "label": "Madurez digital", "detail": f"Presencia web con score {website_score:.1f}/10"})
        elif has_website:
            lead_score += 12
            lead_reasons.append({"delta": 12, "label": "Website activo", "detail": "Presencia web detectada"})
            opportunity_score += 8
            opp_reasons.append({"delta": 8, "label": "Presencia web detectable", "detail": "El negocio tiene website (aún no auditado)"})
        else:
            lead_score += 0
            opp_reasons.append({"delta": 2, "label": "Sin website", "detail": "No hay presencia web detectable"})

        # --- detected opportunities -----------------------------------------
        if audit and audit.opportunities:
            opp_weight = self._opportunity_weight(audit)
            lead_score += 10
            lead_reasons.append({"delta": 10, "label": "Oportunidades de automatización", "detail": f"{len(audit.opportunities)} oportunidad(es) detectadas"})
            opportunity_score += opp_weight
            opp_reasons.append({"delta": opp_weight, "label": "Brechas de automatización claras", "detail": "; ".join(o["title"] for o in audit.opportunities[:3])})

        # --- contactability ----------------------------------------------------
        if has_phone:
            lead_score += 5
            lead_reasons.append({"delta": 5, "label": "Teléfono disponible", "detail": "Contacto telefónico público"})
            opportunity_score += 4
            opp_reasons.append({"delta": 4, "label": "Contacto telefónico", "detail": "Facilita el primer contacto"})
        if has_email:
            conf_points = {"HIGH": 9, "MEDIUM": 7, "LOW": 3}.get(email_confidence or "LOW", 3)
            lead_score += conf_points
            lead_reasons.append({"delta": conf_points, "label": "Email público encontrado", "detail": f"Confianza {email_confidence}"})
            opportunity_score += conf_points
            opp_reasons.append({"delta": conf_points, "label": "Email disponible", "detail": f"Confianza {email_confidence}"})

        # --- fit bonus from weak automation (opportunity side) --------------------
        if audit:
            if audit.subscores.get("automation", 10) < 6:
                opportunity_score += 6
                opp_reasons.append({"delta": 6, "label": "Automatización ausente o básica", "detail": f"Subscore automatización {audit.subscores['automation']}/10"})
            if audit.subscores.get("booking", 10) < 6:
                opportunity_score += 5
                opp_reasons.append({"delta": 5, "label": "Sin reserva online", "detail": "El negocio gestiona turnos manualmente"})

        lead_score = min(100, lead_score)
        opportunity_score = min(100, opportunity_score)

        recommended_service = self._recommend_service(audit)
        temperature = temperature_for(lead_score)
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
        if not audit or not audit.opportunities:
            return "Custom AI Integration"
        scores: dict[str, int] = {}
        for opportunity in audit.opportunities:
            service = str(opportunity.get("service", ""))
            title = str(opportunity.get("title", ""))
            key = next((rule.key for rule in _RULE_LIST if rule.label.lower() in title.lower()), None)
            scores[service] = scores.get(service, 0) + RULE_WEIGHTS.get(key or "", 1)
        best = max(scores, key=lambda k: (scores[k], -SERVICE_ORDER.index(k) if k in SERVICE_ORDER else 0))
        return best

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
                "Aun así, la gestión de consultas y reservas sigue dependiendo mayormente de procesos manuales."
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
            return "El negocio está en su mejor momento digital; una automatización temprana genera ventaja competitiva."
        return "El negocio podría estar receptivo a mejorar procesos; conviene validar con una primera conversación corta."


from app.services.catalog import OPPORTUNITY_RULES as _RULE_LIST  # noqa: E402
