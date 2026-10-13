"""Web-design services and evidence-based sales opportunities."""
from __future__ import annotations

from dataclasses import dataclass

AVA_SCHO_SERVICES = {
    "Landing page": {"description": "Una página enfocada en un servicio o campaña, con contenido claro y una llamada a la acción para consultar.", "signal": "conversion"},
    "Sitio web institucional": {"description": "Un sitio adaptable a celulares con presentación del negocio, servicios y canales de contacto.", "signal": "website"},
    "Rediseño web": {"description": "Renovar la estructura y experiencia móvil del sitio, con mejoras de contenido y contacto basadas en su revisión.", "signal": "redesign"},
}
SERVICE_ORDER = list(AVA_SCHO_SERVICES)


@dataclass(frozen=True)
class OpportunityRule:
    key: str
    label: str
    opportunity: str
    service: str
    service_reason: str


OPPORTUNITY_RULES = [
    OpportunityRule("no_cta", "Landing con llamada a la acción", "Diseñar una landing con un próximo paso claro para consultar.", "Landing page", "No se detectaron llamadas a la acción en las páginas revisadas."),
    OpportunityRule("no_contact", "Contacto visible en la web", "Organizar los servicios y el contacto en un sitio institucional.", "Sitio web institucional", "No se detectó una página de contacto."),
    OpportunityRule("no_mobile", "Rediseño adaptable a celulares", "Revisar el diseño móvil y adaptar la estructura de las páginas.", "Rediseño web", "No se encontró la etiqueta viewport; conviene validar la experiencia móvil."),
    OpportunityRule("no_seo", "Contenido web mejor estructurado", "Revisar títulos y descripciones para presentar mejor los servicios.", "Rediseño web", "Faltan señales básicas de estructura en las páginas revisadas."),
]


def web_opportunities(site):
    """Only observed absences; no claims about invisible business workflows."""
    if not site.page_count:
        return []
    signals = {
        "no_cta": (not site.has_cta, "No se detectó una llamada a la acción en las páginas analizadas."),
        "no_contact": (not site.has_contact_page, "No se detectó una página de contacto en las páginas analizadas."),
        "no_mobile": (not site.has_viewport, "No se encontró una etiqueta viewport en el HTML analizado."),
        "no_seo": (not site.title or not site.meta_description or not site.h1_count, "No se encontraron todas las señales de título, descripción y H1 en el HTML analizado."),
    }
    return [dict(title=r.label, opportunity=r.opportunity, service=r.service,
                 service_reason=r.service_reason, evidence=signals[r.key][1],
                 source_url=site.url, confidence=0.8, kind="INFERENCE")
            for r in OPPORTUNITY_RULES if signals[r.key][0]]


def recommended_web_service(has_website, website_score=None):
    if not has_website:
        return "Sitio web institucional"
    if website_score is not None and website_score < 7:
        return "Rediseño web"
    return "Landing page"
