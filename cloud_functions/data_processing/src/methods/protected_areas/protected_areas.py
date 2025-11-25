import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from src.core.params import (
    BUCKET,
    EEZ_FILE_NAME,
    GADM_FILE_NAME,
    MPATLAS_META_FILE_NAME,
    TOLERANCES,
    WDPA_META_FILE_NAME,
)
from src.core.processors import (
    add_constants,
    add_environment,
    add_oecm_status,
    add_percent_coverage,
    add_year,
    calculate_area,
    convert_type,
    remove_columns,
    remove_non_designated_m,
    remove_non_designated_p,
    update_mpaa_establishment_stage,
)
from src.methods.protected_areas.pa_processors import (
    get_identifier,
    get_identifier_children,
    get_unique_identifier,
    num_dif_idx,
    ordered_list_dif_idx,
    relation_diff_index,
    str_dif_idx,
)
from src.utils.gcp import (
    read_dataframe,
    read_json_df,
)

PROTECTED_PLANET = "protected-planet"
MPATLAS = "mpatlas"


def generate_protected_areas_table(
    wdpa_file_name: str = WDPA_META_FILE_NAME,
    mpatlas_file_name: str = MPATLAS_META_FILE_NAME,
    eez_file_name: str = EEZ_FILE_NAME,
    gadm_file_name: str = GADM_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    def add_parent_children(subset: pd.DataFrame, fields=None) -> pd.DataFrame:
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

        if fields is None:
            fields = ["wdpa_id", "wdpa_pid", "zone_id", "location"]

        # Priority lists
        same_id = (subset["wdpaid"] == subset["wdpa_p_id"]).fillna(False).to_numpy()
        data_source_pp = subset["data_source"].values == PROTECTED_PLANET
        data_source_mp = subset["data_source"].values == MPATLAS

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

    def process_wdpa(wdpa):
        wdpa = wdpa.copy()

        # Create one row per country
        wdpa["ISO3"] = wdpa["ISO3"].str.split(";")
        wdpa = wdpa.explode("ISO3")
        wdpa["ISO3"] = wdpa["ISO3"].str.strip()

        # force Antarctica PAs to ABNJ and ALA to FIN
        wdpa.loc[wdpa["ISO3"] == "ATA", "ISO3"] = "ABNJ"
        wdpa.loc[wdpa["ISO3"] == "ALA", "ISO3"] = "FIN"

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
                    "zone_id": None,
                    "data_source": PROTECTED_PLANET,
                    "mpaa_establishment_stage": None,
                    "mpaa_protection_level": None,
                },
            )
            .pipe(remove_columns, ["STATUS", "MARINE", "PA_DEF"])
            .pipe(
                convert_type,
                {
                    "bbox": ["list_of_floats"],
                    "wdpaid": [pd.Int64Dtype(), str],
                    "wdpa_p_id": [str],
                    "zone_id": [pd.Int64Dtype(), str],
                },
            )
        )

        return wdpa_pa

    def process_mpa(mpatlas):
        mpatlas = mpatlas.copy()

        # Create one row per country
        # Some inconsitencies in how the api splits countries. This delieation
        # is not enforced in MPAtlas, so we may need to audit this and add new
        # delineators
        mpatlas["country"] = mpatlas["country"].astype(str).str.split(r"[;:,]")
        mpatlas = mpatlas.explode("country")
        mpatlas["country"] = mpatlas["country"].str.strip()

        # force Antarctica PAs to ABNJ
        mpatlas.loc[mpatlas["country"] == "ATA", "country"] = "ABNJ"

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
            .pipe(update_mpaa_establishment_stage)
            .pipe(add_year)
            .pipe(
                add_constants,
                {
                    "protection_status": "pa",  # MPAtlas only has Pa's not OECM's
                    "environment": "marine",
                    "data_source": MPATLAS,
                    "iucn_category": None,
                },
            )
            .pipe(remove_columns, "designated_date")
            .pipe(
                convert_type,
                {
                    "bbox": ["list_of_floats"],
                    "wdpaid": [pd.Int64Dtype(), str],
                    "wdpa_p_id": [str],
                    "zone_id": [pd.Int64Dtype(), str],
                },
            )
        )

        return mpa_pa

    if verbose:
        print("loading PA metadata")
    mpatlas = read_dataframe(bucket, mpatlas_file_name)
    wdpa = read_dataframe(bucket, wdpa_file_name)

    tolerance = TOLERANCES[0]

    eez_file_name = eez_file_name.replace(".geojson", f"_{tolerance}.geojson")
    gadm_file_name = gadm_file_name.replace(".geojson", f"_{tolerance}.geojson")
    if verbose:
        print(f"loading eez from {eez_file_name}")
    eez = read_json_df(BUCKET, eez_file_name)

    if verbose:
        print(f"loading gadm from {gadm_file_name}")
    gadm = read_json_df(BUCKET, gadm_file_name)
    gadm = calculate_area(gadm, output_area_column="AREA_KM2")

    if verbose:
        print("processing WDPAs")
    wdpa_pa = process_wdpa(wdpa)

    if verbose:
        print("processing MPAs")
    mpa_pa = process_mpa(mpatlas)

    pas = pd.concat((wdpa_pa[mpa_pa.columns], mpa_pa), axis=0)
    pas["area"] = pd.to_numeric(pas["area"], errors="coerce")
    pas["wdpa_p_id"] = pas["wdpa_p_id"].replace("", None)
    pas = add_percent_coverage(pas, eez, gadm)
    pas = pas.sort_values(["wdpaid", "wdpa_p_id", "zone_id"])

    # TODO: Currently this will not add ALA (marine), and
    # BVT (marine) because there is not GADM/EEZ lookup so the coverage
    # is None. Do we want to roll them up, add polygons, or ignore?
    pas = pas[~pas["coverage"].isnull()]

    if verbose:
        print("adding parent/child relationships")

    results = []
    # Split by country to ensure parent/children are of the same country
    for _, pa_cnt in tqdm(
        pas.groupby("location", sort=False),
        total=pas["location"].nunique(),
        desc="processing countries",
    ):
        # Split by environment to ensure parent/children are of the same environment
        for _, pa_env in pa_cnt.groupby("environment", sort=False):
            for _, subset in pa_env.groupby("wdpaid", sort=False):
                results.append(
                    add_parent_children(
                        subset, fields=["wdpaid", "wdpa_p_id", "zone_id", "environment", "location"]
                    )
                )

    protected_areas = pd.concat(results, ignore_index=True)

    return protected_areas


def make_pa_updates(current_db, updated_pas, verbose=True):
    """
    Compares newly downloaded PA data to existing PA's in the Database and generates
    a pickle file dictating which PA's are new, updated, or deleted
    """
    current_db = current_db.copy()
    updated_pas = updated_pas.copy()

    # Create unique identifier and attach to the current and updated PAs for comparison
    if verbose:
        print("adding unique identifier")
    cols_for_id = ["environment", "wdpaid", "wdpa_p_id", "zone_id", "location"]
    updated_pas["identifier"] = updated_pas.apply(
        lambda x: get_unique_identifier(x, cols_for_id), axis=1
    )
    if len(current_db) > 0:
        current_db["identifier"] = current_db.apply(
            lambda x: get_unique_identifier(x, cols_for_id), axis=1
        )

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

    if len(current_db) > 0:
        new = list(set(updated_pas["identifier"]) - set(current_db["identifier"]))
        deleted = list(set(current_db["identifier"]) - set(updated_pas["identifier"]))
        static = set(current_db["identifier"]).intersection(set(updated_pas["identifier"]))

        if verbose:
            print("getting static PA tables")
        # Current DB entries for PAs that are in updated table
        static_current = (
            current_db[current_db["identifier"].isin(static)]
            .sort_values(by="identifier")
            .reset_index(drop=True)
        )
        # Updated table entries for PAs that are in the current DB
        static_updated = (
            updated_pas[updated_pas["identifier"].isin(static)]
            .sort_values(by="identifier")
            .reset_index(drop=True)
        )
        # Add DB id to static updated table
        static_updated = pd.merge(
            static_updated, current_db[["identifier", "id"]], on="identifier", how="left"
        )

        # specify which columns get which comparison
        string_cols = list(
            set(updated_pas.columns) - set(["children", "parent", "area", "coverage", "bbox"])
        )
        num_cols = ["area", "coverage"]
        relation_list_cols = ["children", "parent"]
        ordered_list_cols = [] #["bbox"]

        # build up combined mask
        change_indx = pd.Series(False, index=static_current.index)
        changed_cols = pd.DataFrame()
        for col in string_cols:
            changed_cols[col] = str_dif_idx(static_current, static_updated, col)
            change_indx |= str_dif_idx(static_current, static_updated, col)

        for col in relation_list_cols:
            changed_cols[col] = relation_diff_index(static_current, static_updated, col)
            change_indx |= relation_diff_index(static_current, static_updated, col)

        for col in num_cols:
            changed_cols[col] = num_dif_idx(static_current, static_updated, col)
            change_indx |= num_dif_idx(static_current, static_updated, col)

        for col in ordered_list_cols:
            changed_cols[col] = ordered_list_dif_idx(static_current, static_updated, col)
            change_indx |= ordered_list_dif_idx(static_current, static_updated, col)

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
        }, changed_cols
    else:
        new = list(set(updated_pas["identifier"]))
        if verbose:
            print(f"new: {len(new)}")

        return {
            "new": updated_pas[updated_pas["identifier"].isin(new)]
            .drop(columns="identifier")
            .to_dict(orient="records"),
            "changed": [],
            "deleted": [],
        }, None
