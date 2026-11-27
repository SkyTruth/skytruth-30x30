import geopandas as gpd
import pandas as pd

from src.core.commons import load_iho_regions, load_regions
from src.core.params import (
    BUCKET,
    FISHING_PROTECTION_FILE_NAME,
    PROJECT,
    PROTECTED_SEAS_FILE_NAME,
    PROTECTED_SEAS_SITES_FILE_NAME,
)
from src.core.processors import (
    add_protected_from_fishing_area,
    add_protected_from_fishing_percent,
    fp_location,
    remove_columns,
)
from src.utils.gcp import read_dataframe, read_parquet_from_gcs, upload_dataframe
from src.utils.logger import Logger

logger = Logger()


def get_iho_fishing_protection_region_stats(sites_file_name, bucket=BUCKET, verbose=True):
    # Load the simplified IHO sea areas at the requested tolerance.
    iho = load_iho_regions(buffer=True).rename(columns={"area": "total_area"})

    # Load the current Protected Seas sites.
    ps_sites = read_parquet_from_gcs(bucket, sites_file_name, verbose=verbose)

    # Keep only the highly protected sites, then merge them into a single
    # geometry so we can measure their overlap with each IHO sea area.
    highly = ps_sites[ps_sites["fishing_protection_level"] == "highly"].copy()

    # Repair any invalid site geometries before the overlay/dissolve.
    if verbose:
        logger.info({"message": "making Protected Seas geometries valid"})
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
                sites_file_name, bucket=bucket, verbose=verbose
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
