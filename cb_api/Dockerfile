FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=true \
  POETRY_VIRTUALENVS_IN_PROJECT=true \
  POETRY_VIRTUALENVS_OPTIONS_NO_PIP=true \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  POETRY_HOME='/usr/local'

WORKDIR /app

COPY poetry.lock pyproject.toml ./

RUN POETRY_VERSION="$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["tool"]["poetry"]["requires-poetry"])')" && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "poetry${POETRY_VERSION}" && \
    poetry install --only main && \
    rm -rf "${POETRY_CACHE_DIR}"


FROM python:3.13-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:${PATH}"

RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Nothing installs packages at runtime; pip's vendored libraries only add CVEs
RUN pip uninstall -y pip

RUN addgroup --system --gid 1001 api && \
    adduser --system --uid 1001 --ingroup api api

WORKDIR /app

COPY --from=builder --chown=api:api /app/.venv ./.venv
COPY --chown=api:api src/ ./src/

USER api

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
