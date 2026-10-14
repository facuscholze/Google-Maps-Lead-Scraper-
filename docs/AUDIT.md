# Auditoría — AvaScho Lead Intelligence (Fase 0)

> Fecha: 2026-10-14 · Auditor: equipo de rediseño · Alcance: repo completo
> (`facuscholze/Google-Maps-Lead-Scraper-`, commit base `577b962`).
> Este documento es el entregable de la Fase 0. **No se escribió código de producto.**

---

## 0. Estado verificado empíricamente (no solo leído)

| Verificación | Comando | Resultado |
|---|---|---|
| Tests backend | `cd backend && rm -f test_avascho.db && .venv/bin/python -m pytest tests/ -q` | **92 tests: 91 pasan · 1 FALLA** (`test_packaged_template_matches_source`) |
| Type-check frontend | `cd frontend && npx tsc --noEmit` | ✅ Sin errores |
| Build frontend | `cd frontend && npm run build` | ✅ Compila (11 rutas, First Load JS ~105–144 kB) |
| Tests online | — | Ninguno: todo mockeado ✅ (regla no negociable respetada) |

> La documentación dice "83 tests" (README.md:120, LEVANTAR.md): desactualizada.

---

## 1. Mapa de arquitectura actual

### 1.1 Módulos backend (`backend/app/`)

```
app/
├── main.py                    App factory + lifespan (init_db + seed en no-producción)
├── core/
│   ├── config.py              Settings (pydantic-settings), singleton `settings`
│   ├── database.py            Engine SQLAlchemy + init_db()
│   ├── enums.py               Estados como strings (SearchStatus, JobType, LeadStatus...)
│   ├── security.py            PBKDF2 passwords, JWT HS256 (12 h, sin refresh), Fernet
│   ├── middleware.py          CORS + security headers + rate limit 120 req/min por IP
│   └── seed.py                Usuario demo
├── models/                    Workspace/User · Lead · Search/SearchLead/SearchPreset
│                              WebsiteAudit/WebsitePage · EmailAccount/Proposal/Email/
│                              EmailEvent/SuppressionEntry · Job
├── api/                       routes_auth, searches, leads, proposals, emails,
│                              email_accounts, jobs, suppression, dashboard, health
├── repositories/              Acceso a datos por agregado (scoping por workspace)
├── services/
│   ├── pipeline.py            Orquestador: 6 stages como Jobs tracked
│   ├── query_builder.py       Normaliza "rubro + ubicación" (anti-duplicación)
│   ├── place_mapper.py        Places JSON → dict de Lead + filtros de search
│   ├── field_mask.py          Field mask centralizado (una sola definición) ✅
│   ├── website_service.py     crawl → extract → audit → persist (caché 7 días)
│   ├── analysis/              auditor.py (10 dimensiones, reglas) · scorer.py (0–100
│   │                          explicable con breakdown) · types.py
│   ├── catalog.py             3 servicios web + 4 reglas de oportunidad
│   ├── lead_service.py        score_lead() persiste score/breakdown en Lead
│   ├── dashboard_service.py   Agregaciones del panel
│   ├── google_sheets_service.py  Export a Sheets (service account)
│   └── emailing/
│       ├── proposal.py        ProposalWriter (plantillas rule_based)
│       ├── proposal_service.py  generate/update/approve/discard
│       ├── email_html.py      Render server-side del HTML de marca (escapado ✅)
│       ├── queue.py           Cola: aprobación obligatoria, supresión, límites,
│       │                      horarios, delays aleatorios, mock sender
│       └── templates/innblock.html   Copia empaquetada de la plantilla de mail
├── integrations/
│   ├── google/                client.py (httpx + tenacity, paginación, field mask)
│   │                          places.py (facade: google | mock | auto)
│   ├── crawler/               crawler.py (httpx, robots.txt, caps, virtual mock host)
│   │                          extractor.py (emails/teléfonos/WA/social/CTA/tech)
│   ├── gmail/                 oauth.py (flow, tokens) + sender.py (raw RFC-822 + mock)
│   ├── ai/                    rule_based (offline determinístico) | openai_compatible
│   └── mock_fixtures.py       Places y sitios sintéticos determinísticos
└── workers/                   celery_app + tasks (solo si EXECUTION_MODE=celery)
```

### 1.2 Flujo de datos (búsqueda)

```
POST /searches → Search(PENDING)
POST /searches/{id}/run
  └─ inline: BackgroundTasks → SearchPipeline.run()
     stages (cada uno = fila Job con progreso):
       1 GOOGLE_PLACES   searchText(query) hasta max_results (paginación nextPageToken)
       2 FILTER          map_place → filtros → upsert Lead (dedupe workspace+place_id) + SearchLead
       3 WEBSITE_CRAWL   por lead con web: crawler educado (robots, delay, caps)
       4 WEBSITE_ANALYSIS extractor → auditor (subscores+evidencia) → WebsiteAudit
       5 LEAD_SCORING    score_lead() → lead_score/opportunity_score/breakdown
       6 CONTACT_DISCOVERY  marca LOW-confidence como REVIEW_FIRST
  └─ celery: run_search_task → … (ver BUG-08: ¡saltea los stages 3–6!)

UI: polling GET /searches/{id}/status cada 2 s (jobs) · dashboard cada 15 s
```

### 1.3 Flujo de propuesta y envío

```
POST /leads/{id}/generate-proposal → ProposalService.generate()
  contexto (solo evidencia real) → AI provider (rule_based | openai)
  → Proposal(READY_FOR_REVIEW) con fields editables + body_html render
    (templates/innblock.html, variables {{apertura}}/{{observacion}}/… escapadas)
PUT /proposals/{id}        edición humana → re-render server-side
POST /proposals/{id}/approve  → APPROVED (aprobación humana ✅ regla respetada)
POST /proposals/{id}/send     → EmailQueueService.queue_for_lead()
  valida: lead no suprimido · email existe · confianza ≠ LOW · propuesta APPROVED
  → Email(QUEUED, scheduled_at = ahora + delay aleatorio 90–420 s)
process_email_queue (cada 30 s en celery; bajo demanda en inline)
  → send_due(): horario laboral + días + límite diario por cuenta
  → mock (demo) o Gmail API (OAuth, tokens Fernet-encrypted ✅)
```

### 1.4 Jobs y progreso

- Progreso persistido en tabla `jobs` (type/status/progress/current_step); la UI hace
  **polling**, no hay SSE/WebSocket.
- `EXECUTION_MODE=inline` corre el pipeline en un thread del proceso API.
- Cola de mails: scheduler manual; en celery hay beat cada 30 s. En compose solo corre
  `inline` y **no hay proceso schedulando `send_due`** salvo el "send_now" del endpoint.

### 1.5 Frontend (`frontend/`)

- Next.js 15 App Router, React 19, Tailwind 3, TanStack Query 5 + Table 8.
- Tema claro "sand/gold" (`#F4F1EA`, gold `#B08D3E`, Cormorant Garamond) — **no es la
  identidad innblock** (rojo/negro) que exige el rediseño.
- Páginas: dashboard, searches (lista/detalle/new), leads (lista/detalle), proposals
  (lista/detalle con preview desktop/mobile/html/plain), settings (cuentas Gmail +
  supresión), login.
- Proxy propio `app/api/[[...path]]/route.ts` (lee `API_URL` en runtime ✅ bien
  documentado), JWT en `localStorage` (`avascho_token`).
- Sin mapa, sin kanban, sin acciones masivas, sin skeletons, sin toasts, sin i18n,
  filtros no sincronizados con la URL (salvo `search_id`).

---

## 2. Deuda técnica y bugs detectados

Severidad: 🔴 rompe funcionalidad/tests · 🟠 comportamiento incorrecto · 🟡 deuda.

### 2.1 Bugs

| # | Sev. | Archivo:línea | Hallazgo |
|---|---|---|---|
| BUG-01 | 🔴 | `backend/tests/test_innblock_web_proposals.py:21` y `backend/scripts/sync_proposal_template.py:8` | Ambos leen `nuevo html innblock.html` (raíz) que **no existe**. El test falla (verificado) y el script de sync está roto. El archivo real es `nuevo html mail.html`. |
| BUG-02 | 🔴 | `backend/app/services/pipeline.py:53-58` | En `EXECUTION_MODE=celery` el pipeline **saltea los stages 3–6** (crawl, análisis, scoring, contact discovery) y marca la búsqueda COMPLETED igual. El modo celery deja leads crudos sin auditar ni puntuar. |
| BUG-03 | 🟠 | `backend/app/services/emailing/queue.py:54-58` + `config.py:100,123-131` | Off-by-one de días laborales: `WORKING_DAYS=1,2,3,4,5` documentado como "ISO weekday" (lun=1…dom=7) pero se compara contra `datetime.weekday()` (lun=0…dom=6) → los defaults cubren **martes a sábado**, no lunes a viernes. |
| BUG-04 | 🟠 | `backend/app/schemas/api.py:30` + `frontend/app/searches/new/page.tsx:113` | `max_results` admite hasta 500 y la UI ofrece 250/500, pero **searchText (New) devuelve máx. 60 resultados en total** (ver §4.1). La búsqueda jamás entrega lo prometido; el estimador (`routes_searches.py:38-46`, `ceil(max_results/20)`) sobrestima llamadas para >60 y no avisa el tope. |
| BUG-05 | 🟠 | `frontend/app/page.tsx:104` | `idx >= funnel.potential_clients === false` compara un índice con un booleano: la clase del embudo siempre resuelve igual (`bg-ink/80`). Bug visual silente. |
| BUG-06 | 🟠 | `backend/app/services/pipeline.py:106` | `map_place(p)` se ejecuta dos veces por candidato (dentro de la condición y del append). Trabajo duplicado (menor, pero en barridos grandes suma). |
| BUG-07 | 🟠 | `backend/app/integrations/crawler/crawler.py:84-95,168` | `RobotFileParser.read()` es **red sincrónica dentro de código async** y `time.sleep()` bloquea el event loop del crawler async. Funciona porque corre en threads, pero es frágil y bloqueante. |
| BUG-08 | 🟡 | `backend/app/services/emailing/queue.py:236-243` | Cuenta Gmail real **sin token** cae silenciosamente al mock sender si `ALLOW_MOCK_EMAIL_SENDING=true`: un usuario puede creer que envió mails reales que no salieron. Hay que hacerlo explícito en UI/logs. |
| BUG-09 | 🟡 | Compose + `routes_proposals.py:147-155` | En modo inline (default) **nada corre `send_due()` periódicamente**: los mails QUEUED con `send_now=false` solo salen si otro envío dispara `_dispatch_now`. Falta scheduler de cola fuera de celery. |
| BUG-10 | 🟡 | `backend/dev.db` | Base SQLite **commiteada en git**. Debe salir del índice y agregarse a `.gitignore`. |

### 2.2 Deuda técnica (no rompe hoy, frena mañana)

| # | Archivo / zona | Deuda |
|---|---|---|
| DEB-01 | Raíz + `backend/` | Dos `.env.example` **divergentes** (el de raíz no trae Sheets; el de backend no trae crawler limits ni `PROPOSAL_*`). Fuente única necesaria. |
| DEB-02 | `README.md:147-170` | Documenta `nuevo html innblock.html` (inexistente) y 83 tests (son 92). |
| DEB-03 | Master prompt vs repo | `instalar_mail_web.py` **no existe** en el repo (el prompt lo lista como parte del estado actual). Se constata ausencia; no hay nada que auditar ahí. |
| DEB-04 | `integrations/gmail/` | Scope `gmail.readonly` se pide pero **no hay sincronización de rebotes/respuestas** (ni baja por respuesta "BAJA", prometida en el pie del mail). |
| DEB-05 | `core/security.py` | JWT de 12 h sin refresh token ni revocación; `localStorage` (XSS-lootable). Aceptable para single-user; a endurecer en Fase 10. |
| DEB-06 | `core/middleware.py:41-61` | Rate limit 120 req/min por IP, pero **todo el tráfico llega desde la IP del proxy Next** (no se propaga `X-Forwarded-For`): es un límite global, no por usuario. |
| DEB-07 | `api/routes_proposals.py:27-37`, `api/routes_emails.py:17-26` | Listados **sin paginar** (proposals y emails completos en memoria). |
| DEB-08 | `repositories/leads.py:24-46` | Paginación por offset, sin cursor; sin FTS (`pg_trgm`/`tsvector`); índices simples, faltan compuestos para los filtros combinados del rediseño. |
| DEB-09 | `models/lead.py:78` + `models/search.py:61-69` | `Lead.matched` siempre `True` (redundante con `SearchLead.matched`). |
| DEB-10 | `services/website_service.py` | La "performance" del auditor mide alt de imágenes/HTTPS/CMS, **no mide TTFB, peso, ni captura screenshots**; no hay validación MX de emails; emails LOW quedan pero nunca se MEJORAN a MEDIUM/HIGH por validación. |
| DEB-11 | `.env.example` / compose | `EXECUTION_MODE=celery` existe pero compose **no incluye servicio redis ni worker**: el modo documentado no se puede levantar con `docker compose up`. |
| DEB-12 | `frontend/app/leads/[id]/page.tsx`, `proposals/[id]/page.tsx` | `window.location.href` para navegar (full reload) en vez de `next/link`; sin estados de errorBoundary. |
| DEB-13 | General backend | Errores de API parcialmente en inglés y parcialmente en español; sin envelope tipado de errores. |

### 2.3 Lo que ya está **bien** (no tocar)

- Field mask **centralizado** y comentado (`services/field_mask.py`) — base correcta para el estimador de costos.
- Render del mail 100% server-side, con escape HTML y validación de links (`email_html.py`) — cumple "cero datos inventados / seguridad".
- Guardarraíles de envío: aprobación humana `APPROVED`, supresión chequeada al encolar **y al enviar**, confianza LOW nunca se encola, límites/horarios/delays aleatorios ✅.
- Crawler educado: robots.txt, caps de páginas/tamaño/redirects, delay, UA identificable.
- Scorer explicable con `score_breakdown` persistido (base ideal para la UI "por qué este score").
- Suite de tests offline con providers mock determinísticos.

---

## 3. Problemas de UX/UI actuales

| # | Problema | Impacto |
|---|---|---|
| UX-01 | **No hay mapa en ninguna pantalla** (ni en búsqueda ni en leads). | El diferencial central del producto (descubrir por zona) no existe. |
| UX-02 | Nueva búsqueda: solo rubro+ubicación de texto; sin grilla, área dibujada, matriz multi-rubro, presupuesto ni progreso real (solo barra por job). | Modo de búsqueda único y ciego en costos. |
| UX-03 | Filtros de leads: 6 controles básicos, **no persisten en URL**, sin chips ni vistas guardadas; tabla no virtualizada; sin selección múltiple ni acciones masivas; sin export de columnas elegidas. | Trabajo repetitivo en la tarea más frecuente. |
| UX-04 | Detalle de lead sin timeline, sin evidencia visual (capturas), sin notas; navegación con full-reload (`window.location`). | Contexto pobre para decidir/aprobar. |
| UX-05 | Editor de propuestas: no hay lado-a-lado, ni variantes de asunto/enfoque, ni indicadores de spam/longitud, ni envío de mail de prueba. Preview PC/móvil existe ✅ (iframe 390px) pero sin modo oscuro ni text-plain contiguo. | Revisión más lenta y menos segura. |
| UX-06 | Dashboard sin uso/costo de API, sin cola de acciones accionable con un tap, y labels mezclados en inglés ("Potential clients", "Average Lead Score"). | Panel poco accionable; i18n inconsistente. |
| UX-07 | Mobile: nav = tira horizontal scrolleable arriba (no bottom-tab), header fijo ocupa mucho alto, tarjetas ok pero filtros apretados; sin bottom sheets. | Flujo difícil de operar desde el celular (pillar del rediseño). |
| UX-08 | Carga = spinner genérico (sin skeletons), errores = cartel plano, **sin toasts ni undo** en acciones destructivas, sin actualizaciones optimistas. | Velocidad percibida baja. |
| UX-09 | Tema claro sand/gold no refleja la marca; sin modo oscuro; contraste de chips de temperatura irregular en móvil. | Identidad innblock ausente en el producto. |
| UX-10 | Settings mezcla cuentas Gmail + supresión; no existe configuración de ICP, pesos de scoring, marca/firma, plantillas, IA ni límites por cuenta. | El producto no es configurable donde importa. |
| UX-11 | Accesibilidad: chips/filtros con targets < 44 px, foco por defecto sin estilo propio, contraste `taupe on sand` < AA en textos chicos. | AA no alcanzado hoy. |

---

## 4. Costos de API — Google Places (New)

Fuentes oficiales verificadas el 2026-10-14:

- **Paginación y tope**: `pageSize` máx. **20** por request; `nextPageToken` para páginas
  siguientes; **máximo 60 resultados en total por consulta** ("subject to change").
  [Doc oficial Text Search (New)](https://developers.google.com/maps/documentation/places/web-service/text-search)
- **Facturación por field mask**: "You are billed at the highest SKU applicable to your
  request". [Usage and Billing (oficial)](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing)
- **Campos actuales del repo** (`services/field_mask.py:9-24`): `places.id`,
  `displayName`, `formattedAddress`, `location`, `googleMapsUri`, `types`,
  `primaryType`, `primaryTypeDisplayName`, `businessStatus`, `nextPageToken`
  → tier **Pro**; **pero** `websiteUri`, `nationalPhoneNumber`,
  `internationalPhoneNumber`, `rating`, `userRatingCount` → tier **Enterprise**
  (mapeo campo→SKU en la doc oficial de Text Search, sección "Required parameters").
- **Precio vigente** (lista global de precios; re-verificar en cada deploy porque Google
  actualiza): Text Search Pro **USD 32 / 1.000 llamadas** (5.000 gratis/mes) · Text
  Search Enterprise **USD 35 / 1.000** (1.000 gratis/mes).
  [Global pricing list (oficial)](https://developers.google.com/maps/billing-and-pricing/pricing#places-pricing)
- **Sesgo geográfico**: `locationBias` (círculo) y `locationRestriction` (rectángulo)
  existen en el request body de searchText — son la base oficial para el **área dibujada
  y la grilla**. [Referencia oficial searchText](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places/searchText)

### 4.1 Conclusiones de costo

1. **El field mask actual NO pide campos de más**: los 5 campos Enterprise se usan todos
   (rating/reseñas → scoring y filtros; website → auditoría; teléfonos → contactabilidad
   y filtro "solo con teléfono"). No hay recorte posible sin perder funcionalidad.
   → Cada llamada de búsqueda **factura como Enterprise (~USD 0,035)**.
2. **El tope de 60 resultados/query hace obligatoria la grilla** para "barrer una
   ciudad": N consultas con `locationRestriction` rectangular + dedupe por `place_id`
   (o `nearbySearch` con círculo). Hoy la app promete hasta 500 resultados con una sola
   cadena paginada (BUG-04).
3. **El "estimador" actual** (`ceil(max_results/20)`) no refleja ni el tope de 60 ni el
   precio por SKU. El estimador del rediseño debe calcular: `celdas × páginas_esperadas
   × precio_sku_vigente`, mostrarlo antes de ejecutar y respetar un **tope de
   presupuesto** configurable.
4. Cada búsqueda debe registrar en DB: llamadas realizadas, SKU cobrado, costo estimado
   → alimenta el panel "uso/costo de API".
5. `places.types` está en el tier ID-Only/Pro y ya se pide (barato); sirve para filtros
   por rubro sin costo extra. `priceLevel` es Enterprise y NO se pide hoy: evaluar como
   señal de presupuesto en Fase 2 (decisión registrada en `DECISIONS.md`).

---

## 5. Tabla MANTENER / MEJORAR / ELIMINAR / AGREGAR

### 5.1 MANTENER (tal cual)

| Ítem | Justificación (1 línea) |
|---|---|
| Pipeline estricto Places→…→HUMAN APPROVE→Send | Columna vertebral y regla no negociable. |
| `integrations/google/client.py` (httpx + retry + paginación) | Correcto contra la API oficial; solo falta grilla. |
| `services/field_mask.py` centralizado | Única fuente del field mask; habilita el estimador de costos. |
| Guardarraíles de envío (aprobación, supresión, límites, delays) | Reglas no negociables ya implementadas y testeadas. |
| Cifrado Fernet de tokens OAuth | Cumple "secretos solo en backend". |
| Renderer server-side del mail con escape (`email_html.py`) | Seguro y testeado; cambia solo la plantilla inyectada. |
| Crawler educado (robots, caps, UA) y extractor evidencia-based | Base sólida del motor de auditoría. |
| Scorer con breakdown + auditor con findings FACT/INFERENCE | La explicabilidad pedida ya existe en datos; falta la UI. |
| Providers mock determinísticos (places, sitios, gmail, IA) | Mantener **solo** para tests/demo (criterio Sección 12 del brief). |
| Proxy Next runtime `/api/*` (`route.ts`) | Resuelve bien el caso Docker; se conserva. |
| Tests offline con SQLite | Regla del proyecto; se amplía cobertura. |

### 5.2 MEJORAR

| Ítem | Justificación |
|---|---|
| **Plantilla de mail** → adoptar `nuevo html mail.html` como única fuente (ver §6) | Es la marca actual (Estudio, rojo/negro); hoy el sistema renderiza la variante vieja. |
| Cola/jobs: estados `queued/running/paused/failed/done`, cancelación, scheduler de envíos también en inline, SSE en vez de polling | BUG-02/09; progreso en vivo es requisito central. |
| Auditoría web: + TTFB/peso/redirects reales, screenshot desktop/móvil (Playwright), MX check de emails, TLS, sitemap/robots, PageSpeed opcional | Evidencia verificable es regla; hoy no hay capturas ni métricas reales. |
| Extracción de emails: ranking de calidad (genéricos, ``noreply``, dominio propio), fuente/confianza, verificación MX | Mejora directa de entregabilidad. |
| Scoring: pesos configurables por workspace + perfiles por servicio (web nueva, rediseño, SEO, WhatsApp bot, automatización) | Hoy pesos hardcodeados; editable es requisito. |
| Filtros de leads: ~30 filtros combinables, chips, URL-sync, vistas guardadas, orden múltiple | La lista completa está en brief §6.1; hoy hay 6. |
| Listados: paginación cursor + FTS (`pg_trgm`) + índices compuestos | Escala y búsqueda libre decente. |
| `.env.example` único + README/LEVANTAR actualizados | DEB-01/02; onboarding roto hoy por docs. |
| Auth: refresh tokens, expiración corta, propagar IP real al rate limiter | DEB-05/06; endurecimiento Fase 10. |
| Fix bugs BUG-01…BUG-10 | Listados en §2 con severidad. |

### 5.3 ELIMINAR / SIMPLIFICAR

| Ítem | Justificación |
|---|---|
| Tema sand/gold + Cormorant Garamond del frontend | Identidad incorrecta; va el sistema innblock oscuro (tokens del mail). |
| `backend/dev.db` del índice git | Datos locales no pertenecen al repo (BUG-10). |
| Referencias a `nuevo html innblock.html` (test, script de sync, README) | Archivo inexistente; una sola fuente: `nuevo html mail.html`. |
| `Lead.matched` (columna) | Redundante con `SearchLead.matched`; migración reversible. |
| Selector `max_results` 250/500 por consulta simple | Imposible por el tope de 60 (BUG-04); lo reemplaza la grilla. |
| Modo `auto` con fallback silencioso a mock en producción | Oculta errores de configuración; mock solo explícito en dev/test. |
| Polling de 2 s/15 s en la UI | Reemplazado por SSE (+ polling como fallback). |

### 5.4 AGREGAR (priorizado impacto/esfuerzo)

| Prioridad | Ítem |
|---|---|
| 🔥 Alta | Búsqueda por mapa + grilla con dedupe y progreso por celda · estimador de costo con tope de presupuesto · filtros de presencia digital · vistas guardadas · vista mapa/tarjetas de leads · capturas de evidencia · preview PC/celular del mail nuevo + mail de prueba · sync de rebotes/respuestas (baja automática) · bottom-tab móvil + sidebar colapsable + tema oscuro innblock · contador de uso/costo de API por búsqueda · búsquedas recurrentes "solo nuevos". |
| Medio | Kanban drag&drop · notas/recordatorios · etiquetas y listas · XLSX con columnas elegidas · multi-rubro × multi-zona (matriz) · plantillas por rubro · keywords relacionadas aprobables · ⌘K y atajos · secuencias de seguimiento (máx. 2–3, con aprobación) · calentamiento de cuota · benchmark zona (solo con datos reales). |
| Evaluar | PDF de auditoría 1 página marca innblock · panel de rendimiento (tasa respuesta por rubro/asunto) · A/B de asuntos · webhooks n8n · sync Google Sheets bidireccional · WhatsApp manual asistido (`wa.me` precargado, envío humano) · modo campaña. |

---

## 6. La plantilla de mail — análisis de `nuevo html mail.html`

**Hallazgo clave (decisión ya tomada en `DECISIONS.md`):**

- `nuevo html mail.html` (raíz, 22 KB) es un **editor/generador** con la plantilla real
  dentro de `<script type="text/plain" id="plantilla">` y un bloque `<script>CONFIG`
  con variables. Colores de marca: **rojo `#d90000`**, **negro `#070707`**,
  acento claro `#ff3b30`; tipografías Archivo / Instrument Serif / Martian Mono;
  marca "Estudio", firma con socios (Facundo Scholze, Yamall Avalos), pie con
  "respondé BAJA".
- La copia activa del sistema (`backend/.../templates/innblock.html`) es una **variante
  anterior** ("Innblock — Landing pages y sitios web") con **otros slots**
  (`{{apertura}}`, `{{observacion}}`, `{{oportunidades}}`, …) que el renderer actual
  rellena. El archivo raíz y el empaquetado **no comparten variables** → adoptar el
  nuevo exige mapear la personalización a su estructura SIN tocar su estética.
- Ya es técnicamente sano: layout con tablas + estilos inline, `role="presentation"`,
  `@media (max-width:480px)` apila columnas, `prefers-reduced-motion`, viewport meta.
- Gaps a robustecer (sin cambiar su aspecto): ancho fluido en móvil (hoy tabla fija
  600 px con `width="600"` — añadir `width:100%;max-width:600px` ya lo tiene en style,
  validar en clientes), botón CTA sin VML para Outlook, fuentes externas sin
  `mso` fallback explícito, **sin meta `color-scheme`** (riesgo de inversión en modo
  oscuro), opt-out manual por respuesta "BAJA" (a complementar con link de baja +
  endpoint webhook de supresión), texto plano multipart ya se genera ✅ pero desde la
  plantilla vieja.

**Tests de mail que agrega la Fase 7:** render con datos largos/cortos, ausencia de
`{{` residual, peso < 100 KB, capturas Playwright 375/1280 en `docs/email-previews/`.

---

## 7. Plan por fases (con esfuerzo y riesgos)

Esfuerzo relativo: **S** < 1 día · **M** 1–3 días · **L** > 3 días. Riesgo = probabilidad
de bloqueo o regresión.

| Fase | Entregable | Esfuerzo | Riesgo principal |
|---|---|---|---|
| 0 | Este documento + `DECISIONS.md` + `CHANGELOG.md` | S | — (espera tu aprobación) |
| 1 | Fundaciones frontend: tokens innblock (rojo/negro, oscuro default), shadcn/ui+Radix instalado, shell nuevo (sidebar colapsable / bottom-tab), navegación completa, tema claro opcional, skeletons/toasts base, i18n es-AR, cliente API tipado desde OpenAPI | M | Migración de tema sin romper páginas existentes (se hace por capas; páginas viejas conviven hasta su fase) |
| 2 | Backend búsqueda: fix BUG-01/02/03/04/10, jobs con estados completos, cola Celery+Redis en compose, grilla (rectángulos → searchText con `locationRestriction`), dedupe place_id + heurística teléfono/dominio, estimador de costo con precios SKU + tope de presupuesto, SSE `/searches/{id}/events`, costo por búsqueda en DB, propagación `X-Forwarded-For` | L | Descuadre del estimador vs. facturación real (mitigación: margen 20 % y doc de precios versionada) |
| 3 | Pantalla **Descubrir**: mapa grande (Leaflet + OSM, decisión en `DECISIONS.md`), dibujar área (círculo/rectángulo/polígono→celdas), autocompletado de zonas, matriz multi-rubro×multi-zona, keywords relacionadas, plantillas por rubro, búsquedas guardadas/recurrentes, vista previa de costo, progreso en vivo con clusters | L | Complejidad de dibujo de área en móvil (mitigación: fallback a radio simple + centro) |
| 4 | **Leads**: ~30 filtros combinables+URL (`nuqs`), chips, vistas guardadas, tabla virtualizada con selección masiva y acciones, tarjetas, mapa con clusters y heatmap, kanban DnD, detalle con timeline/notas, export CSV/XLSX por columnas, undo en destructivas | L | Volumen de filtros nuevos requiere backfill de columnas/índices (migraciones cuidadosas) |
| 5 | Auditoría v2: timing TTFB/peso, screenshots Playwright (servicio aparte en compose), MX validation, detección tech/CMS ampliada, caché TTL configurable, hallazgo = `{tipo, severidad, evidencia, url, ts}` persistido y visible | L | Playwright en contenedor puede ser pesado/inestable en Windows (mitigación: servicio opcional con degradación a "sin captura") |
| 6 | Scoring configurable: pesos por workspace + perfiles por servicio, recálculo background, UI de desglose con barras, prioridad 🔥 configurable | M | Cambiar pesos dispara recálculos masivos (job con progreso; no bloquear UI) |
| 7 | **Mail**: `nuevo html mail.html` → plantilla del sistema (variables nuevas mapeadas, estética intacta, backup del original), inliner CSS, botones VML, color-scheme, texto plano, opt-out link + endpoint, preview PC/celular + mail de prueba, tests de render + capturas 375/1280 | M | Clientes de mail impredecibles (mitigación: suite de regresión visual + clientes prioritarios documentados) |
| 8 | Propuestas: IA solo-evidencia con citas internas, variantes de asunto/enfoque, editor lado-a-lado con indicadores, flujo completo aprobación→cola, sync rebotes/respuestas Gmail (actualiza lead + frena secuencias), secuencias máx. 2–3 con aprobación, registro de actividad | L | Gmail history sync puede ser complejo (mitigación: polling incremental por cuenta + tests con fixtures) |
| 9 | Panel/Inicio: KPIs reales, embudo, cola de acciones, uso/costo API; extras priorizados (⌘K, atajos, panel rendimiento básico) | M | Métricas con poco volumen real → umbrales "datos insuficientes" |
| 10 | Endurecimiento: auth refresh+revocación, rate limit real con IP, errores tipados, logging estructurado, CI (lint+tsc+pytest+build), Lighthouse ≥90 móvil en pantallas clave, README/LEVANTAR/Makefile, limpieza final Sección 12 | M | Caza de regresiones finales |

**Orden de dependencias:** 1→(3,4,7 son frontend pesado y dependen del shell) ;
2→3 (grilla) ; 5→6 (scoring consume hallazgos) ; 7→8 (el mail define el render de
propuestas) ; 9 consume todo lo anterior.

---

## 8. Preguntas NO bloqueantes (ya decididas en `DECISIONS.md`, revertibles)

1. Variable "Evidencia" del mail nuevo: el bloque negro de estadísticas es de marca
   (fijo). La evidencia del lead viaja en la intro personalizada (`{{intro}}`,
   `{{observacion}}`) manteniendo tipografías/estructura. ✅ decidido, se valida en Fase 7.
2. Mapa: **Leaflet + OpenStreetMap** (sin API key, sin SKU extra) como default;
   Google Maps JS queda como opción configurable. ✅ decidido.
3. Grilla: implementada sobre **searchText + `locationRestriction` rectangular**
   (círculos/polígonos se aproximan por celdas rectangulares con dedupe).
4. Behance de "solo nuevos" en recurrentes: dedupe por `place_id` existente en DB.

---

## 9. Anexos

### 9.1 Comandos de verificación usados

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
rm -f test_avascho.db && .venv/bin/python -m pytest tests/ -q   # 91 passed, 1 failed
cd frontend && npm install && npx tsc --noEmit && npm run build  # OK
```

### 9.2 Links oficiales citados

- Text Search (New): https://developers.google.com/maps/documentation/places/web-service/text-search
- Referencia searchText (request body): https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places/searchText
- Usage and Billing (field mask → SKU más alto): https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
- Global pricing list (re-verificar en cada deploy): https://developers.google.com/maps/billing-and-pricing/pricing#places-pricing
