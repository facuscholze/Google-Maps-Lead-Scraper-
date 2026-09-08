"""AvaScho brand email HTML builder (spec §40).

Produces inline-styled, email-client compatible HTML (Gmail, Outlook, Apple
Mail, mobile). Brand palette: white/black/beige/gold. All business-provided
text is escaped before interpolation.
"""
from __future__ import annotations

import html
import string
from pathlib import Path
from typing import Any

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "email.html"


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _paragraphs(text: str | None) -> str:
    if not text:
        return ""
    blocks = [b.strip() for b in str(text).split("\n") if b.strip()]
    return "\n".join(f'<p style="margin:0 0 14px 0;">{_esc(b)}</p>' for b in blocks)


def render_proposal_email(content: dict[str, Any]) -> str:
    """Render full email HTML from proposal content dict."""
    try:
        template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover
        template_text = "<html><body>$body_html</body></html>"

    opportunities = content.get("opportunities") or []
    opp_html = "\n".join(
        f"""
        <tr>
          <td style="padding:0 0 10px 0;font-size:14px;line-height:21px;color:#333333;">
            <span style="color:#B08D3E;font-weight:700;">✓</span>&nbsp;
            <strong>{_esc(o.get('title', ''))}</strong>
            {f'<span style="color:#777777;">— {_esc(o.get("opportunity", ""))}</span>' if o.get('opportunity') else ''}
          </td>
        </tr>"""
        for o in opportunities[:4]
    )
    strengths = content.get("strengths") or []
    strengths_html = (
        "\n".join(
            f'<span style="display:inline-block;background:#F5F1E8;color:#444444;'
            f'border-radius:999px;padding:5px 12px;font-size:12px;margin:0 4px 6px 0;">'
            f'{_esc(s)}</span>'
            for s in strengths[:6]
        )
    )

    values = {
        "brand": "AvaScho",
        "business": _esc(content.get("business_name") or "tu empresa"),
        "website_score_badge": (
            f'<div style="background:#111111;color:#ffffff;border-radius:14px;'
            f'padding:18px 22px;text-align:center;max-width:220px;margin:18px auto;">'
            f'<div style="font-size:11px;letter-spacing:1.5px;color:#C9B27A;">WEBSITE SCORE</div>'
            f'<div style="font-size:30px;font-weight:700;color:#ffffff;">'
            f'{_esc(content.get("website_score") or "—")}<span style="font-size:14px;color:#C9B27A;">/10</span>'
            f'</div></div>'
            if content.get("website_score") is not None
            else ""
        ),
        "opening": _paragraphs(content.get("opening")),
        "observation": _paragraphs(content.get("personalized_observation")),
        "strengths_html": strengths_html,
        "opportunities_html": opp_html,
        "solution_title": _esc(content.get("recommended_service") or "Nuestra recomendación"),
        "solution_desc": _paragraphs(content.get("recommended_solution")),
        "cta_text": _esc(content.get("call_to_action") or "Responder a este correo"),
        "cta_link": _esc(content.get("cta_link") or "mailto:hola@avascho.com"),
        "signature": _paragraphs(content.get("signature") or "Saludos,\nEquipo AvaScho"),
        "score_value": _esc(content.get("website_score") or ""),
    }
    return string.Template(template_text).safe_substitute(values)


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
    lines.append(content.get("signature") or "Saludos,\nEquipo AvaScho")
    lines.append("")
    lines.append("Si preferís no recibir más mensajes nuestros, simplemente respondé a este correo y lo tendremos en cuenta.")
    return "\n".join(str(line) for line in lines)
