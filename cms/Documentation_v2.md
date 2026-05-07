# 30x30 Progress Tracker REST API Documentation (v2)

## Overview

This API is a single source for open conservation data — terrestrial and marine — that powers the [SkyTruth 30x30 Progress Tracker](https://30x30.skytruth.org/). It exposes statistics on protection coverage, fishing-protection levels, MPA protection levels, habitat protection, and the underlying catalog of protected areas (PAs) and locations they belong to. Most users will find the [30x30 web application](https://30x30.skytruth.org/) easier than direct API access — the application is built on top of this same API and visualizes everything described below.

## v2 release

The v2 API went live on **May 6, 2026**. If you integrated against the API prior to that date, the response contract has changed. Please refer to the previously published documentation for the v1 contract and migration guidance — this document only describes v2.

## Base URL

```
https://30x30.skytruth.org/cms/api/
```

## Quickstart: global protection coverage, most recent year

The most common single question — _what percent of the planet is currently protected?_ — is one request. It filters protection coverage stats to the worldwide location (`code = GLOB`) and the latest reporting year (`is_last_year = true`), and populates the related location and environment so the response is self-describing:

<details>
<summary>cURL</summary>

```bash
curl --globoff -H 'Content-Type: application/json' -H 'Accept: application/json' 'https://30x30.skytruth.org/cms/api/protection-coverage-stats?filters[location][code][$eq]=GLOB&filters[is_last_year][$eq]=true&populate[location][fields][0]=code&populate[location][fields][1]=name&populate[environment][fields][0]=slug&populate[environment][fields][1]=name'
```

</details>

<details>
<summary>JavaScript</summary>

```javascript
const url =
  "https://30x30.skytruth.org/cms/api/protection-coverage-stats?filters[location][code][$eq]=GLOB&filters[is_last_year][$eq]=true&populate[location][fields][0]=code&populate[location][fields][1]=name&populate[environment][fields][0]=slug&populate[environment][fields][1]=name";

const response = await fetch(url, {
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});
const data = await response.json();
console.log(data);
```

</details>

<details>
<summary>Python</summary>

```python
import requests

url = "https://30x30.skytruth.org/cms/api/protection-coverage-stats?filters[location][code][$eq]=GLOB&filters[is_last_year][$eq]=true&populate[location][fields][0]=code&populate[location][fields][1]=name&populate[environment][fields][0]=slug&populate[environment][fields][1]=name"

response = requests.get(
    url,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
)
print(response.json())
```

</details>

Response (truncated to one row):

```json
{
  "data": [
    {
      "id": 6113,
      "year": 2026,
      "protected_area": 36333056.85,
      "createdAt": "2026-01-01T13:06:04.143Z",
      "updatedAt": "2026-05-01T12:06:11.637Z",
      "protected_areas_count": 17182,
      "coverage": 10.01,
      "pas": 97.86,
      "oecms": 2.14,
      "is_last_year": true,
      "global_contribution": 10.01,
      "total_area": "361000000",
      "documentId": "a93ce901d376aba529138e49",
      "publishedAt": "2026-05-01T12:06:11.625Z",
      "location": {
        "id": 1,
        "documentId": "a13d32acf55907599c6f48ee",
        "code": "GLOB",
        "name": "Global"
      },
      "environment": {
        "id": 1,
        "documentId": "a28a7b45076d554c4b862d4b",
        "slug": "marine",
        "name": "Marine"
      }
    },
    {
      "id": 6115,
      "year": 2026,
      "protected_area": 24804601.97,
      "createdAt": "2026-01-01T13:06:04.264Z",
      "updatedAt": "2026-05-01T12:06:11.669Z",
      "protected_areas_count": 303188,
      "coverage": 18.44,
      "pas": 94.02,
      "oecms": 5.98,
      "is_last_year": true,
      "global_contribution": 18.44,
      "total_area": "134954835",
      "documentId": "a6c3266fece0f19fb8bdd5aa",
      "publishedAt": "2026-05-01T12:06:11.663Z",
      "location": {
        "id": 1,
        "documentId": "a13d32acf55907599c6f48ee",
        "code": "GLOB",
        "name": "Global"
      },
      "environment": {
        "id": 2,
        "documentId": "aeb6b5afe45a531db7ec51bd",
        "slug": "terrestrial",
        "name": "Terrestrial"
      }
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "pageSize": 25,
      "pageCount": 1,
      "totalCount": 2
    },
    "updatedAt": "2026-05-01T12:06:11.669Z"
  }
}
```

Two rows come back — one per environment (`marine`, `terrestrial`). Drop the `populate[environment]` clauses to omit environment details, or add `&filters[environment][slug][$eq]=marine` to scope to just one. Similarly, `filters[location][code][$eq]=GLOB` can be updated for any country we track by replacing `GLOB` with the country's ISO3 code.

## Response contract

Every response (success or error) is JSON. A successful list response has the shape:

```json
{ "data": [ /* records */ ], "meta": { "pagination": { ... } } }
```

A successful single-item response has `data` as an object instead of an array.

### Record shape

Records are flat. Top-level fields and relations both live directly on the record:

```json
{
  "id": 30,
  "documentId": "z9y8x7w6v5u4t3s2r1q0p9o8",
  "code": "CHL",
  "name": "Chile",
  "groups": [
    { "id": 8, "documentId": "...", "name": "Latin America & Caribbean" }
  ]
}
```

- `id` is a numeric integer, stable for the lifetime of a record but **not the canonical public identifier**.
- `documentId` is a 24-character string that is the canonical identifier for cross-references and single-item endpoint lookups (`GET /pas/:documentId`). Prefer it in long-lived integrations.
- Single relations are inlined as objects.
- Many relations (one-to-many, many-to-many) are inlined as arrays of objects.
- Empty single relations are `null`. Empty multi-relations are `[]`.

### Error shape

```json
{
  "data": null,
  "error": {
    "status": 404,
    "name": "NotFoundError",
    "message": "Not Found",
    "details": {}
  }
}
```

### Pagination

`meta.pagination` is included on list responses with `page`, `pageSize`, `pageCount`, and `total`. Use `?pagination[page]=2&pagination[pageSize]=50` to navigate. The maximum `pageSize` is `100`.

## Headers

- `Content-Type: application/json`
- `Accept: application/json`

## Query parameters

The API uses Strapi's REST query syntax for `filters`, `populate`, `fields`, `sort`, and `pagination`. We won't repeat the full reference here — see Strapi's [parameter docs][parameter_docs] and [populate guide][populate_docs] — but a few things worth knowing:

- `locale=<en | es | fr | pt>` — sets the response language for translatable fields (English, Spanish, French, Portuguese). Defaults to `en`.
- `populate[<relation>][fields][0]=name&populate[<relation>][fields][1]=code` — pull only specific fields from a relation rather than the full record.
- `filters[<field>][$eq | $ne | $in | $gt | ...]=value` — server-side filtering. Brackets must be URL-encoded in some clients; cURL needs `--globoff`.
- `sort=<field>:asc` (or `:desc`) — sort by a field. Combine with commas for multi-key sort.
- `fields[0]=name&fields[1]=code` — return only listed top-level fields. Combine with `populate` to return only listed fields from related records.

## Citation

When citing the 30x30 Progress Tracker overall, please use:

> SkyTruth [30x30 Progress Tracker][progress-tracker], 2026, licensed under CC BY-SA, [modifications made, if any] by [you, the creator].

### Citing individual data sources

Every Protected Area record carries a `data_source` relation that points to the upstream provider (Protected Planet, MPAtlas, etc.) along with that source's title, URL, and a slug for programmatic identification. To return data sources alongside any query, populate the `data_source` field on protected areas. Where the resource you're querying isn't a PA itself, populate through the relation chain.

**Resources with a Location field** (e.g. [Protection Coverage Stats][protection_coverage_stats]) reach data sources via _Location → Protected Areas → Data Source_:

```
populate[location][populate][pas][populate][data_source][fields]=*
```

**Region-type locations** (`type = region`, e.g. `Europe`, `Africa`) don't have PAs of their own — their PAs live on the member countries. Reach data sources via _Location → Members → PAs → Data Source_:

```
populate[location][populate][members][populate][pas][populate][data_source][fields]=*
```

> ⚠️ Region-scoped citation queries return every data source for every PA in every member country, which is a lot of data. Consider paginating the parent query, scoping with `filters`, or fetching citations once per region rather than per stat row.

Data sources are localized — pass `locale=fr` (or another supported locale) to receive translated `title` fields.

## Resources

### Public collection types

- [Fishing Protection Level Stats][fishing_protection_level_stats]
- [Habitat Stats][habitat_stats]
- [Locations][location]
- [MPAA Protection Level Stats][mpaa_protection_level_stats]
- [Protected Areas][protected_areas]
- [Protection Coverage Stats][protection_coverage_stats]
- [Aggregated Stats][aggregated_stats]

### Related (lookup) types

These are the small enumerated reference tables that the stats and PAs link to. They're queryable on their own but more commonly populated as relations.

- [Data Source][data_source]
- [Environment][environment]
- [Fishing Protection Level][fishing_protection_level]
- [Habitat][habitat]
- [MPAA Protection Level][mpaa_protection_level]
- [MPAA Establishment Stage][mpaa_stage]
- [MPA IUCN Category][pa_iucn_category]
- [Protection Status][protection_status]

In each section below, fields marked 🖇️ are relations that can be expanded with `populate`.

---

## Protection Coverage Stats

Coverage statistics — what fraction of a location is currently protected — broken down by location, environment (marine/terrestrial), and reporting year. This is the table that powers the headline percentages on the 30x30 site — sourced from [Protected Planet](https://www.protectedplanet.net/en).

### Fields

| Name                  | Type        | Description                                                                                                                                                                              |
| --------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| location              | Relation 🖇️ | The [Location][location] this stat covers (country, region, or worldwide).                                                                                                               |
| environment           | Relation 🖇️ | The [Environment][environment] (marine or terrestrial).                                                                                                                                  |
| year                  | Number      | Reporting year.                                                                                                                                                                          |
| coverage              | Number      | Percent of the location's relevant total area covered by protected areas, in percent (0–100).                                                                                            |
| protected_area        | Number      | Protected area in km².                                                                                                                                                                   |
| total_area            | Number      | The total area, in km², that the upstream data provider used to compute `coverage`. Useful when verifying the percentage independently — `coverage ≈ protected_area / total_area * 100`. |
| protected_areas_count | Number      | Number of distinct PA records contributing to this row.                                                                                                                                  |
| pas                   | Number      | Percent of `coverage` contributed by formally designated Protected Areas.                                                                                                                |
| oecms                 | Number      | Percent of `coverage` contributed by Other Effective area-based Conservation Measures (OECMs). `pas + oecms ≈ 100`.                                                                      |
| global_contribution   | Number      | This row's contribution to global protection, in percent of the planet. Sums across all locations approximate the worldwide row's `coverage`.                                            |
| is_last_year          | Boolean     | `true` for the most recent reporting year present for this `(location, environment)` pair. Use this to fetch "current" stats without hard-coding a year.                                 |

### Endpoints

- `GET /protection-coverage-stats`
- `GET /protection-coverage-stats/:documentId`

### Example: terrestrial coverage for every region, latest year

```bash
curl --globoff -H 'Content-Type: application/json' 'https://30x30.skytruth.org/cms/api/protection-coverage-stats?fields[0]=coverage&fields[1]=protected_area&fields[2]=pas&fields[3]=oecms&fields[4]=global_contribution&filters[environment][slug][$eq]=terrestrial&filters[location][type][$eq]=region&filters[is_last_year][$eq]=true&populate[location][fields][0]=code&populate[location][fields][1]=name&sort=location.name:asc'
```

---

## Fishing Protection Level Stats

Stats describing how much of a location's marine area sits under each fishing-protection level (Highly, Moderately, Less). Levels come from [ProtectedSeas](https://navigatormap.org).

### Fields

| Name                     | Type        | Description                                                         |
| ------------------------ | ----------- | ------------------------------------------------------------------- |
| location                 | Relation 🖇️ | The [Location][location] this stat covers.                          |
| fishing_protection_level | Relation 🖇️ | The [Fishing Protection Level][fishing_protection_level].           |
| area                     | Number      | Protected area at this level, in km².                               |
| pct                      | Number      | Percentage of the location's marine area at this level.             |
| total_area               | Number      | The location's total marine area used as the denominator for `pct`. |

### Endpoints

- `GET /fishing-protection-level-stats`
- `GET /fishing-protection-level-stats/:documentId`

### Example

```bash
curl --globoff -H 'Content-Type: application/json' 'https://30x30.skytruth.org/cms/api/fishing-protection-level-stats?populate[fishing_protection_level][fields][0]=name&populate[fishing_protection_level][fields][1]=info&populate[location][fields][0]=name'
```

---

## MPAA Protection Level Stats

Marine Protected Area protection level stats broken down by [MPAA protection level](#mpaa-protection-level) — Full, High, Less, Minimal, etc. — sourced from [MPAtlas](https://mpatlas.org/).

### Fields

| Name                  | Type        | Description                                                                |
| --------------------- | ----------- | -------------------------------------------------------------------------- |
| location              | Relation 🖇️ | The [Location][location] this stat covers.                                 |
| mpaa_protection_level | Relation 🖇️ | The [MPAA Protection Level][mpaa_protection_level].                        |
| area                  | Number      | Protected area at this level, in km².                                      |
| percentage            | Number      | Percentage of the location's marine area at this level.                    |
| total_area            | Number      | The location's total marine area used as the denominator for `percentage`. |

### Endpoints

- `GET /mpaa-protection-level-stats`
- `GET /mpaa-protection-level-stats/:documentId`

---

## Habitat Stats

Per-habitat protection figures by location and year. Habitats include marine ecosystems (mangroves, seagrasses, cold-water corals, etc.) and terrestrial ones (forests, grasslands, deserts, etc.).

### Fields

| Name           | Type        | Description                                                               |
| -------------- | ----------- | ------------------------------------------------------------------------- |
| location       | Relation 🖇️ | The [Location][location].                                                 |
| habitat        | Relation 🖇️ | The [Habitat][habitat].                                                   |
| environment    | Relation 🖇️ | The [Environment][environment] the habitat belongs to.                    |
| year           | Number      | Reporting year.                                                           |
| protected_area | Number      | Protected area of this habitat in this location, in km².                  |
| total_area     | Number      | Total area of this habitat in this location, in km² (use as denominator). |

### Endpoints

- `GET /habitat-stats`
- `GET /habitat-stats/:documentId`

---

## Locations

Geographic units: countries, multi-country regions, the high seas, and the worldwide aggregate. Stats are joined to locations; locations form a 2-level group/member hierarchy (e.g. `Africa` is a group of country members like `Angola`).

### Fields

| Name                           | Type        | Description                                                                                                                                                                                                                                            |
| ------------------------------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| code                           | Text        | Stable textual identifier — ISO-3 for countries (`CHL`), curated codes for regions (`AF`, `LAM`), `GLOB` for worldwide, and a dedicated code for high seas. Prefer `code` over `id` / `documentId` for querying by location.                           |
| name                           | Text        | Localized location name (per `locale` query param).                                                                                                                                                                                                    |
| name_es / name_fr / name_pt    | Text        | Spanish, French, and Portuguese names. Returned regardless of `locale` so a consumer can render multilingual UI without re-fetching.                                                                                                                   |
| type                           | Text        | One of `country`, `region`, `worldwide`, `highseas`. Regions group country members; the worldwide row aggregates everything.                                                                                                                           |
| total_marine_area              | Number      | The location's total marine area in km².                                                                                                                                                                                                               |
| total_terrestrial_area         | Number      | The location's total terrestrial area in km².                                                                                                                                                                                                          |
| marine_bounds                  | Array       | `[minLon, minLat, maxLon, maxLat]` bounding box of the location's marine area.                                                                                                                                                                         |
| terrestrial_bounds             | Array       | `[minLon, minLat, maxLon, maxLat]` bounding box of the location's terrestrial area.                                                                                                                                                                    |
| marine_target                  | Number      | Marine conservation target as a percent (e.g. `30`). May be unset for locations without a published target.                                                                                                                                            |
| marine_target_year             | Number      | Year the location aims to reach `marine_target` by (e.g. `2030`).                                                                                                                                                                                      |
| has_shared_marine_area         | Boolean     | `true` if some portion of this location's marine area is shared, overlapping, or contested with another jurisdiction (e.g. an EEZ claimed by multiple states). When this is true, downstream `protected_area` figures may double-count with neighbors. |
| groups                         | Relation 🖇️ | Parent locations this one belongs to (e.g. Angola → [Africa]).                                                                                                                                                                                         |
| members                        | Relation 🖇️ | Child locations contained in this one (e.g. Africa → [Angola, ...]).                                                                                                                                                                                   |
| pas                            | Relation 🖇️ | The [Protected Areas][protected_areas] inside this location. Empty for `region` and `worldwide` types — fetch via `members.pas` for those.                                                                                                             |
| protection_coverage_stats      | Relation 🖇️ | [Protection Coverage Stats][protection_coverage_stats] for this location.                                                                                                                                                                              |
| fishing_protection_level_stats | Relation 🖇️ | [Fishing Protection Level Stats][fishing_protection_level_stats] for this location.                                                                                                                                                                    |
| mpaa_protection_level_stats    | Relation 🖇️ | [MPAA Protection Level Stats][mpaa_protection_level_stats] for this location.                                                                                                                                                                          |

### Endpoints

- `GET /locations`
- `GET /locations/:documentId`

### Example: Chile with its parent group

```bash
curl --globoff -H 'Content-Type: application/json' 'https://30x30.skytruth.org/cms/api/locations?filters[code][$eq]=CHL&populate[groups][fields][0]=name'
```

---

## Protected Areas

The catalog of protected areas powering the stats above. Each PA is sourced from a single upstream provider (`data_source`); the same physical site may appear as multiple PA records with different metadata fields if multiple providers track it.

### Fields

| Name                     | Type        | Description                                                                                                                                                                                                                                    |
| ------------------------ | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| name                     | Text        | PA name from the upstream source.                                                                                                                                                                                                              |
| area                     | Number      | PA area in km².                                                                                                                                                                                                                                |
| year                     | Number      | Year the PA was established.                                                                                                                                                                                                                   |
| designation              | Text        | Free-text designation as reported by the source (e.g. `National Park`, `Marine Reserve`).                                                                                                                                                      |
| coverage                 | Number      | Percent of the parent [Location][location] covered by this PA. Values below 0.1% round to 0.                                                                                                                                                   |
| bbox                     | Array       | `[minLon, minLat, maxLon, maxLat]` of the PA.                                                                                                                                                                                                  |
| wdpaid                   | Number      | Identifier from the World Database on Protected Areas (WDPA / Protected Planet). Following WDPA's schema change, this corresponds to WDPA's **`site_id`** — the identifier for the site as a whole. Present when this PA originates from WDPA. |
| wdpa_p_id                | Text        | The WDPA **parcel identifier** (`site_pid` in WDPA / Protected Planet) — identifies a specific parcel within a site for sites that are split across multiple geometries. Present alongside `wdpaid` when the PA represents a single parcel.    |
| zone_id                  | Number      | The MPAtlas zone identifier. Present **only** when the PA originates from MPAtlas (i.e. `data_source.slug = "mpatlas"`).                                                                                                                       |
| location                 | Relation 🖇️ | The [Location][location] this PA sits in.                                                                                                                                                                                                      |
| data_source              | Relation 🖇️ | The [Data Source][data_source] this record came from.                                                                                                                                                                                          |
| protection_status        | Relation 🖇️ | [Protection Status][protection_status].                                                                                                                                                                                                        |
| mpaa_protection_level    | Relation 🖇️ | [MPAA Protection Level][mpaa_protection_level].                                                                                                                                                                                                |
| mpaa_establishment_stage | Relation 🖇️ | [MPAA Establishment Stage][mpaa_stage].                                                                                                                                                                                                        |
| iucn_category            | Relation 🖇️ | [MPA IUCN Category][pa_iucn_category].                                                                                                                                                                                                         |
| environment              | Relation 🖇️ | [Environment][environment] (marine or terrestrial).                                                                                                                                                                                            |
| children                 | Relation 🖇️ | PAs nested inside this one.                                                                                                                                                                                                                    |
| parent                   | Relation 🖇️ | PA that contains this one.                                                                                                                                                                                                                     |

### Endpoints

- `GET /pas`
- `GET /pas/:documentId`

### Example: one PA, with location and source

```bash
curl --globoff -H 'Content-Type: application/json' 'https://30x30.skytruth.org/cms/api/pas?fields[0]=*&populate[location][fields][0]=name&populate[data_source][fields][0]=title&populate[data_source][fields][1]=url&pagination[pageSize]=1'
```

---

## Aggregated Stats

A single endpoint that summarizes stats across an arbitrary set of locations and groups them by user-specified dimensions. Use this when you want one combined number for, say, The Caribbean, rather than per-country rows you have to sum yourself.

This endpoint returns its own custom shape — it does **not** follow the per-record `id` / `documentId` envelope used by the other resources, because each row is an aggregate, not a stored record.

### Endpoint

- `GET /aggregated-stats`

### Query parameters

- `locations` (required) — Comma-separated list of location codes, e.g. `USA,MEX,CAN`. Codes are case-insensitive.
- `stats` — Comma-separated list of stat types to compute. Default: `protection_coverage`. Valid values: `protection_coverage`, `habitat`, `mpaa_protection_level`, `fishing_protection_level`.
- `year` — 4-digit year. Only meaningful for `protection_coverage` and `habitat`. Omit to receive all years grouped by year.
- `environment` — `marine` or `terrestrial`. Only meaningful for `protection_coverage` and `habitat`. Omit to receive both environments grouped by environment.
- `habitat` — Habitat slug to scope to. Only meaningful for `habitat`. Omit to receive every habitat grouped by habitat. Valid options depend on environment:
  - Terrestrial: `artificial`, `desert`, `forest`, `grassland`, `rocky-mountains`, `savanna`
  - Marine: `cold-water-corals`, `mangroves`, `saltmarshes`, `seagrasses`, `seamounts`, `warm-water-corals`, `wetland-open-waters`
- `fishing_protection_level` — Slug. Only meaningful for `fishing_protection_level`. Omit to receive each level grouped by level. Valid options: `highly`, `less`, `moderately`.
- `mpaa_protection_level` — Slug. Only meaningful for `mpaa_protection_level`. Omit to receive each level grouped by level. Valid options: `full`, `high`, `fully-highly-protected`, `light`, `minimal`, `unknown`, `incompatible`.
- `locale` — `en | es | fr | pt`. Translates labels in the response.

### Response

```json
{
  "data": {
    "<stat-type>": [
      {
        "year": 2025,
        "environment": "marine",
        "habitat": "warm-water-corals",
        "locations": ["MEX", "USA"],
        "protected_area": 4663.12,
        "total_area": 5650.45,
        "coverage": 82.526,
        "hasSharedMarineArea": false
      }
    ]
  }
}
```

Each row's keys depend on the stat type and on which group-by parameters were omitted:

- `locations` — The set of input location codes that contributed to this row. Always present.
- `protected_area`, `total_area`, `coverage` — Aggregate numbers; `coverage = protected_area / total_area * 100`.
- `year`, `environment`, `habitat`, `fishing_protection_level`, `mpaa_protection_level` — Present when the request grouped by that dimension (i.e. when you omitted the corresponding query parameter).
- `hasSharedMarineArea` — `true` if at least one of the input `locations` has `has_shared_marine_area = true`. Treat this as a flag that the aggregate may double-count across overlapping marine claims.

### Example

Habitat, protection coverage, MPAA level, and fishing-level aggregates for North America in 2025:

```bash
curl --globoff -H 'Content-Type: application/json' 'https://30x30.skytruth.org/cms/api/aggregated-stats?locations=USA,MEX,CAN&stats=habitat,protection_coverage,mpaa_protection_level,fishing_protection_level&year=2025&mpaa_protection_level=fully-highly-protected'
```

---

## Related resources

These resources back the relations on the stats and PA records above. Each is queryable directly (`GET /<plural-name>`) but you'll usually consume them through `populate` on the resource that links to them.

### Data Source

The upstream provider a [Protected Area][protected_areas] came from. See [Citation](#citing-individual-data-sources).

| Name  | Type | Description                                                   |
| ----- | ---- | ------------------------------------------------------------- |
| slug  | Text | Programmatic identifier (e.g. `protected-planet`, `mpatlas`). |
| title | Text | Human-readable title (localized).                             |
| url   | Text | Canonical URL of the source.                                  |

### Environment

Marine vs terrestrial.

| Name | Type | Description                |
| ---- | ---- | -------------------------- |
| slug | Text | `marine` or `terrestrial`. |
| name | Text | Localized name.            |

### Habitat

Habitats used by [Habitat Stats][habitat_stats].

| Name | Type | Description                                              |
| ---- | ---- | -------------------------------------------------------- |
| slug | Text | Programmatic identifier (e.g. `mangroves`, `seamounts`). |
| name | Text | Localized name.                                          |
| info | Text | Longer description of the habitat (localized).           |

### Fishing Protection Level

The protection-level scale used by [Fishing Protection Level Stats][fishing_protection_level_stats]. Values come from ProtectedSeas LFP scoring.

| Name | Type | Description                        |
| ---- | ---- | ---------------------------------- |
| slug | Text | `highly`, `moderately`, or `less`. |
| name | Text | Localized name.                    |
| info | Text | Definition of the level.           |

### MPAA Protection Level

The protection-level scale used by [MPAA Protection Level Stats][mpaa_protection_level_stats] and [PAs][protected_areas]. Sourced from MPAtlas.

| Name | Type | Description                                                                                 |
| ---- | ---- | ------------------------------------------------------------------------------------------- |
| slug | Text | `full`, `high`, `fully-highly-protected`, `light`, `minimal`, `unknown`, or `incompatible`. |
| name | Text | Localized name.                                                                             |
| info | Text | Definition of the level.                                                                    |

### MPAA Establishment Stage

Where an MPA is in its establishment lifecycle (proposed, designated, implemented, etc.).

| Name | Type | Description              |
| ---- | ---- | ------------------------ |
| slug | Text | Programmatic identifier. |
| name | Text | Localized name.          |
| info | Text | Definition of the stage. |

### MPA IUCN Category

The IUCN category assigned to a PA (Ia, Ib, II, III, IV, V, VI, or unset).

| Name | Type | Description                 |
| ---- | ---- | --------------------------- |
| slug | Text | Programmatic identifier.    |
| name | Text | Localized name.             |
| info | Text | Definition of the category. |

### Protection Status

The legal protection status of a [PA][protected_areas].

| Name | Type | Description               |
| ---- | ---- | ------------------------- |
| slug | Text | Programmatic identifier.  |
| name | Text | Localized name.           |
| info | Text | Definition of the status. |

<!-- Internal anchors -->

[aggregated_stats]: #aggregated-stats
[data_source]: #data-source
[environment]: #environment
[fishing_protection_level]: #fishing-protection-level
[fishing_protection_level_stats]: #fishing-protection-level-stats
[habitat]: #habitat
[habitat_stats]: #habitat-stats
[location]: #locations
[mpaa_protection_level]: #mpaa-protection-level
[mpaa_protection_level_stats]: #mpaa-protection-level-stats
[mpaa_stage]: #mpaa-establishment-stage
[pa_iucn_category]: #mpa-iucn-category
[protected_areas]: #protected-areas
[protection_coverage_stats]: #protection-coverage-stats
[protection_status]: #protection-status

<!-- External -->

[parameter_docs]: https://docs.strapi.io/dev-docs/api/rest/parameters
[populate_docs]: https://docs.strapi.io/dev-docs/api/rest/guides/understanding-populate
[progress-tracker]: https://30x30.skytruth.org/progress-tracker
