# CMS / API

This directory contains a [Strapi][strapi] headless CMS, which provides a backoffice and an API for the PostrgreSQL database backing the 30x30 tracker.

Strapi comes with a full featured [Command Line Interface][strapi_cli] (CLI) which lets you scaffold and manage your project in seconds.

## Config

The CMS needs to be configured with server and PostgreSQL database instance connection details. Please check the `.env.example` file for required environment variables. Those are set by Terraform in GH Secrets, and then passed into the docker images during deployment by GH Actions. Please refer to [infrastructure documentation][infrastructure] for details.

### Local Config Setup

In order to make changes to the database schema or to add new data to exiting tables, you need to make the desired changes in the [strapi backoffice][backoffice]. The following steps are also needed for initial development to ensure database configs are in sync with prod, even if no changes are being made to the database. To set this up:

- Create a new Postgres DB on your local machine
- Start your local postgres server
- Install the postgis extension on your new table
- Update the `.env` file to contain the credentials for the local database
- [Build] and [Start the local server][start]
  - This will perform the necessary migrations to make your local database schema match the production DB schema. It does not, however, populate the DB with any data
- Navigate to the [local backoffice][local_backoffice]
- create your personal credentials to log in with
  - There is no local password recovery. If you need to reset local auth, you'll need to start fresh with a new local database
- From the left nav drawer navigate `Settings -> Config Sync -> Interface`
- If there are difference between the DB and the [sync directory][sync] they will be highlighted here. Select Import to sync your DB with the [sync directory][sync]
  - This will synchronize your local DB configs with the production configs

## Run locally

### `develop`

Start your Strapi application with autoReload enabled. [Learn more][strapi_cli_develop]

```
npm run dev
# or
yarn dev
```

### `start`

Start your Strapi application with autoReload disabled. [Learn more][strapi_cli_develop]

```
npm run start
# or
yarn start
```

### `build`

Build your admin panel. [Learn more][strapi_cli_build]

```
npm run build
# or
yarn build
```

### Usage with Docker (recommended)

To run with docker:

docker compose up --build

Open the app at <http://localhost:1337>

## Deploy

Deployment to GCP handled by GH Actions. Please refer to [infrastructure documentation][infrastructure].

## API documentation

The documentation is available at `/documentation` path locally, `/cms/documentation` in staging / production.

## Strapi data models

The data model definitions can be found in `src/api`. Each model corresponds to a database table, with linking tables where there are associations between models.

What is important to note is that the data might be updated differently depending on model.

### Models updated via the admin backoffice

These models are intended to be updated manually.

*For all models which contain a slug, that needs to managed carefully, as it is referenced either in the client application or the data pipelines.*

Models for the Knowledge Hub:

- data-tool
- data-tool-ecosystem
- data-tool-language
- data-tool-resource-type

Layers for the map:

- layer

Static data for the homepage:

- static_indicators
- contact_details

Tooltips and dictionary values for the dashboard:

- data-info
- data-source
- fishing-protection-level
- habitat
- location
- mpa
- mpaa-establishment-stage
- mpaa-protection-level
- protection-status

General configurations

- [feature-flag]

### Updating models via the backoffce

Changes to the database need to be made via the Strapi backoffice locally. To do this, follow the [local config setup instructions][local-config-setup]. Then make your changes in the [local backoffice][local_backoffice]. This will update the corresponding files in the this directory. Merging these changes to the `develop` brach migrate the changes to the staging database and similarly for merges to `main` and the production database

### Models updated by scripts

These models are updated by an import script, which utilises the Strapi import / export API. Please refer to [data documentation][data].

- fishing-protection-level-stat
- habitat-stat
- mpa-protection-coverage-stat
- mpaa-establishment-stage-stat
- mpaa-protection-level-stat
- protection-coverage-stat

## config-sync plugin and configuration version control

This Strapi is configured to use the [config-sync plugin](https://market.strapi.io/plugins/strapi-plugin-config-sync), which allows to version control config data and migrate it between environments.

Examples of configuration under config-sync are user and admin role permissions, API permissions and settings of the admin panel. The consequence of this is that if any settings are changed directly in the staging / production admin panel, but not synced in the repository, they will be overwritten on subsequent deployments.

## Strapi resources

- [Resource center][strapi_rc] - Strapi resource center.
- [Strapi documentation][strapi_docs] - Official Strapi documentation.
- [Strapi tutorials][strapi_tutorials] - List of tutorials made by the core team and the community.
- [Strapi blog][strapi_docs] - Official Strapi blog containing articles made by the Strapi team and the community.
- [Changelog][strapi_changelog] - Find out about the Strapi product updates, new features and general improvements.

Feel free to check out the [Strapi GitHub repository](https://github.com/strapi/strapi). Your feedback and contributions are welcome!

## Feature Flags

The Feature Flag table is intended to be updated from the cms back office and is meant to be used in the front end and within the API. The `find` endpoint for this resource is set up to return records, mainly a catch-all `payload` json blob, if the record is not `archived` and the date is determined to be active. The payload field can contain any kind of data to help programmatically control resources. Use of feature flags is meant to be temporary: for testing, feature releases, etc and flags should be archived after they are no longer in use.

A note on date validity. If a feature flag record has an `active_on` date that feature will be returned if the current date is after the `active_on` date. This can be tested by spoofing the current date with either a query param of `run-as-of` or a request header of `run-as-of`. The request header is given preference if both are set and the value of either should be a string date of the format: `2026-07-12T21:32:42.532Z`

[backoffice]: #updating-models-via-the-backoffce
[build]: #build
[data]: ../data/README.md
[feature-flag]: #feature-flags
[infrastructure]: ../infrastructure/README.md
[local_backoffice]: http://localhost:1337/admin/
[start]: #start
[strapi]:https://strapi.io/
[strapi_changelog]: https://strapi.io/changelog
[strapi_cli]: https://docs.strapi.io/developer-docs/latest/developer-resources/cli/CLI.html
[strapi_cli_build]: https://docs.strapi.io/developer-docs/latest/developer-resources/cli/CLI.html#strapi-build
[strapi_cli_develop]: https://docs.strapi.io/developer-docs/latest/developer-resources/cli/CLI.html#strapi-develop
[strapi_docs]: https://docs.strapi.io
[strapi_rc]: https://strapi.io/resource-center
[strapi_tutorials]: https://strapi.io/tutorials
[sync]: ./config/sync/
