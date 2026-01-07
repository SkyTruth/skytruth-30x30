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

def serialize_response(data: dict) -> dict:
    """Converts the data from the database
    into a Dict {locations_area:{"code":<location_iso>, "protected_area": <area>}, "total_area":<total_area>} response
    """
    if not data or len(data) == 0:
        raise ValueError(
            "No data found, this is likely due to a geometry that does not intersect with a marine area."
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
    with db.connect() as conn:
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
                    SELECT
                        geom,
                        round((st_area(st_transform(geom,
                        '+proj=longlat +datum=WGS84 +no_defs +type=crs',
                        '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)
                        ) AS user_area_km2
                    FROM user_data
                )
            SELECT
                t.location,
                round((st_area(st_transform(
                    st_makevalid(st_intersection(the_geom, user_data_stats.geom)),
                    '+proj=longlat +datum=WGS84 +no_defs +type=crs',
                    '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)
                    ) AS portion_area_km2,
                user_data_stats.user_area_km2
            FROM
                data.{table} AS t
            JOIN
                user_data_stats ON t.the_geom && user_data_stats.geom
                AND st_intersects(t.the_geom, user_data_stats.geom)
            """
        )
        data_response = conn.execute(
            stmt, parameters={"geometry": get_geojson(geojson)}
        ).all()

    return serialize_response(data_response)
