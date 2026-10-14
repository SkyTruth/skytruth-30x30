# Data Processing

The purpose of this Cloud Function is to download, store, process, and update the database with current data related to protected areas. The function is called via a series of Cloud Schedulers.

## Architecture

For architecture, data sources and the high-level data update plan, please see the [internal documentation][documentation].

## Development

This project is managed using [Poetry][poetry]. Install Poetry and then run `poetry install` from this directory to install dependencies.

### Environment Variables

There are several environment variables that need to be set for local development. These variables are all set by terraform in production, see the [infrastructure docs][infrastructure] for more information. The necessary env vars are defined in `.env.default`. Create a new file called `.env` adjacent to `.env.default` copy `.env.default` to `.env` and populate with the needed values. These values can be found in GCP secret manager.

Some helpful commands while developing:

* Linting: `poetry run ruff check --fix`
* Formatting: `poetry run ruff format`
* Testing: `poetry run pytest`

### Daily shared-dataset activity

The shared IHO loader reports after a successful return, including its in-process
cache, and near-shore processing reports after successfully reading the canonical
IHO input. Loading a locally derived near-shore artifact alone does not count as
a new use of the shared input. Failed dataset operations do not report use.

Cloud Run supplies `K_SERVICE`: `x30-prod-data` selects the production producer
and `x30-dev-data` selects development. Other runtimes do not report. Set
`DATASET_USAGE_ENABLED=false` to pause reporting. The SDK uses managed credentials,
coalesces observations by dataset/activity/UTC day and explicitly flushes before
the operation returns. Bounded reporting failures emit diagnostics without failing
the processing operation; no persistent upload queue is created.

The tracking project's reviewed grants allow each runtime identity to create
receipts only inside its registered prefix, without tracking-data read access or
canonical shared-dataset write access. Release requires the new immutable SDK
archive and refreshed Poetry lock/export. Verify production/development receipts,
cached use and reporting outages before marking these producers connected.

### Running the Function Locally

The function could can be run locally for testing either natively or via docker.
Natively:

```shell
poetry run functions-framework --source=./local.py --target=main --port=3001
```

or run it in docker - NOTE: you must have docker and docker-compose installed

```shell
docker compose up --build
```

Either option will expose the function on `http://localhost:3001`. It can be called like:

```shell
curl --location 'http://localhost:3001' \
--header 'Content-Type: application/json' \
--data '{
    "METHOD": "dry_run"
}'
```

If writing to an actual GCP bucket you must be authorized locally to write to and read from the bucket in question.

### Seeding Protected Seas Sites

`seed_protected_seas_sites` is a one-time bootstrap for creating the Protected Seas sites dataset from local Navigator LFP GeoJSON exports. The directory must contain files with `LFP0` through `LFP5` in their names and a filename ending in `_MMDDYY.json`. From the `data_processing` directory, run:

```shell
poetry run python -c 'from src.methods.protected_seas import seed_protected_seas_sites; seed_protected_seas_sites("/path/to/navigator/exports")'
```

The function combines the exports, uploads a dated archive snapshot, and copies that snapshot to the current Protected Seas sites file. By default it uses the bucket and project configured by the local environment; they can also be supplied directly with the `bucket` and `project` arguments. Local GCP credentials must have permission to write to the target bucket.

### Running Deployed Functions

Each method can be run in CLI via a statement like

```shell
gcloud functions call x30-dev-data --data '{"METHOD": "download_habitats"}' --region us-east1
```

The gcloud util has an unchangeable timeout of 5 minutes, so it might be necessary to trigger the function using cURL:

```shell
curl -H "Content-Type: application/json" \
     -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     -d '{"METHOD": "download_habitats"}' \
     --max-time 3600 \
     https://us-east1-x30-399415.cloudfunctions.net/x30-dev-data
```

There are scheduled monthly jobs to download MPATLAS, Protected Seas, and Protected Planet data. The habitat data and Marine Region data is more or less static and can be run with the above statement.

- #TODO: The Marine Region and habitat filenames are currently hardcoded in params.py and we should update this.

[documentation]: https://drive.google.com/drive/folders/1EkZvHqNViCg__OaCxpPrYIQoTj_YLJIo
[infrastructure]: ../../infrastructure/README.md
[poetry]: https://python-poetry.org/docs/
