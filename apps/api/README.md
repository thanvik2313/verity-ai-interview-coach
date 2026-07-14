# Verity API

FastAPI backend for Verity — see the repository root [`README.md`](../../README.md)
and [`docs/architecture/`](../../docs/architecture) for the full product and
system design. This document covers only running this application locally.

> **Status:** Task 2.1, Part A — core configuration, JWT/refresh-token
> utilities, and email encryption/hashing helpers, plus the app composition
> root and a health check. No database models, migrations, auth routes, or
> OAuth flow exist yet; they land in subsequent parts of Task 2.1 and later
> tasks. See the root README's "Current scope" section for the authoritative
> status.

## Prerequisites

- Python 3.12
- The Milestone 1A local infrastructure services running from the repo root:

  ```bash
  docker compose up -d
  ```

  This starts PostgreSQL, Redis, and MinIO. Only PostgreSQL is used by the
  code in this app so far.

## Setup

```bash
cd apps/api

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e ".[dev]"

cp .env.example .env
```

Then edit `.env` and replace every placeholder secret. `.env.example`
includes the exact command to generate each one, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"          # VERITY_JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # VERITY_EMAIL_ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_hex(32))"              # VERITY_EMAIL_HASH_KEY
```

`.env` is git-ignored and must never be committed. Staging/production read
these same variable names from the deployment platform's managed secret
store instead of a file (see `TechStack.md` §7).

## Running the app

```bash
uvicorn verity.main.app:app --reload --host "$VERITY_API_HOST" --port "$VERITY_API_PORT"
```

Then check:

- `GET http://localhost:8000/health` — unauthenticated liveness check
- `GET http://localhost:8000/docs` — interactive API docs (disabled when
  `VERITY_ENVIRONMENT=production`)

The app fails to start if any required environment variable is missing or
still holds its `.env.example` placeholder value — this is intentional
fail-fast configuration validation (`verity.core.config.Settings`), not a
bug.

## What exists in this part of the codebase

| Path | Purpose |
| --- | --- |
| `src/verity/core/config.py` | Typed, validated settings sourced from environment variables |
| `src/verity/core/security.py` | JWT access-token issuance/verification; opaque refresh-token generation and hashing (no persistence yet) |
| `src/verity/core/crypto.py` | Email encryption (Fernet) and keyed lookup-hash (HMAC-SHA256) helpers for the future `users` table |
| `src/verity/core/errors.py` | Typed exception hierarchy used across the core layer |
| `src/verity/db/base.py` | SQLAlchemy declarative base, naming convention, and a shared timestamp mixin |
| `src/verity/db/session.py` | Async engine/session factory and the `get_db` FastAPI dependency |
| `src/verity/main/app.py` | FastAPI app factory: lifespan-managed DB engine, CORS, security headers, typed-error handlers, `/health` |

Not yet present: the `User` ORM model, Alembic migrations, any `/v1/auth/*`
route, Google OAuth, refresh-session persistence/rotation, and tests. These
are tracked as the remaining parts of Task 2.1 and subsequent Sprint 2
tasks.

## Code quality

```bash
ruff check .
ruff format .
mypy .
pytest   # no tests exist yet in this part
```

These also run in CI per the quality gates described in `TechStack.md` §6.