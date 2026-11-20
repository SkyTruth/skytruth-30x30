import sqlalchemy

from src.errors import BadRequestError

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

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
