from io import BytesIO
import os
import pandas as pd
import requests
import gcsfs
import zipfile
import io
import fiona
import geopandas as gpd

from src.params import (
    CHUNK_SIZE,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
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
    HABITATS_FILE_NAME,
    HABITATS_ZIP_FILE_NAME,
    ARCHIVE_HABITATS_FILE_NAME,
    SEAMOUNTS_URL,
    SEAMOUNTS_FILE_NAME,
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
    read_dataframe,
    read_json_from_gcs,
    save_file_bucket,
    upload_dataframe,
)

from utils.processors import (
    add_constants,
    add_environment,
    add_highly_protected_from_fishing_area,
    add_highly_protected_from_fishing_percent,
    add_pas_oecm,
    add_percentage_protection_mp,
    add_year,
    calculate_area,
    extract_column_dict_str,
    remove_columns,
    remove_non_designated_m,
    remove_non_designated_p,
    update_mpatlas_asterisk,
)

verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")

GLOBAL_MARINE_AREA_KM2 = 361000000


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


def download_mpatlas(
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
    habitats_file_name: str = HABITATS_FILE_NAME,
    archive_habitats_file_name: str = ARCHIVE_HABITATS_FILE_NAME,
    seamounts_url: str = SEAMOUNTS_URL,
    seamounts_file_name: str = SEAMOUNTS_FILE_NAME,
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
    seamounts_file_name : str
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
        seamounts_file_name,
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
    if verbose:
        print(f"loading gs://{bucket}/{wdpa_file_name}")
    wdpa = load_gdb_layer_from_gcs(wdpa_file_name, bucket)

    if verbose:
        print(f"loading gs://{bucket}/{mpatlas_file_name}")
    mpatlas = read_mpatlas_from_gcs(bucket, mpatlas_file_name)

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
    )

    return wdpa_pa, mpa_pa


def generate_habitats_table(
    habitats_file_name: str = HABITATS_ZIP_FILE_NAME,
    file_name_out: str = HABITATS_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    habitats = ["warmwatercorals", "coldwatercorals", "seagrasses", "saltmarshes"]

    if verbose:
        print("downloading habitats zipfile into memory")

    with gcsfs.GCSFileSystem() as fs:
        with fs.open(f"gs://{bucket}/{habitats_file_name}", "rb") as f:
            zip_bytes = f.read()

    dfs = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
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

    # TODO: Add Mangroves and Sea Mounts

    upload_dataframe(bucket, marine_habitats, file_name_out, project_id=project, verbose=True)


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

    return combined_regions


def generate_protection_coverage_stats_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protection_coverage_file_name: str = PROTECTION_COVERAGE_FILE_NAME,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    percent_type: str = "area",  # area or counts,
    verbose: bool = True,
):
    def process_protected_area(wdpa_country, environment="marine"):
        wdpa_dict = {
            "id": "location",
            "pas_count": "protected_area_count",
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
        if loc == "GLOB":
            df_group = df
            total_area = GLOBAL_MARINE_AREA_KM2
        else:
            df_group = df[df["location"].isin(relations[loc])]
            total_area = df_group["area"].sum()

        if len(df_group) > 0:
            total_protected_area = df_group["protected_area"].sum()
            if percent_type == "area":
                coverage = df_group["coverage"].sum()
                pas = 100 * df_group["pa_coverage"].sum() / coverage if coverage > 0 else None
                oecm = 100 - pas if pas is not None else None
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

            return {
                "location": loc,
                "environment": df_group.iloc[0]["environment"] if not df_group.empty else None,
                "protected_area": total_protected_area,
                "protected_area_count": df_group["protected_area_count"].sum(),
                "coverage": 100 * total_protected_area / total_area if total_area else None,
                "pas": pas,
                "oecm": oecm,
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
        global_protected_area = reg[reg["location"] == "GLOB"].iloc[0]["protected_area"]
        reg["global_contribution"] = 100 * reg["protected_area"] / global_protected_area

        return reg

    # Load protected planet country level statistics
    if verbose:
        print(
            f"loading Protected Planet Country-level data gs://{bucket}/{wdpa_country_level_file_name}"
        )
    wdpa_country = read_dataframe(bucket, wdpa_country_level_file_name)

    # Load related countries and regions
    if verbose:
        print("loading country and region groupings")
    combined_regions = load_regions()

    # WDPA country level
    if verbose:
        print("processing Marine and terrestrial country level stats")

    wdpa_cl_m = process_protected_area(wdpa_country, environment="marine")
    wdpa_cl_t = process_protected_area(wdpa_country, environment="land")

    if verbose:
        print("Grouping by sovereign country and region")

    # Roll up into sovereign countries and regions
    reg_t = group_by_region(wdpa_cl_t, combined_regions)
    reg_m = group_by_region(wdpa_cl_m, combined_regions)

    protection_coverage_table = pd.concat((reg_t, reg_m), axis=0)

    upload_dataframe(
        bucket,
        protection_coverage_table,
        protection_coverage_file_name,
        project_id=project,
        verbose=verbose,
    )

    return protection_coverage_table


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
    combined_regions = load_regions()

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

    upload_dataframe(
        bucket,
        protection_level_table,
        protection_level_file_name,
        project_id=project,
        verbose=verbose,
    )

    return protection_level_table


def generate_fishing_protection_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protected_seas_file_name: str = PROTECTED_SEAS_FILE_NAME,
    wdpa_marine_area_file_name: str = PROTECTION_COVERAGE_FILE_NAME,
    fishing_protecton_file_name: str = FISHING_PROTECTION_FILE_NAME,
    verbose: bool = True,
):
    def get_group_stats(
        df,
        loc,
        relations,
        marine_area,
        global_marine_area=361000000,
        fishing_protection_level="Highly protected from fishing",
    ):
        if loc == "GLOB":
            df_group = df
            total_area = global_marine_area
        else:
            df_group = df[df["location"].isin(relations[loc])]
            ma = marine_area[marine_area["location"] == loc]
            total_area = ma.iloc[0]["area"] if len(ma) > 0 else 0

        highly_protected_area = df_group["highly_protected_area"].sum()
        assessed = True if len(df) > 0 else False

        return {
            "location": loc,
            "area": total_area,
            "highly_protected_area": highly_protected_area if assessed else None,
            "fishing_protection_level": fishing_protection_level,
            "percent": (
                100 * highly_protected_area / total_area if assessed and total_area > 0 else None
            ),
        }

    # Load related countries and regions
    if verbose:
        print("loading country and region groupings")
    combined_regions = load_regions()

    if verbose:
        print(f"downloading Protected Seas from gs://P{bucket}/{protected_seas_file_name}")
    protected_seas = read_dataframe(bucket, protected_seas_file_name)

    if verbose:
        print("loading Protected Planet country level data for Marine Area")

    marine_area = read_dataframe(bucket, wdpa_marine_area_file_name)
    marine_area = marine_area[(marine_area["environment"] == "marine")]

    if verbose:
        print("processing fishing level protection")

    fishing_protection_level = "Highly protected from fishing"
    ps_dict = {
        "iso_ter": "location",
        "total_area": "area",
        "lfp5_area": "lfp5_area",
        "lfp4_area": "lfp4_area",
    }
    cols = [i for i in ps_dict]
    # TODO: I think total_area is not the same as marine area,
    # need to update with marine area from WDPA!
    ps_cl_fp = (
        protected_seas[cols]
        .rename(columns=ps_dict)
        .pipe(add_highly_protected_from_fishing_area)
        .pipe(add_constants, {"fishing_protection_level": "Highly protected from fishing"})
        .pipe(add_highly_protected_from_fishing_percent)
    )

    fishing_protection_table = pd.DataFrame(
        stat
        for loc in combined_regions
        if (
            stat := get_group_stats(
                ps_cl_fp,
                loc,
                combined_regions,
                marine_area,
                fishing_protection_level=fishing_protection_level,
            )
        )
        is not None
    )

    upload_dataframe(
        bucket,
        fishing_protection_table,
        fishing_protecton_file_name,
        project_id=project,
        verbose=verbose,
    )

    return fishing_protection_table
