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

# --resolve: запрос идёт на этот сервер с настоящим сертификатом домена,
# не завися от DNS-кэша самого VPS
RESOLVE="--resolve ${DOMAIN}:443:127.0.0.1"

step "HTTPS https://${DOMAIN}/health/ready"
code="$(curl -s ${RESOLVE} -o /dev/null -w '%{http_code}' "https://${DOMAIN}/health/ready")"
[ "${code}" = "200" ] && ok || bad "(HTTP ${code})"

step "Mini App отдаётся по HTTPS"
code="$(curl -s ${RESOLVE} -o /dev/null -w '%{http_code}' "https://${DOMAIN}/")"
[ "${code}" = "200" ] && ok || bad "(HTTP ${code})"

step "DNS домена указывает на этот VPS"
public_ip="$(curl -4 -s --max-time 5 ifconfig.me)"
dns_ip="$(getent ahostsv4 "${DOMAIN}" | awk 'NR==1{print $1}')"
[ -n "${public_ip}" ] && [ "${public_ip}" = "${dns_ip}" ] && ok || echo "WARN (VPS ${public_ip}, DNS ${dns_ip}; кэш обновится сам)"

step "PostgreSQL не слушает порт на хосте"
ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE ':5432$' && bad "(порт 5432 открыт)" || ok

step "Тесты backend"
docker compose exec -T backend pytest -q >/tmp/contact-pytest.log 2>&1 && ok || bad "(см. /tmp/contact-pytest.log)"

step "Бот без ошибок в логе"
docker compose logs --tail 50 bot 2>&1 | grep -qiE 'error|traceback' && bad "(docker compose logs bot)" || ok

echo
[ "${fail}" -eq 0 ] && echo "ALL_CHECKS_OK" || echo "ЕСТЬ ОШИБКИ — пришлите вывод целиком"
exit "${fail}"
