# skytruth-30x30
SkyTruth 30x30 Tracker is a compelling online experience that builds momentum towards meeting global biodiversity targets by unlocking opportunities for protecting the marine environment and forging connections with the wider 30x30 community.

## Maintenance documentation

### Key Components
- *Next.js Client*: The client-side application is developed using Next.js, a React framework that facilitates server-side rendering and efficient client-side navigation.

- *Strapi Headless CMS*: The back-end application is implemented using Strapi, which provides a flexible content management system and exposes APIs for dynamic data retrieval.

- *Analysis Cloud Function*: On-the-fly analysis results are generated through a cloud function, which connects to a spatially enabled PostgreSQL database.

- *Data Pipelines*: Data pipelines are responsible for feeding structured data into the SQL database and layers into Mapbox.

External services:

- *Mapbox*: used for serving layers for the map

- *HubSpot*: used for the contact form, see [configuration instructions][hubspot]

This repository contains all the code and documentation necessary to set up and deploy the project. It is organised in 5 main subdirectories, with accompanying documentation inside each.

| Subdirectory name        | Description                                                                                      | Documentation                               |
|--------------------------|--------------------------------------------------------------------------------------------------|---------------------------------------------|
| frontend                 | The Next.js client application                                                                   | [frontend][frontend]                        |
| cms                      | The Strapi CMS / API                                                                             | [cms]                                       |
| cloud_functions/analysis | The on-the-fly analysis cloud function                                                           | [cloud functions][cloud_functions_analysis] |
| data                     | The Python data importers and uploaders                                                          | [data]                                      |
| infrastructure           | The Terraform project & GH Actions workflow (provisioning & deployment to Google Cloud Platform) | [infrastructure]                            |


### Deployment and Infrastructure
The project is deployed on the Google Cloud Platform (GCP) using GitHub Actions for continuous integration and deployment. The infrastructure is provisioned and managed using Terraform scripts, ensuring consistent and reproducible deployments.

### Development
In General each of subdirectories listed above act as standalone services and can be developed in isolation. For detailed instructions on development in those services please see the linked README's for the given service. There are, however, a few exceptions to this which are outlined below.

#### Frontend Typescript Types
Type definitions and internal data fetching hooks are automatically generated via integrations with [Orval][orval] and [Strapi][strapi]. Please see the [frontend documentation][frontend_types] for how to manage this dependency when developing locally.

#### Development Hooks
This repo uses `husky` to manage development flow hooks. There are hooks for: `pre-commit`, `post-checkout`, and `post-merge`. These hooks ensure the code is linted and formatted, as well as ensuring that generated types are up to date and the Strapi CMS config models are all up to date. For these checks to pass you must have an accurate `.env` file in the CMS directory and have the config file synced from the Strapi back office. Please refer to the [developing strapi docs][strapi_config] and the [strapi config sync docs][strapi_config_sync] to set this up prior to branching and committing. 

[cloud_functions_analysis]: cloud_functions/analysis/README.md
[cms]: cms/README.md
[data]: data/README.md
[frontend]: frontend/README.md
[frontend_types]: frontend/README.md#automatic-type-building
[hubspot]: hubspot.md
[infrastructure]: infrastructure/README.md
[orval]: https://orval.dev/overview
[strapi]: https://strapi.io/
[strapi_config_sync]: cms/README.md#config-sync-plugin-and-configuration-version-control
[strapi_config]: cms/README.md#local-config-setup