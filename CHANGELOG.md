# Changelog

Todas las novedades relevantes del rediseño, por fase. Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Fase 6 — Scoring configurable y explicable (2026-10-14)
- **Configuración de scoring por workspace** (`scoring_configs`, migración
  `c7f3a19bd5e2`): pesos multiplicativos 0–3 por categoría (reputación, reseñas,
  presencia web, calidad web, oportunidades, teléfono, email) y umbrales
  HOT/WARM/COLD con validación estricta. Opt-in: sin fila, defaults idénticos
  a lo vigente (comportamiento invariable, D6.1).
- **API nueva**: `GET/PUT/DELETE /api/scoring-config` · `POST
  /api/scoring-config/rescore` (por ids o global, cap 500, ignora archivados)
  · `GET /api/scoring-config/categories` (metadatos es-AR para la UI).
- **Breakdown con peso aplicado**: cada ítem del `score_breakdown` registra
  `base_delta`, `delta`, `weight` y `category` — el detalle de lead muestra
  "×1.50" junto al delta cuando una señal está ponderada (D6.2).
- **Rescore siempre explícito (D6.4)**: guardar config no modifica leads; el
  usuario dispara el recompute (determinista, local, sin costo de API, sin
  tocar datos observados), con confirmación y resultado resumido.
- **UI `/settings/scoring`**: sliders por categoría y por umbral, guardar /
  restablecer defaults / re-puntuar todo, enlace desde `/settings`. Pipeline
  pasa la config vigente al scoring (carga una vez por búsqueda).
- Tests: `test_scoring_config.py` (resolver de pesos con clamp, umbrales
  custom, ponderación con meta, roundtrip API, validaciones 422, rescore por
  ids y global, reset a defaults) — suite completa verde; tsc + build 12/12.

### Fase 5 — Website audit con evidencia + screenshots (2026-10-14)
- **Findings persistidos**: `website_audits.findings` (migración `b5c9e2d41f07`)
  guarda la evidencia completa — problema, evidencia textual, `source_url`,
  `kind` FACT/INFERENCE, dimensión. Audits previos quedan con lista vacía
  (nada backfilleado inventado, D5.1) y la API los expone igual.
- **Screenshots reales con degradación honesta (D5.2–D5.5)**: nuevo
  `ScreenshotService` provider-driven (`none`|`playwright`), captura del
  *home fold* 1280×800 jpeg para cada audit nuevo; si la captura no es
  posible, el audit queda sin imagen — jamás sintética. Config vía env
  (`SCREENSHOT_*`), PATH de archivos bajo `settings.screenshots_dir`.
- **Descarga autenticada**: `GET /api/leads/{id}/audit/screenshots/{index}`
  (FileResponse + scoping de workspace; el path físico nunca sale en la API;
  anti path traversal en `resolve_screenshot_path`, D5.4).
- **Docker**: imagen backend instala Chromium (`playwright install --with-deps
  chromium`), `playwright==1.49.0` pineada, compose activa el provider por
  defecto (D5.3). `.env.example` documenta todas las settings; `.gitignore`
  excluye `backend/screenshots/`.
- **Fix transversal (D5.6)**: re-ejecutar una búsqueda ya no viola el índice
  único de `search_leads` — el stage de ingest precarga los vínculos
  existentes. Detectado en el E2E (re-run tras FAILED intermedio).
- **Frontend `/leads/[id]`**: card "Captura del sitio" (blob autenticado,
  caption URL+fecha, estado honesto cuando no hay navegador) y card
  "Findings" con chips `FACT`/`INFERENCE` + dimensión + evidencia + fuente.
- **E2E verificado en vivo** (mock): búsqueda grid re-ejecutada hasta
  COMPLETED (96 leads, 93 webs, 13 emails); re-audit con cache invalidada
  persiste 10 findings (2 FACT/8 INFERENCE) expuestos por la API.
- Tests: `test_audit_evidence.py` (persistencia, provider none, soft-fail,
  endpoint 404/200 con archivo fake, analyze_lead robusto) + suite completa
  verde; tsc --noEmit + build limpios.

### Fase 4 — Leads Pro: selección, vistas a cuenta, evidencia y bulk (2026-10-14)
- **Tabla de leads pro (`/leads`):** selección por fila con barra flotante de
  acciones masivas; visibilidad de columnas (dropdown) con persistencia en la
  vista activa; headers ordenables server-side; fila de filtros extended
  (ciudad, categoría, tag, responsable) plegable; conteos y paginación con
  `page_size` hasta 500 (corrige el cap de la vista mapa, bug D3.5).
- **Vistas guardadas en la cuenta (`lead_views`):** migración automática de
  las locales al primer uso, upsert por nombre, CRUD vía `GET/POST/PUT/DELETE
  /api/lead-views` (D4.1).
- **Bulk actions (`POST /api/leads/bulk`):** set_status, archivar/
  desarchivar (nunca borrar), agregar/quitar tags (padded CSV, D4.2),
  asignar/quitar responsable (string libre, D4.3). Respuesta `{updated,
  skipped}`. Export CSV/Sheets de la selección reusa `selection=selected&ids`.
- **Bulk propuestas (`POST /api/leads/bulk-proposals`):** genera propuestas
  por lead con errores por-ítem en `skipped[]`; todas quedan
  `READY_FOR_REVIEW` (guardrail humano intacto, D4.5).
- **Detalle de lead conmás control:** ownership + etiquetas editables inline,
  re-auditoría manual del website, propuestas del lead y **historial real**
  (`GET /api/leads/{id}/activity`: creado/auditorías/propuestas/emails,
  nada sintético — D4.6).
- **Backend aditivo:** `Lead.tags` + `Lead.owner_name` (migración
  `a3b8f5c29d1e`, batch_alter sqlite), `lead_views` nueva tabla, filtros
  city/category/tag/owner en list+export, sort whitelist con 422 (D4.4).
- **Bug fix transversal (encontrado en E2E F4, pre-F4):** comparación
  tz naive/aware rompía la búsqueda tras calificar leads (`website_service`,
  rotación de cuentas). Helper `as_utc()` en `app/utils/text.py` (D4.7).
- **E2E verificado en vivo** (mock): búsqueda grilla COMPLETED 25/25 celdas,
  96 leads, $0.875; bulk tags/owner → filtros matchean; sort asc/422;
  vistas CRUD; `page_size=500` devuelve 144 items; timeline con auditoría.
- Tests: `test_leads_pro.py` (bulk, filtros, sort, vistas, actividad) +
  suite completa verde; tsc --noEmit + next build limpios.

### Fase 3 — UX de descubrimiento: mapa, área y barrido en vivo (2026-10-14)
- **Mapa Leaflet** (infra `components/map/`): wrapper imperativo SSR-safe con
  tiles conscientes del tema (OSM / CartoDB Dark); estilos de marca para pines,
  clusters, controles y atribución. Sin react-leaflet (D3.1).
- **`/searches/new` reescrita:** dos modos — *Por texto* (ciudad + rubro) y
  *Por mapa* con editor de área (rectángulo/círculo/polígono, herramientas
  propias en es-AR). Preview v2 conectada a la API: modo, nº de celdas,
  llamadas y costo con rango, tope de presupuesto (input), alertas (60/query,
  área excedida) y disclaimer de billing. Mobile-first: mapa a ancho completo.
- **`/searches/[id]` en vivo:** progreso por SSE (`use-search-events`, D3.4)
  con fallback a polling y chip de canal; barra de grilla celda a celda;
  panel de costo real vs estimado vs tope; cancelación con confirmación
  (Radix Dialog) y relanzado; métricas incl. dedupeados en modo grilla.
- **`/leads`:** vista mapa con pines coloreados por temperatura + clustering
  (hasta 500 del filtro activo, pie honesto) y **vistas guardadas** nombradas
  en localStorage (aplicar/actualizar/borrar) — mínima real, D3.3.
- **Backend aditivo:** `LeadSummary` expone `latitude/longitude` (necesario
  para pines; datos públicos de Places). Tipos `lib/api-types.ts` regenerados.
- **E2E verificado en vivo:** preview grid (12 celdas, $0.42–1.26), búsqueda
  por grilla completa con SSE (24 celdas → 240 únicos, $0.84 real vs $0.70
  estimado, 231 websites, 31 emails), páginas `/searches/new` y `/leads` 200.
- tsc --noEmit + next build limpios.

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
