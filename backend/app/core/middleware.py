"""HTTP middleware: secure headers, CORS, naive in-process rate limiting.

Rate limiting protects public write endpoints per IP; production deployments
should pair this with a gateway/Redis-backed limiter.
"""
from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings


def add_security_and_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, limit=120, window=60)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def _is_trusted_peer(host: str) -> bool:
    entries = settings.trusted_proxy_set
    if host in entries:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    for entry in entries:
        if "/" not in entry:
            continue
        try:
            if ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_ip(request: Request) -> str:
    """Real client IP: trust X-Forwarded-For only from configured proxies.

    Without this, every request arriving via Nginx or the Next.js route-handler
    proxy is bucketed under the proxy's IP — one shared quota for all users,
    and a trivial DoS for everyone else. Peers are matched by IP or CIDR
    (docker-compose uses the 172.16.0.0/12 pool).
    """
    host = request.client.host if request.client else "unknown"
    if host != "unknown" and _is_trusted_peer(host):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    return host


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window limiter keyed by client IP."""

    def __init__(self, app, limit: int = 120, window: int = 60) -> None:
        super().__init__(app)
        self._limit = limit
        self._window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        client = client_ip(request)
        now = time.monotonic()
        bucket = self._hits[client]
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()
        if len(bucket) >= self._limit:
            return Response(content="Too many requests", status_code=429)
        bucket.append(now)
        return await call_next(request)
