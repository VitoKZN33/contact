FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py \
    && pip install . \
    && pip uninstall -y contact-bot \
    && rm -rf app build *.egg-info

COPY app ./app

RUN useradd --system --uid 10002 botuser
USER botuser

CMD ["python", "-m", "app.main"]
