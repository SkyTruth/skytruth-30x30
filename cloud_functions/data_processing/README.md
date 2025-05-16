# Data Processing

The purpose of this Cloud Function is to download, store, process, and update the database with current data related to protected areas. The function is called via a series of Cloud Schedulers.

## Architecture

For architecture, data sources and teh high-level data update plan, please see the [internal documentation][documentation].

## Development

This project is managed using [Poetry][poetry]. Install Poetry, and run `poetry install` from this directory to install dependencies.

### Environment Variables

There are several environment variables that need to be set for local development. These variables are all set by terraform in production, see the [infrastructure docs][infrastructure] for more information. The necessary env vars are defined in `.env.default`. Create a ne file called `.env` adjacent to `.env.default` copy `.env.default` to `.env` and populate with the needed values. These values can be found in GCP secret manager.

Some helpful commands while developing:

* Linting: `poetry run ruff check --fix`
* Formatting: `poetry run ruff format`
* Testing: `poetry run pytest`

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

### Running Deployed Functions

Each method can be run in CLI via a statement like

```shell
gcloud functions call x30-dev-data --data '{"METHOD": "download_habitats"}' --region us-east1
```

There are scheduled monthly jobs to download MPATLAS, Protected Seas, and Protected Planet data. The habitat data and Marine Region data is more or less static and can be run with the above statement.

- #TODO: The Marine Region and habitat filenames are currently hardcoded in params.py and we should update this.

[documentation]: https://drive.google.com/drive/folders/1EkZvHqNViCg__OaCxpPrYIQoTj_YLJIo
[infrastructure]: ../../infrastructure/README.md
[poetry]: https://python-poetry.org/docs/