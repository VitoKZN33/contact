# «Контакт»

Telegram Mini App — тренажёр живого общения с ИИ-собеседником.

Проектная документация (архитектура, БД, API, план этапов): документ «Контакт — Этап 1» в Claude.

## Состав

| Каталог | Что это |
| --- | --- |
| `backend/` | FastAPI + SQLAlchemy 2 + Alembic, Python 3.12 |
| `bot/` | Telegram-бот на aiogram 3: /start, /help, кнопка Mini App |
| `frontend/` | Next.js (static export) + Tailwind; собирается в образ Nginx |
| `infrastructure/` | шаблон Nginx, скрипты сертификата и проверки |
| `docker-compose.yml` | db, backend, bot, web на одном VPS |

Наружу открыты только порты 80 и 443 (Nginx). PostgreSQL и backend доступны лишь внутри сети Docker.

## Первый запуск на VPS (Ubuntu, через Termius)

Все команды — из-под root или с `sudo`.

**1. Docker** — см. раздел «Установка Docker» ниже, если ещё не установлен.

**2. Код:**

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/VitoKZN33/contact.git
cd /opt/contact
```

Репозиторий приватный: при `git clone` GitHub попросит логин и **Personal Access Token** вместо пароля (GitHub → Settings → Developer settings → Fine-grained tokens, доступ Contents: Read к репозиторию `contact`).

**3. Настройки:**

```bash
cp .env.example .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
sed -i "s/^BOT_INTERNAL_SECRET=.*/BOT_INTERNAL_SECRET=$(openssl rand -hex 32)/" .env
nano .env
```

В `nano` заполните `DOMAIN`, `FRONTEND_URL`, `TELEGRAM_WEBAPP_URL` (одинаковый `https://ваш-домен`), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`. Сохранить: `Ctrl+O`, `Enter`, выйти: `Ctrl+X`.

**4. Сертификат HTTPS** (A-запись домена уже должна указывать на VPS):

```bash
bash infrastructure/scripts/issue-cert.sh
```

**5. Сборка и запуск:**

```bash
docker compose up -d --build
```

Первая сборка занимает 3–6 минут.

**6. Проверка:**

```bash
bash infrastructure/scripts/check.sh
```

Ожидаемый итог — `ALL_CHECKS_OK`. Затем откройте бота в Telegram, нажмите /start и «Открыть «Контакт»»: все три проверки на экране должны быть зелёными.

## Обновление

```bash
cd /opt/contact && bash infrastructure/scripts/deploy.sh
```

Скрипт обновляет код, собирает образы, применяет миграции отдельным шагом, перезапускает сервисы, загружает сценарии и запускает проверку.

## Сценарии

Сценарии лежат в `backend/app/scenarios/seed/*.yaml`. Изменили содержимое — увеличьте `version`: старая версия останется в БД для истории тренировок.

```bash
docker compose run --rm backend python -m app.cli validate          # проверить файлы
docker compose run --rm backend python -m app.cli seed              # загрузить
docker compose run --rm backend python -m app.cli list              # что в БД
docker compose run --rm backend python -m app.cli disable coffee-queue
docker compose run --rm backend python -m app.cli enable coffee-queue
```

## Повседневные команды

```bash
cd /opt/contact
docker compose ps                           # состояние
docker compose logs -f --tail 100 backend   # логи (bot, web, db)
docker compose exec backend pytest -q       # тесты (в отдельной базе contact_test)
docker compose run --rm backend alembic upgrade head   # миграции вручную
```

Миграции не запускаются автоматически при старте контейнеров: это отдельный шаг после `git pull`.

## Установка Docker (Ubuntu 26.04)

Ставится из репозиториев Ubuntu; образы тянутся через зеркало `mirror.gcr.io`, так как Docker Hub с российских адресов работает нестабильно.

```bash
apt update && apt install -y docker.io docker-compose-v2 git
systemctl enable --now docker
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": ["https://mirror.gcr.io"],
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "3"}
}
EOF
systemctl restart docker
docker run --rm hello-world && docker compose version
```

## Безопасность

- `.env` не коммитится и не попадает в образы (`.gitignore`, `.dockerignore`).
- Секреты генерируются на сервере командами из шага 3.
- Бот запускается одним контейнером: два процесса polling на одном токене конфликтуют.
