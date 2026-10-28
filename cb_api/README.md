# Conservation Builder API

Spatial analysis service for the 30x30 Conservation Builder. Given an area a user has drawn on the map, it reports how much of that area will have added protection, broken down by location.

It runs on Cloud Run and queries precomputed `data.*` tables in a Cloud SQL PostGIS database. Those tables are produced by `cloud_functions/data_processing`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check, returns `{"status": "ok"}` |
| `POST` | `/coverage` | How much of a drawn area will have added protection coverage, by location |
| `POST` | `/protection-level` | The same, for protection at a given level |
| `POST` | `/habitats` | The same, for one habitat |
| `POST` | `/` | Deprecated alias for `/coverage` |

### `POST /coverage`

`geometry` is required and takes a GeoJSON Feature, FeatureCollection or bare geometry;
it must resolve to a Polygon or MultiPolygon. `environment` is optional and selects the
table the area is compared against (`marine` by default or `terrestrial`).

```bash
curl -X POST localhost:8080/coverage \
  -H 'Content-Type: application/json' \
  -d '{"environment": "marine", "geometry": {"type": "Polygon", "coordinates": [[[146.9,-39.2],[147,-39.2],[147,-39.1],[146.9,-39.1],[146.9,-39.2]]]}}'
```

```json
{
  "locations_area": [{ "code": "AUS", "protected_area": 34.0 }],
  "total_area": 96.0,
  "total_protected_area": 34.0
}
```

Areas are square kilometers, computed in a Mollweide equal-area projection and rounded. `total_area` is the drawn area. `locations_area` breaks it down by location code, and `total_protected_area` is their sum.

`protected_area` and `total_protected_area` are the protected area that would be *added* by the drawn polygon because they're not *currently* protected.

An area that intersects nothing (e.g., a marine request over land) returns zeroes, including `total_area`.

Unrecognized fields in the body are ignored.

### `POST /protection-level`
**Marine only.**

The same as `/coverage`, but for protection at a given level: `protected_area` is the area not yet protected at that level, which the drawn polygon would add. Takes `geometry` and `environment` as above, plus an optional `level` (currently only `fully-highly-protected`, which is the default).

```bash
curl -X POST localhost:8080/protection-level \
  -H 'Content-Type: application/json' \
  -d '{"level": "fully-highly-protected", "geometry": {"type": "Polygon", "coordinates": [[[146.9,-39.2],[147,-39.2],[147,-39.1],[146.9,-39.1],[146.9,-39.2]]]}}'
```

The response is shaped like the one for `/coverage`.

### `POST /habitats`

The same as `/coverage`, but for one habitat: `protected_area` is the area of that habitat not yet protected, which the drawn polygon would add. Takes `geometry` and a **required**
`habitat` (one of `mangroves`, `saltmarshes`, `seagrasses`, `seamounts`, `cold-water-corals`,
`climate-resilient-corals`, `other-corals`). There is no default, and no `environment`:
each habitat has exactly one table.

```bash
curl -X POST localhost:8080/habitats \
  -H 'Content-Type: application/json' \
  -d '{"habitat": "seagrasses", "geometry": {"type": "Polygon", "coordinates": [[[-5,36],[-4.9,36],[-4.9,36.1],[-5,36.1],[-5,36]]]}}'
```

### `POST /` is temporary

The load balancer rewrites the public path to the service root, so the same handler is
registered at `/` as well and is marked deprecated in the schema. It will be removed
once nothing posts to it. New callers should use `/coverage`.

## Configuration

Create a `.env` (copy `example.env` and fill it in) with the details of a local postgres database.

```ini
DATABASE_HOST=host.docker.internal
DATABASE_NAME={database name}
DATABASE_USERNAME={database username}
DATABASE_PASSWORD={database password}
DATABASE_PORT=5432
```

In GCP, these are set by Terraform, with the password coming from Secret Manager. This differs from the other services on purpose to reduce potential secret exposure. Other deploy workflows write `.env` files from GitHub secrets into the image at build time, while Cloud Run gets cb_api's password from Secret Manager when the container starts, so it never enters the image, the registry, or GitHub.

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

```bash
docker compose up --build
curl localhost:8080/health
```

The API container reads `.env` and reloads when files in `src/` change.

## Tests

```bash
poetry install
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
