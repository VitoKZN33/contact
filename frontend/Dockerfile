# Контекст сборки — корень репозитория (см. docker-compose.yml, сервис web)

# --- Сборка статического Mini App ---
FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY frontend/package.json frontend/package-lock.json* ./
# С lock-файлом — воспроизводимая установка, без него — по диапазонам версий
RUN if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi

COPY frontend/ ./
RUN npm run build

# --- Nginx: статика + reverse proxy к backend ---
FROM nginx:stable-alpine
COPY infrastructure/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 80 443
