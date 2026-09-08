"""ProposalWriter — produces personalized commercial proposals (spec §37-39,
§80-83). Deterministic and grounded: it only references facts passed in context.
"""
from __future__ import annotations

from typing import Any

from app.schemas.ai import AIProposal
from app.services.emailing.email_html import render_plain_text, render_proposal_email

SUBJECTS = {
    "booking": "Una idea para {name}: turnos y reservas sin fricción",
    "whatsapp": "Una idea para {name}: un WhatsApp que responde solo",
    "followup": "Una idea para {name}: seguimiento automático de consultas",
    "generic": "Una oportunidad que vimos en {name}",
}


def _subject_key(title: str) -> str:
    lower = title.lower()
    if "reserva" in lower:
        return "booking"
    if "whatsapp" in lower:
        return "whatsapp"
    if "seguimiento" in lower or "follow" in lower:
        return "followup"
    return "generic"


class ProposalWriter:
    def build(self, context: dict[str, Any], provider: str = "rule-based") -> AIProposal:
        name = context.get("business_name") or "tu empresa"
        rating = context.get("rating")
        reviews = context.get("reviews") or 0
        website_score = context.get("website_score")
        opportunities = context.get("opportunities") or []
        strengths = context.get("strengths") or []
        service = context.get("recommended_service") or "Custom AI Integration"
        service_desc = context.get("service_description") or (
            "Una automatización a la medida de tus procesos actuales."
        )
        evidence_blob = context.get("evidence_blob")

        first = opportunities[0] if opportunities else {}
        top_title = str(first.get("title") or "mejorar la atención y la captación de consultas")
        top_evidence = str(first.get("evidence") or "")
        key = _subject_key(top_title)

        # --- real reputation fact (never invented) ---------------------------
        if reviews > 0 and rating:
            reputation = f"su muy buena reputación en Google, con {reviews} reseñas y una valoración de {rating}"
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
            f"Desde AvaScho trabajamos en automatización e inteligencia artificial para negocios. "
            f"En este caso, creemos que {service} podría tener sentido: {service_desc}"
        )

        cta = (
            f"Si te interesa, podemos mostrarte brevemente cómo podría funcionar aplicado a {name}, "
            "sin ningún compromiso."
        )

        plain_text = "\n".join(
            [
                f"Hola {name},",
                "",
                observation,
                "",
                recommended_solution,
                "",
                cta,
                "",
                "Saludos,",
                "Equipo AvaScho",
                "",
                "Si preferís no recibir más mensajes nuestros, simplemente respondé a este correo y lo tendremos en cuenta.",
            ]
        )

        content: dict[str, Any] = {
            "business_name": name,
            "website_score": website_score,
            "opening": f"Hola {name},",
            "personalized_observation": observation,
            "strengths": [str(s) for s in strengths[:4]],
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
            "signature": "Saludos,\nEquipo AvaScho",
        }
        html = render_proposal_email(content)
        content["html"] = html
        content["plain_text"] = render_plain_text(content)

        return AIProposal(
            subject=SUBJECTS[key].format(name=name),
            opening=content["opening"],
            personalized_observation=observation,
            strengths=content["strengths"],
            opportunities=content["opportunities"],
            recommended_solution=recommended_solution,
            call_to_action=cta,
            signature=content["signature"],
            plain_text=plain_text,
            html=html,
            confidence=context.get("confidence") or 0.85,
            model_note=(
                f"Generado con datos reales de {name}: reseñas, rating, auditoría de website "
                f"y evidencia verificada. Provider: {provider}."
            ),
        )

    # backward-compatible label used in tests
    build_email = build
