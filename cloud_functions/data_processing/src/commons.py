import fsspec
import os
import io
import tempfile
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection

from utils.processors import clean_geometries


verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")


def adjust_eez_sovereign(eez, parent_country):
    def eez_location(row, parent_country):
        loc = row["ISO_TER1"] if isinstance(row["ISO_TER1"], str) else row["ISO_SOV1"]
        return parent_country[loc] if loc in parent_country else loc

    eez_adj = eez[["GEONAME", "ISO_TER1", "ISO_SOV1", "AREA_KM2", "geometry"]]
    eez_adj["location"] = eez_adj.apply(eez_location, axis=1, args=(parent_country,))

    return eez_adj


def load_marine_regions(params: dict, bucket: str = BUCKET):
    zipfile_name = params["zipfile_name"]
    shp_filename = f"{params['name'].rsplit('.',1)[0]}/{params['shapefile_name']}"

    gcs_zip_path = f"gs://{bucket}/{zipfile_name}"
    shp_base_name = shp_filename.rsplit(".", 1)[0]

    with fsspec.open(gcs_zip_path, mode="rb") as f:
        zip_bytes = f.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            with tempfile.NamedTemporaryFile(suffix=".zip") as tmp_zip_file:
                with zipfile.ZipFile(tmp_zip_file.name, mode="w") as new_zip:
                    for file in zf.namelist():
                        if file.startswith(shp_base_name):
                            new_zip.writestr(file, zf.read(file))

                # Build the correct path into the .shp file inside the zip
                internal_shp_path = shp_base_name + ".shp"
                zip_path = f"zip://{tmp_zip_file.name}!{internal_shp_path}"
                gdf = gpd.read_file(zip_path).pipe(clean_geometries)

    return gdf


def extract_polygons(geom):
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    elif isinstance(geom, GeometryCollection):
        polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
        return MultiPolygon(polys) if polys else None
    else:
        return None
