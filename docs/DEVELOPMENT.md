# Development Guide

Personal Teacher Assistant for 10th — FastAPI API + Celery worker, Vite admin panel,
Expo (Android) app.

## Prerequisites

- Docker Desktop (Compose v2.24+)
- Node.js 22 (admin / mobile outside Docker)
- Python 3.12 (optional, backend outside Docker)

## 1. Configure environment

```bash
cp .env.example .env    # then fill in OPENAI_API_KEY, TTS_API_KEY, GOOGLE_* ...
```

`.env` is git-ignored and is read at runtime only (never baked into images).
Inside Docker, `DATABASE_URL`, `REDIS_URL` and `S3_*` are overridden by
`docker-compose.yml` to point at the compose services.

> The postgres (`pta`/`pta`), MinIO (`minioadmin`/`minioadmin`) and default
> `SECRET_KEY` values in the compose files are **dev-only**. Never use them in production.

## 2. Run the stack with Docker

Development (hot reload for API, worker code, and Vite admin dev server):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Production-like (gunicorn + nginx-served admin build):

```bash
docker compose up --build
```

The `api` service runs `alembic upgrade head` on start (`RUN_MIGRATIONS=true`).
`minio-init` creates the `pta-media` bucket once and exits.

Stop everything with `docker compose down` (add `-v` to wipe the database/MinIO volumes).

## 3. Seed data and create an admin

```bash
# TN State Board + subjects + sample chapters/topics (English & Tamil)
docker compose exec api python -m app.seed

# Grant admin role to a Google account email
docker compose exec api python -m app.cli create-admin --email <email>
```

## 4. Run the mobile app

```bash
cd mobile
npm install
npx expo start
```

- Android emulator reaches the host API at `http://10.0.2.2:8000`
  (`EXPO_PUBLIC_API_URL=http://10.0.2.2:8000`).
- A physical device needs your machine's LAN IP, e.g. `http://192.168.1.20:8000`.
- Release builds use EAS (`eas build -p android --profile preview`), not Docker.

## 5. URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Admin panel | http://localhost:3000 |
| MinIO S3 API | http://localhost:9000 |
| MinIO console | http://localhost:9001 (dev: `minioadmin` / `minioadmin`) |
| Postgres (dev override only) | localhost:5432 (`pta` / `pta`, db `personal_teacher_assistant`) |
| Redis (dev override only) | localhost:6379 |

> The API talks to MinIO at `S3_ENDPOINT_URL=http://minio:9000` (inside the compose
> network), but signed media URLs are generated for `S3_PUBLIC_ENDPOINT_URL`
> (default `http://localhost:9000`). For the Android emulator set it to
> `http://10.0.2.2:9000`; for a real phone use `http://<your-LAN-IP>:9000`.

## 6. Useful commands

```bash
docker compose logs -f api worker            # follow logs
docker compose exec api alembic revision --autogenerate -m "msg"
docker compose exec api pytest               # needs the dev override (tests are bind-mounted)
docker compose exec api ruff check .
```

## 7. CI

`.github/workflows/ci.yml` runs on push/PR to `main`:

- **backend** — ruff, mypy, `alembic upgrade head`, pytest with 80% coverage gate (`ENVIRONMENT=test`, fake TTS)
- **admin** — `npm ci`, lint, type-check, test, build
- **mobile** — `npm ci`, lint, type-check, test
- **docker** — compose config validation + `docker compose build`
