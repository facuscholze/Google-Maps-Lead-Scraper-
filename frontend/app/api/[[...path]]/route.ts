import { NextResponse, type NextRequest } from "next/server";

/**
 * Runtime reverse proxy: `/api/*` → FastAPI backend.
 *
 * Why a route handler instead of `rewrites()` in next.config.mjs?
 * `rewrites()` is evaluated once during `next build` and frozen into
 * `.next/routes-manifest.json` (which is what the standalone server reads), so
 * the runtime `API_URL` set by docker-compose was ignored and every container
 * kept proxying to the build-time default `http://localhost:8000` →
 * `Failed to proxy http://localhost:8000/api/... [AggregateError] ECONNREFUSED`.
 * A route handler runs per request on the server, so `API_URL` is read at
 * runtime and changing it only needs a container restart, never a rebuild.
 */

/** Used when API_URL is not set (local dev with uvicorn on :8000). */
const DEFAULT_API_URL = "http://localhost:8000";

/** Generous ceiling so long searches / exports never get cut off mid-flight. */
const PROXY_TIMEOUT_MS = 10 * 60 * 1000;

/** Hop-by-hop + framing headers that must not be forwarded as-is. */
const STRIP_REQUEST_HEADERS = [
  "host",
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "content-length", // re-framed by fetch from the body we send
];

/** These are set by the runtime from the body we return, or meaningless here. */
const STRIP_RESPONSE_HEADERS = [
  "connection",
  "keep-alive",
  "transfer-encoding",
  "content-length",
  "content-encoding", // fetch already decompressed the payload
];

/** Response codes that must not carry a body (Response constructor throws). */
const BODYLESS_STATUSES = new Set([101, 204, 205, 304]);

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function targetUrl(request: NextRequest): string {
  const base = (process.env.API_URL?.trim() || DEFAULT_API_URL).replace(/\/+$/, "");
  // request.nextUrl keeps the original path and query string untouched, so ids,
  // encoded slashes and search params reach the backend exactly as the browser
  // sent them.
  return `${base}${request.nextUrl.pathname}${request.nextUrl.search}`;
}

function forwardableRequestHeaders(request: NextRequest): Headers {
  const headers = new Headers(request.headers);
  for (const header of STRIP_REQUEST_HEADERS) headers.delete(header);
  return headers;
}

async function proxy(request: NextRequest): Promise<Response> {
  const target = targetUrl(request);
  const headers = forwardableRequestHeaders(request);

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    const buffer = await request.arrayBuffer();
    if (buffer.byteLength > 0) body = buffer;
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      // 3xx (OAuth start, /api/docs → /api/docs/) is passed through untouched
      // so the browser follows it, instead of being swallowed by the proxy.
      redirect: "manual",
      signal: AbortSignal.timeout(PROXY_TIMEOUT_MS),
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        detail: `No se pudo conectar con el backend en ${target} (${reason}). Revisá API_URL y que el servicio backend esté arriba.`,
      },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers(upstream.headers);
  for (const header of STRIP_RESPONSE_HEADERS) responseHeaders.delete(header);

  // `redirect: "manual"` can surface as a 0-status opaque redirect depending on
  // the runtime; translate it back into a normal redirect.
  if (upstream.status === 0) {
    const location = responseHeaders.get("location");
    if (location) return NextResponse.redirect(location, 302);
    return NextResponse.json({ detail: "Respuesta inválida del backend." }, { status: 502 });
  }

  if (BODYLESS_STATUSES.has(upstream.status) || !upstream.body) {
    return new Response(null, { status: upstream.status, statusText: upstream.statusText, headers: responseHeaders });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
