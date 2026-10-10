"""innblock email brand config — the ONLY place to edit mail branding (socios,
contact, links, colors, services list).

Source: "nuevo html innblock.html" (design reference, left untouched).

⚠️ Values marked TO CONFIRM are carried over from the reference file / brief and
must be checked before sending real mail:
  - BRAND["empresa"]     — brief says "innblock"; the reference file says "Estudio".
  - BRAND["tuEmail"]     — placeholder in the reference ("hola@tudominio.com").
  - BRAND["linkContacto"], BRAND["linkWeb"] — reference points to a vercel preview URL.
  - SOCIOS phones/roles  — taken from the reference file.
  - SERVICIOS and their times, and the "Qué hacemos" copy.
  - Fixed copy in templates/innblock_email.html (e.g. "Trabajamos con pocos
    clientes por vez", the "Evidencia" section title, the "BAJA" footer line).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

BRAND: dict[str, str] = {
    # --- Marca -----------------------------------------------------------------
    "empresa": "innblock",  # TO CONFIRM (reference file says "Estudio")
    "ubicacion": "Uruguay · Argentina",
    "hechoEn": "🇺🇾 Uruguay · 🇦🇷 Argentina · 🇧🇷 Brasil",  # TO CONFIRM
    "lema": "Solucionamos problemas y mejoramos tu servicio web. Sin vender humo.",
    "rojo": "#d90000",
    "negro": "#070707",
    # --- Contacto y links ------------------------------------------------------
    "tuEmail": "hola@tudominio.com",  # TO CONFIRM — placeholder, replace before sending
    "linkContacto": "https://web-estudio-alpha.vercel.app/es/#contacto",  # TO CONFIRM
    "linkWeb": "https://web-estudio-alpha.vercel.app/es/",  # TO CONFIRM
}

# Socios / co-fundadores de la firma. Agregar o quitar libremente (1..n).
# `telefono` se usa para el link wa.me (solo dígitos).
SOCIOS: list[dict[str, str]] = [
    {"nombre": "Facundo Scholze", "rol": "Co-fundador", "telefono": "+54 3755 629953"},  # TO CONFIRM
    {"nombre": "Yamall Avalos", "rol": "Co-fundador", "telefono": "+598 95 657 007"},  # TO CONFIRM
]

# Lista de servicios de la sección "Qué hacemos". Editar acá.
SERVICIOS: list[dict[str, str]] = [
    {
        "titulo": "Software a medida",
        "texto": "Sistemas internos, paneles e integraciones para dejar de cargar cosas a mano.",
        "tiempo": "6–10 sem",  # TO CONFIRM
    },
    {
        "titulo": "Automatización",
        "texto": "Que las tareas repetitivas dejen de comerse el día. Flujos, integraciones y alertas.",
        "tiempo": "2–6 sem",  # TO CONFIRM
    },
    {
        "titulo": "Marca",
        "texto": "Identidad y sistema visual: no un logo suelto, sino la base de todo lo demás.",
        "tiempo": "3–5 sem",  # TO CONFIRM
    },
    {
        "titulo": "Ingeniería",
        "texto": "Sitios y aplicaciones web rápidos, accesibles y fáciles de mantener.",
        "tiempo": "4–8 sem",  # TO CONFIRM
    },
    {
        "titulo": "Seguridad",
        "texto": "Revisión de accesos, datos personales, backups y dependencias viejas.",
        "tiempo": "1–3 sem",  # TO CONFIRM
    },
]

_TZ = ZoneInfo("America/Montevideo")  # UTC−03 year-round, same as the reference footer


def brand_year(now: datetime | None = None) -> str:
    """Año del pie de mail, calculado (no hardcodeado)."""
    return str((now or datetime.now(_TZ)).astimezone(_TZ).year)
