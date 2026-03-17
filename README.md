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
install_wg_ui.sh           рекомендуемый production installer/orchestrator
wg_installer.py            CLI installer/manager поверх общего WireGuard backend
deploy.sh                  вспомогательный rsync deploy-скрипт для текущего production host
```

## Backend

- entrypoint: `main.py`
- API prefix: `/api`
- typed errors и единый JSON error format
- lifespan startup вместо `@on_event`
- DI через `app/core/dependencies.py`
- WireGuard adapter: `app/infrastructure/wireguard/backend.py`
- client orchestration: `app/services/clients.py`
- `install_wg_ui.sh` является рекомендуемой production entrypoint для развертывания
- CLI (`wg_installer.py`) использует тот же WireGuard backend и те же `WIREGUARD_*` settings

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

## Рекомендуемый production запуск

Основной сценарий развертывания: запуск [`install_wg_ui.sh`](./install_wg_ui.sh) на целевом сервере из checkout этого репозитория.

Скрипт поддерживает 3 режима:

- `new`: чистый сервер, установка приложения и запуск интерактивной установки WireGuard через `wg_installer.py --install`
- `reinstall`: переустановка `wg-ui` поверх существующего инстанса сервиса
- `migrate`: перенос существующей WireGuard установки в web UI с импортом peers и клиентских конфигов

Что делает `install_wg_ui.sh`:

- ставит системные зависимости приложения, Python и Node.js
- собирает frontend
- пишет `.env`
- применяет `alembic upgrade head`
- настраивает `systemd` и `nginx`
- при `migrate` и `reinstall` с `RESET_APP_STATE=1` вызывает `wg_installer.py --bootstrap-backend`
- при `new` делегирует установку самого WireGuard в `wg_installer.py --install`

Примеры:

```bash
sudo DOMAIN=wg.example.com LETSENCRYPT_EMAIL=admin@example.com ADMIN_USERNAME=admin ./install_wg_ui.sh new
sudo DOMAIN=wg.example.com LETSENCRYPT_EMAIL=admin@example.com ADMIN_USERNAME=admin ./install_wg_ui.sh reinstall
sudo DOMAIN=wg.example.com LETSENCRYPT_EMAIL=admin@example.com ADMIN_USERNAME=admin CLIENT_IMPORT_DIR=/root ./install_wg_ui.sh migrate
```

Полезные переменные:

- `DOMAIN`: домен для nginx/Let's Encrypt
- `LETSENCRYPT_EMAIL`: email для сертификата
- `ADMIN_USERNAME`: логин администратора web UI
- `ADMIN_PASSWORD`: пароль администратора; если не задан, будет интерактивный prompt там, где это поддерживается
- `CLIENT_IMPORT_DIR`: каталог, откуда импортировать клиентские `.conf` при миграции
- `RESET_APP_STATE=1`: при `reinstall` пересоздать `wireguard.db` и каталог клиентских конфигов, затем заново импортировать состояние из текущего WireGuard
- `ENABLE_HTTPS=auto|0|1`: включение HTTPS

По умолчанию `reinstall` не трогает `.env`, `wireguard.db` и `data/` без `RESET_APP_STATE=1`: они сначала бэкапятся, затем используются повторно.

Важно: при `ENABLE_HTTPS=auto` сертификат выпускается только если задан и `DOMAIN`, и `LETSENCRYPT_EMAIL`. Если email не передан, скрипт остаётся на HTTP и выводит warning.

## Пошаговая установка на чистый сервер

Ниже production-сценарий, проверенный на Ubuntu 24.04.

### 1. Подготовить DNS

Домен должен указывать на IP сервера.

Проверка:

```bash
getent ahostsv4 wg.example.com
```

### 2. Зайти на сервер и получить исходники

Рекомендуется выполнять установку из git checkout прямо на сервере:

```bash
ssh root@your-server-ip
apt-get update
apt-get install -y git
git clone https://github.com/<your-org>/<your-repo>.git /root/wg-ui-src
cd /root/wg-ui-src
chmod +x install_wg_ui.sh
```

### 3. Запустить установку

Для чистого сервера используйте режим `new`:

```bash
DOMAIN=wg.example.com \
LETSENCRYPT_EMAIL=admin@example.com \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD='change-me-now' \
./install_wg_ui.sh new
```

Что сделает скрипт:

- установит системные пакеты, Python, Node.js, nginx, certbot
- скопирует проект в `/opt/wg-ui`
- создаст `.env`
- установит и запустит WireGuard
- применит Alembic миграции
- создаст admin-пользователя
- соберёт frontend
- настроит `systemd` и `nginx`
- выпустит Let's Encrypt сертификат

### 4. Ответить на вопросы WireGuard installer

Во время `new`-установки `wg_installer.py --install` задаст несколько вопросов:

1. IPv4 address: выберите публичный IP сервера.
2. Port: обычно оставляют `51820`.
3. First client name: например `client`.
4. DNS server: можно выбрать default system resolvers или публичные DNS.

После завершения первый клиентский конфиг будет сохранён в:

```bash
/opt/wg-ui/data/<client>.conf
```

### 5. Проверить сервисы

```bash
systemctl status wg-ui
systemctl status nginx
systemctl status wg-quick@wg0
```

Быстрая проверка HTTPS:

```bash
curl -I https://wg.example.com/
```

Проверка логина в API:

```bash
curl -X POST https://wg.example.com/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"change-me-now"}'
```

### 6. Полезные пути на сервере

```text
/opt/wg-ui                  приложение
/opt/wg-ui/.env             production env
/opt/wg-ui/wireguard.db     SQLite база
/opt/wg-ui/data             клиентские .conf
/etc/wireguard/wg0.conf     конфиг WireGuard сервера
/etc/systemd/system/wg-ui.service
/etc/nginx/sites-available/wg-ui
```

### 7. Повторный запуск

Если WireGuard уже установлен и нужно просто обновить приложение:

```bash
DOMAIN=wg.example.com \
LETSENCRYPT_EMAIL=admin@example.com \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD='change-me-now' \
./install_wg_ui.sh reinstall
```

Если нужно пересобрать application state из текущего `wg0.conf`:

```bash
DOMAIN=wg.example.com \
LETSENCRYPT_EMAIL=admin@example.com \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD='change-me-now' \
RESET_APP_STATE=1 \
./install_wg_ui.sh reinstall
```

## Ручные операции через wg_installer.py

Обычно production-развертывание нужно делать через `install_wg_ui.sh`. Прямой запуск `wg_installer.py` нужен как ручной fallback или для точечных операций с WireGuard/backend bootstrap.

Если WireGuard уже развернут отдельно, `wg_installer.py` умеет подготовить backend под текущую установку:

- перенести peers из `wg0.conf` в SQLite cache приложения
- скопировать клиентские `.conf` из существующего каталога в `WIREGUARD_CLIENT_CONFIG_DIR`
- создать admin-пользователя для web UI

Перед bootstrap нужно применить миграции:

```bash
alembic upgrade head
```

Полный bootstrap:

```bash
sudo /opt/wg-ui/venv/bin/python wg_installer.py --bootstrap-backend --import-client-configs-from /root --create-admin admin
```

Если `--import-client-configs-from` не указан, для `--bootstrap-backend` по умолчанию используется `/root`.

Отдельные операции:

```bash
sudo /opt/wg-ui/venv/bin/python wg_installer.py --import-existing-clients
sudo /opt/wg-ui/venv/bin/python wg_installer.py --import-client-configs-from /root
/opt/wg-ui/venv/bin/python wg_installer.py --create-admin admin
```

Если пароль не передан через `--admin-password`, CLI запросит его интерактивно. Для перезаписи уже существующих клиентских `.conf` в каталоге приложения используйте `--overwrite-client-configs`.

## Legacy deploy

В репозитории также лежат:

- `deploy/systemd/wg-ui.service`
- `deploy/nginx/wg-ui.bootstrap.conf`
- `deploy/nginx/wg-ui.conf`
- `deploy/env.production.example`

## Документация

- API: `README_API.md`
- структура проекта: `PROJECT_STRUCTURE.md`
