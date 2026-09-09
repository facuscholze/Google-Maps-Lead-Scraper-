"""Deterministic offline fixtures used by the mock Places provider and the
virtual mock websites (demo / tests). No network, no Google data, no invented
real-world businesses: everything is explicitly synthetic.

Businesses are crafted to cover a realistic spread of digital presence so the
crawler, audit and scoring produce varied, explainable outcomes.

Column format (| separated):
  slug | name | rating | reviews | phone(0/1) | email_loc(c=contact,f=footer,h=home,-=none)
  | booking | whatsapp | form | seo | about | services_page | website
"""
from __future__ import annotations

import html
from typing import Any

_TABLE = """\
clinica-aurora|Clínica Estética Aurora|4.8|327|1|c|1|1|1|1|1|1|1
studio-derma|Studio Derma Montevideo|4.6|412|1|f|1|0|1|1|1|1|1
centro-belleza-miraflores|Centro de Belleza Miraflores|4.2|88|1|c|0|0|1|0|1|1|1
estetica-vittoria|Estética Vittoria|4.9|512|1|c|1|1|1|1|1|1|1
dermia-laser|Dermia Láser|4.0|61|1|-|0|0|0|0|0|0|1
pulso-skin|Pulso Skin & Care|4.7|245|1|f|0|1|1|1|1|1|1
clinicaderma-mvd|Clínica Dermatológica MVD|4.4|158|1|c|1|1|1|1|1|1|1
belleza-renacer|Belleza Renacer|3.8|44|1|-|0|0|0|0|1|1|1
estudio-caroline|Estudio Caroline|4.5|96|1|h|0|0|1|1|1|1|1
nova-estetica|Nova Estética Avanzada|4.1|70|1|c|0|1|1|1|1|1|1
centro-medico-dermavida|Centro Médico DermaVida|4.3|201|1|c|1|0|1|1|1|1|1
lumiere-beauty|Lumière Beauty Studio|5.0|340|1|f|1|1|1|1|1|1|1
vera-clinic|Vera Clinic Estética|3.6|30|1|-|0|0|1|0|1|1|1
skinlab-mvd|SkinLab Montevideo|4.4|133|1|c|1|1|0|1|1|1|1
renovarte|Renovarte Estética Integral|4.7|268|1|c|0|0|1|1|1|1|1
derma-point|Derma Point|4.0|55|0|-|0|0|0|0|0|0|1
glow-salon|Glow Salón & Estética|4.2|77|1|-|0|1|1|1|1|1|1
bio-estetica|Bio Estética Punta Carretas|4.6|189|1|f|0|0|1|1|1|1|1
santa-fe-beauty|Santa Fe Beauty Center|3.9|40|1|-|0|0|0|0|0|0|1
milla-skin|Milla Skin Clinic|4.5|110|1|c|1|0|1|1|1|1|1
estetica-elegance|Estética Élégance|4.1|92|1|-|0|0|1|0|1|1|1
clinic-ice|Clinic ICE Medicina Estética|4.8|290|1|c|1|1|1|1|1|1|1
centro-azul|Centro Azul Estética|3.5|22|1|-|0|0|0|0|0|0|1
beauty-farma|BeautyFarma Dermocosmética|4.3|175|1|f|1|0|1|1|1|1|1
skin-centro|Skin Centro Médico Estético|4.6|222|1|c|1|1|1|1|1|1|1
vital-derma|Vital Derma|4.0|58|0|-|0|0|0|0|0|0|0
lucerna-estetica|Lucerna Estética|4.4|141|1|-|0|1|1|1|1|1|1
puerto-beauty|Puerto Beauty Lab|4.2|66|1|c|0|0|0|0|0|0|1
belo-centre|Belo Centre|4.7|254|1|c|1|1|1|1|1|1|1
dermaclub|DermaClub|3.7|33|1|-|0|0|0|0|0|0|1
estetica-oliva|Estética Oliva|4.5|104|1|h|0|0|0|1|1|1|1
noa-skin|Noa Skin Estudio|4.8|380|1|c|1|0|1|1|1|1|1
bella-vita|Bella Vita Centro|4.1|83|1|f|0|1|1|0|1|1|1
derma-urbana|Derma Urbana|4.0|49|0|-|0|0|0|0|0|0|1
sens-beauty|Sens Beauty & Care|4.6|167|1|c|1|1|1|1|1|1|1
arte-estetica|Arte & Estética|4.4|120|1|c|0|0|1|1|1|1|1
clinic-nova|Clinic Nova|3.9|51|1|-|0|0|0|0|0|0|1
estudio-m|Estudio M Estética|4.7|236|1|f|0|1|1|1|1|1|1
prive-beauty|Privé Beauty Room|4.3|71|1|-|0|1|0|1|1|1|1
lina-derma|Lina Derma & Laser|4.5|155|1|c|1|1|1|1|1|1|1
aura-clinica|Aura Clínica Estética|4.2|64|0|-|0|0|0|0|0|0|1
blend-center|Blend Center|4.9|460|1|c|1|1|1|1|1|1|1
estetica-luz|Estética Luz|3.4|18|1|-|0|0|0|0|0|0|1
casa-derma|Casa Derma|4.1|90|1|-|0|0|1|0|1|1|1
vogue-beauty|Vogue Beauty Studio|4.4|128|1|c|1|0|1|1|1|1|1
dermatica|Dermática Montevideo|4.6|205|1|f|0|0|1|1|1|1|1
alma-estetica|Alma Estética Natural|4.0|57|1|-|0|0|0|0|0|0|0
perla-skin|Perla Skin Center|4.5|190|1|c|1|1|1|1|1|1|1
estudio-irene|Estudio Irene|4.3|98|1|h|0|1|1|1|1|1|1
monte-derma|Monte Derma|3.8|27|0|-|0|0|0|0|0|0|1
roche-beauty|Roché Beauty|4.7|310|1|c|1|1|1|1|1|1|1
centro-laser-uy|Centro Láser Uruguay|4.2|74|1|c|0|0|1|1|1|1|1
fiora-estetica|Fióra Estética|4.0|60|1|-|0|0|0|0|0|0|1
"""


def _parse_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for line in _TABLE.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        slug, name = parts[0], parts[1]
        email_code = parts[5] if parts[5] != "-" else None
        email_loc = {"c": "contact", "f": "footer", "h": "home"}.get(email_code)
        profiles.append(
            {
                "slug": slug,
                "name": name,
                "rating": float(parts[2]),
                "reviews": int(parts[3]),
                "phone": parts[4] == "1",
                "email_loc": email_loc,
                "booking": parts[6] == "1",
                "whatsapp": parts[7] == "1",
                "form": parts[8] == "1",
                "seo": parts[9] == "1",
                "has_about": parts[10] == "1",
                "has_services_page": parts[11] == "1",
                "website": parts[12] == "1",
            }
        )
    return profiles


_PROFILES = _parse_profiles()


def site_profiles() -> list[dict[str, Any]]:
    return list(_PROFILES)


def email_for(slug: str, _name: str | None = None) -> str:
    return f"contacto@{slug}.com.uy"


def place_from_profile(p: dict[str, Any], query: str, index: int) -> dict[str, Any]:
    slug = p["slug"]
    name = p["name"]
    lat = -34.9 - (index % 10) * 0.004
    lng = -56.16 - (index % 7) * 0.003
    website = f"http://mockbusiness.local/{slug}" if p["website"] else None
    return {
        "id": f"mockplace:{slug}",
        "displayName": {"text": name},
        "formattedAddress": (
            f"Av. Principal {1200 + index * 17}, Montevideo, "
            "Departamento de Montevideo, Uruguay"
        ),
        "location": {"latitude": round(lat, 6), "longitude": round(lng, 6)},
        "googleMapsUri": f"https://maps.google.com/?cid={1000000000 + index}",
        "websiteUri": website,
        "nationalPhoneNumber": f"+598 2900 {1000 + index:04d}" if p["phone"] else None,
        "internationalPhoneNumber": f"+598 2 900 {index:04d}" if p["phone"] else None,
        "rating": p["rating"],
        "userRatingCount": p["reviews"],
        "businessStatus": "OPERATIONAL",
        "primaryType": "beauty_salon",
        "primaryTypeDisplayName": {"text": "Clínica estética"},
        "types": ["beauty_salon", "health", "point_of_interest"],
        "_mock": {"email": email_for(slug), "slug": slug, "query": query, "profile": p},
    }


_VARIANT_SUFFIXES = ["", " II", " III"]


def _variant_name(name: str, variant: int) -> str:
    if variant == 0:
        return name
    return f"{name} {_VARIANT_SUFFIXES[min(variant, len(_VARIANT_SUFFIXES) - 1)].strip()}"


def variant_slug(base_slug: str, variant: int) -> str:
    return base_slug if variant == 0 else f"{base_slug}-{variant + 1}"


def generate_places(query: str, max_results: int, seed: int = 7) -> list[dict[str, Any]]:
    """Generate up to max_results synthetic Google-like places (stable per seed).

    When the requested volume exceeds the base profile table, extra variants of
    the same profiles are produced with unique slugs/emails so that pagination
    and deduplication logic is exercised realistically.
    """
    n = len(_PROFILES)
    places: list[dict[str, Any]] = []
    for index in range(max_results):
        source_index = (seed + index) % n
        variant = (seed + index) // n
        p = dict(_PROFILES[source_index])
        if variant:
            p = dict(p)
            p["name"] = _variant_name(p["name"], variant)
            p["slug"] = variant_slug(p["slug"], variant)
            p["rating"] = max(3.0, round(p["rating"] - 0.05 * variant, 1))
            p["reviews"] = max(5, p["reviews"] + (index * 3) % 25)
        places.append(place_from_profile(p, query, index))
    return places


def _base_slug(slug: str) -> str:
    """'clinica-aurora-2' / 'clinica-aurora-3' -> 'clinica-aurora'."""
    for suffix in ("-3", "-2"):
        if slug.endswith(suffix):
            return slug[: -len(suffix)]
    return slug


def get_profile_for_slug(slug: str) -> dict[str, Any] | None:
    for p in _PROFILES:
        if p["slug"] == slug:
            return p
    base = _base_slug(slug)
    for p in _PROFILES:
        if p["slug"] == base:
            return p
    return None


# ---------------------------------------------------------------------------
# Virtual mock websites (deterministic HTML per profile)
# ---------------------------------------------------------------------------
def site_pages(slug: str) -> list[str]:
    profile = get_profile_for_slug(slug)
    if not profile:
        return ["/"]
    pages = ["/"]
    if profile.get("has_services_page"):
        pages.append("/servicios")
    if profile.get("has_about"):
        pages.append("/nosotros")
    pages.append("/contacto")
    return pages[:4]


def _e(name: str) -> str:
    return html.escape(name)


def render_site(slug: str, path: str) -> tuple[str, int]:
    """Return (html, status) for a virtual page — fully deterministic."""
    p = get_profile_for_slug(slug)
    if p is None:
        return "<html><body><h1>404</h1></body></html>", 404
    name = p["name"]
    email_value = email_for(slug, name)
    path = path.split("?")[0].rstrip("/") or "/"
    is_contact = path == "/contacto"

    title = name if p["seo"] else f"{name} — página"
    if is_contact:
        title = f"Contacto — {name}"
    meta = (
        '<meta name="description" content="'
        f'{name}: tratamientos estéticos de alta calidad en Montevideo. Reservá tu turno.">'
        if p["seo"]
        else ""
    )
    booking = (
        '<a class="cta-btn" href="/reservas">Reservar turno online</a>'
        '<a class="cta-btn" href="/booking">Reservar ahora</a>'
        if p["booking"]
        else ""
    )
    whatsapp = (
        '<a href="https://wa.me/59829001000?text=Hola,%20quiero%20informaci%C3%B3n">'
        "Escríbenos por WhatsApp</a>"
        if p["whatsapp"]
        else ""
    )
    email_block = ""
    if (not is_contact and p["email_loc"] == "home") or (
        is_contact and p["email_loc"] in ("contact", "footer", "home")
    ):
        email_block = f'<a href="mailto:{email_value}" class="footer-email">{email_value}</a>'
    elif not is_contact and p["email_loc"] == "footer":
        email_block = ""  # footer only (rendered below in footer)
    form = (
        '<form class="contact-form" action="/enviar">'
        '<input name="nombre" placeholder="Nombre">'
        '<input name="telefono" placeholder="Teléfono">'
        '<textarea name="mensaje" placeholder="Mensaje"></textarea>'
        '<button type="submit">Enviar mensaje</button></form>'
        if p["form"]
        else ""
    )
    nav = "".join(
        f'<a href="{href}">{label}</a>'
        for href, label in (("/servicios", "Servicios"), ("/nosotros", "Nosotros"), ("/contacto", "Contacto"))
    )
    body = f"""
<div id="page-{slug}">
  <header><div class="logo">{_e(name)}</div><nav>{nav}</nav></header>
  <main>
    <h1>{_e(name)}</h1>
    <p class="hero">Cuidado estético y medicina estética en Montevideo. Tecnología de
    última generación y atención personalizada.</p>
    {booking}
    {whatsapp}
    {email_block}
    <section class="servicios"><h2>Nuestros servicios</h2>
      <ul><li>Limpieza facial profunda</li><li>Láser y depilación definitiva</li>
      <li>Radiofrecuencia y reafirmación</li><li>Tratamientos anti-age</li></ul>
    </section>
    <section class="acerca"><h2>Sobre nosotros</h2>
      <p>Somos un equipo de profesionales con más de 10 años de experiencia en
      estética y dermatología.</p>
    </section>
    {form}
  </main>
  <footer>
    <p>&copy; 2026 {_e(name)} — Av. Principal 1234, Montevideo. Lun a Vie 9:00-19:00.</p>
    {'<a href="mailto:' + email_value + '">' + email_value + '</a>' if p["email_loc"] == "footer" else ''}
  </footer>
</div>"""
    doc = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"{meta}<title>{title}</title></head><body>{body}</body></html>"
    )
    return doc, 200


def business_by_slug(slug: str) -> dict[str, Any] | None:
    return get_profile_for_slug(slug)
