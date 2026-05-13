# Frontend

This directory contains the code for the Nextjs, React application that is the user interface for the [30x30 application][30x30].

## Config

The client needs to be configured with settings for accessing the API and external services. Please check the `.env.default` file for required environment variables. Those are set partially by Terraform in GH Secrets, and then passed into the docker images during deployment by GH Actions. Some are managed manually in GH Secrets. Please refer to [infrastructure documentation](../infrastructure/README.md) for details.

See [HubSpot configuration details](../hubspot.md).

## Run locally

### Install

Go to the `frontend/` directory and install the dependencies:

```bash
yarn install
```

Copy the .env.example file to .env.default and fill in the fields with values from LastPass.

**Note:**

`HTTP_AUTH_*` and `NEXTAUTH_*` fields enable temporary auth with a hardcoded user/pass for pre-launch purposes. If all fields are set, a username and password will be required. Auth details are available on LastPass.

### Automatic Type Building

This app makes use of [Orval][orval] to automatically generate types and data fetching hooks for endpoints created by the [Strapi API][strapi]. These types and helper functions are generated using files that are created at build time for the Strapi API and are re-built when starting the dev server. Before starting the dev server it's good to make sure you have the most up-to-date build of the API. Please Follow the [instructions to build the API][cms_build] when you first clone the repo and every time you pull an update from `main`.

### Start

Start the client with:

```bash
yarn dev
```

### Usage with Docker (recommended)

To run with docker:

docker-compose up --build

Open the app at <http://localhost:3000>

## Location name resolution

Location display names (countries, regions, "Global", "High Seas", etc.) are
resolved at render time rather than read from the database. The resolver lives
at `src/lib/i18n/locationName.ts` and is consumed via the `useLocationName()`
hook (`src/hooks/use-location-name.ts`).

Resolution order:

1. `type === 'country'` with a `*` suffix — strip the suffix, resolve the base
   country, then wrap with the `locations.andTerritories` template (e.g.
   `USA*` → "United States and Territories").
2. `type === 'country'` — English override map (`EN_COUNTRY_OVERRIDES` in the
   resolver) applied only when locale is `en`; otherwise
   `Intl.DisplayNames` with the alpha-2 code derived via `i18n-iso-countries`.
3. `type ∈ { region, custom_region, worldwide, highseas }` — Localazy key
   under `locations.<type>.<code>` in `translations/en.json` (translators fill
   in non-English values).
4. Any other type (`inactive`, `inactive_region`, unknown) — falls through to
   the raw code so misses are visible in the UI. These are admin-only today.

### Adding a new bespoke region

1. Pick a stable uppercase code and `type` (one of `region`, `custom_region`,
   `worldwide`, `highseas`).
2. Add the English string to `translations/en.json` under
   `locations.<type>.<code>`.
3. Push the source to Localazy so translators can pick up the new key.
4. Insert the row into Strapi with the matching `code` and `type`. No
   `name_*` columns are needed for new entries.

### Adding an English override for a country

Edit `EN_COUNTRY_OVERRIDES` in `src/lib/i18n/locationName.ts`. Keep the map
small — CLDR is the default and overrides exist only where product copy
differs from CLDR's style.

### Importing `i18n-iso-countries`

Always import from `i18n-iso-countries/index` (not the package root). The
default entry point eagerly registers every supported locale JSON, which
inflates the bundle by hundreds of KB; we only need `alpha3ToAlpha2`.

[30x30]: https://30x30.skytruth.org/
[strapi]: ../cms/README.md
[cms_build]: ../cms/README.md#build
[orval]: https://orval.dev/overview
