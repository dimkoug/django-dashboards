# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

# - PYTHONDONTWRITEBYTECODE: no .pyc files in the image
# - PYTHONUNBUFFERED: stream logs straight to the container stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq5 is the runtime library psycopg (psycopg3) loads to talk to Postgres.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install deps first so the layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# App source.
COPY . .

# Run as an unprivileged user; give it ownership of the collected static/media dirs.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/staticfiles /app/mediafiles \
    && chmod +x /app/entrypoint.sh \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
# Async ASGI server. backend.asgi:application is the Django ASGI entrypoint.
CMD ["uvicorn", "backend.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "3"]
