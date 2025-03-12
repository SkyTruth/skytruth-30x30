# 30x30 Progress Tracker REST API Documentation

## Overview

This API provides a single source for accessing open source data related to terrestrial and marine conservation. For most users, we recommend using the 30x30 web application, which provides a visual interface for exploring the complete set of conservation data layers.

## Base URL

```
https://30x30.skytruth.org/cms/api/
```

## Structure

This API uses Strapi's "Populate" structure for querying. This structure allows users to make GraphQL like queries, specifying which data fields and related data entities they want returned. This document will *not* cover the detailed use of this structure, for that please see the [Populate Structure documentation][populate_docs] including the [documentation on available query parameters][parameter_docs].

## Resources

Below are queryable data entities that you can call. For endpoint specific syntax and examples see the [Endpoints] section. Fields marked with a <strong style="color:red"> * </strong>, indicate a related field that can be linked in a query using the `populate` query parameter.

<details>
  <summary>
  Example Success Response</summary>

  ```json
  {
    "example_key": "example_value"
  }
  ```

</details>

## Endpoints

### GET /resource

#### Description

Provide a description of what this endpoint does.

#### Request

- **Headers**: List any required headers.
- **Parameters**: List any query parameters.

<details>
  <summary>
  Example Success Response</summary>

  ```json
  {
    "example_key": "example_value"
  }
  ```

</details>

<details>
  <summary>Success Response Schema</summary>

  ```json
  {
    "type": "object",
    "properties": {
      "example_key": {
        "type": "string"
      }
    }
  }
  ```

</details>

<details>
  <summary>Example Error Response</summary>

  ```json
  {
    "error": "Invalid request",
    "message": "The request parameters are incorrect."
  }
  ```

</details>

<details>
  <summary>Error Response Schema</summary>

  ```json
  {
    "type": "object",
    "properties": {
      "error": {
        "type": "string"
      },
      "message": {
        "type": "string"
      }
    }
  }
  ```

</details>

#### Example

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET "https://api.example.com/v1/resource" -H "Authorization: Bearer <token>"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://api.example.com/v1/resource", {
    method: "GET",
    headers: {
      "Authorization": "Bearer <token>"
    }
  })
  .then(response => response.json())
  .then(data => console.log(data));
  ```

</details>

<details>
  <summary>Python</summary>

  ```python
  import requests

  url = "https://api.example.com/v1/resource"
  headers = {
    "Authorization": "Bearer <token>"
  }

  response = requests.get(url, headers=headers)
  print(response.json())
  ```

</details>

#### Example Responses

<details>
  <summary>
  Example Success Response</summary>

  ```json
  {
    "data": [
        {
            "id": 99,
            "attributes": {
                "coverage": 13.67,
                "protected_area": 4098984.35,
                "pas": 100,
                "oecms": 0,
                "global_contribution": 3.04,
                "location": {
                    "data": {
                        "id": 3,
                        "attributes": {
                            "name": "Africa",
                            "code": "AF"
                        }
                    }
                },
                "environment": {
                    "data": {
                        "id": 2,
                        "attributes": {
                            "name": "Terrestrial"
                        }
                    }
                }
            }
        },
      // ... Data Truncated ...
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "pageSize": 25,
            "pageCount": 1,
            "total": 7
        },
        "updatedAt": "2024-10-18T08:53:17.039Z"
    }
  }
  ```

</details>

## Related Resources

### Data Source

#### Description

Data related to data sources. This field is queryable as a related field to [Protected Areas][protected_areas]. See the note on [data citation][citation]

<details>
  <summary>Data Sources Fields</summary>

  | Name  | Type | Description |
  |-------|------|-------------|
  | slug  | Text | Unique identifier for the data source |
  | title | Text | Title of the data source |
  | url   | Text | URL of the data source |

</details>

### Environment

#### Description

Data related to environments. This field is queryable as a related field to various resources.

<details>
  <summary>Environments Fields</summary>

  | Name | Type | Description |
  |------|------|-------------|
  | name | Text | Name of the environment |
  | slug | Text | Unique identifier for the environment |

</details>

### Fishing Protection Level

#### Description

Data related to fishing protection levels. This field is queryable as a related field to [Fishing Protection Level Stats][fishing_protection_level_stats].

<details>
  <summary>Fishing Protection Level Fields</summary>

  | Name | Type | Description |
  |------|------|-------------|
  | slug | Text | Unique identifier for the fishing protection level |
  | name | Text | Name of the fishing protection level |
  | info | Text | Additional information about the fishing protection level |

</details>

### MPAA Establishment Stage

#### Description

Data related to Marine Protected Area (MPA) establishment stages. This field is queryable as a related field to [Protected Areas][protected_areas].

<details>
  <summary>MPAA Establishment Stage Fields</summary>

  | Name | Type | Description |
  |------|------|-------------|
  | slug | Text | Unique identifier for the MPAA establishment stage |
  | name | Text | Name of the MPAA establishment stage |
  | info | Text | Additional information about the MPAA establishment stage |

</details>

### MPAA Protection Level

#### Description

Data related to Marine Protected Area (MPA) protection levels. This field is queryable as a related field to [MPAA Protection Level Stats][mpaa_protection_level_stats].

<details>
  <summary>MPAA Protection Level Fields</summary>

  | Name | Type | Description |
  |------|------|-------------|
  | slug | Text | Unique identifier for the MPAA protection level |
  | name | Text | Name of the MPAA protection level |
  | info | Text | Additional information about the MPAA protection level |

</details>

### Protection Status

#### Description

Data related to protection status. This field is queryable as a related field to [Protected Areas][protected_areas]

<details>
  <summary>Protection Status Fields</summary>

  | Name | Type | Description |
  |------|------|-------------|
  | slug | Text | Unique identifier for the protection status |
  | name | Text | Name of the protection status |
  | info | Text | Additional information about the protection status |

</details>

<!-- Internal Sections -->
[citation]: #citation
[fishing_protection_level_stats]: #fishing-protection-level-stats
[mpaa_protection_level_stats]: #mpaa-protection-level-stats
[protected_areas]: #protected-areas

<!-- External Resources -->
[parameter_docs]: https://docs.strapi.io/dev-docs/api/rest/parameters
[populate_docs]: https://docs.strapi.io/dev-docs/api/rest/guides/understanding-populate
