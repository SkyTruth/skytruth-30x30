# Conservation Builder API

This is the FastAPI for Conservation Builder replacing `cloud_functions/analysis`.

## Installation
```
poetry install
```

## Running locally
To run it locally:
```
poetry run uvicorn src.main:app --reload
```

```
docker run --rm -p 8080:8080 conservation-builder-api
```

Format
```
poetry run ruff format
```

Linter
```
poetry run ruff check --fix
```
