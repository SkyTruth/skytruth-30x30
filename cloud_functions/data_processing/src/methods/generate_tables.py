import pickle

import geopandas as gpd
import pandas as pd
from google.cloud import storage

from src.core.commons import (
    add_tolerance_suffix,
    load_marine_regions,
    load_mpatlas_country,
    load_mpatlas_global,
    load_regions,
)
from src.core.land_cover_params import marine_tolerance
from src.core.params import (
    BUCKET,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    EEZ_FILE_NAME,
    FISHING_PROTECTION_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
    HABITAT_PROTECTION_FILE_NAME,
    HABITATS_ZIP_FILE_NAME,
    HIGH_SEAS_PARAMS,
    IHO_SEA_AREAS_FILE_NAME,
    MANGROVES_BY_REGION_FILE_NAME,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_FILE_NAME,
    MPATLAS_GLOBAL_FILE_NAME,
    MPATLAS_META_FILE_NAME,
    PA_TERRESTRIAL_HABITATS_FILE_NAME,
    PROJECT,
    PROTECTED_SEAS_FILE_NAME,
    PROTECTED_SEAS_SITES_FILE_NAME,
    PROTECTION_COVERAGE_FILE_NAME,
    PROTECTION_LEVEL_FILE_NAME,
    SEAMOUNTS_SHAPEFILE_NAME,
    SEAMOUNTS_ZIPFILE_NAME,
    TOLERANCES,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    WDPA_MARINE_FILE_NAME,
    WDPA_META_FILE_NAME,
    WDPA_PA_FILE_NAME,
)
from src.core.processors import (
    add_constants,
    add_protected_from_fishing_area,
    add_protected_from_fishing_percent,
    add_total_area_mp,
    fp_location,
    remove_columns,
    rename_habitats,
    update_mpatlas_asterisk,
)
from src.methods.marine_habitats import process_marine_habitats
from src.methods.protected_areas.protected_areas import (
    generate_protected_areas_table,
    make_pa_updates,
)
from src.methods.protection_coverage import (
    compute_country_global_coverage,
    compute_iho_protection_coverage,
    compute_iho_protection_level_coverage,
)
from src.methods.terrestrial_habitats import process_terrestrial_habitats
from src.utils.database import get_pas
from src.utils.gcp import (
    read_dataframe,
    read_parquet_from_gcs,
    upload_dataframe,
)
from src.utils.logger import Logger

logger = Logger()


def generate_protected_areas_diff_table(
    wdpa_file_name: str = WDPA_META_FILE_NAME,
    mpatlas_file_name: str = MPATLAS_META_FILE_NAME,
    pa_file_name: str = WDPA_PA_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    tolerance: float = TOLERANCES[0],
    verbose: bool = True,
):
    def clean_for_json(obj):
        import math

        """Recursively replace NaN/Infinity with None (-> JSON null)."""
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, str):
            if obj == "":
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(v) for v in obj]
        else:
            return obj

    updated_pas = generate_protected_areas_table(
        wdpa_file_name=wdpa_file_name,
        mpatlas_file_name=mpatlas_file_name,
        bucket=bucket,
        verbose=verbose,
        tolerance=tolerance,
    )

    # Get the current database
    if verbose:
        logger.info({"message": "downloading current PA database"})
    current_db = get_pas()
    current_db_df = pd.DataFrame(current_db)
    if len(current_db_df) > 0:
        current_db_df["area"] = current_db_df["area"].apply(lambda x: float(x))
        current_db_df["coverage"] = current_db_df["coverage"].apply(
            lambda x: float(x) if x is not None else None
        )

    if verbose:
        logger.info({"message": f"current database length: {len(current_db)}"})

    if verbose:
        logger.info({"message": "finding database changes"})
    db_changes, change_cols = make_pa_updates(current_db_df, updated_pas, verbose=verbose)

    # Print which values have changed
    if verbose:
        for col in change_cols.columns:
            size = len(change_cols[change_cols[col]])
            if size > 0:
                logger.info({"message": f"{col}: {size} rows changed"})

    db_changes["new"] = clean_for_json(db_changes["new"])
    db_changes["changed"] = clean_for_json(db_changes["changed"])

    # Save archive DB changes
    source_file = "db_changes.pkl"
    with open(source_file, "wb") as f:
        pickle.dump(db_changes, f)

    client = storage.Client(project=project)
    bucket = client.bucket(bucket)
    blob = bucket.blob(pa_file_name)
    blob.upload_from_filename(source_file)

    if verbose:
        logger.info({"message": f"Uploaded {source_file} to gs://{bucket}/{pa_file_name}"})

    # return True if the database is being updated, otherwise False
    return len(db_changes["new"]) + len(db_changes["changed"]) > 0


def dissolve_multipolygons(gdf: gpd.GeoDataFrame, key: str = "WDPAID") -> gpd.GeoDataFrame:
    counts = gdf[key].value_counts()

    singles = gdf[gdf[key].isin(counts[counts == 1].index)]
    multiples = gdf[gdf[key].isin(counts[counts > 1].index)]

    dissolved = multiples.dissolve(by=key)
    dissolved = dissolved.reset_index()
    result = pd.concat([singles, dissolved], ignore_index=True)

    return result


def generate_habitat_protection_table(
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    habitats_zipfile_name: str = HABITATS_ZIP_FILE_NAME,
    seamounts_zipfile_name: str = SEAMOUNTS_ZIPFILE_NAME,
    seamounts_shapefile_name: str = SEAMOUNTS_SHAPEFILE_NAME,
    mangroves_by_region_file_name: str = MANGROVES_BY_REGION_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    file_name_out: str = HABITAT_PROTECTION_FILE_NAME,
    eez_file: dict = EEZ_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    marine_pa_file_name = add_tolerance_suffix(marine_pa_file_name, marine_tolerance)

    # TODO: check if we should return zero values for total_area. Right now we are not.

    if verbose:
        logger.info({"message": "loading regions"})
    combined_regions, _ = load_regions()

    marine_habitats = process_marine_habitats(
        combined_regions,
        gadm_eez_union_file_name=gadm_eez_union_file_name,
        habitats_zipfile_name=habitats_zipfile_name,
        seamounts_zipfile_name=seamounts_zipfile_name,
        seamounts_shapefile_name=seamounts_shapefile_name,
        mangroves_by_region_file_name=mangroves_by_region_file_name,
        global_mangrove_area_file_name=global_mangrove_area_file_name,
        marine_pa_file_name=marine_pa_file_name,
        eez_file=eez_file,
        bucket=bucket,
        tolerance=marine_tolerance,
        verbose=verbose,
    )

    terrestrial_habitats = process_terrestrial_habitats(
        combined_regions,
        pa_stats_filename=pa_stats_filename,
        country_stats_filename=country_stats_filename,
        bucket=bucket,
        verbose=verbose,
    )

    habitats = pd.concat((marine_habitats, terrestrial_habitats), axis=0)

    habitats = habitats[habitats["total_area"] > 0].pipe(rename_habitats)

    upload_dataframe(bucket, habitats, file_name_out, project_id=project, verbose=True)

    return habitats.to_dict(orient="records")


def generate_protection_coverage_stats_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protection_coverage_file_name: str = PROTECTION_COVERAGE_FILE_NAME,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    percent_type: str = "area",  # area or counts
    verbose: bool = True,
):
    country_global_coverage, sov_country_area = compute_country_global_coverage(
        bucket=bucket,
        wdpa_country_level_file_name=wdpa_country_level_file_name,
        wdpa_global_level_file_name=wdpa_global_level_file_name,
        percent_type=percent_type,
        verbose=verbose,
    )

    if verbose:
        logger.info({"message": "computing IHO sea area protection coverage stats"})
    iho_coverage = compute_iho_protection_coverage(bucket=bucket, verbose=verbose)

    protection_coverage_table = pd.concat(
        (country_global_coverage, iho_coverage), axis=0, ignore_index=True
    )

    protection_coverage_table["total_area"] = (
        protection_coverage_table["total_area"].round(0).astype("Int64")
    )

    upload_dataframe(
        bucket,
        protection_coverage_table,
        protection_coverage_file_name,
        project_id=project,
        verbose=verbose,
    )

    upload_dataframe(
        bucket,
        sov_country_area,
        "temporary/country_areas.csv",
        project_id=project,
        verbose=verbose,
    )

    return protection_coverage_table.to_dict(orient="records")


def generate_marine_protection_level_stats_table(
    mpatlas_country_level_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    mpatlas_global_file_name: str = MPATLAS_GLOBAL_FILE_NAME,
    mpa_file_name: str = MPATLAS_FILE_NAME,
    protection_level_file_name: str = PROTECTION_LEVEL_FILE_NAME,
    high_seas_params: dict = HIGH_SEAS_PARAMS,
    tolerance: float = marine_tolerance,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    def get_group_stats(
        df, loc, relations, mpatlas_global, protection_level="fully-highly-protected"
    ):
        protection_level_dict = {
            "full": ["mpaguide_total_if_km2"],
            "high": ["mpaguide_total_ih_km2"],
            "fully-highly-protected": ["mpaguide_total_if_km2", "mpaguide_total_ih_km2"],
            "light": ["mpaguide_total_il_km2"],
            "minimal": ["mpaguide_total_im_km2"],
            "unknown": ["mpaguide_total_iu_km2", "mpaguide_total_du_km2", "mpaguide_total_pc_km2"],
            # includes lightly, minimally, unknown, and proposed but not implemented MPAs
            "less-protected-unknown": [
                "mpaguide_total_il_km2",
                "mpaguide_total_im_km2",
                "mpaguide_total_iu_km2",
                "mpaguide_total_du_km2",
                "mpaguide_total_pc_km2",
            ],
        }
        if loc == "GLOB":
            total_area = mpatlas_global["total_km2"].iloc[0]
            total_protected_area = (
                mpatlas_global[protection_level_dict[protection_level]].iloc[0].sum()
            )
            return {
                "location": loc,
                "total_area": total_area,
                "area": total_protected_area,
                "mpaa_protection_level": protection_level,
                "percentage": 100 * total_protected_area / total_area,
            }
        df_group = df[df["location"].isin(relations[loc])]
        total_area = df_group["total_area"].sum()

        if len(df_group) > 0:
            total_protected_area = df_group["protected_area"].sum()
            return {
                "location": loc,
                "total_area": total_area,
                "area": total_protected_area,
                "mpaa_protection_level": protection_level,
                "percentage": 100 * total_protected_area / total_area if total_area > 0 else None,
            }
        else:
            return None

    # Load related countries and regions
    if verbose:
        logger.info({"message": "loading country and region groupings"})
    combined_regions, _ = load_regions()

    # Load MPAtlas Country level statistics
    if verbose:
        logger.info(
            {
                "message": f"loading MPAtlas country-level stats from gs://{bucket}/{mpatlas_country_level_file_name}"
            }
        )
    mpatlas_country = load_mpatlas_country(bucket, mpatlas_country_level_file_name)

    # Load MPAtlas global statistics
    if verbose:
        logger.info(
            {
                "message": f"loading MPAtlas global stats from gs://{bucket}/{mpatlas_global_file_name}"
            }
        )
    mpatlas_global = load_mpatlas_global(bucket, mpatlas_global_file_name)

    if verbose:
        logger.info({"message": "loading high seas region to get area"})
    high_seas = load_marine_regions(high_seas_params, bucket)
    high_seas_area_km2 = high_seas.iloc[0]["area_km2"]

    # TODO: verify this is right - MPAtlas leaves wdpa_marine_km2 blank for high
    # seas so this just fills in with Marine Regions estimate
    mpatlas_country = mpatlas_country.copy()
    mpatlas_country.loc[mpatlas_country["id"] == "HS", "wdpa_marine_km2"] = high_seas_area_km2

    if verbose:
        logger.info({"message": "Calculating Marine Protection Level Statistics"})

    protection_level = "fully-highly-protected"
    mpa_dict = {
        "id": "location",
        "highly_protected_km2": "protected_area",
        "highly_protected_percent": "percentage",
        "wdpa_marine_km2": "wdpa_marine_km2",
    }
    cols = [i for i in mpa_dict]

    # TODO: We calculate total area from protected area / protected percent and
    # fill in 0 percent MPAs with wdpa_marine_km2, which doesn't match MPAtlas's
    # total area, but they don't provide theirs. Make sure this is the right way...
    mpa_cl_mps = (
        mpatlas_country[cols]
        .rename(columns=mpa_dict)
        .pipe(update_mpatlas_asterisk, asterisk=False)
        .pipe(add_constants, {"mpaa_protection_level": protection_level})
        .pipe(add_total_area_mp)
    ).drop(columns="wdpa_marine_km2")

    if verbose:
        logger.info({"message": "Grouping by sovereign country and region"})
    protection_level_table = pd.DataFrame(
        stat
        for loc in combined_regions
        if (
            stat := get_group_stats(
                mpa_cl_mps,
                loc,
                combined_regions,
                mpatlas_global,
                protection_level=protection_level,
            )
        )
        is not None
    )

    if verbose:
        logger.info({"message": "computing IHO sea area protection level stats"})
    iho_protection_level = compute_iho_protection_level_coverage(
        bucket=bucket,
        mpa_file_name=mpa_file_name,
        tolerance=tolerance,
        verbose=verbose,
    )

    protection_level_table = pd.concat(
        (protection_level_table, iho_protection_level), axis=0, ignore_index=True
    )

    protection_level_table = protection_level_table[protection_level_table["total_area"] > 0]
    protection_level_table["total_area"] = (
        protection_level_table["total_area"].round(0).astype("Int64")
    )

    upload_dataframe(
        bucket,
        protection_level_table,
        protection_level_file_name,
        project_id=project,
        verbose=verbose,
    )

    return protection_level_table.to_dict(orient="records")


def get_iho_fishing_protection_region_stats(
    iho_file_name, sites_file_name, tolerance, bucket=BUCKET, verbose=True
):
    # Load the simplified IHO sea areas at the requested tolerance.
    iho = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=add_tolerance_suffix(iho_file_name, tolerance),
    ).rename(columns={"area": "total_area"})

    # Load the current Protected Seas sites.
    ps_sites = read_parquet_from_gcs(bucket, sites_file_name, verbose=verbose)

    # Keep only the highly protected sites, then merge them into a single
    # geometry so we can measure their overlap with each IHO sea area.
    highly = ps_sites[ps_sites["fishing_protection_level"] == "highly"]

    # Repair any invalid site geometries before the overlay/dissolve.
    if verbose:
        logger.info({"message": "making geometries valid"})
    highly["geometry"] = highly.make_valid()

    # Dissolve all highly protected sites into one geometry.
    if verbose:
        logger.info({"message": "dissolving highly protected sites"})
    geoms = highly.dissolve()

    # Intersect the dissolved protection with each IHO sea area and compute
    # the protected area (km²) and percent coverage per region.
    inter = gpd.overlay(iho, geoms, how="intersection", keep_geom_type=True)
    inter = inter.to_crs(6933)
    inter["area"] = inter.geometry.area / 1e6
    inter["pct"] = 100 * inter["area"] / inter["total_area"]
    return inter[["MRGID", "area", "fishing_protection_level", "pct", "total_area"]].rename(
        columns={"MRGID": "location"}
    )


def generate_fishing_protection_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protected_seas_file_name: str = PROTECTED_SEAS_FILE_NAME,
    fishing_protecton_file_name: str = FISHING_PROTECTION_FILE_NAME,
    iho_file_name: str = IHO_SEA_AREAS_FILE_NAME,
    sites_file_name: str = PROTECTED_SEAS_SITES_FILE_NAME,
    verbose: bool = True,
):
    def return_stats(df_group, total_area, fishing_protection_level, loc):
        protected_area = df_group[f"{fishing_protection_level}_protected_area"].sum()
        assessed = len(df_group) > 0

        return {
            "location": loc,
            "area": protected_area if assessed else None,
            "fishing_protection_level": fishing_protection_level,
            "pct": (
                min(100, 100 * protected_area / total_area) if assessed and total_area > 0 else None
            ),
            "total_area": total_area,
        }

    def get_region_stats(
        df,
        loc,
        regions,
        fishing_protection_level="highly",
    ):
        if loc in regions:
            df_group = df[df["location"].isin(regions[loc])]
            total_area = df_group["total_area"].sum()
        else:
            return None

        return return_stats(df_group, total_area, fishing_protection_level, loc)

    # Load related countries and regions
    if verbose:
        logger.info({"message": "loading country and region groupings"})
    combined_regions, _ = load_regions()
    combined_regions["GLOB"] = ["GLOB"]

    if verbose:
        logger.info(
            {"message": f"downloading Protected Seas from gs://{bucket}/{protected_seas_file_name}"}
        )
    protected_seas = read_dataframe(bucket, protected_seas_file_name)
    if verbose:
        logger.info({"message": f"loaded {len(protected_seas)} Protected Seas rows"})

    # Map Protected Seas ISO codes that need to be combined into a single
    # location on our end. Each key is the location code we use, and the
    # values are the iso_ter codes from Protected Seas to sum into it.
    # This is because we combine some small locations into a single location.
    protected_seas_iso_map = {
        "SHN": ["ASC", "SHN", "TDC"],  # Saint Helena, Ascension and Tristan da Cunha
        "SJM": ["JMY", "SVB"],  # Svalbard and Jan Mayen
        "FRA": ["NAT", "CPT"],  # Clipperton Island grouped into France national
    }

    # Map different ISO codes that protected seas uses for Croatia and Global Waters
    protected_seas["iso_sov"] = protected_seas["iso_sov"].replace({"CRV": "HRV", "OCN": "GLOB"})

    if verbose:
        logger.info({"message": "processing fishing level protection"})

    ps_cols = [
        "iso_ter",
        "iso_sov",
        "total_area",
        "lfp5_area",
        "lfp4_area",
        "lfp3_area",
        "lfp2_area",
        "lfp1_area",
    ]

    fishing_protection_levels = {
        "highly": ["lfp5_area", "lfp4_area"],
        "moderately": ["lfp3_area"],
        "less": ["lfp2_area", "lfp1_area"],
    }

    if verbose:
        logger.info({"message": "aggregating protected-from-fishing areas by location"})

    lfp_cols = ["lfp5_area", "lfp4_area", "lfp3_area", "lfp2_area", "lfp1_area"]

    ps_cl_fp = (
        protected_seas[ps_cols]
        .pipe(fp_location)
        .pipe(add_protected_from_fishing_area, fishing_protection_levels)
        .pipe(add_protected_from_fishing_percent, fishing_protection_levels)
        .pipe(remove_columns, lfp_cols)
    )

    # Merge locations per protected_seas_iso_map: sum the component rows
    # into a single row for the target location code.
    for target_loc, source_locs in protected_seas_iso_map.items():
        mask = ps_cl_fp["location"].isin(source_locs)
        if not mask.any():
            continue
        merged_row = ps_cl_fp[mask].select_dtypes(include="number").sum()
        merged_row["location"] = target_loc
        ps_cl_fp = pd.concat([ps_cl_fp[~mask], pd.DataFrame([merged_row])], ignore_index=True)

    if verbose:
        logger.info(
            {
                "message": (
                    f"computing per-region stats for {len(combined_regions)} regions "
                    f"across levels: {', '.join(fishing_protection_levels)}"
                )
            }
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
                        stat := get_region_stats(
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

    if verbose:
        logger.info({"message": "computing IHO sea-area fishing protection stats"})
    fishing_protection_table = pd.concat(
        (
            fishing_protection_table,
            get_iho_fishing_protection_region_stats(
                iho_file_name, sites_file_name, marine_tolerance, bucket=bucket, verbose=verbose
            ),
        ),
        axis=0,
    )

    rows_before_filter = len(fishing_protection_table)
    fishing_protection_table = fishing_protection_table[fishing_protection_table["total_area"] > 0]
    if verbose:
        logger.info(
            {
                "message": (
                    f"fishing protection table: {len(fishing_protection_table)} rows "
                    f"({rows_before_filter - len(fishing_protection_table)} dropped for "
                    f"total_area <= 0)"
                )
            }
        )
    fishing_protection_table["total_area"] = (
        fishing_protection_table["total_area"].round(0).astype("Int64")
    )

    upload_dataframe(
        bucket,
        fishing_protection_table,
        fishing_protecton_file_name,
        project_id=project,
        verbose=verbose,
    )

    return fishing_protection_table.to_dict(orient="records")
