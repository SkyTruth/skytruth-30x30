from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

import sqlalchemy

from src.errors import BadRequestError

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None


class AnalysisTable(StrEnum):
    MARINE = "eez_minus_mpa_v2"
    TERRESTRIAL = "gadm_minus_pa_v2"
    FULLY_HIGHLY_PROTECTED = "location_minus_fhp_mpa"
    MANGROVES = "mangroves_minus_pa"
    SALTMARSHES = "saltmarshes_minus_pa"
    SEAGRASSES = "seagrasses_minus_pa"
    SEAMOUNTS = "seamounts_minus_pa"
    COLD_WATER_CORALS = "cold_water_corals_minus_pa"
    CLIMATE_RESILIENT_CORALS = "climate_resilient_corals_minus_pa"
    OTHER_CORALS = "other_corals_minus_pa"


# PostGIS raster table of unprotected terrestrial habitat, one row per tile
TERRESTRIAL_HABITATS_TABLE = "terrestrial_habitats_minus_pa"

# Pixel value of each terrestrial habitat in TERRESTRIAL_HABITATS_TABLE. "Other" (255)
# is left out, as it is in the progress tracker.
TERRESTRIAL_HABITAT_CLASSES = {
    1: "forest",
    2: "savanna",
    3: "shrubland",
    4: "grassland",
    5: "wetlands-open-waters",
    6: "rocky-mountains",
    7: "desert",
    8: "artificial",
}

# SQL CTEs parsing the :geometry parameter into user_data_stats, with the drawn area's
# geometry (geom) and its Mollweide area (user_area_km2)
USER_DATA_CTES = """
    user_data AS (
        SELECT ST_MakeValid(ST_UnaryUnion(ST_GeomFromGeoJSON(:geometry))) AS geom
    ),
    user_data_stats AS (
        SELECT *,
            ST_Area(ST_Transform(geom,
                '+proj=longlat +datum=WGS84 +no_defs +type=crs',
                '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6
            AS user_area_km2
        FROM user_data
    )"""


def get_geojson(geojson: JSON) -> dict:
    if not isinstance(geojson, dict):
        raise BadRequestError("Invalid geometry: unable to parse input geometry")

    if geojson.get("type") == "FeatureCollection":
        features = geojson.get("features")
        if not isinstance(features, list) or not features:
            raise BadRequestError("Invalid geometry: unable to parse input geometry")
        return get_geojson(features[0])
    elif geojson.get("type") == "Feature":
        return geojson.get("geometry")
    else:
        return geojson


def validate_geometry_topology(conn: sqlalchemy.engine.Connection, geometry: dict) -> None:
    stmt = sqlalchemy.text(
        """
        WITH g AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326) AS geom
        )
        SELECT
            ST_GeometryType(geom) AS geom_type,
            ST_IsEmpty(geom) AS is_empty
        FROM g
        """
    )
    try:
        validation = conn.execute(stmt, parameters={"geometry": geometry}).mappings().one()
    except sqlalchemy.exc.DBAPIError as exc:
        # This statement only parses the geometry, so any error the database returns
        # is caused by the input. A lost connection is the exception.
        if exc.connection_invalidated:
            raise
        raise BadRequestError("Invalid geometry: unable to parse input geometry") from exc

    if validation["is_empty"]:
        raise BadRequestError("Invalid geometry: input geometry is empty")

    if validation["geom_type"] not in {"ST_Polygon", "ST_MultiPolygon"}:
        raise BadRequestError("Invalid geometry: input geometry must be a Polygon or MultiPolygon")


def serialize_response(data: Sequence[Mapping[str, Any]]) -> dict:
    """Converts the stats query's rows into a Dict
    {locations: [{"code": <location_iso>, "added_area": <area>}],
    "total_area": <total_area>} response
    """
    sub_result = {}
    for row in data:
        iso = row["location"]
        if iso is None:
            continue
        if iso not in sub_result:
            sub_result[iso] = {"code": iso, "added_area": row["portion_area_km2"]}
        else:
            sub_result[iso]["added_area"] += row["portion_area_km2"]

    return {
        "locations": list(sub_result.values()),
        "total_area": data[0]["user_area_km2"],
    }


def get_locations_stats(
    engine: sqlalchemy.engine.base.Engine,
    geojson: JSON,
    table_name: AnalysisTable | str,
) -> dict:
    try:
        table = AnalysisTable(table_name)
    except ValueError as exc:
        raise LookupError(f"Unknown analysis table: {table_name!r}") from exc

    geometry = get_geojson(geojson)
    with engine.connect() as conn:
        validate_geometry_topology(conn, geometry)
        stmt = sqlalchemy.text(
            f"""
                WITH
                    {USER_DATA_CTES},
                    stats AS (
                        SELECT
                            location,
                            ST_Area(ST_Transform(
                                ST_MakeValid(ST_Intersection(the_geom, user_data_stats.geom)),
                                '+proj=longlat +datum=WGS84 +no_defs +type=crs',
                                '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6
                            AS portion_area_km2,
                            user_data_stats.user_area_km2
                        FROM
                            user_data_stats
                            LEFT JOIN data.{table.value}
                                ON ST_Intersects(the_geom, user_data_stats.geom)
                    )
                SELECT
                    location,
                    SUM(portion_area_km2) AS portion_area_km2,
                    AVG(user_area_km2) AS user_area_km2
                FROM stats
                GROUP BY location
                """
        )
        data_response = conn.execute(stmt, parameters={"geometry": geometry}).mappings().all()

    return serialize_response(data_response)


def serialize_raster_habitats_response(
    data: Sequence[Mapping[str, Any]], classes: Mapping[int, str]
) -> dict:
    """Converts the raster habitats query's rows into a Dict
    {habitats: [{"habitat": <slug>, "locations": [{"code": <location_iso>,
    "added_area": <area>}]}], "total_area": <total_area>} response.

    Every habitat in `classes` is listed, with no locations when the drawn area holds
    none of it.
    """
    locations = {habitat: [] for habitat in classes.values()}
    for row in data:
        if row["location"] is None:
            continue
        locations[classes[row["value"]]].append(
            {"code": row["location"], "added_area": row["portion_area_km2"]}
        )

    return {
        "habitats": [
            {"habitat": habitat, "locations": habitat_locations}
            for habitat, habitat_locations in locations.items()
        ],
        "total_area": data[0]["user_area_km2"],
    }


def get_raster_habitats_stats(
    engine: sqlalchemy.engine.base.Engine,
    geojson: JSON,
    table: str = TERRESTRIAL_HABITATS_TABLE,
    classes: Mapping[int, str] = TERRESTRIAL_HABITAT_CLASSES,
) -> dict:
    """How much of each habitat in the drawn area is not yet protected, by location,
    counted from the unprotected habitat pixels of a PostGIS raster table under it.

    A pixel counts when its centre falls inside the drawn area. Its area is taken from
    its tile's footprint on the ellipsoid, divided evenly between the tile's pixels.

    Parameters
    ----------
    engine : sqlalchemy.engine.base.Engine
        Database engine.
    geojson : JSON
        The drawn area, as a GeoJSON Feature, FeatureCollection or geometry.
    table : str
        Raster table in the data schema, with "location" and "rast" columns, holding
        only unprotected habitat pixels. Defaults to the terrestrial habitats table.
    classes : Mapping[int, str]
        Habitat slug of each pixel value to report; other values are left out. Defaults
        to the terrestrial habitats.
    """
    geometry = get_geojson(geojson)
    with engine.connect() as conn:
        validate_geometry_topology(conn, geometry)
        stmt = sqlalchemy.text(
            f"""
                WITH
                    {USER_DATA_CTES},
                    stats AS (
                        SELECT
                            location,
                            vc.value,
                            vc.count * ST_Area(ST_Envelope(rast)::geography) / 1e6
                                / (ST_Width(rast) * ST_Height(rast)) AS portion_area_km2
                        FROM
                            data.{table},
                            user_data_stats,
                            LATERAL ST_ValueCount(
                                ST_Clip(rast, ST_CollectionExtract(
                                    ST_Intersection(user_data_stats.geom, ST_ConvexHull(rast)), 3
                                )), 1, true
                            ) AS vc
                        WHERE
                            ST_Intersects(ST_ConvexHull(rast), user_data_stats.geom)
                            -- A tile the drawing only touches along an edge would be
                            -- clipped to a line, which counts every pixel on it
                            AND NOT ST_Touches(ST_ConvexHull(rast), user_data_stats.geom)
                            AND vc.value = ANY(:classes)
                    )
                SELECT
                    location,
                    value,
                    SUM(portion_area_km2) AS portion_area_km2,
                    AVG(user_area_km2) AS user_area_km2
                FROM
                    user_data_stats
                    LEFT JOIN stats ON true
                GROUP BY location, value
                """
        )
        data_response = (
            conn.execute(stmt, parameters={"geometry": geometry, "classes": list(classes)})
            .mappings()
            .all()
        )

    return serialize_raster_habitats_response(data_response, classes)
