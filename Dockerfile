# syntax=docker/dockerfile:1

# Assumes pyproject.toml + uv.lock, and a Flask app object at app:app
# (change the gunicorn target below if yours lives elsewhere, e.g. "myapp.main:app").
# Add gunicorn to your deps: `uv add gunicorn`

ARG PYTHON_VERSION=3.14

# ---- builder ----
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first (cached unless lockfile changes)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Then install the project itself
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- runtime ----
FROM python:${PYTHON_VERSION}-slim AS runner

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000

RUN useradd --system --uid 1001 --create-home appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app

USER appuser
EXPOSE 5000
CMD ["sh", "-c", "flask --app main run --host 0.0.0.0 --port ${PORT}"]
