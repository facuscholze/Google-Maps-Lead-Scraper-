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
