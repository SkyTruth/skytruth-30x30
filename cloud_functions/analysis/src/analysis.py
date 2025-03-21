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

### Marine


def serialize_response_marine(data: dict) -> dict:
    """Converts the data from the database
    into a Dict {locations_area:{"code":<location_iso>, "protected_area": <area>, "area":<location_marine_area>}, "total_area":<total_area>} response
    """
    if not data or len(data) == 0:
        raise ValueError(
            "No data found, this is likely due to a geometry that does not intersect with a Marine area."
        )

    result = {"total_area": data[0][5]}
    sub_result = {}
    total_protected_area = 0
    for row in data:
        for iso in filter(lambda item: item is not None, row[1:4]):
            total_protected_area += row[4]
            if iso not in sub_result:
                sub_result[iso] = {
                    "code": iso,
                    "protected_area": row[4],
                    "area": row[0],
                }
            else:
                sub_result[iso]["protected_area"] += row[4]
                sub_result[iso]["area"] += row[0]

    result.update(
        {
            "locations_area": list(sub_result.values()),
            "total_protected_area": total_protected_area,
        }
    )

    return result


def get_locations_stats_marine(
    db: sqlalchemy.engine.base.Engine, geojson: JSON
) -> dict:
    with db.connect() as conn:
        stmt = sqlalchemy.text(
            """
        with user_data as (select ST_GeomFromGeoJSON(:geometry) as geom),
	            user_data_stats as (select *, round((st_area(st_transform(geom,'+proj=longlat +datum=WGS84 +no_defs +type=crs', '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)) user_area_km2 from user_data)
            select area_km2, iso_sov1, iso_sov2, iso_sov3, 
                round((st_area(st_transform(st_makevalid(st_intersection(ST_Subdivide(the_geom, 20000), user_data_stats.geom)),'+proj=longlat +datum=WGS84 +no_defs +type=crs', '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)) portion_area_km2, 
                user_data_stats.user_area_km2 
            from data.eez_minus_mpa emm, user_data_stats
            where st_intersects(the_geom, user_data_stats.geom)
            """
        )
        data_response = conn.execute(
            stmt, parameters={"geometry": get_geojson(geojson)}
        ).all()

    return serialize_response_marine(data_response)


### Terrestrial
def serialize_response_terrestrial(data: dict) -> dict:
    """Converts the data from the database
    into a Dict {locations_area:{"code":<location_iso>, "protected_area": <area>, "area":<location_marine_area>}, "total_area":<total_area>} response
    """
    if not data or len(data) == 0:
        raise ValueError(
            "No data found, this is likely due to a geometry that does not intersect with a Marine area."
        )

    result = {"total_area": data[0][3]}
    sub_result = {}
    total_protected_area = 0
    for row in data:
        for iso in filter(lambda item: item is not None, [row[1]]):
            total_protected_area += row[2]
            if iso not in sub_result:
                sub_result[iso] = {
                    "code": iso,
                    "protected_area": row[2],
                    "area": row[0],
                }
            else:
                sub_result[iso]["protected_area"] += row[2]
                sub_result[iso]["area"] += row[0]

    result.update(
        {
            "locations_area": list(sub_result.values()),
            "total_protected_area": total_protected_area,
        }
    )

    return result


def get_locations_stats_terrestrial(
    db: sqlalchemy.engine.base.Engine, geojson: JSON
) -> dict:
    with db.connect() as conn:
        stmt = sqlalchemy.text(
            """
        with user_data as (select ST_GeomFromGeoJSON(:geometry) as geom),
	            user_data_stats as (select *, round((st_area(st_transform(geom,'+proj=longlat +datum=WGS84 +no_defs +type=crs', '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)) user_area_km2 from user_data), 
	          stats as (select area_km2,gid_0, round((st_area(st_transform(st_makevalid(st_intersection(the_geom, user_data_stats.geom)),'+proj=longlat +datum=WGS84 +no_defs +type=crs', '+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs'))/1e6)) portion_area_km2,
	          user_data_stats.user_area_km2
	          from data.gadm_minus_pa gmp , user_data_stats
            where st_intersects(the_geom, user_data_stats.geom))
      select avg(area_km2) as area_km2, gid_0, sum(portion_area_km2) as portion_area_km2, avg(user_area_km2) as user_area_km2 from stats group  by gid_0
            """
        )
        data_response = conn.execute(
            stmt, parameters={"geometry": get_geojson(geojson)}
        ).all()

    return serialize_response_terrestrial(data_response)
