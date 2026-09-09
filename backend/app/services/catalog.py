"""AvaScho services catalog (spec §30) and opportunity heuristics.

The rule-based provider recommends services from this catalog using detected
evidence. Rules live here — not inside prompts or API handlers.
"""
from __future__ import annotations

from dataclasses import dataclass

AVA_SCHO_SERVICES: dict[str, dict[str, str]] = {
    "AI WhatsApp Agent": {
        "description": "Agente de IA conectado a WhatsApp que responde consultas y califica interesados 24/7.",
        "signal": "whatsapp",
    },
    "AI Customer Support": {
        "description": "Asistente de IA para atención al cliente multicanal con respuestas basadas en la info del negocio.",
        "signal": "support",
    },
    "Appointment Automation": {
        "description": "Reservas y agenda automatizadas con confirmación y recordatorios.",
        "signal": "booking",
    },
    "Lead Follow-up": {
        "description": "Seguimiento automático e inmediato de consultas recibidas por formularios y redes.",
        "signal": "form",
    },
    "CRM Automation": {
        "description": "Automatización de procesos comerciales y gestión de clientes en CRM.",
        "signal": "crm",
    },
    "Website AI Chat": {
        "description": "Chat inteligente en el website que responde y convierte visitas en consultas.",
        "signal": "chat",
    },
    "Sales Automation": {
        "description": "Pipeline comercial automatizado: captura, cualificación y seguimiento de oportunidades.",
        "signal": "sales",
    },
    "Review Automation": {
        "description": "Gestión y solicitud automatizada de reseñas de Google.",
        "signal": "reviews",
    },
    "Custom AI Integration": {
        "description": "Integración de IA a la medida de los procesos del negocio.",
        "signal": "custom",
    },
}


@dataclass(frozen=True)
class OpportunityRule:
    key: str
    label: str
    opportunity: str
    service: str
    service_reason: str


OPPORTUNITY_RULES: list[OpportunityRule] = [
    OpportunityRule(
        key="no_booking",
        label="Automatización de reservas",
        opportunity="Implementar un sistema de reservas automatizado con confirmación y recordatorios.",
        service="Appointment Automation",
        service_reason="El sitio no ofrece reserva online; un sistema automatizado capturaría turnos sin intervención manual.",
    ),
    OpportunityRule(
        key="no_whatsapp",
        label="Atención inteligente por WhatsApp",
        opportunity="Implementar un agente de IA conectado a WhatsApp para responder consultas al instante.",
        service="AI WhatsApp Agent",
        service_reason="WhatsApp es el canal preferido de contacto y hoy no está aprovechado de forma automática.",
    ),
    OpportunityRule(
        key="has_form_no_followup",
        label="Automatizar seguimiento de consultas",
        opportunity="Automatizar el seguimiento inmediato de las consultas recibidas por el formulario de contacto.",
        service="Lead Follow-up",
        service_reason="El sitio captura consultas con un formulario, pero no se detectó un sistema de respuesta automática.",
    ),
    OpportunityRule(
        key="no_chat",
        label="Chat de IA en el website",
        opportunity="Incorporar un chat de IA al website para responder dudas frecuentes y calificar visitas.",
        service="Website AI Chat",
        service_reason="No se detectó atención en vivo ni chat; las visitas sin respuesta se pierden.",
    ),
    OpportunityRule(
        key="good_reputation_no_digital",
        label="Potenciar reputación digital",
        opportunity="Automatizar la solicitud de reseñas para convertir la buena reputación en más clientes.",
        service="Review Automation",
        service_reason="La reputación en Google es fuerte; un sistema automatizado de reseñas la aprovecharía mejor.",
    ),
    OpportunityRule(
        key="no_automation_contact",
        label="Atención automatizada multicanal",
        opportunity="Automatizar la primera respuesta de consultas por los canales que el negocio ya usa.",
        service="AI Customer Support",
        service_reason="No se detectó atención automatizada; la mayoría de las consultas fuera de horario quedan sin respuesta.",
    ),
]

SERVICE_ORDER = [
    "AI WhatsApp Agent",
    "Appointment Automation",
    "AI Customer Support",
    "Lead Follow-up",
    "Website AI Chat",
    "Review Automation",
    "CRM Automation",
    "Sales Automation",
    "Custom AI Integration",
]
