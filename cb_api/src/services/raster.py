from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy

from src.services.geometry import JSON, USER_DATA_CTES, get_geojson, validate_geometry_topology

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


def serialize_raster_habitats_response(
    data: Sequence[Mapping[str, Any]], classes: Mapping[int, str]
) -> dict:
    """Converts the raster habitats query's rows into a Dict
    {locations: [{"code": <location_iso>, "habitats": [{"habitat": <slug>,
    "added_area": <area>}]}], "total_area": <total_area>} response.

    Each location lists only the habitats the drawn area adds in it.
    """
    habitats = {}
    for row in data:
        if row["location"] is None:
            continue
        habitats.setdefault(row["location"], []).append(
            {"habitat": classes[row["value"]], "added_area": row["portion_area_km2"]}
        )

    return {
        "locations": [
            {"code": code, "habitats": location_habitats}
            for code, location_habitats in habitats.items()
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
                ORDER BY location, value
                """
        )
        data_response = (
            conn.execute(stmt, parameters={"geometry": geometry, "classes": list(classes)})
            .mappings()
            .all()
        )

    return serialize_raster_habitats_response(data_response, classes)
