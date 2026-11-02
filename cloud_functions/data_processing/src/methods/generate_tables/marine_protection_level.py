import pandas as pd

from src.core.commons import (
    load_marine_regions,
    load_mpatlas_country,
    load_mpatlas_global,
    load_regions,
)
from src.core.params import (
    BUCKET,
    HIGH_SEAS_PARAMS,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_GLOBAL_FILE_NAME,
    MPATLAS_SEA_PAIRS_FILE_NAME,
    PROJECT,
    PROTECTION_LEVEL_FILE_NAME,
)
from src.core.processors import (
    add_constants,
    add_total_area_mp,
    update_mpatlas_asterisk,
)
from src.methods.protection_coverage import compute_iho_protection_level
from src.utils.gcp import upload_dataframe
from src.utils.logger import Logger

logger = Logger()


def generate_marine_protection_level_stats_table(
    mpatlas_country_level_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    mpatlas_global_file_name: str = MPATLAS_GLOBAL_FILE_NAME,
    mpatlas_sea_pairs_file_name: str = MPATLAS_SEA_PAIRS_FILE_NAME,
    protection_level_file_name: str = PROTECTION_LEVEL_FILE_NAME,
    high_seas_params: dict = HIGH_SEAS_PARAMS,
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
    iho_protection_level = compute_iho_protection_level(
        bucket=bucket,
        mpatlas_sea_pairs_file_name=mpatlas_sea_pairs_file_name,
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
