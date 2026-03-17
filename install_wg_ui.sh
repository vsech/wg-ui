#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="${1:-}"
APP_DIR="${APP_DIR:-/opt/wg-ui}"
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
SERVICE_NAME="${SERVICE_NAME:-wg-ui}"
NGINX_SITE="${NGINX_SITE:-wg-ui}"
ENVIRONMENT="${ENVIRONMENT:-production}"
WIREGUARD_INTERFACE="${WIREGUARD_INTERFACE:-wg0}"
WIREGUARD_CONFIG_PATH="${WIREGUARD_CONFIG_PATH:-/etc/wireguard/${WIREGUARD_INTERFACE}.conf}"
WIREGUARD_CLIENT_CONFIG_DIR="${WIREGUARD_CLIENT_CONFIG_DIR:-${APP_DIR}/data}"
VENV_DIR="${VENV_DIR:-${APP_DIR}/venv}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
FRONTEND_DIR="${FRONTEND_DIR:-${APP_DIR}/frontend}"
DB_FILE="${DB_FILE:-${APP_DIR}/wireguard.db}"
DATABASE_URL="${DATABASE_URL:-sqlite:////${DB_FILE}}"
DOMAIN="${DOMAIN:-}"
PUBLIC_HOST="${PUBLIC_HOST:-${DOMAIN:-$(hostname -f 2>/dev/null || hostname)}}"
SERVER_NAME="${SERVER_NAME:-${PUBLIC_HOST}}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
ENABLE_HTTPS="${ENABLE_HTTPS:-auto}"
CLIENT_IMPORT_DIR="${CLIENT_IMPORT_DIR:-/root}"
OVERWRITE_CLIENT_CONFIGS="${OVERWRITE_CLIENT_CONFIGS:-1}"
RESET_APP_STATE="${RESET_APP_STATE:-0}"
ADMIN_USERNAME="${ADMIN_USERNAME:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
BACKEND_CORS_ORIGINS="${BACKEND_CORS_ORIGINS:-}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/wg-ui}"
BACKUP_DIR="${BACKUP_DIR:-${BACKUP_ROOT}/$(date +%Y%m%d-%H%M%S)}"
BACKUP_CONFIG_DIR=""
PKG_MANAGER=""

log() {
  printf '[%s] %s\n' "$1" "$2"
}

info() {
  log INFO "$1"
}

warn() {
  log WARN "$1" >&2
}

fail() {
  log ERROR "$1" >&2
  exit 1
}

on_error() {
  local line="$1"
  fail "Command failed near line ${line}"
}

trap 'on_error "${LINENO}"' ERR

usage() {
  cat <<EOF
Usage:
  sudo ./${SCRIPT_NAME} <new|reinstall|migrate>

Modes:
  new
    Clean server. Installs OS packages, deploys wg-ui and then runs the
    interactive WireGuard bootstrap via wg_installer.py --install.

  reinstall
    Reinstalls wg-ui on a host where this service already exists.
    By default keeps .env, DB and client configs. Set RESET_APP_STATE=1 to
    recreate application state from the current WireGuard config.

  migrate
    Deploys wg-ui on top of an existing WireGuard installation and imports
    peers/configs into the web service.

Useful environment variables:
  APP_DIR=/opt/wg-ui
  WEB_ROOT=/var/www/html
  DOMAIN=wg.example.com
  LETSENCRYPT_EMAIL=admin@example.com
  PUBLIC_HOST=server.example.com
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=secret
  CLIENT_IMPORT_DIR=/root
  OVERWRITE_CLIENT_CONFIGS=1
  RESET_APP_STATE=1
  ENABLE_HTTPS=auto|0|1

Examples:
  sudo DOMAIN=wg.example.com LETSENCRYPT_EMAIL=admin@example.com ADMIN_USERNAME=admin ./${SCRIPT_NAME} new
  sudo DOMAIN=wg.example.com LETSENCRYPT_EMAIL=admin@example.com ADMIN_USERNAME=admin ./${SCRIPT_NAME} reinstall
  sudo DOMAIN=wg.example.com LETSENCRYPT_EMAIL=admin@example.com ADMIN_USERNAME=admin CLIENT_IMPORT_DIR=/root ./${SCRIPT_NAME} migrate
EOF
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Run this script as root."
  fi
}

validate_mode() {
  case "${MODE}" in
    new|reinstall|migrate) ;;
    ""|-h|--help|help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "Unsupported mode: ${MODE}"
      ;;
  esac
}

bool_is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|y|Y|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

detect_pkg_manager() {
  if command -v apt-get >/dev/null 2>&1; then
    PKG_MANAGER="apt"
  elif command -v dnf >/dev/null 2>&1; then
    PKG_MANAGER="dnf"
  else
    fail "Supported package managers: apt-get, dnf"
  fi
}

install_base_packages() {
  info "Installing application system packages"

  if [[ "${PKG_MANAGER}" == "apt" ]]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y \
      build-essential \
      ca-certificates \
      curl \
      git \
      gnupg \
      libffi-dev \
      nginx \
      openssl \
      python3 \
      python3-dev \
      python3-pip \
      python3-venv \
      rsync \
      sqlite3
  else
    dnf install -y \
      ca-certificates \
      curl \
      gcc \
      git \
      libffi-devel \
      make \
      nginx \
      openssl-devel \
      openssl \
      python3 \
      python3-devel \
      python3-pip \
      rsync \
      sqlite
  fi
}

ensure_nodejs() {
  local node_major="0"

  if command -v node >/dev/null 2>&1; then
    node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || printf '0')"
  fi

  if [[ "${node_major}" =~ ^[0-9]+$ ]] && (( node_major >= 18 )); then
    info "Node.js ${node_major} detected"
    return
  fi

  info "Installing Node.js 20.x"

  if [[ "${PKG_MANAGER}" == "apt" ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
  else
    curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
    dnf install -y nodejs
  fi
}

ensure_directory_layout() {
  mkdir -p "${APP_DIR}" "${WEB_ROOT}" "${BACKUP_ROOT}"
}

backup_path() {
  local path="$1"
  local label="$2"

  if [[ -e "${path}" ]]; then
    mkdir -p "${BACKUP_DIR}"
    info "Backing up ${label} to ${BACKUP_DIR}"
    cp -a "${path}" "${BACKUP_DIR}/"
    if [[ "${path}" == "${WIREGUARD_CLIENT_CONFIG_DIR}" ]]; then
      BACKUP_CONFIG_DIR="${BACKUP_DIR}/$(basename "${path}")"
    fi
  fi
}

backup_existing_state() {
  if [[ "${MODE}" != "reinstall" && "${MODE}" != "migrate" ]]; then
    return
  fi

  backup_path "${ENV_FILE}" ".env"
  backup_path "${DB_FILE}" "database"
  backup_path "${WIREGUARD_CLIENT_CONFIG_DIR}" "client configs"
}

reset_app_state_if_requested() {
  if [[ "${MODE}" != "reinstall" ]]; then
    return
  fi

  if ! bool_is_true "${RESET_APP_STATE}"; then
    return
  fi

  info "RESET_APP_STATE=1, recreating application state"

  if [[ -f "${DB_FILE}" ]]; then
    rm -f "${DB_FILE}"
  fi

  if [[ -d "${WIREGUARD_CLIENT_CONFIG_DIR}" ]]; then
    rm -rf "${WIREGUARD_CLIENT_CONFIG_DIR}"
  fi

  mkdir -p "${WIREGUARD_CLIENT_CONFIG_DIR}"

  if [[ "${CLIENT_IMPORT_DIR}" == "/root" && -n "${BACKUP_CONFIG_DIR}" && -d "${BACKUP_CONFIG_DIR}" ]]; then
    CLIENT_IMPORT_DIR="${BACKUP_CONFIG_DIR}"
  fi
}

sync_source_tree() {
  if [[ "${SOURCE_DIR}" == "${APP_DIR}" ]]; then
    info "Source directory is already ${APP_DIR}, skipping sync"
    return
  fi

  info "Syncing application files into ${APP_DIR}"

  rsync -a --delete \
    --exclude '.git' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude 'wireguard.db' \
    --exclude '*.db' \
    --exclude 'data' \
    --exclude 'venv' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'frontend/node_modules' \
    --exclude 'frontend/dist' \
    "${SOURCE_DIR}/" "${APP_DIR}/"
}

setup_python_env() {
  info "Installing backend dependencies"

  python3 -m venv --clear "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
  "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
}

build_frontend() {
  info "Installing frontend dependencies"
  npm --prefix "${FRONTEND_DIR}" ci

  info "Building frontend"
  npm --prefix "${FRONTEND_DIR}" run build

  info "Publishing frontend to ${WEB_ROOT}"
  rsync -a --delete "${FRONTEND_DIR}/dist/" "${WEB_ROOT}/"
}

ensure_secret_key() {
  if [[ -n "${SECRET_KEY:-}" ]]; then
    return
  fi

  SECRET_KEY="$(openssl rand -hex 32)"
}

resolve_https_flag() {
  local existing_cert_dir=""

  if [[ -n "${DOMAIN}" ]]; then
    existing_cert_dir="/etc/letsencrypt/live/${DOMAIN}"
  fi

  case "${ENABLE_HTTPS}" in
    1|true|TRUE|yes|YES|on|ON)
      [[ -n "${DOMAIN}" ]] || fail "DOMAIN is required when ENABLE_HTTPS=1"
      [[ -n "${LETSENCRYPT_EMAIL}" ]] || fail "LETSENCRYPT_EMAIL is required when ENABLE_HTTPS=1"
      ENABLE_HTTPS="1"
      ;;
    0|false|FALSE|no|NO|off|OFF)
      ENABLE_HTTPS="0"
      ;;
    auto)
      if [[ -n "${DOMAIN}" && -n "${LETSENCRYPT_EMAIL}" ]]; then
        ENABLE_HTTPS="1"
      elif [[ -n "${existing_cert_dir}" && -d "${existing_cert_dir}" ]]; then
        info "Existing Let's Encrypt certificate found for ${DOMAIN}, HTTPS will remain enabled"
        ENABLE_HTTPS="1"
      else
        if [[ -n "${DOMAIN}" ]]; then
          warn "DOMAIN is set but LETSENCRYPT_EMAIL is empty, so ENABLE_HTTPS=auto falls back to HTTP. Set LETSENCRYPT_EMAIL or ENABLE_HTTPS=1 to issue a certificate."
        fi
        ENABLE_HTTPS="0"
      fi
      ;;
    *)
      fail "ENABLE_HTTPS must be one of: auto, 0, 1"
      ;;
  esac
}

write_env_file() {
  local cors_origins="${BACKEND_CORS_ORIGINS}"

  ensure_secret_key

  if [[ -z "${cors_origins}" ]]; then
    if [[ "${ENABLE_HTTPS}" == "1" ]]; then
      cors_origins="https://${PUBLIC_HOST},http://${PUBLIC_HOST}"
    else
      cors_origins="http://${PUBLIC_HOST}"
    fi
  fi

  info "Writing ${ENV_FILE}"

  mkdir -p "${APP_DIR}" "${WIREGUARD_CLIENT_CONFIG_DIR}"

  cat > "${ENV_FILE}" <<EOF
ENVIRONMENT=${ENVIRONMENT}
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=${DATABASE_URL}
BACKEND_CORS_ORIGINS=${cors_origins}
WIREGUARD_INTERFACE=${WIREGUARD_INTERFACE}
WIREGUARD_CONFIG_PATH=${WIREGUARD_CONFIG_PATH}
WIREGUARD_CLIENT_CONFIG_DIR=${WIREGUARD_CLIENT_CONFIG_DIR}
BOOTSTRAP_ADMIN_ENABLED=false
EOF

  chmod 600 "${ENV_FILE}"
}

stamp_legacy_db_if_needed() {
  if [[ ! -f "${DB_FILE}" ]]; then
    return
  fi

  if ! sqlite3 "${DB_FILE}" ".tables" | grep -Eq '(^| )users( |$)|(^| )clients( |$)'; then
    return
  fi

  if sqlite3 "${DB_FILE}" ".tables" | grep -Eq '(^| )alembic_version( |$)'; then
    return
  fi

  info "Stamping legacy database with initial Alembic revision"
  (
    cd "${APP_DIR}"
    "${VENV_DIR}/bin/alembic" stamp 0001_initial_schema
  )
}

run_migrations() {
  info "Applying database migrations"
  (
    cd "${APP_DIR}"
    "${VENV_DIR}/bin/alembic" upgrade head
  )
}

run_wireguard_install() {
  [[ ! -f "${WIREGUARD_CONFIG_PATH}" ]] || fail "WireGuard config already exists: ${WIREGUARD_CONFIG_PATH}"

  info "Running interactive WireGuard installation"
  (
    cd "${APP_DIR}"
    "${VENV_DIR}/bin/python" wg_installer.py --install
  )
}

create_admin_if_requested() {
  if [[ -z "${ADMIN_USERNAME}" ]]; then
    warn "ADMIN_USERNAME is not set, admin creation skipped"
    return
  fi

  info "Creating admin user ${ADMIN_USERNAME}"

  if [[ -n "${ADMIN_PASSWORD}" ]]; then
    (
      cd "${APP_DIR}"
      "${VENV_DIR}/bin/python" wg_installer.py \
        --create-admin "${ADMIN_USERNAME}" \
        --admin-password "${ADMIN_PASSWORD}"
    )
    return
  fi

  (
    cd "${APP_DIR}"
    "${VENV_DIR}/bin/python" wg_installer.py --create-admin "${ADMIN_USERNAME}"
  )
}

write_systemd_unit() {
  local service_path="/etc/systemd/system/${SERVICE_NAME}.service"

  info "Installing systemd unit ${service_path}"

  cat > "${service_path}" <<EOF
[Unit]
Description=WireGuard UI FastAPI service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}.service"
}

write_nginx_http_site() {
  local site_path

  site_path="$(get_nginx_site_path)"

  cat > "${site_path}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${SERVER_NAME};

    root ${WEB_ROOT};
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
}

write_nginx_https_site() {
  local site_path

  site_path="$(get_nginx_site_path)"

  cat > "${site_path}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${SERVER_NAME};

    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${SERVER_NAME};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root ${WEB_ROOT};
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
}

get_nginx_site_path() {
  if [[ "${PKG_MANAGER}" == "apt" ]]; then
    printf '/etc/nginx/sites-available/%s' "${NGINX_SITE}"
  else
    printf '/etc/nginx/conf.d/%s.conf' "${NGINX_SITE}"
  fi
}

enable_nginx_site() {
  if [[ "${PKG_MANAGER}" == "apt" ]]; then
    ln -sfn "/etc/nginx/sites-available/${NGINX_SITE}" "/etc/nginx/sites-enabled/${NGINX_SITE}"
    rm -f /etc/nginx/sites-enabled/default
  fi
  systemctl enable nginx
  nginx -t
  systemctl restart nginx
}

ensure_certbot() {
  if command -v certbot >/dev/null 2>&1; then
    return
  fi

  info "Installing certbot"

  if [[ "${PKG_MANAGER}" == "apt" ]]; then
    apt-get install -y certbot
  else
    dnf install -y certbot
  fi
}

ensure_letsencrypt_ssl_options() {
  local options_path="/etc/letsencrypt/options-ssl-nginx.conf"
  local dhparam_path="/etc/letsencrypt/ssl-dhparams.pem"

  mkdir -p /etc/letsencrypt

  if [[ ! -f "${options_path}" ]]; then
    info "Writing default TLS options to ${options_path}"
    cat > "${options_path}" <<'EOF'
ssl_session_cache shared:le_nginx_SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_ecdh_curve X25519:prime256v1:secp384r1;
add_header Strict-Transport-Security "max-age=31536000" always;
EOF
  fi

  if [[ ! -f "${dhparam_path}" ]]; then
    info "Generating ${dhparam_path}"
    openssl dhparam -out "${dhparam_path}" 2048
  fi
}

configure_nginx() {
  info "Configuring nginx"

  write_nginx_http_site
  enable_nginx_site

  if [[ "${ENABLE_HTTPS}" != "1" ]]; then
    return
  fi

  ensure_certbot

  if [[ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
    info "Requesting Let's Encrypt certificate for ${DOMAIN}"
    certbot certonly \
      --webroot \
      -w "${WEB_ROOT}" \
      -d "${DOMAIN}" \
      -m "${LETSENCRYPT_EMAIL}" \
      --agree-tos \
      --no-eff-email \
      --non-interactive
  else
    info "Let's Encrypt certificate already exists for ${DOMAIN}"
  fi

  ensure_letsencrypt_ssl_options
  write_nginx_https_site
  enable_nginx_site
}

restart_app() {
  info "Restarting ${SERVICE_NAME}.service"
  systemctl restart "${SERVICE_NAME}.service"
}

verify_wireguard_exists() {
  [[ -f "${WIREGUARD_CONFIG_PATH}" ]] || fail "WireGuard config not found: ${WIREGUARD_CONFIG_PATH}"
  command -v wg >/dev/null 2>&1 || fail "WireGuard binary 'wg' not found. Install WireGuard first or use mode 'new'."
}

run_bootstrap_backend() {
  local cmd=(
    "${VENV_DIR}/bin/python" "wg_installer.py"
    "--bootstrap-backend"
    "--import-client-configs-from" "${CLIENT_IMPORT_DIR}"
  )

  if bool_is_true "${OVERWRITE_CLIENT_CONFIGS}"; then
    cmd+=("--overwrite-client-configs")
  fi

  if [[ -n "${ADMIN_USERNAME}" ]]; then
    cmd+=("--create-admin" "${ADMIN_USERNAME}")
    if [[ -n "${ADMIN_PASSWORD}" ]]; then
      cmd+=("--admin-password" "${ADMIN_PASSWORD}")
    fi
  fi

  info "Importing existing WireGuard state from ${CLIENT_IMPORT_DIR}"
  (
    cd "${APP_DIR}"
    "${cmd[@]}"
  )
}

main() {
  require_root
  validate_mode
  detect_pkg_manager
  resolve_https_flag
  ensure_directory_layout
  install_base_packages
  ensure_nodejs
  backup_existing_state
  sync_source_tree
  reset_app_state_if_requested
  setup_python_env
  write_env_file

  if [[ "${MODE}" == "new" ]]; then
    run_wireguard_install
  fi

  stamp_legacy_db_if_needed
  run_migrations

  case "${MODE}" in
    migrate)
      verify_wireguard_exists
      run_bootstrap_backend
      ;;
    reinstall)
      if bool_is_true "${RESET_APP_STATE}"; then
        verify_wireguard_exists
        run_bootstrap_backend
      else
        create_admin_if_requested
      fi
      ;;
    new)
      create_admin_if_requested
      ;;
  esac

  build_frontend
  write_systemd_unit
  restart_app
  configure_nginx

  info "Installation finished"
  info "Mode: ${MODE}"
  info "App directory: ${APP_DIR}"
  info "Web root: ${WEB_ROOT}"
  if [[ -n "${ADMIN_USERNAME}" ]]; then
    info "Admin user: ${ADMIN_USERNAME}"
  fi
}

main "$@"
