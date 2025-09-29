import geopandas as gpd
import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from src.core.commons import (
    load_marine_regions,
    load_mpatlas_country,
    load_regions,
    load_wdpa_global,
)
from src.core.land_cover_params import marine_tolerance
from src.core.params import (
    BUCKET,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    EEZ_FILE_NAME,
    FISHING_PROTECTION_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    GADM_FILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
    GLOBAL_MARINE_AREA_KM2,
    GLOBAL_TERRESTRIAL_AREA_KM2,
    HABITAT_PROTECTION_FILE_NAME,
    HABITATS_ZIP_FILE_NAME,
    HIGH_SEAS_PARAMS,
    MANGROVES_BY_COUNTRY_FILE_NAME,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_META_FILE_NAME,
    PA_TERRESTRIAL_HABITATS_FILE_NAME,
    PROJECT,
    PROTECTED_SEAS_FILE_NAME,
    PROTECTION_COVERAGE_FILE_NAME,
    PROTECTION_LEVEL_FILE_NAME,
    SEAMOUNTS_SHAPEFILE_NAME,
    SEAMOUNTS_ZIPFILE_NAME,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_META_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    WDPA_MARINE_FILE_NAME,
)
from src.core.processors import (
    add_constants,
    add_environment,
    add_oecm_status,
    add_percent_coverage,
    add_pas_oecm,
    add_protected_from_fishing_area,
    add_protected_from_fishing_percent,
    add_total_area_mp,
    add_year,
    calculate_area,
    convert_type,
    extract_column_dict_str,
    fp_location,
    remove_columns,
    remove_non_designated_m,
    remove_non_designated_p,
    rename_habitats,
    update_mpatlas_asterisk,
)
from src.core.strapi import Strapi
from src.methods.marine_habitats import process_marine_habitats
from src.methods.terrestrial_habitats import process_terrestrial_habitats
from src.utils.database import get_pas
from src.utils.gcp import (
    read_dataframe,
    read_json_df,
    upload_dataframe,
)


def generate_protected_areas_table(
    wdpa_file_name: str = WDPA_META_FILE_NAME,
    mpatlas_file_name: str = MPATLAS_META_FILE_NAME,
    eez_file_name: str = EEZ_FILE_NAME,
    gadm_file_name: str = GADM_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    def add_parent_children(
        subset: pd.DataFrame, fields=["wdpa_id", "wdpa_pid", "zone_id"]
    ) -> pd.DataFrame:
        """
        Reorder rows by priority, then set the first row as parent and the rest as children.
        Priority (lower is earlier):
            0: data_source=='Protected Planet' & wdpa_id==wdpa_pid
            1: data_source=='Protected Planet'
            2: data_source=='MPATLAS' & wdpa_id==wdpa_pid
            3: all others
        """
        if subset.empty:
            return subset

        # Priority lists
        same_id = subset["wdpaid"].values == subset["wdpa_p_id"].values
        data_source_pp = subset["data_source"].values == "Protected Planet"
        data_source_mp = subset["data_source"].values == "MPATLAS"

        # select priority ranking
        priority = np.select(
            [
                data_source_pp & same_id,
                data_source_pp,
                data_source_mp & same_id,
            ],
            [0, 1, 2],
            default=3,
        )

        # Sort by priority
        ordered = subset.iloc[np.argsort(priority, kind="stable")].copy()

        ordered["parent"] = None
        ordered["children"] = None

        if len(ordered) > 1:
            # create parent and list of children
            parent_dict = ordered.iloc[0][fields].to_dict()
            children_list = ordered.iloc[1:][fields].to_dict("records")

            # Assign parent and children to each PA
            ordered.iat[0, ordered.columns.get_loc("children")] = children_list
            ordered.loc[ordered.index[1:], "parent"] = [parent_dict] * (len(ordered) - 1)

        return ordered

    if verbose:
        print("loading PA metadata")
    mpatlas = read_dataframe(bucket, mpatlas_file_name)
    wdpa = read_dataframe(bucket, wdpa_file_name)

    eez_file_name = eez_file_name.replace(".geojson", "_0.001.geojson")
    gadm_file_name = gadm_file_name.replace(".geojson", "_0.001.geojson")
    if verbose:
        print(f"loading eez from {eez_file_name}")
    eez = read_json_df(BUCKET, eez_file_name)

    if verbose:
        print(f"loading eez from {gadm_file_name}")
    gadm = read_json_df(BUCKET, gadm_file_name)
    gadm = calculate_area(gadm, output_area_column="AREA_KM2")

    if verbose:
        print("processing WDPAs")
    wdpa_dict = {
        "NAME": "name",
        "calculated_area_km2": "area",
        "STATUS": "STATUS",
        "PA_DEF": "PA_DEF",
        "STATUS_YR": "year",
        "WDPAID": "wdpaid",
        "WDPA_PID": "wdpa_p_id",
        "DESIG_TYPE": "designation",
        "ISO3": "location",
        "IUCN_CAT": "iucn_category",
        "MARINE": "MARINE",
        "bbox": "bbox",
    }
    cols = [i for i in wdpa_dict]

    wdpa_pa = (
        wdpa[cols]
        .rename(columns=wdpa_dict)
        .pipe(remove_non_designated_p)
        .pipe(add_environment)
        .pipe(add_oecm_status)
        .pipe(
            add_constants,
            {
                "zone_id": "",
                "data_source": "Protected Planet",
                "mpaa_establishment_stage": "",
                "mpaa_protection_level": "",
            },
        )
        .pipe(remove_columns, ["STATUS", "MARINE", "PA_DEF"])
        .pipe(
            convert_type,
            {
                "wdpaid": [pd.Int64Dtype(), str],
                "wdpa_p_id": [str],
                "zone_id": [pd.Int64Dtype(), str],
            },
        )
    )

    if verbose:
        print("processing MPAs")

    mpa_dict = {
        "name": "name",
        "calculated_area_km2": "area",
        "designated_date": "designated_date",
        "wdpa_id": "wdpaid",
        "wdpa_pid": "wdpa_p_id",
        "zone_id": "zone_id",
        "designation": "designation",
        "establishment_stage": "mpaa_establishment_stage",
        "country": "location",
        "protection_mpaguide_level": "mpaa_protection_level",
        "bbox": "bbox",
    }
    cols = [i for i in mpa_dict]
    mpa_pa = (
        mpatlas[cols]
        .rename(columns=mpa_dict)
        .pipe(remove_non_designated_m)
        .pipe(add_year)
        # TODO: Are all MPAtlas MPAs PAs (not OECMs)? Should protection_status be
        # replaced with "pa" instead of blank?
        .pipe(
            add_constants,
            {
                "protection_status": "",
                "environment": "marine",
                "data_source": "MPATLAS",
                "iucn_category": "",
            },
        )
        .pipe(remove_columns, "designated_date")
        .pipe(
            convert_type,
            {
                "wdpaid": [pd.Int64Dtype(), str],
                "wdpa_p_id": [str],
                "zone_id": [pd.Int64Dtype(), str],
            },
        )
    )

    pas = pd.concat((wdpa_pa[mpa_pa.columns], mpa_pa), axis=0)
    pas["area"] = pd.to_numeric(pas["area"], errors="coerce")
    pas = add_percent_coverage(pas, eez, gadm)
    pas = pas.sort_values(["wdpaid", "wdpa_p_id", "zone_id"])

    results = []
    # Split by environment to ensure parent/children are of the same environment
    for environment, pa_env in pas.groupby("environment", sort=False):
        print(environment)
        for _, subset in tqdm(
            pa_env.groupby("wdpaid", sort=False),
            total=pa_env["wdpaid"].nunique(),
            desc=f"{environment} wdpa_id groups",
        ):
            results.append(
                add_parent_children(
                    subset, fields=["wdpaid", "wdpa_p_id", "zone_id", "environment"]
                )
            )

    protected_areas = pd.concat(results, ignore_index=True)

    return protected_areas


def database_updates(current_db, updated_pas, verbose=True):
    def normalize_value(v):
        # match Pandas .astype(str) behavior: np.nan -> '<NA>'
        if pd.isna(v):
            return "<NA>"
        return str(v)

    def get_identifier(x, cols, current_db):
        if not isinstance(x, dict):
            return None

        # build identifier in the same way as updated_pas["identifier"]
        identifier = "_".join(normalize_value(x.get(c)) for c in cols)

        match = current_db.loc[current_db["identifier"] == identifier, "id"]
        _id = int(match.iloc[0]) if not match.empty else None

        return {**x, "id": _id}

    def get_identifier_children(children, cols, current_db):
        if not isinstance(children, list):
            return None
        return [get_identifier(child, cols, current_db) for child in children]

    def str_dif_idx(df1, df2, col):
        return (~df2[col].isnull()) & (df2[col] != df1[col])

    def area_dif_idx(df1, df2):
        return (~df2["area"].isna()) & (
            (df1["area"].isna()) | (abs(df2["area"] - df1["area"]) / df1["area"] > 0.01)
        )

    def list_dict_dif_idx(df1, df2, col):
        p1 = df1[col]
        p2 = df2[col]
        both_na = p1.isna() & p2.isna()
        dif = p1.ne(p2)
        return (~both_na) & dif

    # Create unique identifier and attach to the current and updated PAs for comparison
    if verbose:
        print("adding unique identifier")
    cols_for_id = ["environment", "wdpaid", "wdpa_p_id", "zone_id"]
    updated_pas["identifier"] = updated_pas[cols_for_id].astype(str).agg("_".join, axis=1)
    current_db["identifier"] = current_db[cols_for_id].astype(str).agg("_".join, axis=1)

    # Add identifier to parent/children
    if verbose:
        print("adding database identifier to parent column")
    updated_pas["parent"] = updated_pas["parent"].apply(
        get_identifier, args=(cols_for_id, current_db)
    )
    if verbose:
        print("adding database identifier to children column")
    updated_pas["children"] = updated_pas["children"].apply(
        get_identifier_children, args=(cols_for_id, current_db)
    )

    if verbose:
        print("finding new, deleted, and static PAs")
    new = list(set(updated_pas["identifier"]) - set(current_db["identifier"]))
    deleted = list(set(current_db["identifier"]) - set(updated_pas["identifier"]))
    static = set(current_db["identifier"]).intersection(set(updated_pas["identifier"]))

    static_current = (
        current_db[current_db["identifier"].isin(static)]
        .sort_values(by="identifier")
        .reset_index(drop=True)
    )
    static_updated = (
        updated_pas[updated_pas["identifier"].isin(static)]
        .sort_values(by="identifier")
        .reset_index(drop=True)
    )
    static_updated = pd.merge(
        static_updated, current_db[["identifier", "id"]], on="identifier", how="left"
    )

    # specify which columns get which comparison
    string_cols = list(set(updated_pas.columns) - set(["children", "parent", "area", "bbox"]))
    list_cols = ["parent", "children"]

    # build up combined mask
    change_indx = pd.Series(False, index=static_current.index)

    for col in string_cols:
        change_indx |= str_dif_idx(static_current, static_updated, col)

    for col in list_cols:
        change_indx |= list_dict_dif_idx(static_current, static_updated, col)

    change_indx |= area_dif_idx(static_current, static_updated)

    # Updated version of changed entries
    changed = static_updated[change_indx]

    if verbose:
        print(f"new: {len(new)}, deleted: {len(deleted)}, changed: {len(changed)}")

    return {
        "new": updated_pas[updated_pas["identifier"].isin(new)]
        .drop(columns="identifier")
        .to_dict(orient="records"),
        "changed": changed.drop(columns="identifier").to_dict(orient="records"),
        "deleted": list(current_db[current_db["identifier"].isin(deleted)]["id"]),
    }


def update_protected_areas_table(
    wdpa_file_name: str = WDPA_META_FILE_NAME,
    mpatlas_file_name: str = MPATLAS_META_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    updated_pas = generate_protected_areas_table(
        wdpa_file_name=wdpa_file_name,
        mpatlas_file_name=mpatlas_file_name,
        bucket=bucket,
        verbose=verbose,
    )

    # Get the current database
    if verbose:
        print("downloading current PA database")
    current_db = get_pas()
    current_db_df = pd.DataFrame(current_db)

    db_changes = database_updates(current_db_df, updated_pas, verbose=verbose)

    strapi = Strapi()
    strapi.upsert_pas(db_changes["new"] + db_changes["changed"])
    strapi.delete_pas(db_changes["deleted"])

    return db_changes


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
    mangroves_by_country_file_name: str = MANGROVES_BY_COUNTRY_FILE_NAME,
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
    marine_pa_file_name = marine_pa_file_name.replace(".geojson", f"_{marine_tolerance}.geojson")

    # TODO: check if we should return zero values for total_area. Right now we are not.

    if verbose:
        print("loading regions")
    combined_regions, _ = load_regions()

    marine_habitats = process_marine_habitats(
        combined_regions,
        gadm_eez_union_file_name=gadm_eez_union_file_name,
        habitats_zipfile_name=habitats_zipfile_name,
        seamounts_zipfile_name=seamounts_zipfile_name,
        seamounts_shapefile_name=seamounts_shapefile_name,
        mangroves_by_country_file_name=mangroves_by_country_file_name,
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

    def get_group_stats(df, loc, relations, percent_type):
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
                "total_area": total_area,
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
            return float(df[df["type"] == col].iloc[0]["value"])

        df = df.copy()

        environment2 = "ocean" if environment == "marine" else "land"
        oecms_pas = get_value(global_stats, f"total_{environment2}_area_oecms_pas")
        oecms = get_value(global_stats, f"total_{environment2}_area_oecms")
        pas = oecms_pas - oecms

        global_dict = {
            "location": "GLOB",
            "environment": environment,
            "protected_area": get_value(global_stats, f"total_{environment2}_area_oecms_pas"),
            "protected_areas_count": get_value(global_stats, f"total_{environment}_oecms_pas"),
            "coverage": get_value(
                global_stats, f"total_{environment2}_oecms_pas_coverage_percentage"
            ),
            "pas": 100 * pas / oecms_pas,
            "oecms": 100 * oecms / oecms_pas,
            "global_contribution": get_value(
                global_stats, f"total_{environment2}_oecms_pas_coverage_percentage"
            ),
            "total_area": GLOBAL_MARINE_AREA_KM2
            if environment2 == "ocean"
            else GLOBAL_TERRESTRIAL_AREA_KM2,
        }

        df = pd.concat((df, pd.DataFrame([global_dict])), axis=0, ignore_index=True)

        if environment == "terrestrial":
            return df
        else:
            total_area = get_value(global_stats, "high_seas_pa_coverage_area")
            oecms = get_value(wdpa_global, "total_ocean_area_oecms") - get_value(
                wdpa_global, "national_waters_oecms_coverage_area"
            )
            oecms_pas = get_value(wdpa_global, "total_ocean_area_oecms_pas") - get_value(
                wdpa_global, "national_waters_oecms_pas_coverage_area"
            )
            pas = oecms_pas - oecms
            high_seas_dict = {
                "location": "ABNJ",
                "environment": environment,
                "protected_area": total_area,
                "protected_areas_count": -9999,
                "coverage": get_value(global_stats, "high_seas_pa_coverage_percentage"),
                "pas": 100 * pas / oecms_pas,
                "oecms": 100 * oecms / oecms_pas,
                "global_contribution": 100 * total_area / GLOBAL_MARINE_AREA_KM2,
                "total_area": GLOBAL_MARINE_AREA_KM2
                * get_value(wdpa_global, "global_ocean_percentage")
                / 100,
            }

            df = pd.concat((df, pd.DataFrame([high_seas_dict])), axis=0, ignore_index=True)

        return df

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
    wdpa_global = load_wdpa_global(bucket, wdpa_global_level_file_name)

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
    protection_coverage_table = protection_coverage_table[
        protection_coverage_table["total_area"] > 0
    ]
    sov_country_area = protection_coverage_table[["location", "environment", "total_area"]]
    protection_coverage_table = protection_coverage_table.pipe(
        add_global_stats, wdpa_global, "marine"
    ).pipe(add_global_stats, wdpa_global, "terrestrial")

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
    protection_level_file_name: str = PROTECTION_LEVEL_FILE_NAME,
    high_seas_params: dict = HIGH_SEAS_PARAMS,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    def get_group_stats(df, loc, relations, protection_level="fully-highly-protected"):
        if loc == "GLOB":
            df_group = df
            total_area = GLOBAL_MARINE_AREA_KM2
        else:
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
        print("loading country and region groupings")
    combined_regions, _ = load_regions()

    # Load MPAtlas Country level statistics
    if verbose:
        print(
            f"loading MPAtlas country-level stats from gs://{bucket}/{mpatlas_country_level_file_name}"
        )
    mpatlas_country = load_mpatlas_country(bucket, mpatlas_country_level_file_name)

    if verbose:
        print("loading high seas region to get area")
    high_seas = load_marine_regions(high_seas_params, bucket)
    high_seas_area_km2 = high_seas.iloc[0]["area_km2"]

    # TODO: verify this is right - MPAtlas leaves wdpa_marine_km2 blank for high
    # seas so this just fills in with Marine Regions estimate
    mpatlas_country = mpatlas_country.copy()
    mpatlas_country.loc[mpatlas_country["id"] == "HS", "wdpa_marine_km2"] = high_seas_area_km2

    if verbose:
        print("Calculating Marine Protection Level Statistics")

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


def generate_fishing_protection_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protected_seas_file_name: str = PROTECTED_SEAS_FILE_NAME,
    fishing_protecton_file_name: str = FISHING_PROTECTION_FILE_NAME,
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
        global_marine_area=361000000,
        fishing_protection_level="highly",
    ):
        if loc == "GLOB":
            df_group = df
            total_area = global_marine_area
        elif loc in regions:
            df_group = df[df["location"].isin(regions[loc])]
            total_area = df_group["total_area"].sum()

        return return_stats(df_group, total_area, fishing_protection_level, loc)

    # Load related countries and regions
    if verbose:
        print("loading country and region groupings")
    combined_regions, _ = load_regions()

    if verbose:
        print(f"downloading Protected Seas from gs://P{bucket}/{protected_seas_file_name}")
    protected_seas = read_dataframe(bucket, protected_seas_file_name)
    protected_seas["iso_sov"] = protected_seas["iso_sov"].replace("CRV", "HRV")

    if verbose:
        print("processing fishing level protection")

    ps_dict = {
        "iso_ter": "iso_ter",
        "iso_sov": "iso_sov",
        "total_area": "total_area",
        "lfp5_area": "lfp5_area",
        "lfp4_area": "lfp4_area",
        "lfp3_area": "lfp3_area",
        "lfp2_area": "lfp2_area",
        "lfp1_area": "lfp1_area",
    }
    cols = [i for i in ps_dict]

    fishing_protection_levels = {
        "highly": ["lfp5_area", "lfp4_area"],
        "moderately": ["lfp3_area"],
        "less": ["lfp2_area", "lfp1_area"],
    }

    if verbose:
        print("processing fishing level protection")

    ps_cl_fp = (
        protected_seas[cols]
        .rename(columns=ps_dict)
        .pipe(fp_location)
        .pipe(add_protected_from_fishing_area, fishing_protection_levels)
        .pipe(add_protected_from_fishing_percent, fishing_protection_levels)
        .pipe(
            remove_columns,
            ["lfp5_area", "lfp4_area", "lfp3_area", "lfp2_area", "lfp1_area"],
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

    fishing_protection_table = fishing_protection_table[fishing_protection_table["total_area"] > 0]
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
