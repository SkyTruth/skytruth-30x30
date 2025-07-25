import pandas as pd
import geopandas as gpd
from tqdm.auto import tqdm

from src.core.commons import (
    read_mpatlas_from_gcs,
    load_wdpa_global,
    load_mpatlas_country,
    load_marine_regions,
    load_regions,
)

from src.core.params import (
    today_formatted,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    EEZ_PARAMS,
    EEZ_LAND_UNION_PARAMS,
    HIGH_SEAS_PARAMS,
    MPATLAS_FILE_NAME,
    PROTECTED_SEAS_FILE_NAME,
    WDPA_FILE_NAME,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    HABITAT_PROTECTION_FILE_NAME,
    HABITATS_ZIP_FILE_NAME,
    MANGROVES_BY_COUNTRY_FILE_NAME,
    SEAMOUNTS_SHAPEFILE_NAME,
    SEAMOUNTS_ZIPFILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
    REGIONS_FILE_NAME,
    PROTECTION_COVERAGE_FILE_NAME,
    PROTECTION_LEVEL_FILE_NAME,
    FISHING_PROTECTION_FILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
    WDPA_MARINE_FILE_NAME,
    PA_TERRESTRIAL_HABITATS_FILE_NAME,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    GLOBAL_MARINE_AREA_KM2,
    GLOBAL_TERRESTRIAL_AREA_KM2,
    BUCKET,
    PROJECT,
)

from src.core.processors import (
    add_constants,
    add_environment,
    add_protected_from_fishing_area,
    add_protected_from_fishing_percent,
    add_parent,
    add_pas_oecm,
    add_percentage_protection_mp,
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

from src.methods.marine_habitats import create_marine_habitat_subtable

from src.methods.terrestrial_habitats import create_terrestrial_habitats_subtable

from src.utils.gcp import (
    load_gdb_layer_from_gcs,
    read_dataframe,
    read_json_from_gcs,
    upload_dataframe,
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
    wdpa = load_gdb_layer_from_gcs(
        wdpa_file_name,
        bucket,
        layers=[f"WDPA_poly_{today_formatted}", f"WDPA_point_{today_formatted}"],
    )

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


def dissolve_multipolygons(gdf: gpd.GeoDataFrame, key: str = "WDPAID") -> gpd.GeoDataFrame:
    counts = gdf[key].value_counts()

    singles = gdf[gdf[key].isin(counts[counts == 1].index)]
    multiples = gdf[gdf[key].isin(counts[counts > 1].index)]

    dissolved = multiples.dissolve(by=key)
    dissolved = dissolved.reset_index()
    result = pd.concat([singles, dissolved], ignore_index=True)

    return result


def generate_habitat_protection_table(
    eez_land_union_params: dict = EEZ_LAND_UNION_PARAMS,
    habitats_zipfile_name: str = HABITATS_ZIP_FILE_NAME,
    seamounts_zipfile_name: str = SEAMOUNTS_ZIPFILE_NAME,
    seamounts_shapefile_name: str = SEAMOUNTS_SHAPEFILE_NAME,
    mangroves_by_country_file_name: str = MANGROVES_BY_COUNTRY_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    file_name_out: str = HABITAT_PROTECTION_FILE_NAME,
    eez_params: dict = EEZ_PARAMS,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    marine_tolerance = 0.0001
    marine_pa_file_name = marine_pa_file_name.replace(".geojson", f"_{marine_tolerance}.geojson")

    # TODO: check if we should return zero values for total_area. Right now we are not.

    if verbose:
        print("loading regions")
    combined_regions, parent_country = load_regions()

    marine_habitats = create_marine_habitat_subtable(
        combined_regions,
        parent_country,
        eez_land_union_params=eez_land_union_params,
        habitats_zipfile_name=habitats_zipfile_name,
        seamounts_zipfile_name=seamounts_zipfile_name,
        seamounts_shapefile_name=seamounts_shapefile_name,
        mangroves_by_country_file_name=mangroves_by_country_file_name,
        global_mangrove_area_file_name=global_mangrove_area_file_name,
        marine_pa_file_name=marine_pa_file_name,
        eez_params=eez_params,
        bucket=bucket,
        verbose=verbose,
    )

    terrestrial_habitats = create_terrestrial_habitats_subtable(
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
            total_area = df_group["area"].sum()

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
        "wdpa_marine_km2": "area",
    }
    cols = [i for i in mpa_dict]
    mpa_cl_mps = (
        mpatlas_country[cols]
        .rename(columns=mpa_dict)
        .pipe(update_mpatlas_asterisk, asterisk=False)
        .pipe(add_constants, {"mpaa_protection_level": protection_level})
        .pipe(add_percentage_protection_mp)
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

    protection_level_table = protection_level_table[protection_level_table["total_area"] > 0]

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
    protection_coverage_file_name: str = PROTECTION_COVERAGE_FILE_NAME,
    regions_file_name: str = REGIONS_FILE_NAME,
    verbose: bool = True,
):
    def return_stats(df_group, total_area, fishing_protection_level, loc):
        protected_area = df_group[f"{fishing_protection_level}_protected_area"].sum()
        assessed = True if len(df_group) > 0 else False

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
            total_area = df_group["area"].sum()

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
        print("loading Protected Planet country level data for Marine Area")

    marine_area = read_dataframe(bucket, protection_coverage_file_name)
    marine_area = marine_area[(marine_area["environment"] == "marine")]

    if verbose:
        print("processing fishing level protection")

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
