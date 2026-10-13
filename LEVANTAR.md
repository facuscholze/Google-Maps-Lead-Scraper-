# Cómo levantar el proyecto — paso a paso

Guía práctica para correr **AvaScho Lead Intelligence** (FastAPI + Next.js 15).
Hay tres caminos; elegí uno. La **Opción A (Docker)** es la más corta si tenés
Docker; la **Opción B (SQLite)** es la que no necesita instalar ni Docker ni
Postgres (es la que está corriendo ahora mismo en este entorno).

---

## Requisitos

| Camino | Necesitás |
| --- | --- |
| A — Docker | Docker + Docker Compose |
| B — SQLite (rápido) | Python 3.11+ y Node 20+ |
| C — Postgres local | Python 3.11+, Node 20+, PostgreSQL 14+ |

Credenciales de las claves que vas a necesitar (generalas una vez):

```bash
# SECRET_KEY (firma de JWT)
python3 -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY (Fernet: cifra los tokens OAuth de Gmail en la base)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> Las claves **solo** van en `backend/.env`. Ese archivo está en `.gitignore`,
> nunca se commitea y nunca llega al navegador.

---

## Opción A — Docker (todo el stack)

```bash
# 1) Crear el .env del backend a partir del ejemplo
cp backend/.env.example backend/.env

# 2) Editar backend/.env y completar como mínimo:
#    SECRET_KEY=<hex de 32 bytes>
#    ENCRYPTION_KEY=<clave Fernet>
#    (opcional) GOOGLE_MAPS_API_KEY=<tu Places API key>

# 3) Levantar los 3 servicios (postgres + backend + frontend)
docker compose up --build
```

Queda disponible en:

- Frontend / UI → <http://localhost:3000>
- API + Swagger → <http://localhost:8000/api/docs>
- Postgres → `localhost:5432` (usuario/clave/base: `avascho`)

Al arrancar, el contenedor del backend ejecuta `alembic upgrade head` solo.
Para bajar todo: `docker compose down` (agregá `-v` si querés borrar la base).

---

## Opción B — Local con SQLite (sin Docker ni Postgres)

Ideal para probar rápido. Todo el pipeline funciona offline con datos mock.

### 1. Backend

```bash
cd backend

# Entorno virtual + dependencias
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configuración
cp .env.example .env
```

Editá `backend/.env` y ajustá **estas 5 líneas**:

```ini
DATABASE_URL=sqlite:///./dev.db        # en vez de postgresql+psycopg2://...
SEARCH_PROVIDER=mock                   # sin API key de Google: usa el proveedor mock
SECRET_KEY=<hex de 32 bytes>
ENCRYPTION_KEY=<clave Fernet>
CORS_ORIGINS=*                         # si vas a entrar desde otra IP/puerto
```

Atajo equivalente por línea de comandos:

```bash
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=sqlite:///./dev.db|"          .env
sed -i "s|^SEARCH_PROVIDER=.*|SEARCH_PROVIDER=mock|"                  .env
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=*|"                           .env
printf '\nSECRET_KEY=%s\nENCRYPTION_KEY=%s\n' "$SECRET_KEY" "$ENCRYPTION_KEY" >> .env
```

Creá las tablas y el usuario demo (una sola vez):

```bash
# Opción 1: migraciones Alembic (recomendado, funciona igual en SQLite)
.venv/bin/alembic upgrade head

# Opción 2: dejar que la app cree las tablas sola al arrancar (modo development)
#           — no hace falta hacer nada, init_db() corre en el startup
```

Y levantá la API:

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
# equivalente si activaste el venv: uvicorn app.main:app --reload --port 8000
```

Verificá que responde:

```bash
curl http://localhost:8000/api/health
# {"status":"ok", ..., "google_places":"not_configured", ...}
```

Swagger: <http://localhost:8000/api/docs>

> Si vas a acceder desde otra máquina o desde un preview remoto, escuchá en
> todas las interfaces: `--host 0.0.0.0`.

### 2. Frontend

En **otra terminal**:

```bash
cd frontend
npm install

# Decirle a Next dónde está el backend (lo usa el rewrite de next.config.mjs)
echo "API_URL=http://localhost:8000" > .env.local

npm run dev
```

Abrí <http://localhost:3000>.

El browser **nunca** habla con el backend directo: Next hace de proxy
(`/api/*` → `API_URL/api/*`), así que no hay CORS ni secretos en el cliente.

### 3. Usuario demo

Se crea automáticamente al arrancar el backend (`AUTO_CREATE_DEMO_USER=true`):

| | |
| --- | --- |
| Email | valor de `DEMO_EMAIL` (por defecto `demo@avascho.com`) |
| Password | valor de `DEMO_PASSWORD` |

Ojo: `.env.example` trae `DEMO_PASSWORD=change-me-too`.
Si querés la clave `demo-avascho-2026` (el default del código), borrá o editá
esa línea en tu `.env`.

---

## Opción C — Local con PostgreSQL

Igual que la Opción B, pero antes de todo:

```bash
# 1) Crear base y usuario
psql -U postgres -c "CREATE USER avascho WITH PASSWORD 'avascho';"
psql -U postgres -c "CREATE DATABASE avascho OWNER avascho;"

# 2) En backend/.env dejar:
DATABASE_URL=postgresql+psycopg2://avascho:avascho@localhost:5432/avascho

# 3) Migrar y levantar
cd backend && .venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Si **no** tenés Postgres instalado, el repo trae un bootstrap que baja binarios
reales de PostgreSQL y crea las bases `avascho` y `avascho_test`:

```bash
cd backend
pip install pgserver
python scripts/devstack.py start     # deja el proceso vivo e imprime el DSN
python scripts/devstack.py status    # en otra terminal: ¿está arriba?
```

---

## Ya está arriba: qué hacer en la UI

1. **Login** en <http://localhost:3000/login> con el usuario demo.
2. **Searches → Nueva búsqueda**: categoría (`Dentistas`) + ubicación
   (`Córdoba, Argentina`), filtros de reseñas/rating y `max_results`.
   El botón *Preview* muestra la query final y el disclaimer de uso de la API.
3. **Ejecutar** la búsqueda: el pipeline corre solo —
   `Places → Lead → auditoría web → score → oportunidad → propuesta`.
   Con `SEARCH_PROVIDER=mock` no sale a internet y tarda ~1 segundo.
4. **Leads**: tabla con score y temperatura (*hot / warm / cold*), website
   auditado, email detectado, y export a CSV/XLSX (y a Google Sheets si está
   configurado).
5. **Proposals**: revisar y **editar** la propuesta generada.
6. **Aprobar** (`APPROVED`) → elegir cuenta + horario → **Enviar**.
   Con `ALLOW_MOCK_EMAIL_SENDING=true` el envío es simulado: queda registrado,
   no sale ningún mail. Para envío real hacen falta `GOOGLE_CLIENT_ID/SECRET`
   y conectar la cuenta de Gmail en *Settings*.

Reglas que la app no deja saltear: nada se envía sin aprobación humana, se
respeta la lista de supresión (`DO_NOT_CONTACT`), y los emails de confianza
`LOW` o inexistentes no se encolan.

---

## Tests (offline, solo mocks)

```bash
cd backend
. .venv/bin/activate
rm -f test_avascho.db          # la suite usa su propio SQLite; conviene arrancar limpio
python -m pytest tests/ -q     # 83 tests, sin llamadas de red

cd ../frontend
npx tsc --noEmit
npm run build
```

---

## Problemas comunes

| Síntoma | Causa / solución |
| --- | --- |
| `OperationalError: connection to server at "localhost" port 5432 failed` | `DATABASE_URL` apunta a Postgres y no hay Postgres. Cambiá a `sqlite:///./dev.db` o levantá Postgres (Opción C). |
| `pydantic ... field required` / `ENCRYPTION_KEY` vacía al guardar un token | Falta generar la clave Fernet en `backend/.env`. |
| Login responde 401 con las credenciales demo | El `.env` tiene otro `DEMO_PASSWORD`. Cambialo o mirá el log del backend: imprime `demo user ready: <email>`. |
| La UI carga pero todo `/api/*` da error de red | El backend no está en el puerto que dice `frontend/.env.local` (`API_URL`). Es solo la URL del proxy, no la del navegador. |
| Pantalla vacía / dashboard sin datos | No hay búsquedas todavía. Corré una desde *Searches*. |
| `429 Too many requests` | Hay un rate limit en memoria de 120 req/min por IP (`app/core/middleware.py`). Esperá un minuto. |
| Las búsquedas devuelven datos raros / de ejemplo | `SEARCH_PROVIDER=mock`. Poné `SEARCH_PROVIDER=auto` (o `google`) y cargá `GOOGLE_MAPS_API_KEY` — se usa la **Places API `searchText`** oficial, nunca scraping. |

---

## Variables que más vas a tocar (`backend/.env`)

| Variable | Para qué |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://…` en serio, `sqlite:///./dev.db` para pruebas |
| `SECRET_KEY`, `ENCRYPTION_KEY` | Firma de JWT y cifrado de tokens OAuth. **Obligatorias en producción.** |
| `SEARCH_PROVIDER` / `GOOGLE_MAPS_API_KEY` | `auto` \| `google` \| `mock` |
| `AI_PROVIDER` | `rule_based` (offline, determinístico) o `openai_compatible` |
| `ALLOW_MOCK_EMAIL_SENDING` | `true` = demo sin salida; `false` en producción |
| `DAILY_EMAIL_LIMIT`, `MIN/MAX_SEND_DELAY_SECONDS`, `ALLOWED_HOURS_*`, `WORKING_DAYS` | Guardrails del envío |
| `EXECUTION_MODE` | `inline` (pipeline en el proceso) o `celery` (+ `REDIS_URL`) |
| `AUTO_CREATE_DEMO_USER`, `DEMO_EMAIL`, `DEMO_PASSWORD` | Usuario de demo |

Más detalle del producto y la arquitectura: [`README.md`](README.md).
