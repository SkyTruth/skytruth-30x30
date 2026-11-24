import sqlalchemy

from src.errors import BadRequestError

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

# SQL CTEs parsing the :geometry parameter into user_data_stats, with the drawn area's
# geometry (geom) and its Mollweide area (user_area_km2)
#
# The data stops at ±180°, so each polygon crossing the antimeridian is split there
# first. One drawn across it on the map arrives with longitudes past ±180, possibly
# whole world copies away, and is moved back so its west edge lies in -180–180. One
# already inside -180–180 is taken as drawn. Polygons are moved one at a time, as the
# parts of a multipolygon may lie on different world copies.
USER_DATA_CTES = """
    user_parts AS (
        SELECT
            ST_WrapX(
                ST_Translate(part.geom, -360 * floor((ST_XMin(part.geom) + 180) / 360), 0),
                180,
                -360
            ) AS geom
        FROM ST_Dump(ST_GeomFromGeoJSON(:geometry)) AS dumped,
            LATERAL ST_MakeValid(dumped.geom) AS part(geom)
    ),
    user_data AS (
        SELECT ST_MakeValid(ST_UnaryUnion(ST_Collect(geom))) AS geom
        FROM user_parts
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

    # Moved back by whole world copies, a polygon wider than the world would still
    # reach past 180°
    if widest_polygon_degrees(geometry) > 360:
        raise BadRequestError("Invalid geometry: a polygon spans more than 360° of longitude")


def widest_polygon_degrees(geometry: dict) -> float:
    """The widest longitude span of the outer rings of a Polygon or MultiPolygon."""
    coordinates = geometry["coordinates"]
    polygons = coordinates if geometry["type"] == "MultiPolygon" else [coordinates]
    return max(
        (
            max(point[0] for point in polygon[0]) - min(point[0] for point in polygon[0])
            for polygon in polygons
            if polygon
        ),
        default=0,
    )
