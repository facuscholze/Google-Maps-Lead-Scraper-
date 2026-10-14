# Changelog

Todas las novedades relevantes del rediseño, por fase. Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Fase 2 — Backend de búsqueda (2026-10-14)
- **Grilla geo→searchText** (`app/services/geo_grid.py`): celdas rectangulares
  solapadas para áreas rect/circle/polygon; una consulta Text Search por celda
  con `locationRestriction.rectangle` (oficial). Celdas saturadas (≥60) se
  subdividen ×4 hasta depth 2; progreso `grid_done/total/capped_cells` en vivo.
- **Guardarraíles de costo:** estimador SKU-verificado (`place_pricing`,
  Text Search Enterprise $35/1k configurable), `POST /searches/preview` v2 con
  modo, celdas, rango de costo (1–3 páginas/celda) y alertas; estimados
  persistidos en cada búsqueda; `budget_cap_usd` frena el barrido
  cooperativamente y queda `budget_exhausted`; `api_calls`/`api_cost_usd`
  reales se acumulan y persisten.
- **Clients API realistas (BUG-04):** `TextSearchClient` respeta el tope
  oficial de 60 resultados/query (3 páginas de 20); preview avisa cuando
  `max_results>60` y sugiere grilla.
- **Dedupe reforzado:** por `place_id` entre celdas dentro del barrido + señal
  secundaria por teléfono/dominio normalizados en ingest (excluye
  `PLATFORM_HOSTS`); merges contados en `deduped_count` y logeados.
- **SSE:** `GET /api/searches/{id}/events` (snapshot búsqueda+jobs cada cambio,
  heartbeat 15 s, done al terminal) con auth `?token=` o bearer; cancelación
  cooperativa con `POST /api/searches/{id}/cancel`.
- **BUG-02:** el modo celery ya no salta las etapas 3–6 del pipeline (auditoría,
  scoring, contactos corren en cualquier modo).
- **BUG-03:** `WORKING_DAYS` ahora es estrictamente ISO 1-7 (validator +
  `isoweekday()`); ENV con `0` falla al arrancar en vez de enviar desfasado.
- **BUG-06:** eliminada la doble llamada a `map_place` en el ingest.
- **BUG-09:** drenaje de cola email en modo inline vía scheduler asyncio en el
  lifespan (`QUEUE_SCHEDULER_*`, apagado en tests); celery usa el beat del
  worker (`docker compose`: servicios `redis` + `worker -B`).
- **BUG-10:** `backend/dev.db` fuera del repo; `.gitignore` ignora `*.db`.
- **Rate limiting por IP real:** el backend respeta `X-Forwarded-For` solo de
  peers en `TRUSTED_PROXIES` (IP o CIDR — el proxy Next lo propaga sin que el
  navegador pueda falsearlo).
- **Migración `9f4c2e1a7b3d`:** 13 columnas nuevas en `searches` (modo, geo,
  presupuesto, estimados, costo real, progreso grilla, dedupe, cancelación),
  upgrade/downgrade verificados en SQLite.
- **Tests:** +23 (grilla geo, pipeline grid con dedupe/costo/cap/cancel,
  preview/SSE/auth, working days ISO). Suite: **115 passed / 1 xfailed**.

### Fase 1 — Fundaciones frontend (2026-10-14)
- **Tema innblock:** tokens CSS en `globals.css` (rojo `#D90000` / negro `#070707` /
  `#FF3B30`, HSL channels), **oscuro por defecto** con opción clara (next-themes,
  sin transición al cargar). Fuentes de marca (Archivo / Instrument Serif /
  Martian Mono) vía `<link>` para no romper builds offline.
- **shadcn/ui + Radix:** primitivos nuevos en `components/ui/` (button, card,
  badge, skeleton, input, label, dialog, sheet, dropdown-menu, tooltip, sonner)
  escritos con la API canónica de shadcn (el sandbox no accede al registry;
  ver DECISIONS.md D1.1). Iconos lucide-react, Framer Motion con
  `reducedMotion="user"`, tailwindcss-animate.
- **Shell responsive nuevo:** sidebar colapsable (persistente, con tooltips) en
  desktop y **bottom-tab bar + sheet "Más"** en móvil; top bars slim; targets
  táctiles ≥ 44 px; área segura iOS (`safe-area-inset`). Navegación de 6
  secciones: Inicio, Descubrir, Leads, Propuestas, **Envíos**, Ajustes.
- **Paleta ⌘K / Ctrl+K:** navegación, acciones (nueva búsqueda, cambiar tema) y
  búsqueda en vivo de leads sobre la API.
- **Pantalla Envíos** (`/shipments`): KPIs (cola/enviados/fallidos/no-contactar),
  lista de correos con estado y horarios, cancelación de envíos encolados con
  toasts de confirmación.
- **Cliente API tipado:** `lib/api-types.ts` **generado desde el OpenAPI** del
  backend (openapi-typescript, `npm run gen:types`); `lib/types.ts` re-exporta
  los schemas con refinamientos de unión; código nuevo consume los schemas
  directamente.
- **Re-skin de páginas existentes:** los colores legados (sand/gold/taupe…) son
  aliases de los nuevos tokens, así toda la app toma la identidad innblock sin
  reescribir cada pantalla (su rediseño llega en fases 3, 4, 7, 8 y 9).
- **Fixes:** bug visual del embudo del dashboard (comparación rota, BUG-05);
  labels del dashboard en español rioplatense.
- **Tests:** el test de plantilla vieja (BUG-01) queda `xfail(strict)` con razón
  documentada — se reemplaza en Fase 7 junto con el script de sync.
- **Verificado:** 91 passed + 1 xfailed (backend) · `tsc --noEmit` OK ·
  `npm run build` OK (12 rutas) · smoke test HTTP del shell (nav desktop/móvil,
  `/shipments` 200, `/login` sin chrome) · compose YAML válido (Docker no
  disponible en este sandbox).

### Fase 0 — Auditoría (2026-10-14)
- **Docs:** `docs/AUDIT.md` con mapa de arquitectura, 10 bugs (archivo:línea), deuda
  técnica, problemas de UX, análisis de costos de Places API (New) verificado contra
  documentación oficial, tabla MANTENER/MEJORAR/ELIMINAR/AGREGAR y plan por fases.
- **Docs:** `DECISIONS.md` inicial (fuente del mail, Leaflet+OSM, grilla searchText,
  Celery+Redis, tokens innblock, mocks solo dev/test).
- **Estado verificado:** 91/92 tests backend pasan (falla
  `test_packaged_template_matches_source` por referencia a archivo inexistente
  `nuevo html innblock.html`), `tsc --noEmit` OK, `npm run build` OK.
- Sin cambios de código de producto (pendiente aprobación de la Fase 0).
