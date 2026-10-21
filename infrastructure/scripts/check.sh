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

step "Миграции применены (head)"
docker compose exec -T backend alembic current 2>/dev/null | grep -q '(head)' && ok || bad "(docker compose run --rm backend alembic upgrade head)"

step "Ключ DeepSeek задан"
grep -qE '^DEEPSEEK_API_KEY=.+' .env && ok || echo "WARN (впишите DEEPSEEK_API_KEY в .env)"

step "Сценарии загружены"
active="$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM scenarios WHERE is_active"' 2>/dev/null | tr -d '[:space:]')"
[ -n "${active}" ] && [ "${active}" -gt 0 ] 2>/dev/null && echo "OK (${active})" || bad "(python -m app.cli seed)"

# --resolve: запрос идёт на этот сервер с настоящим сертификатом домена,
# не завися от DNS-кэша самого VPS
RESOLVE="--resolve ${DOMAIN}:443:127.0.0.1"

step "HTTPS https://${DOMAIN}/health/ready"
code="$(curl -s ${RESOLVE} -o /dev/null -w '%{http_code}' "https://${DOMAIN}/health/ready")"
[ "${code}" = "200" ] && ok || bad "(HTTP ${code})"

step "Mini App отдаётся по HTTPS"
code="$(curl -s ${RESOLVE} -o /dev/null -w '%{http_code}' "https://${DOMAIN}/")"
[ "${code}" = "200" ] && ok || bad "(HTTP ${code})"

step "Поддельный initData отклоняется"
code="$(curl -s ${RESOLVE} -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
  -d '{"init_data":"user=%7B%22id%22%3A1%7D&auth_date=1&hash=deadbeef"}' "https://${DOMAIN}/api/v1/auth/telegram")"
[ "${code}" = "401" ] && ok || bad "(HTTP ${code}, ожидался 401)"

step "API без токена закрыт"
code="$(curl -s ${RESOLVE} -o /dev/null -w '%{http_code}' "https://${DOMAIN}/api/v1/scenarios")"
[ "${code}" = "401" ] && ok || bad "(HTTP ${code}, ожидался 401)"

step "DNS домена указывает на этот VPS"
public_ip="$(curl -4 -s --max-time 5 ifconfig.me)"
dns_ip="$(getent ahostsv4 "${DOMAIN}" | awk 'NR==1{print $1}')"
[ -n "${public_ip}" ] && [ "${public_ip}" = "${dns_ip}" ] && ok || echo "WARN (VPS ${public_ip}, DNS ${dns_ip}; кэш обновится сам)"

step "PostgreSQL не слушает порт на хосте"
ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE ':5432$' && bad "(порт 5432 открыт)" || ok

step "Тесты backend"
if docker compose exec -T backend pytest -q >/tmp/contact-pytest.log 2>&1; then
  echo "OK ($(tail -1 /tmp/contact-pytest.log | tr -d '=' | xargs))"
else
  bad "(полный лог: cat /tmp/contact-pytest.log)"
  grep -E '^(FAILED|ERROR)' /tmp/contact-pytest.log | head -15
  tail -1 /tmp/contact-pytest.log
fi

step "Бот без ошибок в логе"
docker compose logs --tail 50 bot 2>&1 | grep -qiE 'error|traceback' && bad "(docker compose logs bot)" || ok

echo
[ "${fail}" -eq 0 ] && echo "ALL_CHECKS_OK" || echo "ЕСТЬ ОШИБКИ — пришлите вывод целиком"
exit "${fail}"
