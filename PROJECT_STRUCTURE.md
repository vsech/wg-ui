# WireGuard UI - Project Structure

Документ описывает текущее состояние репозитория после выноса WireGuard-логики в инфраструктурный слой, добавления Alembic и production deploy artifacts.

## Directory Structure

```text
wg-ui/
├── app/
│   ├── core/
│   │   ├── config.py              # BaseSettings, env parsing, CORS parsing
│   │   ├── database.py            # SQLAlchemy engine/session
│   │   ├── dependencies.py        # DI for auth/client services
│   │   ├── exceptions.py          # Typed application exceptions
│   │   ├── logging.py             # Structured logging setup
│   │   └── security.py            # JWT and password hashing
│   ├── infrastructure/
│   │   └── wireguard/
│   │       └── backend.py         # Adapter over wg, wg0.conf, client .conf files
│   ├── models/
│   │   ├── database.py            # SQLAlchemy models
│   │   └── schemas.py             # Pydantic schemas
│   ├── routers/
│   │   ├── auth.py                # /api/auth/*
│   │   └── clients.py             # /api/clients/*
│   └── services/
│       ├── auth.py                # Authentication use cases
│       ├── clients.py             # Client sync/orchestration/compensation
│       └── qr_generator.py        # QR generation
├── deploy/
│   ├── env.production.example     # Minimal production env example
│   ├── nginx/
│   │   ├── wg-ui.bootstrap.conf   # HTTP-only config before certificate issuance
│   │   └── wg-ui.conf             # Final HTTPS nginx site
│   └── systemd/
│       └── wg-ui.service          # Production unit for uvicorn
├── frontend/
│   └── src/
│       ├── components/            # UI components
│       ├── composables/           # Downloads and formatting helpers
│       ├── router/                # Vue router
│       ├── services/              # Axios API client
│       ├── stores/                # Auth and clients state
│       └── views/                 # Login, home, clients pages
├── migrations/
│   └── versions/                  # Alembic revisions
├── alembic.ini
├── deploy.sh                      # Deploy script for current production topology
├── main.py                        # FastAPI app entrypoint
├── start.py                       # Local dev launcher
├── wg_installer.py                # Legacy CLI installer/manager
├── README.md
├── README_API.md
└── PROJECT_STRUCTURE.md
```

## Layer Responsibilities

### `app/core`

- configuration loading from env
- DB engine and sessions
- authentication/security primitives
- DI wiring
- common exception model
- structured logging

### `app/infrastructure`

- direct work with `wg`
- parsing `/etc/wireguard/wg0.conf`
- reading/writing `/opt/wg-ui/data/*.conf`
- runtime stats via `wg show`

Этот слой не знает о FastAPI-роутах и не должен содержать web-specific orchestration.

### `app/services`

- application use cases
- sync между WireGuard source of truth и кешем в SQLite
- compensation logic при частичных ошибках create/delete
- assembly response payloads for routers

### `app/routers`

- thin HTTP layer
- request/response schemas
- auth guards через dependencies

### `frontend`

- SPA поверх REST API
- отдельные stores для auth и clients
- composables вынесены из компонентов, чтобы не дублировать форматирование и скачивание

## Runtime Data Model

- peers и их allowed IPs: `/etc/wireguard/wg0.conf`
- client config downloads: `/opt/wg-ui/data/*.conf`
- users и cached client stats: `wireguard.db`

Это важно operationally: потеря `data/*.conf` не ломает существующий peer на сервере, но ломает повторную выдачу client config и QR через API.

## Deploy Model

Production deploy опирается на:
- `deploy.sh`
- `deploy/systemd/wg-ui.service`
- `deploy/nginx/wg-ui.bootstrap.conf`
- `deploy/nginx/wg-ui.conf`

`deploy.sh` специально не синхронизирует stateful сущности:
- `.env`
- `wireguard.db`
- `*.db`
- `data/`

Именно код и infra-артефакты деплоятся, а не рабочие данные хоста.

## Historical Notes

- `wg_installer.py` остаётся в репозитории как legacy CLI flow
- web API больше не зависит от него напрямую
- schema evolution теперь идёт через Alembic, а не через `create_all`
