"""innblock email renderer.

Single source of truth for the mail design:
  - templates/innblock_email.html  → the template (extracted from
    "nuevo html innblock.html", the visual reference, which is NOT used at runtime)
  - brand_config.py                → brand/socios/services config

Rules enforced here:
  - every lead-provided value is HTML-escaped before it is inserted;
  - the HTML fragments (servicios, firma, diagnóstico, evidencia, observación)
    are built by this module from escaped values only;
  - an unresolved {{placeholder}} raises instead of being sent to a lead;
  - nothing is invented: sections that have no real data are omitted, and
    evidence cells show "—" when the lead has no value for them.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from app.services.emailing.brand_config import BRAND, SERVICIOS, SOCIOS, brand_year

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "innblock_email.html"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
_MONO = "font-family:'Martian Mono','Courier New',monospace;"
_MAX_EVIDENCE_CHARS = 300

PLAIN_UNSUBSCRIBE = (
    'Si no querés recibir más correos, respondé con la palabra "BAJA" y no te volvemos a escribir.'
)


class TemplateRenderError(Exception):
    pass


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _paragraphs(text: str | None, style: str) -> str:
    if not text:
        return ""
    blocks = [b.strip() for b in str(text).split("\n") if b.strip()]
    return "\n".join(f'<p style="{style}">{_esc(b)}</p>' for b in blocks)


# ----------------------------------------------------------------- fragments --
def _servicios_html() -> str:
    rows = []
    last = len(SERVICIOS) - 1
    for i, s in enumerate(SERVICIOS):
        borde = f"border-top:1px solid {BRAND['negro']};" if i == 0 else "border-top:1px solid #e3e3e3;"
        fin = f"border-bottom:1px solid {BRAND['negro']};" if i == last else ""
        rows.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="{borde}{fin}"><tr>'
            f'<td width="40" valign="top" style="padding:16px 0;{_MONO}color:{BRAND["rojo"]};font-size:12px;">{i + 1:02d}</td>'
            f'<td valign="top" style="padding:16px 0;"><p style="margin:0 0 4px 0;color:{BRAND["negro"]};font-size:16px;font-weight:600;">{_esc(s["titulo"])}</p>'
            f'<p style="margin:0;color:#666666;font-size:13px;line-height:20px;">{_esc(s["texto"])}</p></td>'
            f'<td width="90" align="right" valign="top" style="padding:16px 0;{_MONO}color:#777777;font-size:11px;">{_esc(s["tiempo"])}</td>'
            "</tr></table>"
        )
    return "\n".join(rows)


def _firma_html() -> str:
    width = 100 // max(1, len(SOCIOS))
    cells = []
    for p in SOCIOS:
        digits = re.sub(r"\D", "", p["telefono"])
        wa = f"https://wa.me/{digits}" if digits else "#"
        cells.append(
            f'<td class="col" width="{width}%" valign="top" style="padding:0 16px 0 0;">'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td valign="top" style="border-left:3px solid {BRAND["rojo"]};padding:2px 0 2px 12px;">'
            f'<p style="margin:0;color:{BRAND["negro"]};font-size:16px;font-weight:800;">{_esc(p["nombre"])}</p>'
            f'<p style="margin:3px 0 0 0;{_MONO}color:{BRAND["rojo"]};font-size:11px;letter-spacing:1px;text-transform:uppercase;">'
            f'{_esc(p["rol"])} · {_esc(BRAND["empresa"])}</p>'
            f'<p style="margin:6px 0 0 0;font-size:13px;"><a href="{_esc(wa)}" style="color:#555555;text-decoration:none;">{_esc(p["telefono"])}</a></p>'
            "</td></tr></table></td>"
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        + "".join(cells)
        + "</tr></table>"
    )


def _observacion_html(content: dict[str, Any]) -> str:
    return _paragraphs(
        content.get("personalized_observation"),
        "margin:0 0 16px 0;color:#444444;font-size:15px;line-height:25px;",
    )


def _diagnostico_html(content: dict[str, Any]) -> str:
    """Oportunidades reales de la auditoría + recomendación. Vacío si no hay datos."""
    items = []
    for o in (content.get("opportunities") or [])[:4]:
        title = str(o.get("title") or "").strip()
        if not title:
            continue
        detail = str(o.get("opportunity") or "").strip()
        evidence = _clip(str(o.get("evidence") or ""), _MAX_EVIDENCE_CHARS)
        head = _esc(title) + (f" — {_esc(detail)}" if detail else "")
        body = f'<p style="margin:4px 0 0 0;color:#666666;font-size:13px;line-height:20px;">{_esc(evidence)}</p>' if evidence else ""
        items.append(
            '<tr><td style="padding:0 0 14px 0;">'
            f'<p style="margin:0;color:{BRAND["negro"]};font-size:15px;font-weight:600;line-height:22px;">{head}</p>{body}'
            "</td></tr>"
        )
    solution = str(content.get("recommended_solution") or "").strip()
    if not items and not solution:
        return ""
    list_html = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{"".join(items)}</table>'
        if items
        else ""
    )
    solution_html = (
        f'<p style="margin:10px 0 0 0;border-left:3px solid {BRAND["rojo"]};padding:2px 0 2px 12px;color:#444444;font-size:14px;line-height:22px;">'
        f"{_esc(solution)}</p>"
        if solution
        else ""
    )
    return (
        '<tr><td class="pad" style="padding:0 40px 10px 40px;">'
        f'<p style="margin:0 0 6px 0;{_MONO}color:{BRAND["rojo"]};font-size:11px;letter-spacing:1px;">01 · Diagnóstico</p>'
        f'<p style="margin:0 0 18px 0;color:{BRAND["negro"]};font-size:22px;font-weight:800;">Lo que vimos en tu presencia digital</p>'
        f"{list_html}{solution_html}"
        "</td></tr>"
    )


def _evidencia_html(content: dict[str, Any]) -> str:
    """Estadísticas REALES del lead. Si no hay ninguna, la sección no se muestra."""
    reviews = content.get("reviews")
    rating = content.get("rating")
    web = content.get("website_score")
    if reviews is None and rating is None and web is None:
        return ""

    def fmt_num(v: Any, digits: int = 0) -> str:
        if v is None:
            return "—"
        return f"{float(v):.{digits}f}" if digits else f"{int(v)}"

    cells = [
        (fmt_num(reviews), "reseñas en Google", "#ffffff"),
        (f"{fmt_num(rating, 1)} ⭐" if rating is not None else "—", "valoración en Google", BRAND["rojo"]),
        (f"{fmt_num(web, 1)}/10" if web is not None else "—", "score de tu sitio web", BRAND["rojo"]),
    ]
    cell_html = [
        f'<td class="col" width="50%" valign="top" style="padding:10px;">'
        f'<p style="margin:0;color:{color};font-size:30px;font-weight:800;">{_esc(value)}</p>'
        f'<p style="margin:4px 0 0 0;color:#9a9a9a;font-size:12px;line-height:18px;">{_esc(label)}</p></td>'
        for value, label, color in cells
    ]
    # 2 x 2 grid like the reference; the 4th cell is empty when there are 3 stats.
    cell_html.append('<td class="col" width="50%" valign="top" style="padding:10px;">&nbsp;</td>')
    row1 = f"<tr>{cell_html[0]}{cell_html[1]}</tr>"
    row2 = f"<tr>{cell_html[2]}{cell_html[3]}</tr>"
    return (
        '<tr><td class="pad" style="padding:30px 40px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{BRAND["negro"]};">'
        '<tr><td style="padding:24px 26px 6px 26px;">'
        f'<p style="margin:0;{_MONO}color:#ff3b30;font-size:11px;letter-spacing:1px;text-transform:uppercase;">05 · Evidencia</p>'
        '</td></tr>'
        '<tr><td style="padding:10px 16px 22px 16px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f"{row1}{row2}"
        "</table></td></tr></table></td></tr>"
    )


def _saludo(content: dict[str, Any]) -> str:
    opening = str(content.get("opening") or "").strip()
    if opening:
        return _esc(opening)
    business = str(content.get("business_name") or "").strip()
    return _esc(f"Hola, equipo de {business}," if business else "Hola,")


# ------------------------------------------------------------------ render ----
def _template_values(content: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {k: _esc(v) for k, v in BRAND.items()}
    values["anio"] = _esc(brand_year())
    values["saludo"] = _saludo(content)
    values["observacion"] = _observacion_html(content)
    values["diagnostico"] = _diagnostico_html(content)
    values["evidencia"] = _evidencia_html(content)
    values["servicios"] = _servicios_html()
    values["firma"] = _firma_html()
    return values


def render_proposal_email(content: dict[str, Any]) -> str:
    """Render the innblock HTML email from proposal content (see module docstring)."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    values = _template_values(content)

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise TemplateRenderError(f"placeholder sin valor: {{{{{key}}}}}")
        return values[key]

    return _PLACEHOLDER.sub(_sub, template)


def render_plain_text(content: dict[str, Any]) -> str:
    """Versión texto plano (multipart/alternative). Mismos datos que el HTML."""
    lines: list[str] = []
    lines.append(str(content.get("opening") or "Hola,").strip())
    lines.append("")
    observation = str(content.get("personalized_observation") or "").strip()
    if observation:
        lines.extend([observation, ""])

    opportunities = [o for o in (content.get("opportunities") or [])[:4] if o.get("title")]
    if opportunities:
        lines.append("Lo que vimos en tu presencia digital:")
        for o in opportunities:
            detail = f": {o.get('opportunity')}" if o.get("opportunity") else ""
            lines.append(f"• {o.get('title')}{detail}")
        lines.append("")

    solution = str(content.get("recommended_solution") or "").strip()
    if solution:
        lines.extend([solution, ""])

    cta = str(content.get("call_to_action") or "").strip()
    if cta:
        lines.extend([cta, ""])

    lines.append("Qué hacemos:")
    for s in SERVICIOS:
        lines.append(f"• {s['titulo']} ({s['tiempo']}): {s['texto']}")
    lines.append("")

    lines.append("Si querés, contanos qué estás construyendo y lo vemos juntos.")
    lines.append(f"Escribinos a {BRAND['tuEmail']} o visitá {BRAND['linkWeb']}")
    lines.append("")
    signature = str(content.get("signature") or "").strip()
    if signature:
        lines.append(signature)
    else:
        lines.append("Saludos,")
        for p in SOCIOS:
            lines.append(f"{p['nombre']} · {p['rol']} · {BRAND['empresa']} · {p['telefono']}")
    lines.append("")
    lines.append(PLAIN_UNSUBSCRIBE)
    return "\n".join(lines)
