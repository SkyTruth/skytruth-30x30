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

Open the app at http://localhost:3000

[30x30]: https://30x30.skytruth.org/
[cms]: ../cms/README.md
[cms_build]: ../cms/README.md#build
[orval]: https://orval.dev/overview