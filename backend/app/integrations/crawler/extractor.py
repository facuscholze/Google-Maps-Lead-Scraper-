"""Website field extraction (spec §17-19) from crawled pages.

Pure functions over PageData — everything returned is something actually found
in the fetched HTML/text (no invented emails, phones or addresses).
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup

from app.integrations.crawler.crawler import extract_main_text
from app.services.analysis.types import ExtractedWebsite, PageData

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?<!\w)(\+?\d[\d\s().\-/]{6,}\d)(?!\w)")
WA_RE = re.compile(r"(?:wa\.me|api\.whatsapp\.com/send)[^\"'\s>]*", re.IGNORECASE)
SOCIAL_HOSTS = {"facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "tiktok.com"}
HOURS_RE = re.compile(
    r"(?:horario|horarios|lunes|martes|miercoles|miércoles|jueves|viernes|lun a vie|9:00|"
    r"8:00|10:00|de \d{1,2}:\d{2})[^<\n]{0,80}",
    re.IGNORECASE,
)
ADDRESS_RE = re.compile(
    r"(?:av\.|av |avenida|calle|camino|ruta|bvar|bulevar|boulevard|gral\.)[^<\n]{0,90}",
    re.IGNORECASE,
)
CTA_HINT = ["btn", "cta", "button", "boton", "botón", "wp-block-button", "reservar", "contactar"]
META_DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', re.I)
GENERATOR_RE = re.compile(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']', re.I)
JS_FRAMEWORK_RE = {
    "react": r"react",
    "next.js": r"_next/|__next|nextjs",
    "vue": r"vue\.js|vue@|data-v-",
    "angular": r"ng-version|angular",
    "svelte": r"svelte",
    "jquery": r"jquery",
    "alpine": r"alpinejs|x-data",
}
SERVICE_KEYWORDS = [
    "tratamiento", "servicio", "limpieza facial", "láser", "laser", "radiofrecuencia",
    "depilación", "depilacion", "dermatología", "dermatologia", "botox", "relleno",
    "facial", "anti-age", "antiage", "estética", "estetica", "drenaje", "peeling",
]


class WebsiteExtractor:
    def extract(self, pages: list[PageData]) -> ExtractedWebsite:
        site = ExtractedWebsite(
            url=pages[0].url if pages else "",
            pages_seen=[p.url for p in pages],
            page_count=len(pages),
            https=pages[0].url.startswith("https") if pages else True,
        )
        for page in pages:
            self._page(site, page)
        self._dedupe_and_finalize(site)
        return site

    # ------------------------------------------------------------------
    def _page(self, site: ExtractedWebsite, page: PageData) -> None:
        html = page.html or ""
        soup = BeautifulSoup(html, "lxml")
        site.text = " ".join(part for part in (site.text, page.text or "") if part)
        text_lower = (page.text or "").lower()

        # --- titles / metas (homepage takes priority) -------------------
        if page.kind == "home" or (site.title is None and page.title):
            site.title = page.title
        meta_match = META_DESC_RE.search(html) or re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html, re.I
        )
        if meta_match and site.meta_description is None:
            site.meta_description = meta_match.group(1).strip()

        # --- body text description ---------------------------------------
        if site.business_description is None:
            for paragraph in soup.find_all("p"):
                text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
                if len(text) >= 40:
                    site.business_description = text[:600]
                    break

        # --- structural flags ---------------------------------------------
        path = (page.url or "").split("?")[0].rstrip("/") or "/"
        html_links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        combined_links = list(dict.fromkeys(list(page.links or []) + html_links))
        if page.kind == "contact" or any("/contact" in u for u in combined_links):
            site.has_contact_page = True
        if page.kind == "about" or any("/about" in u or "/nosotros" in u for u in combined_links):
            site.has_about_page = True
        if (
            page.kind == "booking"
            or self._looks_like_booking(page, text_lower)
            or any(
                any(f in u.split("?")[0].lower() for f in ("/reserv", "/booking", "/turno", "/agenda", "/cita", "/schedule"))
                for u in combined_links
            )
        ):
            site.has_booking_page = True
        if soup.find("form"):
            site.has_form = True
        site.has_viewport = site.has_viewport or bool(soup.find("meta", attrs={"name": "viewport"}))
        site.h1_count += len(soup.find_all("h1"))
        site.word_count += len(re.findall(r"\S+", page.text or ""))
        site.img_without_alt += sum(
            1 for img in soup.find_all("img") if not img.get("alt") or not img["alt"].strip()
        )
        if page.kind == "home":
            site.https = page.url.startswith("https")

        # --- contact signals ------------------------------------------------
        self._extract_emails(site, page, html, soup)
        self._extract_phones(site, page, text_lower)
        self._extract_whatsapp(site, page, html)
        self._extract_social(site, page, page.links)
        self._extract_ctas(site, page, soup)

        if site.address_found is None:
            m = ADDRESS_RE.search(page.text or "")
            if m:
                site.address_found = m.group(0).strip()[:200]
        if site.opening_hours_found is None:
            m = HOURS_RE.search(page.text or "")
            if m:
                site.opening_hours_found = m.group(0).strip()[:200]

        # --- services list ----------------------------------------------------
        self._extract_services(site, soup, page)

        # --- technology hints ---------------------------------------------------
        generator = GENERATOR_RE.search(html)
        if generator:
            gen = generator.group(1).lower()
            for name in ("wordpress", "wix", "squarespace", "joomla", "drupal", "webflow", "shopify"):
                if name in gen:
                    site.tech_hints.setdefault(name, True)
        lower_html = html.lower()
        found_js = False
        for name, pattern in JS_FRAMEWORK_RE.items():
            if re.search(pattern, lower_html):
                site.tech_hints.setdefault(name, True)
                found_js = True
        if not found_js and not any(k in site.tech_hints for k in ("wordpress", "wix", "squarespace", "joomla", "webflow")):
            site.tech_hints.setdefault("no_cms", True)

    # ------------------------------------------------------------------
    @staticmethod
    def _looks_like_booking(page: PageData, text_lower: str) -> bool:
        booking_words = ["reservar", "reserva tu turno", "turno online", "reserva online", "agenda tu", "book now", "book online", "schedule"]
        return any(w in text_lower for w in booking_words) or any(
            "reserv" in urllib.parse.urlparse(link).path.lower() for link in (page.links or [])
        )

    def _extract_emails(self, site: ExtractedWebsite, page: PageData, html: str, soup: BeautifulSoup) -> None:
        found: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.lower().startswith("mailto:"):
                email = href.split(":", 1)[1].split("?")[0].strip()
                if email:
                    self._record_email(site, email, "HIGH", page.url, found)
        # visible email-ish text
        for text in soup.get_text(" ", strip=True).split():
            if "@" in text and "." in text.split("@")[1]:
                for email in EMAIL_RE.findall(text):
                    if email not in found:
                        conf = "MEDIUM" if page.kind == "contact" else "LOW"
                        if page.kind in ("contact", "home") and "footer" in str(link_parents(soup, email)):
                            conf = "MEDIUM"
                        self._record_email(site, email, conf, page.url, found)
        # raw html scan for emails not in visible text/mailto
        for email in EMAIL_RE.findall(html):
            if email not in found:
                conf = "MEDIUM" if page.kind == "contact" else "LOW"
                self._record_email(site, email, conf, page.url, found)

    def _record_email(self, site: ExtractedWebsite, email: str, confidence: str, url: str, seen: set[str]) -> None:
        email = email.strip().lower()
        if not email or email in seen:
            return
        seen.add(email)
        site.emails.append({"email": email, "confidence": confidence, "source_url": url})

    def _extract_phones(self, site: ExtractedWebsite, page: PageData, text_lower: str) -> None:
        for link in BeautifulSoup(page.html or "", "lxml").find_all("a", href=True):
            href = link.get("href", "")
            if href.lower().startswith("tel:"):
                number = href.split(":", 1)[1].strip()
                if number and number not in site.phones:
                    site.phones.append(number)
        # skip obvious non-phone strings
        for match in PHONE_RE.findall(page.text or ""):
            digits = re.sub(r"\D", "", match)
            if len(digits) >= 7 and match not in site.phones and match.strip("() .-/") != "":
                site.phones.append(match.strip())

    def _extract_whatsapp(self, site: ExtractedWebsite, page: PageData, html: str) -> None:
        for match in WA_RE.findall(html):
            number = re.search(r"(?:wa\.me/|phone=)(\d+)", match)
            if number and number.group(1) not in site.whatsapp_numbers:
                site.whatsapp_numbers.append(number.group(1))

    def _extract_social(self, site: ExtractedWebsite, page: PageData, links: list[str]) -> None:
        for link in links:
            host = urllib.parse.urlparse(link).netloc.lower().replace("www.", "")
            base = host.split(".")[0]
            if base in {h.split(".")[0] for h in SOCIAL_HOSTS} and link not in site.social_links:
                site.social_links.append(link)

    def _extract_ctas(self, site: ExtractedWebsite, page: PageData, soup: BeautifulSoup) -> None:
        if site.has_cta:
            pass
        for element in soup.find_all(["a", "button"]):
            text = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip().lower()
            classes = " ".join(element.get("class", [])) if isinstance(element.get("class"), list) else ""
            href = (element.get("href") or "").lower()
            if any(h in classes for h in CTA_HINT) or text in ("reservar", "reserva tu turno", "contactar") or any(
                k in text for k in ("reserva", "turno", "escribinos", "escríbenos", "contactar", "cotizar", "consultar", "solicitar")
            ) or "reserv" in href:
                if text:
                    site.cta_texts.append(text[:120])
                site.has_cta = True

    def _extract_services(self, site: ExtractedWebsite, soup: BeautifulSoup, page: PageData) -> None:
        for li in soup.find_all("li"):
            text = re.sub(r"\s+", " ", li.get_text(" ", strip=True)).strip()
            lowered = text.lower()
            if any(k in lowered for k in SERVICE_KEYWORDS) and len(text) > 3 and text not in site.services:
                site.services.append(text[:160])
        for heading in soup.find_all(["h2", "h3"]):
            text = heading.get_text(" ", strip=True)
            if text.lower() in ("servicios", "nuestros servicios", "tratamientos"):
                siblings = heading.find_next_siblings()
                for sibling in siblings[:3]:
                    if sibling.name in ("p", "ul", "div"):
                        for li in sibling.find_all("li"):
                            t = li.get_text(" ", strip=True)
                            if t and t not in site.services:
                                site.services.append(t[:160])

    # ------------------------------------------------------------------
    @staticmethod
    def _dedupe_and_finalize(site: ExtractedWebsite) -> None:
        # unique, ordered by confidence
        seen: set[str] = set()
        ordered: list[dict[str, Any]] = []
        for item in sorted(site.emails, key=lambda e: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(e["confidence"], 3)):
            if item["email"] in seen:
                continue
            seen.add(item["email"])
            ordered.append(item)
        site.emails = ordered
        site.phones = list(dict.fromkeys(site.phones))[:8]
        site.social_links = list(dict.fromkeys(site.social_links))[:8]
        site.services = list(dict.fromkeys(site.services))[:20]
        if site.meta_description is None:
            # one more pass on the concatenated html of all pages
            site.meta_description = None


def link_parents(soup: BeautifulSoup, needle: str) -> str:
    """Crude helper: does any visible link containing `needle` live in a footer?"""
    for link in soup.find_all("a", href=True):
        if needle in link.get("href", "").lower():
            parent_classes = " ".join(str(c) for c in (link.parent.get("class") or []))
            return parent_classes.lower()
    return ""


def extract_emails_from_html(html_content: str, page_url: str, kind: str = "other") -> list[dict[str, Any]]:
    """Convenience for tests: run email extraction over a single HTML blob."""
    page = PageData(url=page_url, html=html_content, text=extract_main_text(html_content), kind=kind)
    extractor = WebsiteExtractor()
    extracted = extractor.extract([page])
    return extracted.emails
