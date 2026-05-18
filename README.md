# Dashboard

A task / kanban dashboard: a Django REST API backend and a React single-page
frontend, fully containerized with Docker Compose.

## Tech stack

**Backend** (`backend/`)
- Django 6.0 + Django REST Framework
- JWT auth via `djangorestframework-simplejwt` (with token blacklist)
- Django Channels + `channels-redis` for WebSocket notifications
- `django-filter` for list filtering
- Served by Uvicorn (ASGI), Postgres via PgBouncer, Redis for the Channels layer & cache
- `psycopg` 3, `markdown` + `nh3` (sanitized rich text)

**Frontend** (`frontend/`)
- React 18 + TypeScript + Vite
- Redux Toolkit / RTK Query
- React Router 6, `@dnd-kit` (drag-and-drop board), `react-select`, `react-toastify`
- Built to static assets and served by nginx (which also reverse-proxies the API)

## Architecture

```
                 :9005
  browser ───────────────▶  frontend (nginx)
                              ├─ /            → React SPA (static)
                              ├─ /static/, /media/ → shared volumes (read-only)
                              └─ /api/ /admin/ /ws/ → web (Uvicorn :8000)
                                                       │
                          web (Django/ASGI) ──────────┼── pgbouncer ── postgres
                                                       └── redis (Channels pub/sub + cache)
```

Compose services: `frontend`, `web`, `redis`, `postgres`, `pgbouncer`.
nginx (the `frontend` service) is the only publicly exposed entry point.

## Repository layout

```
.
├── backend/              Django project
│   ├── backend/          settings, urls, asgi/wsgi
│   ├── dashboard/        the app (models, views, serializers, migrations)
│   ├── Dockerfile
│   ├── entrypoint.sh     waits for DB → makemigrations → migrate → collectstatic → uvicorn
│   └── requirements.txt  pinned
├── frontend/             React + Vite app, multi-stage Dockerfile (build → nginx)
├── docker-compose.yml
├── .env.sample           template — copy to .env (the real .env is git-ignored)
└── .github/workflows/    CI
```

## Quick start (Docker)

1. **Create the environment file** at the project root (next to `docker-compose.yml`):

   ```sh
   cp .env.sample .env
   ```

2. **Set a secret key** in `.env` (`DJANGO_SECRET_KEY` is required — the app
   will not start without it):

   ```sh
   python -c "import secrets; print(''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#%^&*(-_=+)') for _ in range(64)))"
   ```

3. **To use the bundled Postgres**, set `DB_ENGINE=postgresql` in `.env`
   (it defaults to `sqlite3`; the `web` container reaches Postgres through
   PgBouncer automatically).

4. **Build and run:**

   ```sh
   docker compose up --build
   ```

5. Open **http://localhost:9005**. Register a user via the sign-up page, or
   create an admin:

   ```sh
   docker compose exec web python manage.py createsuperuser
   ```

`entrypoint.sh` runs `makemigrations`, `migrate`, and `collectstatic` on every
`web` start, so the schema is applied automatically.

## Configuration

`.env` lives at the project root and is loaded by `backend/settings.py`
(`BASE_DIR.parent / '.env'`). It is **git-ignored**; only `.env.sample` is
committed. Inside Compose, the `web` service overrides `DB_HOST`→`pgbouncer`
and `REDIS_HOST`→`redis` so containers reach each other by service name.

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | **Required**, no default | — |
| `DJANGO_DEBUG` | Debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins (incl. the public nginx origin) | — |
| `DB_ENGINE` | `sqlite3` or `postgresql` | `sqlite3` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Postgres credentials | `dashboard` / `dashboard` / — |
| `DB_HOST` / `DB_PORT` | DB address (overridden to `pgbouncer:5432` in Compose) | `127.0.0.1` / `5432` |
| `REDIS_HOST` / `REDIS_PORT` | Channels layer & cache | `127.0.0.1` / `6379` |
| `EMAIL_HOST` etc. | SMTP; blank ⇒ console email backend | console |
| `DEFAULT_FROM_EMAIL` | From address | `dashboard@example.com` |

## API overview

All endpoints are under `/api/` (proxied by nginx to Django). DRF defaults to
`IsAuthenticated`, so unauthenticated requests return `401`.

- **Auth:** `auth/register/`, `auth/token/`, `auth/token/refresh/`,
  `auth/token/verify/`, `auth/me/`, `auth/change-password/`, `auth/logout/`,
  `auth/preferences/`
- **Resources (ViewSets):** `dashboards/`, `columns/`, `labels/`, `todos/`,
  `subtasks/`, `comments/`, `attachments/`, `saved-views/`, `notifications/`,
  `webhooks/`
- **Other:** `users/`, `activity/`, `search/`, `calendar/feed/`,
  `calendar/<token>.ics`, `ws-ticket/`

Access tokens live 15 minutes, refresh tokens 1 day.

### Realtime notifications

WebSocket endpoint `/ws/notifications/` (Channels, backed by Redis pub/sub so
it works across Uvicorn workers). Clients first `POST /api/ws-ticket/` to get a
short-lived single-use ticket (cached in Redis) and connect with it as a query
param.

## Local development (without Docker)

**Backend**

```sh
cd backend
python -m venv .venv && .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Requires a `.env` at the project root and a running Redis/Postgres (or set
`DB_ENGINE=sqlite3` to skip Postgres). Note Channels WebSockets need an ASGI
server; `runserver` covers HTTP, use `uvicorn backend.asgi:application` for the
full stack.

**Frontend**

```sh
cd frontend
npm install
npm run dev      # Vite dev server
npm run build    # type-check + production build
```

## Database & migrations

Migration files in `backend/dashboard/migrations/` are source code and are
committed to git. `entrypoint.sh` runs `makemigrations` then `migrate` on
container start — after changing models, generate and **commit** the new
migration so every environment applies the identical schema history.

## Ports

| Port | Service |
|---|---|
| `9005` | Public app (nginx → SPA + proxied API/admin/ws) |
| `15432` | Postgres (host-mapped, for debugging) |
| `16432` | PgBouncer (host-mapped, for debugging) |

## Teardown

```sh
docker compose down        # stop & remove containers
docker compose down -v     # also drop the Postgres data volume
```
