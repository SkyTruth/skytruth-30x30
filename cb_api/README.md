# Conservation Builder API

Spatial analysis service for the 30x30 Conservation Builder. Given an area a user has
drawn on the map, it reports how much of that area is already protected, broken down by
location.

It runs on Cloud Run and queries precomputed `data.*` tables in a Cloud SQL PostGIS
database. Those tables are produced by `cloud_functions/data_processing`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check, returns `{"status": "ok"}` |

Interactive docs are served at `/docs`, and the schema at `/openapi.json`.

Every response, including errors, carries `Access-Control-Allow-Origin: *`. Errors are
always shaped `{"error": "<message>"}` — 400 when the caller can fix it, 500 otherwise.

## Configuration

Settings are read from the environment, falling back to a `.env` file in this directory.
`.env` is gitignored; copy `example.env` to start. In GCP these are set by Terraform,
with the password coming from Secret Manager.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_HOST` | yes | — | Postgres host |
| `DATABASE_NAME` | yes | — | Database name |
| `DATABASE_USERNAME` | yes | — | Postgres user |
| `DATABASE_PASSWORD` | yes | — | Held as a `SecretStr`, so it cannot leak through a log line or a stack trace |
| `DATABASE_PORT` | no | `5432` | |
| `DATABASE_POOL_SIZE` | no | `5` | Connections held open |
| `DATABASE_MAX_OVERFLOW` | no | `5` | Extra connections under load. With the Cloud Run concurrency of 10, `POOL_SIZE + MAX_OVERFLOW` covers a full instance |
| `DATABASE_POOL_RECYCLE_SECONDS` | no | `1800` | Cloud SQL closes idle connections; recycle before it does |

Startup builds the connection pool but opens no connection, so the service starts
whether or not the database happens to be reachable.

## Running locally

Install dependencies:

```bash
poetry install
```

Start a local PostGIS. It listens on host port **5434**, so it will not collide with a
Postgres already running on 5432:

```bash
docker compose up -d
```

Run the service with reload:

```bash
poetry run uvicorn src.main:app --reload
curl localhost:8080/health
```

### In Docker

```bash
docker build -t cb-api .
docker run --rm -p 8080:8080 --env-file .env cb-api
```

Use
`host.docker.internal` when the API runs in Docker and the database runs beside it.

## Tests

```bash
poetry run pytest                        # everything
poetry run pytest -m "not integration"   # unit tests only, no database needed
```

Integration tests need PostGIS. They skip when nothing is listening, so a plain `pytest` works with no services running, but that also means
`65 passed, 13 skipped` is a run in which the spatial query was never tested. Start
the database first to get all tests.

## Code quality

```bash
poetry run ruff format
poetry run ruff check --fix
```

## Layout

| Path | Contents |
| --- | --- |
| `src/main.py` | App, lifespan, CORS, routes |
| `src/config.py` | Settings |
| `src/db.py` | Engine and connection pool |
| `src/analysis.py` | The spatial query and its result shaping |
| `src/schemas.py` | Request and response models |
| `src/errors.py` | Exception handlers |
