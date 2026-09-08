"""Deterministic website auditor (spec §20-24).

Subscores (0-10): design, mobile, seo, performance, conversion, cta, contact,
booking, trust, automation. Every negative/positive signal carries evidence
and is labelled FACT (directly observed) or INFERENCE (absence or deduction).
Nothing is invented: only data from `ExtractedWebsite` is used.
"""
from __future__ import annotations

import re

from app.services.analysis.types import AuditResult, ExtractedWebsite, Finding

DIMENSIONS = [
    "design",
    "mobile",
    "seo",
    "performance",
    "conversion",
    "cta",
    "contact",
    "booking",
    "trust",
    "automation",
]

CTA_KEYWORDS = [
    "reservar", "reserva", "turno", "agenda", "contactar", "escribinos", "escríbenos",
    "llamanos", "llámanos", "consultanos", "consultar", "solicitar", "cotizar",
    "pedir turno", "book", "schedule", "appointment", "get started", "contact us",
]

BOOKING_PATHS = ["/reserv", "/booking", "/agenda", "/turno", "/schedule", "/cita"]
CONTACT_PATHS = ["/contact", "/contacto"]
ABOUT_PATHS = ["/about", "/about-us", "/nosotros", "/quienes", "/quienes-somos"]
SERVICE_PATHS = ["/services", "/servicios", "/tratamiento", "/precios", "/pricing"]

MISSING_META_TEXT = "El sitio no declara una meta description en las páginas analizadas."
HTML_KEYWORDS = [
    "wordpress", "wix", "squarespace", "joomla", "drupal", "webflow", "shopify",
]
JS_HINTS = ["react", "next.js", "nextjs", "vue", "angular", "svelte", "jquery", "alpine"]


def _path_of(url: str) -> str:
    url = url.split("?")[0].rstrip("/") or "/"
    return url.lower()


def _link_in(urls: list[str], fragments: list[str]) -> bool:
    return any(any(f in _path_of(u) for f in fragments) for u in urls)


class WebsiteAuditor:
    def audit(self, site: ExtractedWebsite, content_hash: str | None = None) -> AuditResult:
        findings: list[Finding] = []
        text_lower = (site.text or "").lower()
        all_text = f"{site.title or ''} {site.meta_description or ''} {site.text}".lower()
        home_url = site.pages_seen[0] if site.pages_seen else site.url

        # ---------------- per-dimension score builders ----------------
        design = 10.0
        if not site.h1_count or site.h1_count > 3:
            design -= 1.5
            findings.append(
                Finding(
                    problem="Estructura de encabezados mejorable",
                    evidence=f"Se detectaron {site.h1_count} H1 en las páginas analizadas.",
                    source_url=home_url, kind="FACT", dimension="design",
                )
            )
        if not site.title:
            design -= 1.0
            findings.append(Finding("Título de página ausente", "No se encontró <title> en el HTML.", home_url, "FACT", "design"))
        if len(site.cta_texts) == 0:
            design -= 1.0
            findings.append(Finding("CTA poco visible", "No se detectó ningún botón o enlace claro de acción en las páginas analizadas.", home_url, "INFERENCE", "design"))

        mobile = 10.0
        if not site.has_viewport:
            mobile -= 4.0
            findings.append(Finding("Diseño no optimizado para móviles", "No se encontró meta viewport; la página puede verse mal en celulares.", home_url, "FACT", "mobile"))

        seo = 10.0
        if not site.meta_description:
            seo -= 3.0
            findings.append(Finding("SEO básico mejorable", MISSING_META_TEXT, home_url, "FACT", "seo"))
        if not site.title or "— página" in (site.title or ""):
            seo -= 1.5
            findings.append(Finding("Título poco descriptivo", "El <title> no describe claramente el negocio ni la ubicación.", home_url, "FACT", "seo"))
        if site.word_count < 200:
            seo -= 1.5
            findings.append(Finding("Contenido limitado", f"Se detectaron aproximadamente {site.word_count} palabras de contenido visible.", home_url, "FACT", "seo"))
        if site.page_count < 3:
            seo -= 1.0
            findings.append(Finding("Sitio de una sola página", f"El crawler encontró {site.page_count} página(s) interna(s).", home_url, "FACT", "seo"))

        performance = 10.0
        img_alt_penalty = min(2.0, site.img_without_alt * 0.5)
        if img_alt_penalty:
            performance -= img_alt_penalty
            findings.append(Finding("Imágenes sin atributo alt", f"{site.img_without_alt} imagen(es) sin texto alternativo.", home_url, "FACT", "performance"))
        if site.https is False:
            performance -= 5.0
            findings.append(Finding("Sitio sin HTTPS", "La conexión no es HTTPS, lo que afecta confianza y posicionamiento.", home_url, "FACT", "performance"))
        tech = site.tech_hints
        if tech.get("no_cms"):
            performance -= 1.0
            findings.append(Finding("Sitio estático sin CMS", "No se detectó un CMS moderno (WordPress, Wix, etc.) que facilite actualizaciones.", home_url, "INFERENCE", "performance"))

        conversion = 10.0
        cta = 10.0 if site.has_cta else 4.0
        if not site.has_cta:
            findings.append(Finding("Sin llamadas a la acción claras", "No se encontraron botones de reserva, contacto o WhatsApp en las páginas analizadas.", home_url, "INFERENCE", "cta"))
        if not site.has_form:
            conversion -= 2.0
            findings.append(Finding("Sin formulario de contacto", "No se detectó formulario de captación de consultas.", home_url, "INFERENCE", "conversion"))
        if not site.has_cta:
            conversion -= 2.0

        contact = 10.0
        if not site.phones:
            contact -= 2.0
            findings.append(Finding("Teléfono no visible", "No se encontró número de teléfono en el contenido analizado.", home_url, "INFERENCE", "contact"))
        if not site.has_contact_page:
            contact -= 2.0
            findings.append(Finding("Sin página de contacto dedicada", "No se encontró una página /contacto entre las analizadas.", home_url, "INFERENCE", "contact"))
        if not site.emails:
            contact -= 2.0
            findings.append(Finding("Email no publicado", "No se encontró dirección de email pública en el sitio.", home_url, "INFERENCE", "contact"))
        if not site.whatsapp_numbers:
            contact -= 1.5
            findings.append(Finding("WhatsApp no detectado", "No se encontró enlace wa.me ni botón de WhatsApp.", home_url, "INFERENCE", "contact"))

        booking = 10.0
        if not site.has_booking_page:
            booking -= 5.0
            findings.append(Finding("No se detectó sistema de reservas", "No se encontró enlace o botón de reserva en las páginas analizadas.", home_url, "INFERENCE", "booking"))
        if site.has_booking_page:
            findings.append(Finding("Reserva online disponible", "Se detectó página/enlace de reserva.", home_url, "FACT", "booking"))

        trust = 10.0
        if site.https is False:
            trust -= 3.0
        if not site.has_about_page:
            trust -= 1.5
            findings.append(Finding("Sin página de presentación", "No se encontró página del tipo /nosotros que genere confianza.", home_url, "INFERENCE", "trust"))
        if not site.address_found:
            trust -= 1.0
            findings.append(Finding("Dirección no publicada", "No se encontró dirección en el contenido analizado.", home_url, "INFERENCE", "trust"))
        if not site.opening_hours_found:
            trust -= 0.5
            findings.append(Finding("Horarios no publicados", "No se encontraron horarios de atención en el contenido.", home_url, "INFERENCE", "trust"))

        automation = 10.0
        if not site.whatsapp_numbers and not site.has_booking_page and not site.has_form:
            automation -= 4.0
            findings.append(
                Finding(
                    "No se detectó atención automática",
                    "No hay WhatsApp, reserva online ni formulario que disparen procesos automáticos.",
                    home_url, "INFERENCE", "automation",
                )
            )
        if site.has_booking_page and not site.whatsapp_numbers:
            automation -= 1.0
        if "whatsapp" in text_lower or "wa.me" in text_lower:
            findings.append(Finding("WhatsApp presente", "Se detectó enlace de WhatsApp.", home_url, "FACT", "automation"))

        subscores = {
            "design": max(0.0, round(design, 1)),
            "mobile": max(0.0, round(mobile, 1)),
            "seo": max(0.0, round(seo, 1)),
            "performance": max(0.0, round(performance, 1)),
            "conversion": max(0.0, round(conversion, 1)),
            "cta": max(0.0, round(cta, 1)),
            "contact": max(0.0, round(contact, 1)),
            "booking": max(0.0, round(booking, 1)),
            "trust": max(0.0, round(trust, 1)),
            "automation": max(0.0, round(automation, 1)),
        }
        weights = {
            "design": 0.12, "mobile": 0.12, "seo": 0.12, "performance": 0.08,
            "conversion": 0.10, "cta": 0.08, "contact": 0.10, "booking": 0.12,
            "trust": 0.08, "automation": 0.08,
        }
        overall = round(sum(subscores[d] * weights[d] for d in DIMENSIONS), 1)

        # ---------------- strengths / weaknesses / opportunities ----------------
        strengths: list[dict] = []
        if site.https:
            strengths.append({"text": "HTTPS habilitado", "evidence": "El sitio se sirve sobre HTTPS.", "kind": "FACT"})
        if site.title and "— página" not in (site.title or ""):
            strengths.append({"text": "Título descriptivo", "evidence": f"<title>: “{site.title[:120]}”", "kind": "FACT"})
        if site.meta_description:
            strengths.append({"text": "Meta description presente", "evidence": site.meta_description[:160], "kind": "FACT"})
        if site.business_description:
            strengths.append({"text": "Servicios claramente explicados", "evidence": site.business_description[:200], "kind": "FACT"})
        if site.has_contact_page:
            strengths.append({"text": "Información de contacto visible", "evidence": "Se detectó página de contacto.", "kind": "FACT"})
        if site.emails:
            strengths.append({"text": "Email de contacto publicado", "evidence": site.emails[0].get("email", ""), "kind": "FACT"})
        if site.opening_hours_found:
            strengths.append({"text": "Horarios publicados", "evidence": site.opening_hours_found[:120], "kind": "FACT"})
        if site.page_count >= 3:
            strengths.append({"text": "Website activo con varias secciones", "evidence": f"{site.page_count} páginas internas analizadas.", "kind": "FACT"})
        if site.whatsapp_numbers:
            strengths.append({"text": "Usa WhatsApp", "evidence": "Enlace wa.me detectado.", "kind": "FACT"})

        weaknesses: list[dict] = []
        # Deterministic derived weaknesses from lowest dimensions.
        low_dimensions = sorted(subscores.items(), key=lambda kv: kv[1])[:3]
        mapped_problem = {
            "booking": "No se detectó reserva online",
            "automation": "No se detectó atención automática",
            "cta": "CTA poco visible",
            "contact": "Contacto limitado",
            "seo": "SEO básico mejorable",
            "conversion": "Conversión limitada",
            "mobile": "Experiencia móvil mejorable",
            "trust": "Confianza mejorable",
            "performance": "Performance mejorable",
            "design": "Diseño mejorable",
        }
        for dim, score in low_dimensions:
            if score >= 8.0:
                continue
            problem = mapped_problem[dim]
            evidence = next(
                (f.evidence for f in findings if f.dimension == dim), ""
            )
            weaknesses.append({
                "text": problem,
                "evidence": evidence or f"Score {dim}: {score}/10 en la auditoría.",
                "kind": "INFERENCE",
                "dimension": dim,
                "score": score,
            })

        from app.services.catalog import OPPORTUNITY_RULES

        opportunities: list[dict] = []
        active_keys: set[str] = set()
        if not site.has_booking_page:
            rule = next(r for r in OPPORTUNITY_RULES if r.key == "no_booking")
            opportunities.append({
                "title": rule.label,
                "opportunity": rule.opportunity,
                "service": rule.service,
                "service_reason": rule.service_reason,
                "evidence": "No se encontró enlace o botón de reserva en las páginas analizadas.",
                "source_url": home_url,
                "confidence": 0.9,
            })
            active_keys.add("no_booking")
        if not site.whatsapp_numbers:
            rule = next(r for r in OPPORTUNITY_RULES if r.key == "no_whatsapp")
            opportunities.append({
                "title": rule.label,
                "opportunity": rule.opportunity,
                "service": rule.service,
                "service_reason": rule.service_reason,
                "evidence": "No se encontró enlace wa.me ni botón WhatsApp.",
                "source_url": home_url,
                "confidence": 0.85,
            })
            active_keys.add("no_whatsapp")
        if site.has_form:
            rule = next(r for r in OPPORTUNITY_RULES if r.key == "has_form_no_followup")
            opportunities.append({
                "title": rule.label,
                "opportunity": rule.opportunity,
                "service": rule.service,
                "service_reason": rule.service_reason,
                "evidence": "El sitio incluye un formulario de contacto sin respuesta automática visible.",
                "source_url": home_url,
                "confidence": 0.75,
            })
            active_keys.add("has_form_no_followup")
        if site.whatsapp_numbers and not site.has_booking_page:
            # WhatsApp present but no booking automation
            pass
        if not active_keys:
            rule = next(r for r in OPPORTUNITY_RULES if r.key == "no_chat")
            opportunities.append({
                "title": rule.label,
                "opportunity": rule.opportunity,
                "service": rule.service,
                "service_reason": rule.service_reason,
                "evidence": "No se detectó atención en vivo ni chatbot en las páginas analizadas.",
                "source_url": home_url,
                "confidence": 0.7,
            })

        return AuditResult(
            overall_score=overall,
            subscores=subscores,
            strengths=strengths[:8],
            weaknesses=weaknesses[:6],
            opportunities=opportunities[:5],
            findings=findings,
            extracted=site,
            content_hash=content_hash,
            model_used="rule-based",
        )
