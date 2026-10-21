#!/usr/bin/env bash
# Первичный выпуск сертификата Let's Encrypt для DOMAIN из .env.
# Запускать из корня проекта на VPS: bash infrastructure/scripts/issue-cert.sh
set -euo pipefail

cd "$(dirname "$0")/../.."
DOMAIN="$(grep -E '^DOMAIN=' .env | cut -d= -f2- | tr -d '[:space:]')"
if [ -z "${DOMAIN}" ] || [ "${DOMAIN}" = "app.example.ru" ]; then
  echo "ОШИБКА: укажите реальный DOMAIN в .env" >&2
  exit 1
fi

if ! command -v certbot >/dev/null 2>&1; then
  apt-get update && apt-get install -y certbot
fi

PROJECT_DIR="$(pwd)"
# Порт 80 должен быть свободен: останавливаем web, если он запущен
docker compose stop web >/dev/null 2>&1 || true

certbot certonly --standalone --non-interactive --agree-tos \
  --register-unsafely-without-email \
  -d "${DOMAIN}" \
  --pre-hook "docker compose --project-directory ${PROJECT_DIR} stop web" \
  --post-hook "docker compose --project-directory ${PROJECT_DIR} start web"

echo "CERT_OK: /etc/letsencrypt/live/${DOMAIN}/"
echo "Продление настроено автоматически (certbot.timer), web перезапускается хуками."
