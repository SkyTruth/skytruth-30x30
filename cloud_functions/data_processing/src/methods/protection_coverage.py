import pandas as pd
from shapely.validation import make_valid

from src.core.commons import (
    compute_global_area,
    get_wdpa_global_value,
    intersect_mpatlas_with_iho,
    intersect_wdpa_with_iho,
    load_iho_regions,
    load_regions,
    load_wdpa_global,
)
from src.core.land_cover_params import marine_tolerance
from src.core.params import (
    BUCKET,
    MPATLAS_FILE_NAME,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
)
from src.core.processors import (
    add_constants,
    add_pas_oecm,
    extract_column_dict_str,
    remove_columns,
)
from src.utils.gcp import read_dataframe
from src.utils.geo import robust_unary_union
from src.utils.logger import Logger

logger = Logger()


def compute_iho_protection_coverage(
    bucket: str = BUCKET,
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    tolerance: float = marine_tolerance,
    verbose: bool = True,
) -> pd.DataFrame:
    if verbose:
        logger.info({"message": "loading IHO sea areas from shared datasets"})
    iho = load_iho_regions()

    if verbose:
        logger.info(
            {
                "message": f"loading Protected Planet Global-level data gs://{bucket}/{wdpa_global_level_file_name}"
            }
        )
    wdpa_global = load_wdpa_global(bucket, wdpa_global_level_file_name)
    global_marine_area = compute_global_area(wdpa_global, "marine")

    pairs = intersect_wdpa_with_iho(bucket=bucket, tolerance=tolerance)
    by_sea = dict(list(pairs.groupby("MRGID", sort=False)))

    # The join validates its own inputs, but `total_area` below is measured off
    # this frame: 4 of the 102 IHO geometries are invalid, and repairing the
    # South Pacific Ocean moves its area by ~5,900 km².
    iho_proj = iho.to_crs(epsg=6933)
    iho_proj["geometry"] = iho_proj.geometry.apply(make_valid)

    results = []

    empty_stats = {
        "protected_area": 0.0,
        "coverage": 0.0,
        "pas": 0.0,
        "oecms": 0.0,
        "protected_areas_count": 0,
        "global_contribution": 0.0,
    }

    for _, sea in iho_proj.iterrows():
        base = {
            "location": str(sea["MRGID"]),
            "environment": "marine",
            "total_area": round(sea.geometry.area / 1e6, 2),
        }

        clipped = by_sea.get(sea["MRGID"])
        if clipped is None:
            results.append({**base, **empty_stats})
            continue

        # The pieces are already sea ∩ PA, so dissolving them gives sea ∩ union(PAs):
        # shared portions of overlapping designations are counted only once.
        protected_area = robust_unary_union(clipped.geometry).area / 1e6
        pa_area = robust_unary_union(clipped[clipped["PA_DEF"] == 1].geometry).area / 1e6
        oecm_area = robust_unary_union(clipped[clipped["PA_DEF"] == 0].geometry).area / 1e6

        # Calculate sea coverage and the PA/OECM shares of its protected area.
        coverage = (protected_area / base["total_area"]) * 100 if base["total_area"] else 0.0
        pas_pct = (pa_area / protected_area) * 100 if protected_area else 0.0
        oecms_pct = (oecm_area / protected_area) * 100 if protected_area else 0.0

        # Share of the whole ocean that this sea's protected area accounts for.
        global_contribution = (
            (protected_area / global_marine_area) * 100 if global_marine_area else None
        )

        results.append(
            {
                **base,
                "protected_area": round(protected_area, 2),
                "protected_areas_count": len(clipped),
                "coverage": round(coverage, 2),
                "pas": round(pas_pct, 2),
                "oecms": round(oecms_pct, 2),
                "global_contribution": round(global_contribution, 2)
                if global_contribution is not None
                else None,
            }
        )

    return pd.DataFrame(results)


def compute_iho_protection_level(
    bucket: str = BUCKET,
    mpa_file_name: str = MPATLAS_FILE_NAME,
    verbose: bool = True,
) -> pd.DataFrame:
    if verbose:
        logger.info({"message": "loading IHO sea areas from shared datasets"})
    iho = load_iho_regions()

    fully_highly = intersect_mpatlas_with_iho(
        bucket=bucket, mpa_file_name=mpa_file_name, fully_highly_only=True
    )

    iho_proj = iho[iho.geometry.notna()].copy().to_crs(epsg=6933)
    iho_proj["geometry"] = iho_proj.geometry.apply(make_valid)

    results = []
    for mrgid, group in fully_highly.groupby("MRGID"):
        iho_geom = iho_proj.loc[iho_proj["MRGID"] == mrgid, "geometry"].iloc[0]
        total_area = iho_geom.area / 1e6

        area = robust_unary_union(group.geometry).area / 1e6
        results.append(
            {
                "location": str(mrgid),
                "total_area": total_area,
                "area": area,
                "mpaa_protection_level": "fully-highly-protected",
                "percentage": 100 * area / total_area if total_area else None,
            }
        )

    return pd.DataFrame(results)


def compute_country_global_coverage(
    bucket: str = BUCKET,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    percent_type: str = "area",
    verbose: bool = True,
) -> tuple:
    def process_protected_area(wdpa_country, environment="marine"):
        wdpa_dict = {
            "id": "location",
            "pas_count": "protected_areas_count",
            "statistics": "statistics",
        }

        stats_dict = {
            f"{environment}_area": "total_area",
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

    def get_group_stats(df, loc, relations, percent_type, global_area):
        """
        Computes summary stats for a group of related locations.
        """
        if loc != "GLOB":
            df_group = df[df["location"].isin(relations[loc])]
            total_area = df_group["total_area"].sum()
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
            return {
                "location": loc,
                "environment": df_group.iloc[0]["environment"] if not df_group.empty else None,
                "protected_area": total_protected_area,
                "protected_areas_count": df_group["protected_areas_count"].sum(),
                "coverage": 100 * total_protected_area / total_area if total_area else None,
                "pas": pas,
                "oecms": oecm,
                "global_contribution": 100 * total_protected_area / global_area
                if global_area
                else None,
                "total_area": total_area,
            }
        else:
            return None

    def group_by_region(wdpa_cl, combined_regions, global_area):
        reg = pd.DataFrame(
            stat
            for loc in combined_regions
            if (stat := get_group_stats(wdpa_cl, loc, combined_regions, percent_type, global_area))
            is not None
        )
        reg = reg[reg["protected_area"] > 0]

        return reg

    def add_global_stats(df, global_stats, environment):
        df = df.copy()

        environment2 = "ocean" if environment == "marine" else "land"
        oecms_pas = get_wdpa_global_value(global_stats, f"total_{environment2}_area_oecms_pas")
        oecms = get_wdpa_global_value(global_stats, f"total_{environment2}_area_oecms")
        pas = oecms_pas - oecms
        coverage = get_wdpa_global_value(
            global_stats, f"total_{environment2}_oecms_pas_coverage_percentage"
        )

        global_dict = {
            "location": "GLOB",
            "environment": environment,
            "protected_area": oecms_pas,
            "protected_areas_count": get_wdpa_global_value(
                global_stats, f"total_{environment}_oecms_pas"
            ),
            "coverage": coverage,
            "pas": 100 * pas / oecms_pas,
            "oecms": 100 * oecms / oecms_pas,
            "global_contribution": coverage,
            "total_area": compute_global_area(global_stats, environment),
        }

        df = pd.concat((df, pd.DataFrame([global_dict])), axis=0, ignore_index=True)

        if environment == "terrestrial":
            return df
        else:
            total_area = get_wdpa_global_value(global_stats, "high_seas_pa_coverage_area")
            global_ocean_area = compute_global_area(global_stats, environment)
            oecms = get_wdpa_global_value(
                global_stats, "total_ocean_area_oecms"
            ) - get_wdpa_global_value(global_stats, "national_waters_oecms_coverage_area")
            oecms_pas = get_wdpa_global_value(
                global_stats, "total_ocean_area_oecms_pas"
            ) - get_wdpa_global_value(global_stats, "national_waters_oecms_pas_coverage_area")
            pas = oecms_pas - oecms
            coverage = get_wdpa_global_value(global_stats, "high_seas_pa_coverage_percentage")
            high_seas_dict = {
                "location": "ABNJ",
                "environment": environment,
                "protected_area": total_area,
                "protected_areas_count": -9999,
                "coverage": coverage,
                "pas": 100 * pas / oecms_pas,
                "oecms": 100 * oecms / oecms_pas,
                "global_contribution": 100 * total_area / global_ocean_area,
                "total_area": global_ocean_area
                * get_wdpa_global_value(global_stats, "global_ocean_percentage")
                / 100,
            }

            df = pd.concat((df, pd.DataFrame([high_seas_dict])), axis=0, ignore_index=True)

        return df

    if verbose:
        logger.info(
            {
                "message": f"loading Protected Planet Country-level data gs://{bucket}/{wdpa_country_level_file_name}"
            }
        )
    wdpa_country = read_dataframe(bucket, wdpa_country_level_file_name)

    if verbose:
        logger.info(
            {
                "message": f"loading Protected Planet Global-level data gs://{bucket}/{wdpa_global_level_file_name}"
            }
        )
    wdpa_global = load_wdpa_global(bucket, wdpa_global_level_file_name)
    global_marine_area = compute_global_area(wdpa_global, "marine")
    global_terrestrial_area = compute_global_area(wdpa_global, "terrestrial")

    if verbose:
        logger.info({"message": "loading country and region groupings"})
    combined_regions, _ = load_regions()

    if verbose:
        logger.info({"message": "processing Marine and terrestrial country level stats"})

    wdpa_cl_m = process_protected_area(wdpa_country, environment="marine")
    wdpa_cl_t = process_protected_area(wdpa_country, environment="land")
    wdpa_cl_t["environment"] = wdpa_cl_t["environment"].replace("land", "terrestrial")

    if verbose:
        logger.info({"message": "Grouping by sovereign country and region"})

    reg_t = group_by_region(wdpa_cl_t, combined_regions, global_terrestrial_area)
    reg_m = group_by_region(wdpa_cl_m, combined_regions, global_marine_area)

    table = pd.concat((reg_t, reg_m), axis=0)
    table = table[table["total_area"] > 0]
    sov_country_area = table[["location", "environment", "total_area"]]
    table = table.pipe(add_global_stats, wdpa_global, "marine").pipe(
        add_global_stats, wdpa_global, "terrestrial"
    )

    return table, sov_country_area
