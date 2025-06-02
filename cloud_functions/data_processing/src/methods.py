import fsspec
from io import BytesIO
import numpy as np
import os

import pandas as pd
import requests
import gcsfs
import zipfile
import io
import fiona
import geopandas as gpd
import tempfile
from tqdm import tqdm
import shutil
from pathlib import Path

from src.params import (
    CHUNK_SIZE,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    EEZ_PARAMS,
    MPATLAS_URL,
    MPATLAS_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
    PROTECTED_SEAS_URL,
    PROTECTED_SEAS_FILE_NAME,
    ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    WDPA_API_URL,
    WDPA_URL,
    WDPA_FILE_NAME,
    ARCHIVE_WDPA_FILE_NAME,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_URL,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    HABITATS_URL,
    HABITAT_PROTECTION_FILE_NAME,
    HABITATS_ZIP_FILE_NAME,
    ARCHIVE_HABITATS_FILE_NAME,
    SEAMOUNTS_URL,
    SEAMOUNTS_SHAPEFILE_NAME,
    SEAMOUNTS_ZIPFILE_NAME,
    ARCHIVE_SEAMOUNTS_FILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
    REGIONS_FILE_NAME,
    PROTECTION_COVERAGE_FILE_NAME,
    PROTECTION_LEVEL_FILE_NAME,
    FISHING_PROTECTION_FILE_NAME,
)

from src.utils.gcp import (
    download_zip_to_gcs,
    duplicate_blob,
    load_gdb_layer_from_gcs,
    load_zipped_shapefile_from_gcs,
    read_dataframe,
    read_json_from_gcs,
    save_file_bucket,
    upload_dataframe,
)

from utils.processors import (
    add_constants,
    add_environment,
    add_protected_from_fishing_area,
    add_protected_from_fishing_percent,
    add_parent,
    add_pas_oecm,
    add_percentage_protection_mp,
    add_year,
    calculate_area,
    clean_geometries,
    convert_type,
    extract_column_dict_str,
    fp_location,
    remove_columns,
    remove_non_designated_m,
    remove_non_designated_p,
    rename_habitats,
    update_mpatlas_asterisk,
)


verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")

GLOBAL_MARINE_AREA_KM2 = 361000000
GLOBAL_TERRESTRIAL_AREA_KM2 = 134954835


def read_mpatlas_from_gcs(
    bucket: str = BUCKET, filename: str = MPATLAS_FILE_NAME
) -> gpd.GeoDataFrame:
    """
    Reads a GeoJSON file from GCS and preserves the top-level 'id' field
    as zone_id

    Parameters
    ----------
    bucket : str
        The name of the GCS bucket.
    filename : str
        Path to the GeoJSON file in the bucket.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame that includes top-level 'id' and all properties.
    """
    fs = gcsfs.GCSFileSystem()
    with fs.open(f"gs://{bucket}/{filename}", "rb") as f:
        raw_bytes = f.read()

    # Open the GeoJSON from in-memory bytes
    with fiona.open(BytesIO(raw_bytes), driver="GeoJSON") as src:
        features = list(src)

        # Extract top-level 'id' and merge with properties
        for feature in features:
            feature["properties"]["zone_id"] = feature.get("id")

        gdf = gpd.GeoDataFrame.from_features(features)
        gdf.set_crs(src.crs, inplace=True)

    return gdf


def download_and_duplicate_zipfile(
    url: str,
    bucket: str,
    blob_name: str,
    archive_blob_name: str,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads a ZIP file from a URL and stores it in Google Cloud Storage,
    then creates a duplicate of the uploaded blob within the same GCS bucket.

    Parameters:
    ----------
    url : str
        Public or authenticated URL pointing to the ZIP file to download.
    bucket : str
        Name of the GCS bucket where the file will be stored.
    blob_name : str
        Name of the target blob to be created as a duplicate.
    archive_blob_name : str
        Name of the original blob that receives the downloaded ZIP content.
    chunk_size : int, optional
        Size (in bytes) of each chunk used during the download/upload process.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """
    if verbose:
        print(f"downloading {url} to gs://{bucket}/{archive_blob_name}")
    download_zip_to_gcs(url, bucket, archive_blob_name, chunk_size=chunk_size, verbose=verbose)
    duplicate_blob(bucket, archive_blob_name, blob_name, verbose=True)


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


def adjust_eez_sovereign(eez, parent_country):
    def eez_location(row, parent_country):
        loc = row["ISO_TER1"] if isinstance(row["ISO_TER1"], str) else row["ISO_SOV1"]
        return parent_country[loc] if loc in parent_country else loc

    eez_adj = eez[["GEONAME", "ISO_TER1", "ISO_SOV1", "AREA_KM2", "geometry"]]
    eez_adj["location"] = eez_adj.apply(eez_location, axis=1, args=(parent_country,))

    return eez_adj


def get_protected_areas(
    bucket: str = BUCKET, wdpa_file_name: str = WDPA_FILE_NAME, verbose: bool = True
):
    fs = gcsfs.GCSFileSystem()
    gcs_path = f"gs://{bucket}/{wdpa_file_name}"

    if verbose:
        print(f"downloading {gcs_path}")
    with tempfile.TemporaryDirectory() as tmpdir:
        local_zip_path = Path(tmpdir) / "gdb.zip"
        local_extract_path = Path(tmpdir) / "gdb_extracted"

        # Download zip from GCS
        with fs.open(gcs_path, "rb") as remote_file, open(local_zip_path, "wb") as local_file:
            shutil.copyfileobj(remote_file, local_file)

        # Extract the zip file
        shutil.unpack_archive(local_zip_path, local_extract_path)

        # Find the GDB folder inside
        gdb_dirs = list(local_extract_path.glob("*.gdb"))
        if not gdb_dirs:
            raise FileNotFoundError("No .gdb directory found after extraction.")
        gdb_path = gdb_dirs[0]  # Assuming only one .gdb folder

        if verbose:
            print("loading layers")

        layers = fiona.listlayers(gdb_path)
        wdpa = gpd.GeoDataFrame()
        for layer in layers:
            print(layer)
            wdpa = pd.concat((wdpa, gpd.read_file(gdb_path, layer=layer)), axis=0)

    return wdpa


def download_mpatlas_zone(
    url: str = MPATLAS_URL,
    bucket: str = BUCKET,
    filename: str = MPATLAS_FILE_NAME,
    archive_filename: str = ARCHIVE_MPATLAS_FILE_NAME,
    verbose: bool = True,
) -> None:
    """
    Downloads the MPAtlas Zone Assessment dataset from a specified URL,
    saves it to a Google Cloud Storage bucket, and duplicates the blob.

    Parameters:
    ----------
    url : str
        URL of the MPAtlas Zone Assessment file to download.
    bucket : str
        Name of the GCS bucket where the file should be stored.
    filename : str
        GCS blob name for the primary reference copy of the file.
    archive_filename : str
        GCS blob name for the archived/original version of the file.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    if verbose:
        print(f"downloading MPAtlas Zone Assessment from {url}")

    response = requests.get(url)
    response.raise_for_status()

    if verbose:
        print(f"saving MPAtlas Zone Assessment to gs://{bucket}/{archive_filename}")
    save_file_bucket(
        response.content,
        response.headers.get("Content-Type"),
        archive_filename,
        bucket,
        verbose=verbose,
    )
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


def download_mpatlas_country(
    bucket: str = BUCKET,
    project: str = PROJECT,
    url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    current_filename: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    archive_filename: str = ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    upload_dataframe(bucket, pd.DataFrame(data), archive_filename, project_id=project, verbose=True)
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_mpatlas(
    url: str = MPATLAS_URL,
    bucket: str = BUCKET,
    project: str = PROJECT,
    mpatlas_filename: str = MPATLAS_FILE_NAME,
    archive_mpatlas_filename: str = ARCHIVE_MPATLAS_FILE_NAME,
    mpatlas_country_url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    mpatlas_country_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    archive_mpatlas_country_file_name: str = ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    verbose: bool = True,
) -> None:
    download_mpatlas_country(
        bucket,
        project,
        mpatlas_country_url,
        mpatlas_country_file_name,
        archive_mpatlas_country_file_name,
    )

    download_mpatlas_zone(
        url,
        bucket,
        mpatlas_filename,
        archive_mpatlas_filename,
        verbose,
    )


def download_protected_seas(
    url: str = PROTECTED_SEAS_URL,
    bucket: str = BUCKET,
    filename: str = PROTECTED_SEAS_FILE_NAME,
    archive_filename: str = ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    project: str = PROJECT,
    verbose: bool = True,
) -> None:
    """
    Downloads Protected Seas data from the provided URL, processes it into a DataFrame,
    and uploads both a current version and an archived version to Google Cloud Storage.

    Parameters:
    ----------
    url : str
        The URL to fetch the Protected Seas data from.
    bucket : str
        GCS bucket name where the data will be saved.
    filename : str
        Blob name for the current, active version of the data.
    archive_filename : str
        Blob name for the archived version of the data.
    project : str
        Google Cloud project ID used for authentication during upload.
    verbose : bool, optional
        If True, prints progress and status messages. Default is True.
    """
    response = requests.get(url)
    response.raise_for_status()

    data = pd.DataFrame(response.json())

    data["includes_multi_jurisdictional_areas"] = data["includes_multi_jurisdictional_areas"].map(
        {"t": True, "f": False}
    )

    if verbose:
        print(f"saving Protected Seas to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


def download_protected_planet_global(
    current_filename: str,
    archive_filename: str,
    project_id: str = PROJECT,
    url: str = WDPA_GLOBAL_LEVEL_URL,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """
    Downloads the Global Protected Planet statistics CSV from the specified URL,
    uploads it to Google Cloud Storage, and stores both an archived and current version.

    Parameters:
    ----------
    current_filename : str
        GCS blob name for the primary/current version of the data.
    archive_filename : str
        GCS blob name for the archived version of the data.
    project_id : str, optional
        Google Cloud project ID used for authentication. Defaults to `PROJECT`.
    url : str, optional
        URL to download the global statistics CSV. Defaults to `WDPA_GLOBAL_LEVEL_URL`.
    bucket : str, optional
        GCS bucket name where the file will be saved. Defaults to `BUCKET`.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    response = requests.get(url)
    response.raise_for_status()
    data = pd.read_csv(BytesIO(response.content))

    if verbose:
        print(f"saving Global Protected Planet statistics to to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project_id, verbose=True)
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet_country(
    current_filename: str,
    archive_filename: str,
    pp_api_key: str,
    bucket: str = BUCKET,
    project: str = PROJECT,
    url: str = WDPA_API_URL,
    per_page: int = 50,
    verbose: bool = True,
) -> None:
    """
    Downloads country-level statistics from the Protected Planet API,
     compiles all paginated results, and uploads the data to Google Cloud Storage
     as both a current and archived file.

    Parameters:
    ----------
    current_filename : str
        GCS blob name for the latest, actively used version of the data.
    archive_filename : str
        GCS blob name for the archived backup copy of the data.
    pp_api_key : str
        Protected Planet API token for authenticated requests.
    bucket : str, optional
        Name of the GCS bucket to upload data to. Defaults to `BUCKET`.
    project : str, optional
        Google Cloud project ID used during upload. Defaults to `PROJECT`.
    url : str, optional
        Base URL of the Protected Planet API. Defaults to `WDPA_API_URL`.
    per_page : int, optional
        Number of results to fetch per API page. Default is 50.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """

    def fetch_data(params):
        response = requests.get(f"{url}/countries", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("countries", [])

    page = 1
    params = {"token": pp_api_key, "per_page": per_page, "page": page}
    all_areas = []

    results = fetch_data(params)
    while results:
        if verbose:
            print(f"Fetching page {page}...")

        all_areas.extend(results)
        page += 1
        params = {"token": pp_api_key, "per_page": per_page, "page": page}
        results = fetch_data(params)

    if verbose:
        print(f"Uploading {len(all_areas)} protected areas to gs://{bucket}/{archive_filename}")

    upload_dataframe(
        bucket, pd.DataFrame(all_areas), archive_filename, project_id=project, verbose=True
    )
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet(
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    archive_wdpa_global_level_file_name: str = ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    archive_wdpa_country_level_file_name: str = ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    pp_api_key: str = PP_API_KEY,
    project_id: str = PROJECT,
    wdpa_global_url: str = WDPA_GLOBAL_LEVEL_URL,
    wdpa_url: str = WDPA_URL,
    api_url: str = WDPA_API_URL,
    wdpa_file_name: str = WDPA_FILE_NAME,
    archive_wdpa_file_name: str = ARCHIVE_WDPA_FILE_NAME,
    bucket: str = BUCKET,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads and processes data from Protected Planet, including:
    - The main WDPA ZIP archive
    - Global-level protected area statistics
    - Country-level protected area statistics

    All datasets are stored in Google Cloud Storage with both current and archived versions.

    Parameters:
    ----------
    wdpa_global_level_file_name : str
        GCS blob name for the current global statistics file.
    archive_wdpa_global_level_file_name : str
        GCS blob name for the archived global statistics file.
    wdpa_country_level_file_name : str
        GCS blob name for the current country statistics file.
    archive_wdpa_country_level_file_name : str
        GCS blob name for the archived country statistics file.
    pp_api_key : str
        Protected Planet API token for accessing country-level stats.
    project_id : str
        Google Cloud project ID used for uploads.
    wdpa_global_url : str
        URL for the global statistics CSV.
    wdpa_url : str
        URL for the WDPA ZIP file.
    api_url : str
        URL for the Protected Planet API (used for country-level stats).
    wdpa_file_name : str
        GCS blob name for the current WDPA ZIP file.
    archive_wdpa_file_name : str
        GCS blob name for the archived WDPA ZIP file.
    bucket : str
        Name of the GCS bucket to upload all files to.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """
    # download wdpa
    download_and_duplicate_zipfile(
        wdpa_url,
        bucket,
        wdpa_file_name,
        archive_wdpa_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )

    # download wdpa global stats
    download_protected_planet_global(
        wdpa_global_level_file_name,
        archive_wdpa_global_level_file_name,
        project_id=project_id,
        url=wdpa_global_url,
        bucket=bucket,
    )

    # download wdpa country stats
    download_protected_planet_country(
        wdpa_country_level_file_name,
        archive_wdpa_country_level_file_name,
        pp_api_key,
        bucket=bucket,
        project=project_id,
        url=api_url,
        per_page=50,
        verbose=verbose,
    )


def download_habitats(
    habitats_url: str = HABITATS_URL,
    habitats_file_name: str = HABITATS_ZIP_FILE_NAME,
    archive_habitats_file_name: str = ARCHIVE_HABITATS_FILE_NAME,
    seamounts_url: str = SEAMOUNTS_URL,
    seamounts_zipfile_name: str = SEAMOUNTS_ZIPFILE_NAME,
    archive_seamounts_file_name: str = ARCHIVE_SEAMOUNTS_FILE_NAME,
    bucket: str = BUCKET,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads habitat-related datasets (habitats and seamounts) and uploads them to GCS
    as both current and archived versions.

    Parameters:
    ----------
    habitats_url : str
        URL to download the general habitat ZIP file.
    habitats_file_name : str
        GCS blob name for the current habitat dataset.
    archive_habitats_file_name : str
        GCS blob name for the archived habitat dataset.
    seamounts_url : str
        URL to download the seamounts ZIP file.
    seamounts_zipfile_name : str
        GCS blob name for the current seamounts dataset.
    archive_seamounts_file_name : str
        GCS blob name for the archived seamounts dataset.
    bucket : str
        Name of the GCS bucket where all files will be uploaded.
    chunk_size : int, optional
        Size in bytes of each chunk used during download.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    # download habitats
    download_and_duplicate_zipfile(
        habitats_url,
        bucket,
        habitats_file_name,
        archive_habitats_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )

    # download mangroves
    # TODO: Add this

    # download seamounts
    download_and_duplicate_zipfile(
        seamounts_url,
        bucket,
        seamounts_zipfile_name,
        archive_seamounts_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )


def generate_protected_areas_table(
    wdpa_file_name: str = WDPA_FILE_NAME,
    mpatlas_file_name: str = MPATLAS_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    def unique_pa(w, m, wdpa_id):
        w = w[w["wdpa_id"] == wdpa_id].sort_values(by="wdpa_pid")
        m = m[m["wdpa_id"] == wdpa_id].sort_values(by="wdpa_pid")

        if len(w) > 0:
            parent = w[w["wdpa_id"] == w["wdpa_pid"]]
            parent = parent.iloc[0:1] if len(parent) == 1 else w.iloc[0:1]
            children = (
                pd.concat([w.drop(index=parent.index), m], axis=0)
                if len(m) > 0
                else w.drop(index=parent.index)
            )
        else:
            parent = m[m["wdpa_id"] == m["wdpa_pid"]]
            parent = parent.iloc[0:1] if len(parent) == 1 else m.iloc[0:1]
            children = m.drop(index=parent.index)

        parent = parent.copy()
        children = children.copy()
        parent["parent"] = True
        children["parent"] = False

        return pd.concat([parent, children], axis=0)

    if verbose:
        print(f"loading gs://{bucket}/{wdpa_file_name}")
    wdpa = load_gdb_layer_from_gcs(wdpa_file_name, bucket)

    if verbose:
        print(f"loading gs://{bucket}/{mpatlas_file_name}")
    mpatlas = read_mpatlas_from_gcs(bucket, mpatlas_file_name)

    related_countries = read_json_from_gcs(BUCKET, RELATED_COUNTRIES_FILE_NAME, verbose=True)
    parent_dict = {}
    for cnt in related_countries:
        for c in related_countries[cnt]:
            parent_dict[c] = cnt

    if verbose:
        print("processing WDPAs")
    wdpa_dict = {
        "NAME": "name",
        "GIS_AREA": "area",
        "STATUS": "STATUS",
        "STATUS_YR": "year",
        "WDPAID": "wdpa_id",
        "DESIG_TYPE": "designation",
        "ISO3": "iso_3",
        "IUCN_CAT": "iucn_category",
        "MARINE": "MARINE",
        "PARENT_ISO3": "parent_id",
        "geometry": "geometry",
    }
    cols = [i for i in wdpa_dict]

    wdpa_pa = (
        wdpa[cols]
        .rename(columns=wdpa_dict)
        .pipe(remove_non_designated_p)
        .pipe(add_environment)
        .pipe(add_constants, {"data_source": "Protected Planet"})
        .pipe(remove_columns, ["STATUS", "MARINE"])
        .pipe(convert_type, {"wdpa_id": [pd.Int64Dtype(), str], "wdpa_pid": [str]})
    )

    if verbose:
        print("processing MPAs")

    mpa_dict = {
        "name": "name",
        "designated_date": "designated_date",
        "wdpa_id": "wdpa_id",
        "designation": "designation",
        "establishment_stage": "mpaa_establishment_stage",
        "sovereign": "location",
        "protection_mpaguide_level": "mpaa_protection_level",
        "geometry": "geometry",
    }
    cols = [i for i in mpa_dict]
    mpa_pa = (
        mpatlas[cols]
        .rename(columns=mpa_dict)
        .pipe(remove_non_designated_m)
        .pipe(add_year)
        .pipe(add_constants, {"environment": "marine", "data_source": "MPATLAS"})
        .pipe(remove_columns, "designated_date")
        .pipe(calculate_area)
        .pipe(add_parent, parent_dict, location_name="location")
        .pipe(convert_type, {"wdpa_id": [pd.Int64Dtype(), str], "wdpa_pid": [str]})
    )

    results = []
    for environment in ["marine", "terrestrial"]:
        print(environment)

        # Filter once per environment
        w = wdpa_pa[wdpa_pa["environment"] == environment]
        m = mpa_pa[mpa_pa["environment"] == environment]

        # Union of unique wdpa_ids
        wdpa_ids = sorted(set(w["wdpa_id"]) | set(m["wdpa_id"]))

        for wdpa_id in tqdm(wdpa_ids):
            entries = unique_pa(w, m, wdpa_id)
            results.append(entries)

    # Combine all at once
    protected_areas = pd.concat(results, axis=0, ignore_index=True)

    return protected_areas.to_dict(orient="records")


def load_regions(
    bucket: str = BUCKET,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    regions_file_name: str = REGIONS_FILE_NAME,
):
    # Load related countries and regions
    related_countries = read_json_from_gcs(bucket, related_countries_file_name, verbose=verbose)
    regions = read_json_from_gcs(bucket, regions_file_name, verbose=verbose)

    combined_regions = related_countries | regions
    combined_regions["GLOB"] = []

    parent_country = {}
    for cnt in combined_regions:
        if len(cnt) == 3:
            for c in combined_regions[cnt]:
                parent_country[c] = cnt

    return combined_regions, parent_country


def create_habitat_subtable(
    bucket: str, habitats_file_name: str, combined_regions: dict, verbose: bool
):
    def get_group_stats(df, loc, relations, habitat):
        if loc == "GLOB":
            df_group = df[df["habitat"] == habitat].replace("-", np.nan)
            total_area = GLOBAL_MARINE_AREA_KM2
        else:
            df_group = df[(df["ISO3"].isin(relations[loc])) & (df["habitat"] == habitat)].replace(
                "-", np.nan
            )

            # Ensure numeric conversion
            df_group["total_area"] = pd.to_numeric(df_group["total_area"], errors="coerce")
            total_area = df_group["total_area"].sum()

        df_group["protected_area"] = pd.to_numeric(df_group["protected_area"], errors="coerce")
        protected_area = df_group["protected_area"].sum()

        return {
            "location": loc,
            "habitat": habitat,
            "environment": "marine",
            "protected_area": protected_area,
            "total_area": total_area,
            # "percent_protected": 100 * protected_area / total_area if total_area else None,
        }

    habitats = ["warmwatercorals", "coldwatercorals", "seagrasses", "saltmarshes"]

    if verbose:
        print("downloading habitats zipfile into memory")

    fs = gcsfs.GCSFileSystem()
    with fs.open(f"gs://{bucket}/{habitats_file_name}", "rb") as f:
        zip_bytes = f.read()

    dfs = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in habitats:
            with zf.open(f"Ocean+HabitatsDownload_Global/{name}.csv") as csv_file:
                dfs[name] = pd.read_csv(csv_file)

    if verbose:
        print("generating habitats table")

    marine_habitats = pd.DataFrame()
    for habitat in habitats:
        tmp = dfs[habitat][["ISO3", "protected_area", "total_area"]].copy()
        tmp["environment"] = "marine"
        tmp["habitat"] = habitat
        marine_habitats = pd.concat((marine_habitats, tmp))

    if verbose:
        print("Grouping by sovereign country and region")

    marine_habitats_group = []
    for habitat in habitats:
        df = pd.DataFrame(
            [
                stat
                for loc in combined_regions
                if (stat := get_group_stats(marine_habitats, loc, combined_regions, habitat))
                is not None
            ]
        )
        marine_habitats_group.append(df)

    return pd.concat(marine_habitats_group, axis=0, ignore_index=True)


def create_seamounts_subtable(
    seamounts_zipfile_name,
    seamounts_shapefile_name,
    bucket,
    eez,
    marine_protected_areas,
    combined_regions,
    verbose,
):
    def get_group_stats(df_eez, df_pa, loc, relations):
        if loc == "GLOB":
            df_eez_group = df_eez[["PEAKID", "AREA2D"]].drop_duplicates()
            df_pa_group = df_pa[["PEAKID", "AREA2D"]].drop_duplicates()
            total_area = GLOBAL_MARINE_AREA_KM2
        else:
            df_eez_group = df_eez[df_eez["location"].isin(relations[loc])][
                ["PEAKID", "AREA2D"]
            ].drop_duplicates()
            df_pa_group = df_pa[df_pa["location"].isin(relations[loc])][
                ["PEAKID", "AREA2D"]
            ].drop_duplicates()
            total_area = df_eez_group["AREA2D"].sum()

        protected_area = min(df_pa_group["AREA2D"].sum(), total_area)

        return {
            "location": loc,
            "habitat": "seamounts",
            "environment": "marine",
            "protected_area": protected_area,
            "total_area": total_area,
            # "percent_protected": 100 * protected_area / total_area if total_area > 0 else np.nan,
        }

    if verbose:
        print("loading seamounts")

    seamounts = load_zipped_shapefile_from_gcs(
        seamounts_zipfile_name, bucket, internal_shapefile_path=seamounts_shapefile_name
    )

    if verbose:
        print("spatially joining seamounts with eezs and marine protected areas")

    eez_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        eez[["GEONAME", "location", "geometry"]],
        how="left",
        predicate="within",
    )

    marine_pa_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        marine_protected_areas[["wdpa_id", "location", "geometry"]],
        how="left",
        predicate="within",
    )

    return pd.DataFrame(
        [
            get_group_stats(eez_joined, marine_pa_joined, cnt, combined_regions)
            for cnt in combined_regions
        ]
    )


def generate_habitat_protection_table(
    habitats_zipfile_name: str = HABITATS_ZIP_FILE_NAME,
    seamounts_zipfile_name: str = SEAMOUNTS_ZIPFILE_NAME,
    seamounts_shapefile_name: str = SEAMOUNTS_SHAPEFILE_NAME,
    file_name_out: str = HABITAT_PROTECTION_FILE_NAME,
    eez_params: dict = EEZ_PARAMS,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    combined_regions, parent_country = load_regions()

    if verbose:
        print("loading eezs")
    eez = load_marine_regions(eez_params, bucket)
    eez = adjust_eez_sovereign(eez, parent_country)

    if verbose:
        print("getting marine protected areas (this may take a few minutes)")

    protected_areas = get_protected_areas()
    marine_protected_areas = protected_areas[protected_areas["MARINE"].isin(["1", "2"])]
    marine_protected_areas = marine_protected_areas.rename(
        columns={"WDPAID": "wdpa_id", "PARENT_ISO3": "location"}
    )
    marine_protected_areas = marine_protected_areas[["wdpa_id", "location", "geometry"]]

    marine_habitats_subtable = create_habitat_subtable(
        bucket, habitats_zipfile_name, combined_regions, verbose
    )
    seamounts_subtable = create_seamounts_subtable(
        seamounts_zipfile_name,
        seamounts_shapefile_name,
        bucket,
        eez,
        marine_protected_areas,
        combined_regions,
        verbose,
    )

    # TODO: add mangroves
    marine_habitats = pd.concat((marine_habitats_subtable, seamounts_subtable), axis=0)

    # TODO: combine with terrestrial
    habitats = marine_habitats.copy()

    habitats = habitats[habitats["total_area"] > 0].pipe(rename_habitats)

    upload_dataframe(bucket, habitats, file_name_out, project_id=project, verbose=True)

    return habitats.to_dict(orient="records")


def generate_protection_coverage_stats_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protection_coverage_file_name: str = PROTECTION_COVERAGE_FILE_NAME,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    percent_type: str = "area",  # area or counts,
    verbose: bool = True,
):
    def process_protected_area(wdpa_country, environment="marine"):
        wdpa_dict = {
            "id": "location",
            "pas_count": "protected_areas_count",
            "statistics": "statistics",
        }

        stats_dict = {
            f"{environment}_area": "area",
            f"oecms_pa_{environment}_area": "protected_area",
            f"percentage_oecms_pa_{environment}_cover": "coverage",
            f"pa_{environment}_area": "pa_protected_area",
            f"percentage_pa_{environment}_cover": "pa_coverage",
            "protected_area_polygon_count": "protected_area_polygon_count",
            "protected_area_point_count": "protected_area_point_count",
            "oecm_polygon_count": "oecm_polygon_count",
            "oecm_point_count": "oecm_point_count",
        }
        cols = [i for i in wdpa_dict]
        wdpa_cl = (
            wdpa_country[cols]
            .rename(columns=wdpa_dict)
            .pipe(add_constants, {"environment": environment})
            .pipe(extract_column_dict_str, stats_dict, "statistics")
            .pipe(add_pas_oecm)
            .pipe(
                remove_columns,
                [
                    "statistics",
                    "protected_area_polygon_count",
                    "protected_area_point_count",
                    "oecm_polygon_count",
                    "oecm_point_count",
                ],
            )
        )
        return wdpa_cl

    def get_group_stats(df, loc, relations, percent_type):
        """
        Computes summary stats for a group of related locations.
        """
        if loc != "GLOB":
            df_group = df[df["location"].isin(relations[loc])]
            total_area = df_group["area"].sum()
        else:
            return None

        if len(df_group) > 0:
            total_protected_area = df_group["protected_area"].sum()
            if percent_type == "area":
                coverage = df_group["coverage"].sum()
                pas = 100 * df_group["pa_coverage"].sum() / coverage if coverage > 0 else 0
                oecm = 100 - pas if coverage > 0 else 0
            elif percent_type == "counts":
                pas = (
                    100
                    * df_group["pas_count"].sum()
                    / (df_group["pas_count"] + df_group["oecm_count"]).sum()
                )
                oecm = (
                    100
                    * df_group["oecm_count"].sum()
                    / (df_group["pas_count"] + df_group["oecm_count"]).sum()
                )
            global_area = (
                GLOBAL_MARINE_AREA_KM2
                if df_group.iloc[0]["environment"] == "marine"
                else GLOBAL_TERRESTRIAL_AREA_KM2
            )

            return {
                "location": loc,
                "environment": df_group.iloc[0]["environment"] if not df_group.empty else None,
                "protected_area": total_protected_area,
                "protected_areas_count": df_group["protected_areas_count"].sum(),
                "coverage": 100 * total_protected_area / total_area if total_area else None,
                "pas": pas,
                "oecms": oecm,
                "global_contribution": 100 * total_protected_area / global_area,
                "area": total_area,
            }
        else:
            return None

    def group_by_region(wdpa_cl, combined_regions):
        reg = pd.DataFrame(
            stat
            for loc in combined_regions
            if (stat := get_group_stats(wdpa_cl, loc, combined_regions, percent_type)) is not None
        )
        reg = reg[reg["protected_area"] > 0]

        return reg

    def add_global_stats(df, global_stats, environment):
        def get_value(df, col):
            return df[df["type"] == col].iloc[0]["value"]

        environment2 = "ocean" if environment == "marine" else "land"
        oecms_pas = get_value(global_stats, f"total_{environment2}_area_oecms_pas")
        oecms = get_value(global_stats, f"total_{environment2}_area_oecms")
        pas = oecms_pas - oecms

        return pd.concat(
            (
                df,
                pd.DataFrame(
                    [
                        {
                            "location": "GLOB",
                            "environment": environment,
                            "protected_area": get_value(
                                global_stats, f"total_{environment2}_area_oecms_pas"
                            ),
                            "protected_areas_count": get_value(
                                global_stats, f"total_{environment}_oecms_pas"
                            ),
                            "coverage": get_value(
                                global_stats, f"total_{environment2}_oecms_pas_coverage_percentage"
                            ),
                            "pas": 100 * pas / oecms_pas,
                            "oecms": 100 * oecms / oecms_pas,
                            "global_contribution": get_value(
                                global_stats, f"total_{environment2}_oecms_pas_coverage_percentage"
                            ),
                        }
                    ]
                ),
            )
        )

    # Load protected planet country level statistics
    if verbose:
        print(
            f"loading Protected Planet Country-level data gs://{bucket}/{wdpa_country_level_file_name}"
        )
    wdpa_country = read_dataframe(bucket, wdpa_country_level_file_name)

    if verbose:
        print(
            f"loading Protected Planet Global-level data gs://{bucket}/{wdpa_global_level_file_name}"
        )
    wdpa_global = read_dataframe(bucket, wdpa_global_level_file_name)

    # Load related countries and regions
    if verbose:
        print("loading country and region groupings")
    combined_regions, _ = load_regions()

    # WDPA country level
    if verbose:
        print("processing Marine and terrestrial country level stats")

    wdpa_cl_m = process_protected_area(wdpa_country, environment="marine")
    wdpa_cl_t = process_protected_area(wdpa_country, environment="land")
    wdpa_cl_t["environment"] = wdpa_cl_t["environment"].replace("land", "terrestrial")

    if verbose:
        print("Grouping by sovereign country and region")

    # Roll up into sovereign countries and regions
    reg_t = group_by_region(wdpa_cl_t, combined_regions)
    reg_m = group_by_region(wdpa_cl_m, combined_regions)

    protection_coverage_table = pd.concat((reg_t, reg_m), axis=0)
    protection_coverage_table = protection_coverage_table[protection_coverage_table["area"] > 0]
    protection_coverage_table = (
        protection_coverage_table.drop(columns="area")
        .pipe(add_global_stats, wdpa_global, "marine")
        .pipe(add_global_stats, wdpa_global, "terrestrial")
    )

    upload_dataframe(
        bucket,
        protection_coverage_table,
        protection_coverage_file_name,
        project_id=project,
        verbose=verbose,
    )

    return protection_coverage_table.to_dict(orient="records")


def generate_marine_protection_level_stats_table(
    mpatlas_country_level_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    protection_level_file_name: str = PROTECTION_LEVEL_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    def get_group_stats(df, loc, relations, protection_level="highly/fully"):
        if loc == "GLOB":
            df_group = df
            total_area = GLOBAL_MARINE_AREA_KM2
        else:
            df_group = df[df["location"].isin(relations[loc])]
            total_area = df_group["area"].sum()

        if len(df_group) > 0:
            total_protected_area = df_group["protected_area"].sum()

            return {
                "location": loc,
                "protected_area": total_protected_area,
                "area": total_area,
                "mpaa_protection_level": protection_level,
                "percent": 100 * total_protected_area / total_area if total_area > 0 else None,
            }
        else:
            return None

    # Load related countries and regions
    if verbose:
        print("loading country and region groupings")
    combined_regions, _ = load_regions()

    # Load MPAtlas Country level statistics
    if verbose:
        print(
            f"loading MPAtlas country-level stats from gs://{bucket}/{mpatlas_country_level_file_name}"
        )
    mpatlas_country = read_dataframe(bucket, mpatlas_country_level_file_name)

    if verbose:
        print("Calculating Marine Protection Level Statistics")

    protection_level = "highly/fully"
    mpa_dict = {
        "id": "location",
        "highly_protected_km2": "protected_area",
        "wdpa_marine_km2": "area",
    }
    cols = [i for i in mpa_dict]
    mpa_cl_mps = (
        mpatlas_country[cols]
        .rename(columns=mpa_dict)
        .pipe(add_constants, {"mpaa_protection_level": protection_level})
        .pipe(add_percentage_protection_mp)
        .pipe(update_mpatlas_asterisk, asterisk=False)
    )

    if verbose:
        print("Grouping by sovereign country and region")
    protection_level_table = pd.DataFrame(
        stat
        for loc in combined_regions
        if (
            stat := get_group_stats(
                mpa_cl_mps,
                loc,
                combined_regions,
                protection_level=protection_level,
            )
        )
        is not None
    )

    protection_level_table = protection_level_table[protection_level_table["area"] > 0]

    upload_dataframe(
        bucket,
        protection_level_table,
        protection_level_file_name,
        project_id=project,
        verbose=verbose,
    )

    return protection_level_table.to_dict(orient="records")


def generate_fishing_protection_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protected_seas_file_name: str = PROTECTED_SEAS_FILE_NAME,
    fishing_protecton_file_name: str = FISHING_PROTECTION_FILE_NAME,
    verbose: bool = True,
):
    def get_group_stats(
        df,
        loc,
        relations,
        global_marine_area=361000000,
        fishing_protection_level="highly",
    ):
        if loc == "GLOB":
            df_group = df
            total_area = global_marine_area
        else:
            df_group = df[df["location"].isin(relations[loc])]
            total_area = df_group["area"].sum()

        protected_area = df_group[f"{fishing_protection_level}_protected_area"].sum()
        assessed = True if len(df) > 0 else False

        return {
            "location": loc,
            "area": protected_area if assessed else None,
            "fishing_protection_level": fishing_protection_level,
            "pct": (
                min(100, 100 * protected_area / total_area) if assessed and total_area > 0 else None
            ),
            "total_area": total_area,
        }

    # Load related countries and regions
    if verbose:
        print("loading country and region groupings")
    combined_regions, _ = load_regions()

    if verbose:
        print(f"downloading Protected Seas from gs://P{bucket}/{protected_seas_file_name}")
    protected_seas = read_dataframe(bucket, protected_seas_file_name)

    if verbose:
        print("processing fishing level protection")

    fishing_protection_levels = {
        "highly": ["lfp5_area", "lfp4_area"],
        "moderately": ["lfp3_area"],
        "less": ["lfp2_area", "lfp1_area"],
    }

    ps_dict = {
        "iso_ter": "iso_ter",
        "iso_sov": "iso_sov",
        "total_area": "area",
        "lfp5_area": "lfp5_area",
        "lfp4_area": "lfp4_area",
        "lfp3_area": "lfp3_area",
        "lfp2_area": "lfp2_area",
        "lfp1_area": "lfp1_area",
    }
    cols = [i for i in ps_dict]

    ps_cl_fp = (
        protected_seas[cols]
        .rename(columns=ps_dict)
        .pipe(fp_location)
        .pipe(add_protected_from_fishing_area, fishing_protection_levels)
        .pipe(add_protected_from_fishing_percent, fishing_protection_levels)
        .pipe(
            remove_columns,
            ["iso_ter", "iso_sov", "lfp5_area", "lfp4_area", "lfp3_area", "lfp2_area", "lfp1_area"],
        )
    )

    fishing_protection_table = pd.DataFrame()
    for level in fishing_protection_levels:
        fishing_protection_table = pd.concat(
            (
                fishing_protection_table,
                pd.DataFrame(
                    stat
                    for loc in combined_regions
                    if (
                        stat := get_group_stats(
                            ps_cl_fp,
                            loc,
                            combined_regions,
                            fishing_protection_level=level,
                        )
                    )
                    is not None
                ),
            ),
            axis=0,
        )

    # Remove countries with no ocean
    fishing_protection_table = fishing_protection_table[
        fishing_protection_table["total_area"] > 0
    ].drop(columns="total_area")

    upload_dataframe(
        bucket,
        fishing_protection_table,
        fishing_protecton_file_name,
        project_id=project,
        verbose=verbose,
    )

    return fishing_protection_table.to_dict(orient="records")
