# Conservation Builder API

Spatial analysis service for the 30x30 Conservation Builder. Given an area a user has drawn on the map, it reports how much of that area is already protected, broken down by location.

It runs on Cloud Run and queries precomputed `data.*` tables in a Cloud SQL PostGIS database. Those tables are produced by `cloud_functions/data_processing`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check, returns `{"status": "ok"}` |

## Configuration

Create a `.env` (copy `example.env` and fill it in). 

```ini
DATABASE_HOST=127.0.0.1
# The local PostGIS in docker-compose.yml is created with these same values
DATABASE_NAME=skytruth_test
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=postgres
DATABASE_PORT=5434
```

In GCP, these are set by Terraform, with the password coming from Secret Manager.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_HOST` | yes | — | Postgres host |
| `DATABASE_NAME` | yes | — | Database name |
| `DATABASE_USERNAME` | yes | — | Postgres user |
| `DATABASE_PASSWORD` | yes | — | Postgres password |
| `DATABASE_PORT` | no | `5432` | |
| `DATABASE_POOL_SIZE` | no | `5` | Connections held open |
| `DATABASE_MAX_OVERFLOW` | no | `5` | Extra connections under load. With the Cloud Run concurrency of 10, `POOL_SIZE + MAX_OVERFLOW` covers a full instance |
| `DATABASE_POOL_RECYCLE_SECONDS` | no | `1800` | Cloud SQL closes idle connections; recycle before it does |

## Running locally

`docker-compose.yml` defines the API and a local test Postgres database.

### Everything in Docker

```bash
docker compose up --build
curl localhost:8080/health
```

### API on your machine, with reload

Start a local Postgres database with PostGIS in Docker, without the API container (published on host port **5434** so it will not interfere with a database already running on 5432).

```bash
poetry install
docker compose up -d postgis
poetry run uvicorn src.main:app --reload
curl localhost:8000/health
```

## Tests

```bash
poetry run pytest                        # everything
poetry run pytest -m "not integration"   # unit tests only, no database needed
```

Integration tests start their own PostGIS container with [Testcontainers](https://testcontainers.com/), so they need Docker running but not `docker compose`. They never connect to any other database. Without Docker they are skipped, except when `CI` is set, where they fail instead.

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
