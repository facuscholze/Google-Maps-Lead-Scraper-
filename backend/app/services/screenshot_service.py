"""Screenshot evidence capture (Fase 5, D5.2).

Captura real del home del sitio del lead con un navegador headless
(Playwright/Chromium). Regla de producto: **cero datos inventados** — si el
provider está en "none" o el browser no está instalado o la captura falla, el
audit simplemente queda sin screenshot (metadatos vacíos) y así se muestra en
la UI; jamás se genera una imagen sintética.

Los archivos se guardan en ``settings.screenshots_dir`` bajo
``{workspace_id}/{lead_id}-{audit_id}.jpg`` y solo se sirven vía
``GET /api/leads/{id}/audit/screenshots/{idx}`` (endpoint autenticado con
scoping de workspace), de modo que las rutas relativos persistidas siguen
siendo válidas si el directorio se reubica (D5.4).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import log_event
from app.utils.text import utcnow

logger = logging.getLogger("avascho.screenshots")


class ScreenshotCaptureError(Exception):
    """Raised when a capture was attempted but failed for a concrete reason."""


def screenshots_root() -> Path:
    return Path(settings.screenshots_dir).resolve()


def resolve_screenshot_path(relative: str) -> Path | None:
    """Resolve a stored relative path inside the screenshots root.

    Returns None if the path would escape the root (defensa en profundidad:
    el valor viene de nuestra propia row, pero no confiamos ciegamente).
    """
    root = screenshots_root()
    try:
        candidate = (root / relative).resolve()
    except OSError:
        return None
    if root not in candidate.parents and candidate != root:
        return None
    return candidate


class ScreenshotService:
    """Provider-driven screenshot capture."""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = provider or settings.screenshot_provider

    def capture_home(self, url: str, workspace_id: int, lead_id: int, audit_id: int) -> dict[str, Any] | None:
        """Capture the top fold of ``url``. Returns metadata or None (no shot)."""
        if self.provider == "none":
            return None
        if self.provider != "playwright":
            logger.warning("unknown screenshot provider %r — skipping capture", self.provider)
            return None
        try:
            return self._capture_playwright(url, workspace_id, lead_id, audit_id)
        except ScreenshotCaptureError as exc:
            log_event("screenshot_skipped", url=url, reason=str(exc)[:200])
            return None
        except Exception as exc:  # noqa: BLE001
            log_event("screenshot_skipped", url=url, reason=str(exc)[:200])
            return None

    # ------------------------------------------------------------- provider --
    def _capture_playwright(self, url: str, workspace_id: int, lead_id: int, audit_id: int) -> dict[str, Any] | None:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as exc:
            raise ScreenshotCaptureError("playwright no instalado") from exc

        relative = f"{workspace_id}/{lead_id}-{audit_id}.jpg"
        target = resolve_screenshot_path(relative)
        if target is None:  # should never happen (we build the name ourselves)
            raise ScreenshotCaptureError("path inválido")
        target.parent.mkdir(parents=True, exist_ok=True)

        width = settings.screenshot_viewport_width
        height = settings.screenshot_viewport_height
        timeout = settings.screenshot_timeout_ms
        status: int | None = None
        try:
            with sync_playwright() as pw:
                with pw.chromium.launch() as browser:  # raises si falta el binario
                    page = browser.new_page(viewport={"width": width, "height": height})
                    try:
                        response = page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                        status = response.status if response is not None else None
                        # pequeño respiro: muchos sitios pintan el fold tras DOM load
                        page.wait_for_timeout(1200)
                        page.screenshot(
                            path=str(target),
                            type="jpeg",
                            quality=settings.screenshot_jpeg_quality,
                            full_page=False,
                        )
                    finally:
                        page.close()
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "Executable doesn't exist" in message or "no executable" in message.lower():
                raise ScreenshotCaptureError(
                    "browser chromium no instalado (ver Dockerfile / `playwright install chromium`)"
                ) from exc
            raise

        size = target.stat().st_size if target.exists() else 0
        if size == 0:
            target.unlink(missing_ok=True)
            raise ScreenshotCaptureError("captura vacía")
        if size > settings.screenshot_max_bytes:
            target.unlink(missing_ok=True)
            raise ScreenshotCaptureError(f"captura excede {settings.screenshot_max_bytes} bytes")

        log_event("screenshot_captured", url=url, bytes=size, path=relative)
        return {
            "url": url,
            "path": relative,
            "kind": "home-fold",
            "width": width,
            "height": height,
            "bytes": size,
            "http_status": status,
            "captured_at": utcnow().isoformat(),
        }
