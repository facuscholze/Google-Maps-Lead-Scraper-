/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // NOTE: `/api/*` is NOT proxied with `rewrites()` on purpose.
  // Next resolves rewrites at BUILD time and freezes them into
  // routes-manifest.json, so a runtime API_URL (e.g. http://backend:8000 when
  // running in docker compose) was ignored and the container kept proxying to
  // http://localhost:8000 → ECONNREFUSED. The proxy now lives in
  // app/api/[[...path]]/route.ts, where process.env.API_URL is read per request.
};

export default nextConfig;
