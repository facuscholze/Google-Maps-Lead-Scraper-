"""ProposalWriter — produces personalized commercial proposals (spec §37-39,
§80-83). Deterministic and grounded: it only references facts passed in context.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.schemas.ai import AIProposal
from app.services.emailing.email_html import render_plain_text, render_proposal_email



class ProposalWriter:
    def build(self, context: dict[str, Any], provider: str = "rule-based") -> AIProposal:
        name = context.get("business_name") or "tu empresa"
        rating = context.get("rating")
        reviews = context.get("reviews") or 0
        website_score = context.get("website_score")
        opportunities = context.get("opportunities") or []
        strengths = context.get("strengths") or []
        from app.services.catalog import AVA_SCHO_SERVICES, recommended_web_service

        service = context.get("recommended_service")
        if service not in AVA_SCHO_SERVICES:
            service = recommended_web_service(bool(context.get("website_url")), website_score)
        service_desc = context.get("service_description") or (
            AVA_SCHO_SERVICES[service]["description"]
        )

        first = opportunities[0] if opportunities else {}
        top_title = str(first.get("title") or "mejorar la atención y la captación de consultas")
        top_evidence = str(first.get("evidence") or "")

        # --- real reputation fact (never invented) ---------------------------
        if reviews > 0 and rating:
            reputation = f"su presencia en Google, con {reviews} reseñas y una valoración de {rating}"
        elif reviews > 0:
            reputation = f"las {reviews} reseñas acumuladas en Google"
        else:
            reputation = "su actividad en Google"

        # --- concrete observation ---------------------------------------------
        observation_parts = [
            f"Estuvimos revisando la presencia digital de {name} y nos llamó la atención "
            f"{reputation}."
        ]
        if top_evidence:
            observation_parts.append(
                f"También encontramos una oportunidad concreta relacionada con {top_title.lower()}: "
                f"{top_evidence[:280].rstrip('.')}."
            )
        else:
            observation_parts.append(
                f"Creemos que {top_title.lower()} podría abrir una oportunidad interesante "
                "para mejorar la forma en que atienden y captan consultas."
            )
        observation = "\n".join(observation_parts)

        recommended_solution = (
            f"Desde {settings.proposal_brand} diseñamos landing pages y sitios web para negocios. "
            f"En este caso, creemos que {service} podría tener sentido: {service_desc}"
        )

        cta = (
            f"Si te interesa, podemos conversar sobre la estructura y el alcance de una web para {name}, "
            "sin ningún compromiso."
        )

        content: dict[str, Any] = {
            "business_name": name,
            "website_score": website_score,
            "opening": f"Hola {name},",
            "personalized_observation": observation,
            # F7/D7.1: las fortalezas viajan como dicts anclados (text/evidence/kind);
            # el renderer las formatea — acá se conserva la trazabilidad.
            "strengths": strengths[:4] if strengths and isinstance(strengths[0], dict) else [
                {"text": str(s), "evidence": None, "kind": "FACT"} for s in strengths[:4]
            ],
            "opportunities": [
                {
                    "title": o.get("title"),
                    "opportunity": o.get("opportunity"),
                    "evidence": o.get("evidence"),
                }
                for o in opportunities[:3]
            ],
            "recommended_service": service,
            "recommended_solution": recommended_solution,
            "call_to_action": cta,
            "signature": f"Saludos,\nEquipo {settings.proposal_brand}",
        }
        html = render_proposal_email(content)
        content["html"] = html
        content["plain_text"] = render_plain_text(content)

        return AIProposal(
            subject=f"{service} para {name}",
            opening=content["opening"],
            personalized_observation=observation,
            strengths=content["strengths"],
            opportunities=content["opportunities"],
            recommended_solution=recommended_solution,
            call_to_action=cta,
            signature=content["signature"],
            plain_text=content["plain_text"],
            html=html,
            confidence=context.get("confidence") or 0.85,
            model_note=(
                f"Generado con datos reales de {name}: reseñas, rating, auditoría de website "
                f"y evidencia verificada. Provider: {provider}."
            ),
        )

    # backward-compatible label used in tests
    build_email = build
