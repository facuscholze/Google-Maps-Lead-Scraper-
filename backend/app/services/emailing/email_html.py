"""Server-side rendering of the email inside nuevo html innblock.html.

No JavaScript is executed or sent. All lead/model text is HTML-escaped.
The packaged template is also available in standalone backend Docker builds.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.core.config import settings
from app.services.catalog import AVA_SCHO_SERVICES

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "innblock.html"


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _paragraphs(text: str | None) -> str:
    return "\n".join(f'<p style="margin:0 0 14px;">{_esc(b.strip())}</p>'
                     for b in str(text or "").split("\n") if b.strip())


def _safe_link(value: str) -> str:
    url = urlsplit(value)
    if url.scheme not in ("https", "http", "mailto") or (url.scheme != "mailto" and not url.netloc):
        raise ValueError("Proposal contact links must use http(s) or mailto")
    return _esc(value)


def render_proposal_email(content: dict[str, Any]) -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    opportunities = "".join(
        '<p style="margin:0 0 14px;"><strong>' + _esc(o.get("title")) + '</strong><br>'
        + _esc(o.get("opportunity")) + '<br><span style="color:#777777;">'
        + _esc(o.get("evidence")) + '</span></p>'
        for o in (content.get("opportunities") or [])[:4]
    )
    services = "".join(
        f'<table role="presentation" width="100%" style="border-top:1px solid #e3e3e3;">'
        f'<tr><td style="padding:16px 0;color:#d90000;width:40px;">{i:02}</td>'
        f'<td style="padding:16px 0;"><strong>{_esc(name)}</strong>'
        f'<p style="color:#666666;font-size:13px;line-height:20px;">{_esc(service["description"])}</p></td></tr></table>'
        for i, (name, service) in enumerate(AVA_SCHO_SERVICES.items(), 1)
    )
    values = {
        "empresa": _esc(settings.proposal_brand),
        "empresaCliente": _esc(content.get("business_name") or "tu negocio"),
        "ubicacion": "Uruguay · Argentina", "hechoEn": "Uruguay · Argentina · Brasil",
        "anio": str(datetime.now(timezone.utc).year), "rojo": "#d90000", "negro": "#070707",
        "lema": "Diseñamos landing pages y sitios web para presentar tu negocio y facilitar las consultas.",
        "apertura": _paragraphs(content.get("opening")),
        "observacion": _paragraphs(content.get("personalized_observation")),
        "servicioRecomendado": _esc(content.get("recommended_service") or "Nuestra propuesta web"),
        "solucion": _paragraphs(content.get("recommended_solution")),
        "oportunidades": opportunities,
        "fortalezas": "".join(_paragraphs(s) for s in (content.get("strengths") or [])[:4]),
        "servicios": services,
        "llamadaAccion": _esc(content.get("call_to_action") or "¿Conversamos sobre tu próxima web?"),
        "firma": _paragraphs(content.get("signature") or f"Saludos,\nEquipo {settings.proposal_brand}"),
        "tuEmail": _esc(settings.proposal_contact_email),
        "linkContacto": _safe_link(settings.proposal_contact_url),
        "linkWeb": _safe_link(settings.proposal_website_url),
    }
    # Strict substitution: a missing slot is a deployment error, not a broken email.
    return re.sub(r"{{(\w+)}}", lambda match: values[match[1]], template)


def render_plain_text(content: dict[str, Any]) -> str:
    lines: list[str] = []
    opening = content.get("opening") or ""
    observation = content.get("personalized_observation") or ""
    lines.extend([opening.strip(), "", observation.strip(), ""])
    if content.get("strengths"):
        lines.append("Lo que valoramos de tu presencia digital:")
        lines.extend(f"• {s}" for s in content["strengths"][:4])
        lines.append("")
    if content.get("opportunities"):
        lines.append("Oportunidades detectadas:")
        for o in content["opportunities"][:4]:
            lines.append(f"• {o.get('title', '')}: {o.get('opportunity', '')}")
        lines.append("")
    lines.append(f"Nuestra recomendación: {content.get('recommended_service', '')}")
    lines.append("")
    lines.append(content.get("recommended_solution") or "")
    lines.append("")
    lines.append(content.get("call_to_action") or "")
    lines.append("")
    lines.append(content.get("signature") or f"Saludos,\nEquipo {settings.proposal_brand}")
    lines.append("")
    lines.append("Si preferís no recibir más mensajes nuestros, simplemente respondé a este correo y lo tendremos en cuenta.")
    return "\n".join(str(line) for line in lines)
