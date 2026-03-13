#!/bin/bash
set -euo pipefail

APP_HOST="${APP_HOST:-root@178.20.46.152}"
APP_DIR="${APP_DIR:-/opt/wg-ui}"
DOMAIN="${DOMAIN:-v2920386.hosted-by-vdsina.ru}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-a@bxcv.ru}"
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
FRONTEND_DIR="${FRONTEND_DIR:-frontend}"
SYSTEMD_UNIT="${SYSTEMD_UNIT:-wg-ui.service}"
NGINX_SITE="${NGINX_SITE:-wg-ui}"
REMOTE_PYTHON="${REMOTE_PYTHON:-$APP_DIR/venv/bin/python}"
REMOTE_PIP="${REMOTE_PIP:-$APP_DIR/venv/bin/pip}"
REMOTE_ALEMBIC="${REMOTE_ALEMBIC:-$APP_DIR/venv/bin/alembic}"
REMOTE_UVICORN="${REMOTE_UVICORN:-$APP_DIR/venv/bin/uvicorn}"

echo "Building frontend..."
npm --prefix "$FRONTEND_DIR" run build

echo "Syncing application files to $APP_HOST..."
rsync -az --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'wireguard.db' \
  --exclude '*.db' \
  --exclude 'data' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'venv' \
  --exclude '.venv' \
  --exclude "$FRONTEND_DIR/node_modules" \
  --exclude "$FRONTEND_DIR/dist" \
  ./ "$APP_HOST:$APP_DIR/"

echo "Syncing frontend build to $APP_HOST:$WEB_ROOT..."
rsync -az --delete "$FRONTEND_DIR/dist/" "$APP_HOST:$WEB_ROOT/"

echo "Installing backend dependencies and applying migrations..."
ssh "$APP_HOST" "bash -lc '
set -euo pipefail
cd \"$APP_DIR\"

if [[ ! -x \"$REMOTE_PIP\" ]]; then
  python3 -m venv --clear \"$APP_DIR/venv\"
fi

\"$REMOTE_PYTHON\" -m ensurepip --upgrade
\"$REMOTE_PIP\" install -r requirements.txt

if [[ ! -f \"$APP_DIR/.env\" ]]; then
  if [[ -z \"${SECRET_KEY-}\" ]]; then
    echo \"SECRET_KEY is required for first deployment when $APP_DIR/.env does not exist on the host.\" >&2
    exit 1
  fi
  cat > \"$APP_DIR/.env\" <<EOF
ENVIRONMENT=production
SECRET_KEY=${SECRET_KEY-}
BACKEND_CORS_ORIGINS=https://${DOMAIN}
EOF
  chmod 600 \"$APP_DIR/.env\"
fi

if [[ -f wireguard.db ]]; then
  if sqlite3 wireguard.db \".tables\" | grep -Eq \"(^| )users( |$)|(^| )clients( |$)\"; then
    if ! sqlite3 wireguard.db \".tables\" | grep -Eq \"(^| )alembic_version( |$)\"; then
      \"$REMOTE_ALEMBIC\" stamp 0001_initial_schema
    fi
  fi
fi

\"$REMOTE_ALEMBIC\" upgrade head
'"

echo "Installing systemd unit and nginx site..."
scp deploy/systemd/wg-ui.service "$APP_HOST:/etc/systemd/system/$SYSTEMD_UNIT"
scp deploy/nginx/wg-ui.bootstrap.conf "$APP_HOST:/etc/nginx/sites-available/$NGINX_SITE"

ssh "$APP_HOST" "bash -lc '
set -euo pipefail
ln -sfn /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/$NGINX_SITE
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload
systemctl enable \"$SYSTEMD_UNIT\"
systemctl restart \"$SYSTEMD_UNIT\"
nginx -t
systemctl reload nginx

if ! command -v certbot >/dev/null 2>&1; then
  apt-get update
  apt-get install -y certbot
fi

if [[ ! -d \"/etc/letsencrypt/live/${DOMAIN}\" ]]; then
  certbot certonly --webroot -w \"$WEB_ROOT\" \
    -d \"${DOMAIN}\" \
    -m \"${LETSENCRYPT_EMAIL}\" \
    --agree-tos \
    --no-eff-email \
    --non-interactive
fi
'"

scp deploy/nginx/wg-ui.conf "$APP_HOST:/etc/nginx/sites-available/$NGINX_SITE"

ssh "$APP_HOST" "bash -lc '
set -euo pipefail
systemctl restart \"$SYSTEMD_UNIT\"
nginx -t
systemctl reload nginx
'"

echo "Deployment complete."
