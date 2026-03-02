import sqlalchemy
from typing import TypeAlias

JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None


def get_geojson(geojson: JSON) -> dict:
    if geojson.get("type") == "FeatureCollection":
        return get_geojson(geojson.get("features")[0])
    elif geojson.get("type") == "Feature":
        return geojson.get("geometry")
    else:
        return geojson


def validate_geometry_topology(
    conn: sqlalchemy.engine.Connection, geometry: dict
) -> None:
    stmt = sqlalchemy.text(
        """
        WITH g AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326) AS geom
        )
        SELECT
            ST_GeometryType(geom) AS geom_type,
            ST_IsEmpty(geom) AS is_empty,
            ST_IsValid(geom) AS is_valid,
            ST_IsValidReason(geom) AS invalid_reason
        FROM g
        """
    )
    try:
        validation = conn.execute(stmt, parameters={"geometry": geometry}).mappings().one()
    except sqlalchemy.exc.SQLAlchemyError as exc:
        raise ValueError("Unable to parse input geometry") from exc

    if validation["is_empty"]:
        raise ValueError("Input geometry is empty")

    if validation["geom_type"] not in {"ST_Polygon", "ST_MultiPolygon"}:
        raise ValueError("Input geometry must be a Polygon or MultiPolygon")

    if not validation["is_valid"]:
        raise ValueError(f"Invalid input geometry: {validation['invalid_reason']}")


def serialize_response(
    environment: str,
    data: dict
) -> dict:
    """Converts the data from the database
    into a Dict {locations_area:{"code":<location_iso>, "protected_area": <area>}, "total_area":<total_area>} response
    """
    if not data or len(data) == 0:
        raise ValueError(
            f"No data found. This is likely because your custom area does not intersect with an unprotected {environment} area."
        )

    result = {"total_area": data[0][2]}
    sub_result = {}
    total_protected_area = 0
    for row in data:
        for iso in filter(lambda item: item is not None, [row[0]]):
            total_protected_area += row[1]
            if iso not in sub_result:
                sub_result[iso] = {
                    "code": iso,
                    "protected_area": row[1],
                }
            else:
                sub_result[iso]["protected_area"] += row[1]

    result.update(
        {
            "locations_area": list(sub_result.values()),
            "total_protected_area": total_protected_area,
        }
    )

    return result


def get_locations_stats(
    environment: str,
    db: sqlalchemy.engine.base.Engine, 
    geojson: JSON
) -> dict:
    geometry = get_geojson(geojson)
    with db.connect() as conn:
        validate_geometry_topology(conn, geometry)
        if environment == 'marine':
            table = 'eez_minus_mpa_v2'
        elif environment == 'terrestrial':
            table = 'gadm_minus_pa_v2'
        stmt = sqlalchemy.text(
            f"""
            WITH
                user_data AS (
                    SELECT ST_GeomFromGeoJSON(:geometry) AS geom
                ),
                user_data_stats AS (
                    SELECT *,
                        round((st_area(st_transform(geom,
                            '+proj=longlat +datum=WGS84 +no_defs +type=crs',
                            '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)
                        ) AS user_area_km2
                    FROM user_data
                ),
                stats AS (
                    SELECT
                        location,
                        round((st_area(st_transform(
                            st_makevalid(st_intersection(the_geom, user_data_stats.geom)),
                            '+proj=longlat +datum=WGS84 +no_defs +type=crs', 
                            '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)
                        ) AS portion_area_km2,
                        user_data_stats.user_area_km2
                    FROM
                        data.{table},
                        user_data_stats
                    WHERE
                        st_intersects(the_geom, user_data_stats.geom)
                )
            SELECT
                location,
                sum(portion_area_km2) AS portion_area_km2,
                avg(user_area_km2) AS user_area_km2
            FROM stats
            GROUP BY location
            """
        )
        data_response = conn.execute(stmt, parameters={"geometry": geometry}).all()

    return serialize_response(environment, data_response)
