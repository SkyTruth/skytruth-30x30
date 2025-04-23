import geopandas as gpd
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid


def check_bbox_contains_bbox(bbox1, bbox2):
    return (
        bbox1[0] - 1 <= bbox2[0]
        and bbox1[1] - 1 <= bbox2[1]
        and bbox1[2] + 1 >= bbox2[2]
        and bbox1[3] + 1 >= bbox2[3]
    )


def check_crs_area_of_use_contains_bbox(crs, bbox):
    return check_bbox_contains_bbox(crs.area_of_use.bounds, bbox)


def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf.geometry = gdf.geometry.make_valid()
    return gdf


def add_bbox(df: gpd.GeoDataFrame, col_name: str = "bounds") -> gpd.GeoDataFrame:
    return df.assign(**{col_name: df.geometry.bounds.apply(list, axis=1)})


def add_envelope(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return df.assign(geometry=lambda row: row["geometry"].envelope)


def collection_to_multipolygon(geometry_collection):
    """Convert collection of polygons to multipolygon."""

    geom_list = [
        geom.buffer(0.0)
        for geom in geometry_collection.geoms
        if geom.geom_type in ("Polygon", "MultiPolygon") and not geom.is_empty
    ]
    return unary_union(geom_list)


def repair_geometry(geom, tol=0.0001, remove_slivers=False):
    if not geom:
        return Polygon()
    elif not geom.is_valid:
        geom = repair_geometry(make_valid(geom.buffer(0.0)), remove_slivers=True)
    elif geom.geom_type == "GeometryCollection":
        geom = collection_to_multipolygon(geom)

    if remove_slivers:
        return make_valid(
            geom.buffer(tol, resolution=2, cap_style="square").buffer(
                -tol, resolution=2, cap_style="square"
            )
        )
    else:
        return geom


def arrange_dimensions(
    geodataframe_a: gpd.GeoDataFrame, geodataframe_b: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Arrange dimensions."""
    return (
        (geodataframe_a, geodataframe_b)
        if geodataframe_a.shape[0] < geodataframe_b.shape[0]
        else (geodataframe_b, geodataframe_a)
    )


def get_matches(geom: Polygon, df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Get matches."""
    candidates = df.iloc[df.sindex.intersection(geom.bounds)]
    if len(candidates) > 0:
        candidates = candidates[candidates.intersects(geom)]
    return candidates
