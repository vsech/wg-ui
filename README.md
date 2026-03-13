# WireGuard UI

Веб-интерфейс для управления WireGuard-клиентами:
- FastAPI backend с JWT-аутентификацией
- Vue frontend для списка клиентов, генерации QR и скачивания конфигов
- SQLite для пользователей и кеша служебных метаданных
- Alembic для миграций
- Nginx + systemd + Let's Encrypt для production

## Что здесь является source of truth

- WireGuard peers и runtime-состояние берутся из `/etc/wireguard/wg0.conf` и `wg`
- клиентские `.conf` хранятся в `/opt/wg-ui/data`
- SQLite (`wireguard.db`) хранит пользователей и кеш полей `last_handshake`, `bytes_received`, `bytes_sent`

Если файл клиента в `/opt/wg-ui/data/<name>.conf` утерян, endpoint'ы `/api/clients/{name}/config` и `/api/clients/{name}/qr` не смогут восстановить исходный конфиг: приватный ключ клиента в `wg0.conf` не хранится.

## Основные директории

```text
app/                       FastAPI backend
frontend/                  Vue frontend
migrations/                Alembic migrations
deploy/                    production artifacts: nginx, systemd, env example
wg_installer.py            legacy CLI/installer для WireGuard
deploy.sh                  deploy-скрипт для текущего production host
```

## Backend

- entrypoint: `main.py`
- API prefix: `/api`
- typed errors и единый JSON error format
- lifespan startup вместо `@on_event`
- DI через `app/core/dependencies.py`
- WireGuard adapter: `app/infrastructure/wireguard/backend.py`
- client orchestration: `app/services/clients.py`

## Frontend

- Vite + Vue
- stores: `frontend/src/stores`
- composables: `frontend/src/composables`
- axios client: `frontend/src/services/api.js`

Frontend собирается в `frontend/dist` и в production раздаётся nginx из `/var/www/html`.

## Локальный запуск

### 1. Установить зависимости backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Установить зависимости frontend

```bash
npm --prefix frontend install
```

### 3. Подготовить окружение

Минимум нужен `SECRET_KEY`.

Пример:

```bash
cat > .env <<'EOF'
ENVIRONMENT=development
SECRET_KEY=change-me
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
EOF
```

### 4. Применить миграции

```bash
alembic upgrade head
```

### 5. Запустить backend и frontend

```bash
python start.py
npm --prefix frontend run dev
```

Backend по умолчанию слушает `http://127.0.0.1:8000`, frontend dev server проксирует API на backend.

## Обязательные переменные окружения

- `SECRET_KEY`: обязателен
- `ENVIRONMENT`: `development`, `staging`, `production`
- `BACKEND_CORS_ORIGINS`: список origins через запятую

## Полезные настройки backend

- `DATABASE_URL`: по умолчанию `sqlite:///./wireguard.db`
- `WIREGUARD_INTERFACE`: по умолчанию `wg0`
- `WIREGUARD_CONFIG_PATH`: по умолчанию `/etc/wireguard/wg0.conf`
- `WIREGUARD_CLIENT_CONFIG_DIR`: по умолчанию `/opt/wg-ui/data`
- `BOOTSTRAP_ADMIN_ENABLED`: `true/false`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`

## Production deploy

В репозитории лежат:
- `deploy/systemd/wg-ui.service`
- `deploy/nginx/wg-ui.bootstrap.conf`
- `deploy/nginx/wg-ui.conf`
- `deploy/env.production.example`

`deploy.sh` делает следующее:
- собирает frontend
- синхронизирует код на хост
- не трогает stateful-файлы: `.env`, `wireguard.db`, `*.db`, `data/`
- восстанавливает `venv`, если он повреждён
- выполняет `alembic upgrade head`
- обновляет systemd unit и nginx config
- перезапускает `wg-ui`
- выпускает Let's Encrypt сертификат, если его ещё нет

## Документация

- API: `README_API.md`
- структура проекта: `PROJECT_STRUCTURE.md`
