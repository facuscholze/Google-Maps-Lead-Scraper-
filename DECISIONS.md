# Decisiones del rediseño — AvaScho Lead Intelligence

Registro vivo de decisiones tomadas y su porqué. Las decisiones marcadas como
"revertible" pueden cambiarse sin romper el plan; las no negociables vienen del brief.

## D0 — 2026-10-14 (Fase 0)

### D0.1 La fuente de verdad del mail es `nuevo html mail.html` ✅
El master prompt lo define como ÚNICO mail del sistema. El repo traía además una
variante anterior empaquetada (`backend/app/services/emailing/templates/innblock.html`)
con slots distintos. Decisión: la plantilla nueva se convierte en la plantilla del
sistema mapeando sus variables (`{{nombre}}`, `{{empresaCliente}}`, `{{intro}}`,
`{{firma}}`, …) al contenido de propuestas, **sin tocar su estética** (rojo
`#d90000` / negro `#070707`, estructura, textos fijos y firma con socios). El archivo
original queda intacto en la raíz y se conserva una copia de respaldo
`templates/email/innblock_original.html` antes de cualquier adaptación.
*Por qué:* es la marca actual (Estudio) y el brief lo exige literalmente.

### D0.2 Mapa del producto: Leaflet + tiles OpenStreetMap (default) ✅ revertible
*Por qué:* cero costo/licencia, sin API key en el browser, suficiente para pines,
clusters, heatmap y dibujo de área (Leaflet.draw). Google Maps JS sumaría otra SKU de
billing y exigiría exponer la key. Queda documentado como opción configurable futura.
Costo-beneficio claramente a favor de OSM para este caso de uso.

### D0.3 Grilla de barrido sobre `searchText` + `locationRestriction` ✅
Los círculos/polígonos dibujados se aproximan por celdas rectangulares (soportadas
oficialmente por `locationRestriction`) con dedupe por `place_id`. `nearbySearch`
(círculo) queda como complemento opcional futuro.
*Por qué:* un solo endpoint mantiene simple el estimador de costos y la deduplicación;
el tope oficial de 60 resultados/consulta se maneja subdividiendo celdas.

### D0.4 Cola de background: Celery + Redis ya presentes; `inline` solo dev/test ✅
*Por qué:* ya está en `requirements.txt` y el brief pide cola real; se completa el
compose con servicios `redis` + `worker` y se arregla el pipeline en modo celery
(BUG-02). No se evalúa cambiar a ARQ/RQ: costo de migración sin beneficio real.

### D0.5 Sistema de diseño: shadcn/ui + Radix + Tailwind, oscuro por defecto ✅
Tokens de marca extraídos de `nuevo html mail.html`: `--brand-red: #d90000`,
`--brand-black: #070707`, `--brand-red-bright: #ff3b30`. Tipografías del mail
(Archivo / Instrument Serif / Martian Mono) como acentos; Inter/system para UI.
*Por qué:* el brief lo exige y el tema actual sand/gold no es la marca.

### D0.6 `priceLevel` NO se agrega al field mask por ahora ✅ revertible
Es un campo Enterprise (ya estamos en ese tier por rating/website/teléfonos, así que
no subiría el SKU actual), pero no hay consumidor del dato todavía. Se evalúa en la
Fase 6 como señal de presupuesto del scoring.
*Por qué:* regla de no pedir campos sin uso.

### D0.7 Mock providers: solo tests/demo explícito ✅
`SEARCH_PROVIDER=mock` y `ALLOW_MOCK_EMAIL_SENDING=true` quedan como defaults de
desarrollo; en producción el fallback silencioso se elimina (fail fast con mensaje
claro). *Por qué:* criterio de simplificación del brief + evita "envíos fantasma"
(BUG-08).

### D0.8 Baja de mails: link de opt-out + respuesta "BAJA" ✅
El pie actual pide responder "BAJA"; se conserva ese texto fijo del mail y se agrega
un link funcional de baja (endpoint que marca supresión) + sync de respuestas Gmail.
*Por qué:* cumplimiento y la regla "consent-first" no negociable.

### D0.9 Trabajo por rama y commits
Todo el trabajo se hace en la rama de sesión `arena/94b95662-google-maps-lead-scraper`
con commits convencionales por fase, sin tocar `main`.

## D1 — 2026-10-14 (Fase 1)

### D1.1 shadcn/ui escrito a mano (API canónica), no por CLI ✅
El sandbox solo tiene salida a npm/pypi/GitHub: el registry del CLI de shadcn
(ui.shadcn.com) no es alcanzable. Los componentes de `frontend/components/ui/`
siguen la API y convenciones oficiales de shadcn/ui (Radix + cva + tokens CSS),
que es exactamente lo que el CLI copiaría. *Por qué:* mismo resultado, cero
dependencia de red adicional, y queda todo versionado en el repo.

### D1.2 Tema oscuro por defecto, explícito (sin "system") ✅ revertible
`next-themes` con `defaultTheme="dark"` y `enableSystem={false}`: la marca es
oscura y el brief pide oscuro por defecto con opción clara; el usuario elige y
se persiste. El toggle vive en sidebar, en la top bar móvil y en ⌘K.

### D1.3 Aliases de colores legados en Tailwind ✅
Los nombres del tema anterior (`sand`, `gold`, `taupe`, `ink`, `sandline`…) se
mantienen en `tailwind.config.ts` apuntando a los tokens nuevos. *Por qué:*
re-skinnea las páginas viejas sin tocarlas; cada una se reescribe en su fase y
los aliases se eliminan en Fase 10 (limpieza).

### D1.4 Tipos del cliente API: generados + refinados ✅
`lib/api-types.ts` se genera con openapi-typescript desde
`/api/openapi.json` (script `npm run gen:types` contra el backend local). Los
tipos de app viven en `lib/types.ts` como alias refinados; el código nuevo usa
`components["schemas"][...]` directo. *Por qué:* una sola fuente de verdad (el
backend) y cero drift manual, tolerando los `unknown[]` de campos JSON libres.

### D1.5 Envíos estrena navegación con versión mínima real ✅
La sección Envíos (cola/historial/cancelación) entra en Fase 1 para completar la
arquitectura de información con datos reales del endpoint existente
(`/api/emails`), sin anticipar el diseño completo de su pantalla.

## D2 — 2026-10-14 (Fase 2 · backend de búsqueda)

### D2.1 Grilla: celdas rectangulares solapadas (20%), 1.5 km, tope 120 ✅
Celdas generadas por `app/services/geo_grid.py` (rectangulares, soportadas por
`locationRestriction` oficial). Solapamiento default 20% para no perder negocios
en los bordes; el dedupe por `place_id` entre celdas absorbe los repetidos
(verificado con fixtures: celdas solapadas devuelven los mismos places).
Celda que devuelve ≥60 resultados (tope oficial de Text Search New) se
subdivide en 4 hasta `GRID_MAX_SUBDIVISION_DEPTH=2` o `MIN_CELL_KM=0.35`;
si no puede, queda marcada `grid_capped_cells` (conteo expuesto al usuario para
saber que la zona quedó saturada). `GRID_MAX_CELLS=120` frena el costo: áreas
gigantes → 422 con mensaje claro en create, warning en preview.

### D2.2 SSE autenticado con `?token=` (EventSource no envía headers) ✅
`GET /api/searches/{id}/events` acepta JWT por query string (EventSource del
browser no puede mandar `Authorization`) validado con exactamente las mismas
reglas que el bearer (`decode_access_token` + match de workspace); el header
bearer sigue andando para `curl`/clientes. El stream emite `event: snapshot`
con búsqueda+jobs cada cambio, heartbeat cada 15 s y `event: done` al estado
terminal; guard de 30 min. *Por qué polling corto a DB:* funciona igual en
inline y celery (el worker es otro proceso), sin pub/sub extra.

### D2.3 `WORKING_DAYS` pasa a ISO 1-7 (rompe ENV viejas con `0`) ✅
Antes el validator aceptaba 0-6 y la cola comparaba con `isoweekday()` (1-7):
mezcla que corría envíos un día desplazado (BUG-03). Ahora validator exige 1-7
y la cola usa `isoweekday()`. Una ENV vieja con `0` **falla al arrancar** con
mensaje claro — preferible a enviar el día equivocado. Default `1,2,3,4,5`
(lunes–viernes) no cambia.

### D2.4 Precio SKU configurable, nunca hardcodeado ✅
`places_price_per_1k_usd` (default 35 = Text Search Enterprise, el SKU más alto
que factura nuestra field mask verificada contra la doc el 2026-10-14:
https://developers.google.com/maps/billing-and-pricing/pricing). Estimador y
contabilidad leen siempre de settings — re-verificar precio en cada deploy.

### D2.5 Compose pasa a `EXECUTION_MODE=celery` con redis + worker (`-B`) ✅
Inline queda para dev/test. El worker corre `celery ... worker -B --concurrency=2`
(beat embebido: una sola instancia, deploy single-node) y arranca **después**
de que el backend migra+levanta (depends_on service_healthy) para no competir
con `alembic upgrade head`.

### D2.6 Estimador worst-case (ignora franquicia gratuita mensual) ✅
El estimador cobra todas las llamadas al precio de lista sin descontar los
5.000/1.000 gratis mensuales del SKU: no podemos saber el consumo MTD de la
cuenta de Google y subestimar costo es peor que sobrestimarlo. Se persiste
`estimated_api_calls/cost_usd` al crear y `api_calls/api_cost_usd` reales al
correr — la UI muestra estimado vs real.

### D2.7 Dedupe secundario: teléfono/dominio con `PLATFORM_HOSTS` ✅
En ingest, si `place_id` no matchea, se intenta por teléfono normalizado
(dígitos, sin 0 inicial, ≥8) y luego por dominio normalizado. Dominios de
plataformas donde el path es la identidad (facebook.com, linktr.ee, wa.me,
directorios, y `mockbusiness.local` de fixtures) se excluyen de la clave —
son host compartido y fusionarían negocios distintos (lo detectó
`test_full_pipeline` al caer `emails_found`). Los merges secundarios se logean
(`lead_deduped{by=phone|domain}`) y cuentan en `deduped_count`; nunca fusionan
silenciosamente leads creados por búsquedas anteriores.

## D3 — 2026-10-14 (Fase 3 · UX de descubrimiento)

### D3.1 Leaflet imperativo, sin react-leaflet ✅
`components/map/base-map.tsx` crea el `L.map` con imports dinámicos de Leaflet
(CSS incluido) dentro de un efecto client-side. *Por qué:* cero fricción con
React 19/Next 15 (react-leaflet v5 era muy nuevo), control total del ciclo de
vida (StrictMode-safe: remove() en cleanup) y un solo punto donde tocar tiles
consciente del tema (OSM en claro · CartoDB Dark Matter en oscuro, ambas
gratuitas con la atribución de licencia visible).

### D3.2 Toolbar de dibujo propia (no la de leaflet-draw) ✅
Se usan los handlers `L.Draw.Rectangle/Circle/Polygon` pero con botones propios
en es-AR + estilo innblock y hints contextuales. La toolbar default de
leaflet-draw está en inglés y no respeta el sistema de diseño. Formas emitidas
matchean 1:1 el schema GeoArea del backend (rect → sw/ne, circle →
center+radius_km, polygon → puntos).

### D3.3 Vistas guardadas en localStorage (mínima real) ✅
`/leads` guarda combinaciones de filtros nombradas en `localStorage`
(`avascho_lead_views`). Es deliberadamente simple: Fase 4 (Leads Pro) lleva las
vistas al backend con columnas/bulk y ahí se migra. No bloquear F3 por una API
de vistas que aún no existe.

### D3.4 SSE con fallback a polling ✅
`lib/use-search-events.ts` usa EventSource (token por query param, D2.2) y si
el stream nunca abre (proxy que corta, pestaña dormida) degrada a polling de
`/status` cada 2.5 s. La UI muestra el canal activo (chip "en vivo"/"polling").
Polling-only se mantiene como red de seguridad permanente, no como modo
"viejo". EventSource parece muerto → el `done` del stream cierra ambos caminos.

### D3.5 El mapa de leads usa hasta 500 resultados del filtro, no la página ✅
Ver 25 pines de una página confundiría ("¿mi barrido dio solo esto?"). Se hace
una segunda query con `page_size=500` solo al entrar en vista mapa, se informa
el cap en el pie y cuántos leads tienen coordenadas. El límite 500 protege el
browser (markercluster `chunkedLoading`).

## Fase 4 — Leads Pro (2026-10-14)

- **D4.1 — Vistas guardadas al backend (`lead_views`)**: las vistas de la tabla de leads (antes `localStorage avascho_lead_views`) pasan a la tabla `lead_views` con scoping de workspace y `uq(workspace_id, name)`. El `config_json` es **libre** (estado de UI: filtros/orden/columnas) sin validación server-side más allá de `name 1..120`. El frontend migra automáticamente las vistas locales al primer GET (upsert por nombre, POST 200 en lugar de 409 cuando el nombre ya existe — uno por usuario es lo natural).
- **D4.2 — Tags como padded CSV**: `Lead.tags` guarda `",frio,recontacto,"` (lowercase, delimitado por comas) en lugar de JSON. Motivo: filtrado portable con `LIKE '%,frio,%'` en SQLite y Postgres sin casts ni operadores JSON vary entre dialectos. El schema Pydantic expone `list[str]` (validator `mode="before"` que splitea el CSV — `from_attributes` no convierte solo). Normalización en bulk: strip + lowercase.
- **D4.3 — `owner_name` string libre indexado** (no FK a User): el workspace actual es single-user (Facu); un string editable permite asignar a cualquier colaborador futuro sin modelo nuevo. Se filtra con `ilike` para coincidencias parciales.
- **D4.4 — Sort server-side por whitelist**: `GET /leads?sort=&order=` valida contra keys explícitas (business_name, category, city, reviews_count, rating, website_score, opportunity_score, lead_score, created_at) con `pattern=` en FastAPI → 422 ante valores arbitrarios (SQL injection imposible). Fallback `lead_score desc, reviews_count desc`. `page_size` sube de 200 a **500** (corrige bug D3.5: la vista mapa pedía 500 y recibía 422).
- **D4.5 — Bulk nunca borra**: `POST /leads/bulk` implementa `set_status|archive|unarchive|add_tag|remove_tag|assign_owner|clear_owner`; "archivar" → `ARCHIVED`, "desarchivar" → `NEW` (regla de producto: nada se elimina). `POST /leads/bulk-proposals` genera propuestas en `READY_FOR_REVIEW` y captura errores por lead en `skipped[]` sin abortar el lote (el envío sigue requiriendo aprobación humana, guardrail intacto).
- **D4.6 — Timeline 100% real**: `GET /leads/{id}/activity` arma el historial sólo desde filas existentes: `lead.created_at`, `WebsiteAudit` (crawl), `Proposal` (updated_at), `EmailEvent` (vía `Email.lead_id`). Sin eventos sintéticos — si no hay prueba, no hay ítem.
- **D4.7 — Fix tz naive/aware (bug pre-F4 descubierto en E2E)**: SQLite devuelve `DateTime` naives y la app crea datetimes aware → `can't compare offset-naive …` mataba searches tras calificar leads. Se agrega `as_utc()` a `app/utils/text.py` y se normaliza al leer (`website_service.reusable_audit`, rotación round-robin del queue). Test de humo E2E grid cubierto por el pipeline existente; la comparación puntual queda cubierta indirectamente por `tests/test_grid_pipeline.py`.
- **D4.8 — Detalle de lead F4 incremental**: la página `/leads/[id]` conserva su bloque de evidencia (crawl/audit, score breakdown, oportunidades) y suma: ownership+tags editables inline (vía `/leads/bulk` con 1 id), botón "Re-auditar website" (endpoint pre-existente), propuestas del lead (`/api/proposals?lead_id=`) y el timeline. Página de leads: selección por checkbox (barra flotante), visibilidad de columnas persistida en la vista, headers ordenables server-side, filtros extendidos (ciudad/categoría/tag/responsable) y vistas backend con migración local→cuenta.

## Fase 5 — Website audit con evidencia + screenshots (2026-10-14)

- **D5.1 — Findings persistidos**: los findings completos del auditor (problema, evidencia, `source_url`, `kind` FACT/INFERENCE, dimensión, impacto) quedan en `website_audits.findings` (JSON). Antes se derivaban on-the-fly y se perdía la clasificación; hoy la UI distingue hecho observado de inferencia por ausencia. Migración `b5c9e2d41f07` con `server_default="[]"` para retrocompatibilidad — **audits viejos quedan con lista vacía y la UI los respeta sin ingresar datos** (nada se backfilla inventado).
- **D5.2 — Screenshots con degradación honesta**: `settings.screenshot_provider` = `none` (default fuera de Docker) | `playwright`. Si falla la captura (sin browser, timeout, archivo >600KB), el audit queda **sin screenshot** y así se muestra — nunca una imagen sintética ni un dato inventado (regla de producto). El error se loguea como `screenshot_skipped`.
- **D5.3 — Playwright 1.49.0 + Chromium en la imagen Docker**: `backend/Dockerfile` corre `playwright install --with-deps chromium` en build y compose activa `SCREENSHOT_PROVIDER=playwright`. La librería va pineada en `requirements.txt` (peso aceptable dentro de la imagen única de backend; fuera de Docker el provider default es `none`, desarrolladores no necesitan Chromium).
- **D5.4 — Path nunca expuesto**: en `audit.screenshots` solo metadata + path relativo dentro de `settings.screenshots_dir`. El endpoint autenticado `GET /api/leads/{id}/audit/screenshots/{index}` (`FileResponse`, workspace scoping) es la única vía de descarga; `resolve_screenshot_path()` valida que el archivo resuelva dentro del root (defensa en profundidad anti path traversal). Storage local (docker volume implícito); no S3 — suficiente para single-workspace.
- **D5.5 — Hook en `analyze_lead` tras `persist_audit`**: una captura `home-fold` 1280×800 jpeg q80 por audit NUEVO (audits reutilizados por cache conservan los suyos; no se re-captura ni se reescribe evidencia contéstica). Timeout 12s + 1.2s de settle tras `domcontentloaded`.
- **D5.6 — Fix transversal: re-ejecución de búsquedas no viola `uq(search_leads)`**: `_stage_filter_ingest` precarga los pares `(search_id, lead_id)` ya linkeados en corridas anteriores interrumpidas — re-correr una búsqueda FAILED/PENDING queda idempotente. Encontrado en el E2E F5 (re-run de la search 5), no era F5 en origen pero bloqueaba la verificación.
- **D5.7 — UI evidencia**: detalle de lead suma (a) card "Captura del sitio" con blob autenticado y caption fecha/URL, (b) card "Findings" con chips FACT (verde) / INFERENCE (ámbar) + dimensión + evidencia + link a la página fuente. Copy es-AR, estilo F4 (gold/sand).

## Fase 6 — Scoring configurable y explicable (2026-10-14)

- **D6.1 — Config por workspace, opt-in**: la fila `scoring_configs` es opcional — sin fila se usan defaults (pesos 1.0, umbrales 80/60/40 iguales a los hardcodeados pre-F6). Comportamiento por defecto INVARIADO (suite verde sin tocar fixtures). DELETE vuelve a defaults.
- **D6.2 — Pesos por categoría, no por regla**: las reglas se agrupan en 7 categorías (`reputation`, `reviews`, `website_presence`, `website_quality`, `opportunities`, `phone`, `email`) con multiplicador 0–3 (default 1.0). Ajustar por regla individual sería demasiado granular; la categoría es la unidad explicable. El breakdown registra `base_delta`, `weight`, `category` y `delta` final — el cálculo completo queda transparente en cada lead.
- **D6.3 — Umbrales HOT/WARM/COLD configurables** con validación estricta `hot > warm > cold` (422 otherwise). LOW queda implícita debajo de COLD. Priority (P1–P4) y `recommended_action` quedan FIJOS (no configurables) — son derivados del negocio, no preferencias.
- **D6.4 — Rescore siempre explícito**: guardar la config no toca ningún lead. El usuario dispara `POST /scoring-config/rescore` (todos o por ids, cap 500, excluye ARCHIVED). El cálculo es determinista y local: no llama Places, no cobra, no modifica datos observados — solo reagrega. UI lo deja explícito con confirmación y copy claro.
- **D6.5 — Sin history de configs en F6**: se loggea `scoring_config_updated` (JSON línea) por auditoría básica; un historial relacional de cambios sería over-engineering para single-workspace.
- **D6.6 — Hotfix transversal**: `node_modules` y `.venv` no persisten entre snapshots del sandbox (están excluidos); reinstalación registrada (`npm ci`, `python -m venv`).
