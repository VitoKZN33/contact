#!/usr/bin/env bash
# Обновление на VPS одной командой: bash infrastructure/scripts/deploy.sh
# Порядок: код → сборка → миграции (отдельным шагом) → запуск → сценарии → проверка.
set -euo pipefail

cd "$(dirname "$0")/../.."

echo "== 1/6 Обновляю код"
git pull --ff-only

echo "== 2/6 Собираю образы"
docker compose build

echo "== 3/6 Запускаю базу"
docker compose up -d db

echo "== 4/6 Применяю миграции"
docker compose run --rm --no-deps backend alembic upgrade head

echo "== 5/6 Перезапускаю сервисы"
docker compose up -d

echo "== 6/6 Загружаю сценарии"
docker compose run --rm --no-deps backend python -m app.cli seed

echo
bash infrastructure/scripts/check.sh
