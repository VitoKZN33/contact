#!/usr/bin/env bash
# Проверка каркаса после запуска: bash infrastructure/scripts/check.sh
set -uo pipefail

cd "$(dirname "$0")/../.."
DOMAIN="$(grep -E '^DOMAIN=' .env | cut -d= -f2- | tr -d '[:space:]')"
fail=0

step() { printf '%-34s' "$1"; }
ok() { echo "OK"; }
bad() { echo "FAIL $1"; fail=1; }

step "Контейнеры запущены"
running="$(docker compose ps --status running --services | sort | tr '\n' ' ')"
[ "${running}" = "backend bot db web " ] && ok || bad "(${running})"

step "backend /health/ready (внутри)"
docker compose exec -T backend python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=5)" >/dev/null 2>&1 && ok || bad ""

step "HTTPS https://${DOMAIN}/health/ready"
code="$(curl -s -o /dev/null -w '%{http_code}' "https://${DOMAIN}/health/ready")"
[ "${code}" = "200" ] && ok || bad "(HTTP ${code})"

step "Mini App отдаётся по HTTPS"
code="$(curl -s -o /dev/null -w '%{http_code}' "https://${DOMAIN}/")"
[ "${code}" = "200" ] && ok || bad "(HTTP ${code})"

step "PostgreSQL не опубликован наружу"
docker compose port db 5432 >/dev/null 2>&1 && bad "(порт открыт)" || ok

step "Тесты backend"
docker compose exec -T backend pytest -q >/tmp/contact-pytest.log 2>&1 && ok || bad "(см. /tmp/contact-pytest.log)"

step "Бот без ошибок в логе"
docker compose logs --tail 50 bot 2>&1 | grep -qiE 'error|traceback' && bad "(docker compose logs bot)" || ok

echo
[ "${fail}" -eq 0 ] && echo "ALL_CHECKS_OK" || echo "ЕСТЬ ОШИБКИ — пришлите вывод целиком"
exit "${fail}"
