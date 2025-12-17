# 30x30 Progress Tracker REST API Documentation

## Overview

This API provides a single source for accessing open source data related to terrestrial and marine conservation. For most users, we recommend using the 30x30 web application, which provides a visual interface for exploring the complete set of conservation data layers.

## ⚠️ ${\color{red}Upcoming \space Breaking \space Changes}$ ⚠️

A major update of the API will occur sometime in between December 2025 and March 2026 that will introduce breaking changes to the API response contract. We will notify our users of this change when it is planned. In order to safeguard yourself against these changes you can add the following header to your request

${\color{lightgreen} Strapi-Response-Format: v4}$

## Base URL

```bash
https://30x30.skytruth.org/cms/api/
```

## Structure

This API uses Strapi's "Populate" structure for querying. This structure allows users to make GraphQL like queries, specifying which data fields and related data entities they want returned. This document will *not* cover the detailed use of this structure, for that please see the [Populate Structure documentation][populate_docs] including the [documentation on available query parameters][parameter_docs].

## Citation

To cite SkyTruth, pluse use:

SkyTruth [30x30 Progress Tracker](https://30x30.skytruth.org/), 2025, licensed under CC BY-SA, [modifications made, if any] by [you, the creator].

In order to get sources for individual protected areas you can add query params to your search to populate the [Data Source][data_source] fields. Data Sources belong to [Protected Areas][protected_areas], which belong to [Locations][location]. For resources that have Location as as a field, e.g. [Protection Coverage Stats][protection_coverage_stats], the data source can be added to the response with the query params:

```txt
populate[location][populate][pas][populate][data_source][fields]=*
```

Locations which are parents to other locations, typically with `type = region`, e.g. `Europe`, don't have Protected Areas associated with them. In order to query citable data sources for these locations you mus populate the Locations children Locations:

```txt
populate[location][populate][members][populate][pas][populate][data_source][fields]=*
```

Note: The above query param will return a large quantity of data as it returns all of the data citations for all of the Protected Areas in all of the countries in the given region.

## Requests

* **Headers**:
  * `Content-Type: application/json;`
* **Parameters**:
  * `locale=<en | es | fr>`
    * When translations are available, sets response language (es: English, en: Español, fr: Française)
  * See the [parameter docs][parameter_docs] for all other parameters

## Responses

As a result of the Populate structure of the API the success response schemas will vary depending on the query and several examples are given below.

Error Responses are fairly consistent and take on the form:

  ```json
  {
    {
      "data": null,
      "error": {
          "status": 404,
          "name": "NotFoundError",
          "message": "Not Found",
          "details": {}
      }
    }
  } 
  ```

## Resources

### Queryable Resources Table of Contents

* [Fishing Protection Level Stats][fishing_protection_level_stats]
* [Habitat Stats][habitat_stats]
* [Locations][location]
* [Marine Protection Level Stats][mpaa_protection_level_stats]
* [Protected Areas][protected_areas]
* [Protection Coverage Stats][protection_coverage_stats]
* [Aggregated Stats][aggregated_stats]

### Related Resources Table of Contents

* [Data Sources][data_source]
* [Environments][environment]
* [Fishing Protection Level][fishing_protection_level]
* [Marine Protection Level][mpaa_protection_level]
* [Marine Protection Level Establishment Stage][mpaa_stage]
* [Protection Status][protection_status]

## Queryable Resources and Endpoints

Below are queryable data entities and their related data that you can request. Fields marked with a 🖇️ indicate a related field that can be linked in a query using the `populate` query parameter.

## Fishing Protection Level Stats

### Description

Data related to fishing protection levels.

<details>
  <summary>Fishing Protection Level Stats Fields</summary>

  | Name                     | Type                                | Description |
  |--------------------------|-------------------------------------|-------------|
  | location                 | Relation with Location 🖇️           | [Location][location] |
  | fishing_protection_level | Relation with Fishing Protection Level 🖇️ | [Fishing Protection Level][fishing_protection_level_stats] |
  | area                     | Number                              | Protected area in km&#178; |
  | pct                      | Number                              | Percentage of the total location area that is protected |

</details>

### End Points

* `GET /fishing-protection-level-stats`
* `GET /fishing-protection-level-stats/{id}`

### Example Requests

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET --globoff 'https://30x30.skytruth.org/cms/api/fishing-protection-level-stats?populate[fishing_protection_level][fields]=name&populate[fishing_protection_level][fields]=info&populate[location][fields]=name' \
  -H "Content-Type: application/json;"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://30x30.skytruth.org/cms/api/fishing-protection-level-stats?populate[fishing_protection_level][fields]=name&populate[fishing_protection_level][fields]=info&populate[location][fields]=name", {
    method: "GET",
    headers: {
      "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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

  url = "https://30x30.skytruth.org/cms/api/fishing-protection-level-stats?populate[fishing_protection_level][fields]=name&populate[fishing_protection_level][fields]=info&populate[location][fields]=name"
  headers = {
    "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
  }

  response = requests.get(url, headers=headers)
  print(response.json())
  ```

</details>

### Example Responses

<details>
  <summary>
  Example Success Response</summary>

  ```json
  {
    "data": [
        {
            "id": 1,
            "attributes": {
                "area": 704165.07,
                "createdAt": "2024-10-10T13:33:42.833Z",
                "updatedAt": "2024-10-10T13:33:42.828Z",
                "pct": 4.73,
                "fishing_protection_level": {
                    "data": {
                        "id": 1,
                        "attributes": {
                            "name": "Highly",
                            "info": "MPAs that are highly protected from fishing (e.g., Most Restrictive or Heavily Restrictive LFP score) based on ProtectedSeas. Learn more at https://navigatormap.org."
                        }
                    }
                },
                "location": {
                    "data": {
                        "id": 3,
                        "attributes": {
                            "name": "Africa"
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
            "pageCount": 20,
            "total": 492
        }
    }
  }
  ```

</details>

## Habitat Stats

### Description

Data related to habitat statistics.

<details>
  <summary>Habitat Stats Fields</summary>

  | Name            | Type                        | Description |
  |-----------------|-----------------------------|-------------|
  | location        | Relation with Location 🖇️   | [Location][location] |
  | habitat         | Relation with Habitat 🖇️    | [Habitat][habitat] |
  | year            | Number                      | Year of the habitat stat |
  | protected_area  | Number                      | Protected area in km&#178; |
  | total_area      | Number                      | Total area in km&#178; |
  | environment     | Relation with Environment 🖇️ | [Environment][environment] |

</details>

### End Points

* `GET /habitat-stats`
* `GET /habitat-stats/{id}`

### Example Requests

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET --globoff 'https://30x30.skytruth.org/cms/api/habitat-stats?filters[location][type]=region&populate[habitat][fields]=name&populate[location][fields]=name' \
  -H "Content-Type: application/json;"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://30x30.skytruth.org/cms/api/habitat-stats?filters[location][type]=region&populate[habitat][fields]=name&populate[location][fields]=name", {
    method: "GET",
    headers: {
      "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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

  url = "https://30x30.skytruth.org/cms/api/habitat-stats?filters[location][type]=region&populate[habitat][fields]=name&populate[location][fields]=name"
  headers = {
    "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
  }

  response = requests.get(url, headers=headers)
  print(response.json())
  ```

</details>

### Example Responses

<details>
  <summary>
  Example Success Response</summary>

  ```json
  {
    "data": [
        {
            "id": 1999,
            "attributes": {
                "year": 2020,
                "protected_area": 27151.74,
                "total_area": 39893.44,
                "createdAt": "2024-12-11T08:06:30.082Z",
                "updatedAt": "2024-12-11T08:06:30.079Z",
                "habitat": {
                    "data": {
                        "id": 5,
                        "attributes": {
                            "name": "Mangroves"
                        }
                    }
                },
                "location": {
                    "data": {
                        "id": 8,
                        "attributes": {
                            "name": "Latin America & Caribbean"
                        }
                    }
                }
            }
        }
        // ... data truncated ...
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "pageSize": 25,
            "pageCount": 4,
            "total": 85
        },
        "updatedAt": "2024-12-11T08:06:30.100Z"
    }
  }
  ```

</details>

## Aggregated Stats

### Description

An endpoint for fetching other types of statistics aggregated across multiple locations and grouped by user defined fields.

### Query params

* stats: comma separated string that dictates which type or types of statistics will be returned
  * Valid options: `protection_coverage`, `habitat`, `mpaa_protection_level`, `fishing_protection_level`
* year: 4 digit year for which stats will be returned.
  * Only valid for `protection_coverage` and `habitat`
  * Omitting will return all years of available data grouped by year
* environment: the environment for which returned stats are valid
  * Only valid for `protection_coverage` and `habitat`
  * Omitting will return data from all environments grouped by environment
  * Valid options: `marine` and `terrestrial`
* habitat: the habitat for which returned stats are valid
  * Only valid for `habitat`
  * Omitting will return data from all habitats grouped by habitat
  * Valid options depend on environment:
    * Terrestrial: `artificial`, `desert`, `forrest`, grassland`, rocky-mountains`, `savanna`
    * Marine: `cold-water corals`, `mangroves`, `saltmarshes`, `seagrasses`, `seamounts`, `warm-water corals`, `wetland-open-waters`
* fishing_protection_level: the fishing protection level for which stats are returned
  * Only valid for `fishing_protection_level` stats
  * Omitting will return data for all fishing protection levels grouped by level
  * Valid options: `highly`, `less`, `moderately`
* mpaa_protection_level: the protection level for which stats are returned
  * Only valid for `mpaa_protection_level` stats
  * Omitting will return data for all protection levels grouped by level
  * Valid options: 'full', `high`, `fully-highly-protected`, `light`, `minimal`, `unknown`, `incompatible`


<details>
  <summary>Aggregated Stats Fields</summary>

  | Name            | Type                        | Description |
  |-----------------|-----------------------------|-------------|
  | locations       | Relation with Location 🖇️   | [Location][location] just the location code is returned|
  | habitat         | Relation with Habitat 🖇️    | [Habitat][habitat] just the habitat slug |
  | year            | Number                      | Year of the aggregated stat |
  | protected_area  | Number                      | Protected area in km&#178; |
  | total_area      | Number                      | Total area in km&#178; |
  | coverage        | Number                      | Percent of total area covered by protection metric |
  | total_area      | Number                      | Total area in km&#178; |
  | environment     | Relation with Environment 🖇️ | [Environment][environment] just the slug is returned|

</details>

### End Points

* `GET /aggregated-stats`

### Example Requests

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET --globoff 'https://30x30.skytruth.org/cms/api/aggregated-stats/?year=2025&locations=USA%2CMEX%2CCAN&stats=habitat%2Cprotection_coverage%2Cmpaa_protection_level%2Cfishing_protection_level&mpaa_protection_level=fully-highly-protected' \
  -H "Content-Type: application/json;"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://30x30.skytruth.org/cms/api/aggregated-stats/?year=2025&locations=USA%2CMEX%2CCAN&stats=habitat%2Cprotection_coverage%2Cmpaa_protection_level%2Cfishing_protection_level&mpaa_protection_level=fully-highly-protected'", {
    method: "GET",
    headers: {
      "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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

  url = "https://30x30.skytruth.org/cms/api/aggregated-stats/?year=2025&locations=USA%2CMEX%2CCAN&stats=habitat%2Cprotection_coverage%2Cmpaa_protection_level%2Cfishing_protection_level&mpaa_protection_level=fully-highly-protected'"
  headers = {
    "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
  }

  response = requests.get(url, headers=headers)
  print(response.json())
  ```

</details>

### Example Responses

<details>
  <summary>
  Example Success Response</summary>

  ```json
  {
    "data": {
        "habitat": [
            {
                "year": 2025,
                "environment": "marine",
                "habitat": "warm-water corals",
                "total_area": 5650.45,
                "protected_area": 4663.12,
                "locations": [
                    "MEX",
                    "USA"
                ],
                "coverage": 82.52652443610687
            },
            {
                "year": 2025,
                "environment": "terrestrial",
                "habitat": "rocky-mountains",
                "total_area": 135770.79,
                "protected_area": 61654.880000000005,
                "locations": [
                    "CAN",
                    "MEX",
                    "USA"
                ],
                "coverage": 45.411004826590464
            },
            //... Truncated
        ],
        "protection_coverage": [
            {
                "year": 2025,
                "environment": "terrestrial",
                "total_area": 21385230,
                "protected_area": 2903469.09,
                "locations": [
                    "CAN",
                    "MEX",
                    "USA"
                ],
                "coverage": 13.576983226273459
            },
            {
                "year": 2025,
                "environment": "marine",
                "total_area": 17530540,
                "protected_area": 3201545.7199999997,
                "locations": [
                    "CAN",
                    "MEX",
                    "USA"
                ],
                "coverage": 18.2626759928673
            }
        ],
        "mpaa_protection_level": [
            {
                "mpaa_protection_level": "fully-highly-protected",
                "total_area": 17663476,
                "protected_area": 1681172.2899999998,
                "locations": [
                    "CAN",
                    "MEX",
                    "USA"
                ],
                "coverage": 9.517788514559648
            }
        ],
        "fishing_protection_level": [
            {
                "fishing_protection_level": "highly",
                "total_area": 17594270,
                "protected_area": 2053201.3900000001,
                "locations": [
                    "CAN",
                    "MEX",
                    "USA"
                ],
                "coverage": 11.669716276946984
            },
            {
                "fishing_protection_level": "less",
                "total_area": 17594270,
                "protected_area": 13786414.26,
                "locations": [
                    "CAN",
                    "MEX",
                    "USA"
                ],
                "coverage": 78.35740988401338
            },
            {
                "fishing_protection_level": "moderately",
                "total_area": 17594270,
                "protected_area": 1754928.96,
                "locations": [
                    "CAN",
                    "MEX",
                    "USA"
                ],
                "coverage": 9.97443463127484
            }
        ]
    }
}
  ```

</details>

## Locations

### Description

Data related to locations.

<details>
  <summary>Locations Fields</summary>

  | Name                          | Type                                      | Description |
  |-------------------------------|-------------------------------------------|-------------|
  | code                          | Text                                      | Location code |
  | name                          | Text                                      | Location Name |
  | total_marine_area             | Number                                    | Total marine area in km&#178; |
  | type                          | Text                                      | Type of location `<country \| region \| worldwide \| highseas>`
  | groups                        | Relation with Location 🖇️                 | Groups location belongs to, e.g. Angola belongs to the group Africa  |
  | members                       | Relation with Location 🖇️                 | Members within the location e.g. Africa has Angola as a member |
  | fishing_protection_level_stats| Relation with Fishing Protection Level Stats 🖇️ | [Fishing Protection Level Stats][fishing_protection_level_stats] |
  | mpaa_protection_level_stats   | Relation with MPAA Protection Level Stats 🖇️ | [MPAA Protection Level Stats][mpaa_protection_level_stats] |
  | protection_coverage_stats     | Relation with Protection Coverage Stats 🖇️ | [Protection Coverage Stats][protection_coverage_stats] |
  | marine_bounds                 | Array                                     | Bounding box of the locations marine area |
  | total_terrestrial_area        | Number                                    | Total terrestrial area in km&#178; |
  | terrestrial_bounds            | JSON                                      | Bounding box of the locations marine area |
  | name_es                       | Text                                      | Name of the location in Spanish |
  | name_fr                       | Text                                      | Name of the location in French |
  | marine_target                 | Number                                    | Marine conversation target area in % |
  | marine_target_year            | Number                                    | Target year by which to reach to the `marine_target` |
  | pas                           | Relation with PA 🖇️                       | [Protected Areas][protected_areas] within the location |

</details>

### End Points

* `GET /locations`
* `GET /locations/{id}`

### Example Requests

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET --globoff 'https://30x30.skytruth.org/cms/api/locations?filters[code][%24eq]=CHL&populate[groups][fields]=name' \
  -H "Content-Type: application/json;"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://30x30.skytruth.org/cms/api/locations?filters[code][%24eq]=CHL&populate[groups][fields]=name", {
    method: "GET",
    headers: {
      "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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

  url = "https://30x30.skytruth.org/cms/api/locations?filters[code][%24eq]=CHL&populate[groups][fields]=name"
  headers = {
    "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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
            "id": 30,
            "attributes": {
                "code": "CHL",
                "name": "Chile",
                "total_marine_area": "3668775",
                "type": "country",
                "marine_bounds": [
                    -113.19655,
                    -59.85268,
                    -65.72667,
                    -18.35012
                ],
                "total_terrestrial_area": "752264",
                "terrestrial_bounds": [
                    -109.45491,
                    -55.98,
                    -66.41821,
                    -17.49859
                ],
                "name_es": "Chile",
                "name_fr": "Chili",
                "marine_target": 30,
                "marine_target_year": 2030,
                "createdAt": "2024-10-08T22:34:17.631Z",
                "updatedAt": "2024-10-11T13:19:42.431Z",
                "groups": {
                    "data": [
                        {
                            "id": 8,
                            "attributes": {
                                "name": "Latin America & Caribbean"
                            }
                        }
                    ]
                }
            }
        }
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "pageSize": 25,
            "pageCount": 1,
            "total": 1
        }
    }
}
  ```

</details>

### MPAA Protection Level Stats

#### Description

Data related to Marine Protected Area (MPA) protection levels.

<details>
  <summary>MPAA Protection Level Stats Fields</summary>

  | Name                     | Type                                | Description |
  |--------------------------|-------------------------------------|-------------|
  | mpaa_protection_level    | Relation with MPAA Protection Level 🖇️ | [MPAA Protection Level][mpaa_protection_level] |
  | area                     | Number                              | Area of the MPA in km&#178; |
  | percentage               | Number                              | Percentage of the total Location area covered by the MPA |
  | location                 | Relation with Location 🖇️           | [Location][location] |

</details>

#### End Points

* `GET /mpaa-protection-level-stats`
* `GET /mpaa-protection-level-stats/{id}`

#### Example Requests

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET --globoff 'https://30x30.skytruth.org/cms/api/mpaa-protection-level-stats?populate[location][fields]=name&filter[location][type][%24eq]=region&populate[mpaa_protection_level][fields]=name' \
  -H "Content-Type: application/json;"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://30x30.skytruth.org/cms/api/mpaa-protection-level-stats?populate[location][fields]=name&filter[location][type][%24eq]=region&populate[mpaa_protection_level][fields]=name", {
    method: "GET",
    headers: {
      "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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

  url = "https://30x30.skytruth.org/cms/api/mpaa-protection-level-stats?populate[location][fields]=name&filter[location][type][%24eq]=region&populate[mpaa_protection_level][fields]=name"
  headers = {
    "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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
            "id": 1,
            "attributes": {
                "mpaa_protection_level": {
                    "data": {
                        "id": 1,
                        "attributes": {
                            "name": "High"
                        }
                    }
                },
                "area": 1500,
                "percentage": 75,
                "location": {
                    "data": {
                        "id": 1,
                        "attributes": {
                            "name": "Pacific Ocean"
                        }
                    }
                }
            }
        }
        // ... truncated...
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "pageSize": 25,
            "pageCount": 2,
            "total": 36
        }
    }
  }
  ```

</details>

### Protected Areas

#### Description

Data related to world protected areas.
<details>
  <summary>Protected Areas Fields</summary>

  | Name                     | Type                                | Description |
  |--------------------------|-------------------------------------|-------------|
  | name                     | Text                                | Name of PA |
  | area                     | Number                              | Spacial area in km&#178; |
  | year                     | Number                              | Year the PA was established  |
  | protection_status        | Relation with Protection Status 🖇️  | [Protection Status][protection_status] |
  | bbox                     | Array                               | Bounding box of PA |
  | children                 | Relation with PA 🖇️                 | PA's contained within the given PA |
  | data_source              | Relation with Data Source 🖇️        | [Data Source][data_source] |
  | mpaa_establishment_stage | Relation with MPAA Establishment Stage 🖇️ | [MPAA Establishment Stage][mpaa_stage] |
  | location                 | Relation with Location 🖇️           | [Location][location] |
  | wdpaid                   | Number                              | ID reference for WPDA |
  | mpaa_protection_level    | Relation with MPAA Protection Level 🖇️ | [MPAA Protection Level][mpaa_protection_level] |
  | iucn_category            | Relation with MPA iucn category 🖇️  | [MAP IUCN Category][pa_iucn_category] |
  | designation              | Text                                | Descriptive protection designation |
  | environment              | Relation with Environment 🖇️        | [Environment][environment] |
  | coverage                 | Number                              | Percent of [location] area covered by the PA, values less than 0.1% round to 0 |
  | parent                   | Relation with PA 🖇️                 | PA which contained the given PA |

</details>

#### End Points

* `GET /pas`
* `GET /pas/{id}`

#### Example Requests

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET --globoff 'https://30x30.skytruth.org/cms/api/pas?fields[]=*&populate[location][fields]=name&populate[data_source][fields]=url&populate[data_source][fields]=title&pagination[pageSize]=1' \
  -H "Content-Type: application/json;"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://30x30.skytruth.org/cms/api/pas?fields[]=*&populate[location][fields]=name&populate[data_source][fields]=url&populate[data_source][fields]=title&pagination[pageSize]=1", {
    method: "GET",
    headers: {
      "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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

  url = "https://30x30.skytruth.org/cms/api/pas?fields[]=*&populate[location][fields]=name&populate[data_source][fields]=url&populate[data_source][fields]=title&pagination[pageSize]=1"
  headers = {
    "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
  }

  response = requests.get(url, headers=headers)
  print(response.json())
  ```

</details>

#### Example Response

<details>
  <summary>
    Example Success Response
  </summary>

  ```json
  {
    {
      "data": [
          {
              "id": 10,
              "attributes": {
                  "name": "Archipielago Juan Fernadez",
                  "area": 56.1,
                  "year": 1935,
                  "bbox": [
                      -80.83396174699999,
                      -33.811142937,
                      -78.757773316,
                      -33.60018271000001
                  ],
                  "wdpaid": "97",
                  "designation": "National Park",
                  "coverage": 0,
                  "createdAt": "2024-10-08T15:36:02.347Z",
                  "updatedAt": "2024-10-11T09:38:10.532Z",
                  "location": {
                      "data": {
                          "id": 30,
                          "attributes": {
                              "name": "Chile"
                          }
                      }
                  },
                  "data_source": {
                      "data": {
                          "id": 3,
                          "attributes": {
                              "url": "https://www.protectedplanet.net/en/search-areas?geo_type=site&filters%5Bis_type%5D%5B%5D=marine",
                              "title": "Protected Planet"
                          }
                      }
                  }
              }
          }
      ],
      "meta": {
        "pagination": {
            "page": 1,
            "pageSize": 1,
            "pageCount": 306126,
            "total": 306126
        }
      }
    }
  }
  ```

</details>

### Protection Coverage Stats

#### Description

Data related to protection coverage statistics.

<details>
  <summary>Protection Coverage Stats Fields</summary>

  | Name                     | Type                                | Description |
  |--------------------------|-------------------------------------|-------------|
  | location                 | Relation with Location 🖇️           | [Location][location] |
  | year                     | Number                              | Year of the coverage stat |
  | protected_area           | Number                              | Protected area in km&#178; |
  | protected_areas_count    | Number                              | Number of protected areas |
  | environment              | Relation with Environment 🖇️        | [Environment][environment] |
  | coverage                 | Number                              | Amount of [location] covered by protected areas in percent |
  | pas                      | Number                              | Percent of coverage made up by Protected Areas |
  | oecms                    | Number                              | Percent of coverage made up by Other effective area-based conservation measures |
  | is_last_year             | Boolean                             | Indicates if it is the last year of data |
  | global_contribution      | Number                              | Contribution to global conservation in percent |

</details>

#### End Points

* `GET /protection-coverage-stats`
* `GET /protection-coverage-stats/{id}`

#### Example Requests

This example gets terrestrial protected area stats for all regions

<details>
  <summary>cURL</summary>

  ```bash
  curl -X GET --globoff 'https://30x30.skytruth.org/cms/api/protection-coverage-stats?fields[]=coverage&fields[]=protected_area&fields[]=pas&fields[]=oecms&fields[]=global_contribution&populate[location][fields][0]=name&filters[environment][slug][%24eq]=terrestrial&filters[location][type][%24eq]=region&sort=location.name%3Aasc%2Cenvironment.name%3Aasc&populate[location][fields]=code&filters[is_last_year][%24eq]=true' \
  -H "Content-Type: application/json;"
  ```

</details>

<details>
  <summary>JavaScript</summary>

  ```javascript
  fetch("https://30x30.skytruth.org/cms/api/protection-coverage-stats?fields[]=coverage&fields[]=protected_area&fields[]=pas&fields[]=oecms&fields[]=global_contribution&populate[location][fields][0]=name&filters[environment][slug][%24eq]=terrestrial&filters[location][type][%24eq]=region&sort=location.name%3Aasc%2Cenvironment.name%3Aasc&populate[location][fields]=code&filters[is_last_year][%24eq]=true", {
    method: "GET",
    headers: {
      "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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

  url = "https://30x30.skytruth.org/cms/api/protection-coverage-stats?fields[]=coverage&fields[]=protected_area&fields[]=pas&fields[]=oecms&fields[]=global_contribution&populate[location][fields][0]=name&filters[environment][slug][%24eq]=terrestrial&filters[location][type][%24eq]=region&sort=location.name%3Aasc%2Cenvironment.name%3Aasc&populate[location][fields]=code&filters[is_last_year][%24eq]=true"
  headers = {
    "Content-Type": "application/json;"
      "Strapi-Response-Format: v4"    
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
[aggregated_stats]: #aggregated-stats
[citation]: #citation
[data_source]: #data-source
[environment]: #environment
[fishing_protection_level]: #fishing-protection-level
[fishing_protection_level_stats]: #fishing-protection-level-stats
[habitat_stats]: #habitat-stats
[location]: #locations
[mpaa_protection_level]: #mpaa-protection-level
[mpaa_protection_level_stats]: #mpaa-protection-level-stats
[mpaa_stage]: #mpaa-establishment-stage
[protected_areas]: #protected-areas
[protection_coverage_stats]: #protection-coverage-stats
[protection_status]: #protection-status

<!-- External Resources -->
[parameter_docs]: https://docs.strapi.io/dev-docs/api/rest/parameters
[populate_docs]: https://docs.strapi.io/dev-docs/api/rest/guides/understanding-populate
