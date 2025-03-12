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

[Endpoints]: #endpoints
[parameter_docs]: https://docs.strapi.io/dev-docs/api/rest/parameters
[populate_docs]: https://docs.strapi.io/dev-docs/api/rest/guides/understanding-populate