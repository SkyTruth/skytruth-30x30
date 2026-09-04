import gc

import geopandas as gpd
import pandas as pd
import rasterio
import shapely
from joblib import Parallel, delayed
from shapely.geometry import box
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix, extract_polygons, load_iho_regions
from src.core.land_cover_params import marine_tolerance
from src.core.params import (
    BUCKET,
    CLIMATE_RES_CORAL_SOURCE_FILE,
    EEZ_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    GLOBAL_HABITAT_AREA_FILE_PATTERN,
    HABITAT_BY_LOCATION_FILE_PATTERN,
    HABITAT_PROCESSING_PARAMS,
    SEAMOUNTS_SHAPEFILE_NAME,
    SEAMOUNTS_ZIPFILE_NAME,
    WDPA_MARINE_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
)
from src.core.processors import clean_geometries, filter_protected_planet
from src.core.raster_pa_stats import compute_class_areas_by_location, compute_location_class_areas
from src.utils.gcp import (
    download_file_from_gcs,
    load_zipped_shapefile_from_gcs,
    read_json_df,
    read_json_from_gcs,
    read_parquet_from_gcs,
)
from src.utils.geo import get_area_km2, robust_unary_union, fast_union_area_km2
from src.utils.logger import Logger

# Climate-resilient corals raster: 1 = climate-resilient corals, 0 = other corals.
CLIMATE_RESILIENT_CORALS_CLASS_MAP = {0: "other-corals", 1: "climate-resilient-corals"}
CLIMATE_RESILIENT_CORALS_HABITATS = ("climate-resilient-corals", "other-corals")

logger = Logger()


def create_seamounts_subtable(
    marine_protected_areas,
    combined_regions,
    seamounts_zipfile_name: str = SEAMOUNTS_ZIPFILE_NAME,
    seamounts_shapefile_name: str = SEAMOUNTS_SHAPEFILE_NAME,
    eez_file_name: str = EEZ_FILE_NAME,
    tolerance: float = marine_tolerance,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """Compute seamount protection stats per country/region from the ZSL seamounts layer."""

    def get_group_stats(df_eez, df_pa, loc, relations, global_seamount_area):
        if loc == "GLOB":
            df_pa_group = df_pa[["PEAKID", "AREA2D"]].drop_duplicates()
            total_area = global_seamount_area
        else:
            df_pa_group = df_pa[df_pa["location"].isin(relations[loc])][
                ["PEAKID", "AREA2D"]
            ].drop_duplicates()

            df_eez_group = df_eez[df_eez["location"].isin(relations[loc])][
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
        }

    if verbose:
        logger.info({"message": "loading seamounts"})

    seamounts = load_zipped_shapefile_from_gcs(
        seamounts_zipfile_name, bucket, internal_shapefile_path=seamounts_shapefile_name
    )

    if verbose:
        logger.info({"message": "loading eezs"})
    eez = read_json_df(bucket, add_tolerance_suffix(eez_file_name, tolerance), verbose)

    if verbose:
        logger.info({"message": "loading IHO sea areas"})
    iho = load_iho_regions()

    if verbose:
        logger.info({"message": "spatially joining seamounts with eezs, IHO regions, and PAs"})

    eez_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        eez[["location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    eez_seamounts = eez_joined[eez_joined["index_right"].notna()]

    iho_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        iho[["location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    iho_seamounts = iho_joined[iho_joined["index_right"].notna()]

    marine_pa_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        marine_protected_areas[["wdpa_id", "location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    marine_pa_seamounts = marine_pa_joined[marine_pa_joined["index_right"].notna()]

    iho_pa_joined = gpd.sjoin(
        marine_pa_seamounts[["PEAKID", "AREA2D", "geometry"]],
        iho[["location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    iho_pa_seamounts = iho_pa_joined[iho_pa_joined["index_right"].notna()]

    all_seamounts = pd.concat([eez_seamounts, iho_seamounts], ignore_index=True)
    all_pa_seamounts = pd.concat([marine_pa_seamounts, iho_pa_seamounts], ignore_index=True)
    combined_regions = {**combined_regions, **{loc: [loc] for loc in iho["location"]}}

    global_seamount_area = seamounts["AREA2D"].sum()

    return pd.DataFrame(
        [
            get_group_stats(
                all_seamounts,
                all_pa_seamounts,
                cnt,
                combined_regions,
                global_seamount_area,
            )
            for cnt in combined_regions
        ]
    )


def _keep_polygonal(geom):
    """Drop line/point slivers an intersection can leave behind, so unions stay robust."""
    if geom is None or geom.is_empty:
        return None
    polygonal = extract_polygons(geom)
    if polygonal is None or polygonal.is_empty:
        return None
    return make_valid(polygonal)


def _protected_habitat_one_location(
    loc: str,
    habitat_geom,
    total_habitat_area_km2: float,
    pa_geoms,
    pa_location_values,
    pa_locations: set,
    pa_sindex,
) -> tuple[dict, object]:
    """One location's row, plus its contribution to the deduplicated global geometry."""
    shapely.prepare(habitat_geom)
    try:
        candidates = pa_sindex.query(habitat_geom, predicate="intersects")
    finally:
        shapely.destroy_prepared(habitat_geom)

    global_protected = (
        habitat_geom.intersection(robust_unary_union(pa_geoms[candidates]))
        if len(candidates)
        else None
    )

    if loc in pa_locations:
        same_location = pa_location_values[candidates] == loc
        if same_location.all():
            location_protected = global_protected
        elif same_location.any():
            location_protected = habitat_geom.intersection(
                robust_unary_union(pa_geoms[candidates[same_location]])
            )
        else:
            location_protected = None
    else:
        location_protected = global_protected

    row = {
        "location": loc,
        "total_habitat_area_km2": total_habitat_area_km2,
        "protected_habitat_area_km2": (
            0.0 if location_protected is None else get_area_km2(location_protected)
        ),
    }
    return row, _keep_polygonal(global_protected)


def _protected_habitat_all_locations(
    habitat_by_location: gpd.GeoDataFrame,
    locations: gpd.GeoDataFrame,
    protected_areas: gpd.GeoDataFrame,
    n_jobs: int = -1,
) -> tuple[pd.DataFrame, float]:
    """Intersect each location's dissolved habitat geometry with the PAs covering it.

    Returns (per-location rows, global_protected_area_km2).
    """
    pa_location_values = protected_areas["location"].values
    pa_geoms = protected_areas.geometry.values
    pa_locations = set(protected_areas["location"])
    pa_sindex = protected_areas.sindex

    habitat_rows = (
        habitat_by_location.dropna(subset=["location"])
        .drop_duplicates(subset=["location"])
        .set_index("location")
    )
    habitat_locations = sorted(set(locations["location"].dropna()) & set(habitat_rows.index))

    jobs = [
        (loc, habitat_rows.geometry.at[loc], float(habitat_rows["area_km2"].at[loc]))
        for loc in habitat_locations
    ]
    pa_sindex.query(box(0, 0, 0, 0))

    results = Parallel(n_jobs=n_jobs, backend="threading")(
        delayed(_protected_habitat_one_location)(
            loc,
            habitat_geom,
            total_area_km2,
            pa_geoms,
            pa_location_values,
            pa_locations,
            pa_sindex,
        )
        for loc, habitat_geom, total_area_km2 in tqdm(jobs)
    )

    rows = [row for row, _ in results]
    global_protected_geoms = [geom for _, geom in results if geom is not None]

    protected_by_location = pd.DataFrame(
        rows, columns=["location", "total_habitat_area_km2", "protected_habitat_area_km2"]
    )

    global_protected_area_km2 = fast_union_area_km2(global_protected_geoms, n_jobs)

    return protected_by_location, global_protected_area_km2


def create_habitat_subtable(
    all_protected_areas,
    combined_regions,
    habitats: dict = HABITAT_PROCESSING_PARAMS,
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    by_location_file_pattern: str = HABITAT_BY_LOCATION_FILE_PATTERN,
    global_area_file_pattern: str = GLOBAL_HABITAT_AREA_FILE_PATTERN,
    tolerance: float = marine_tolerance,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """Compute protection stats for each habitat from its pre-dissolved geometries.

    Uses the per-location geometries written by process_marine_habitat_geoms, and
    returns a subtable with one row per habitat per location. Habitats include
    mangroves, saltmarshes, seagrasses, and cold-water corals.

    Locations overlap each other, so the GLOB row takes both its total and its protected
    area from deduplicated global geometries (see _protected_habitat_all_locations).
    """

    def get_group_stats(df, loc, relations, habitat, global_area_km2, global_protected_km2):
        if loc == "GLOB":
            return {
                "location": loc,
                "habitat": habitat,
                "environment": "marine",
                "protected_area": global_protected_km2,
                "total_area": global_area_km2,
            }

        df_group = df[df["location"].isin(relations[loc])]

        return {
            "location": loc,
            "habitat": habitat,
            "environment": "marine",
            "protected_area": df_group["protected_habitat_area_km2"].sum(),
            "total_area": df_group["total_habitat_area_km2"].sum(),
        }

    if verbose:
        logger.info({"message": "loading eez/land union"})
    gadm_eez_union_file_name = add_tolerance_suffix(gadm_eez_union_file_name, tolerance)
    country_union = read_json_df(bucket, gadm_eez_union_file_name, verbose=verbose)

    if verbose:
        logger.info({"message": "loading IHO sea areas"})
    iho = load_iho_regions(buffer=True)

    locations = gpd.GeoDataFrame(
        pd.concat(
            [country_union[["location", "geometry"]], iho[["location", "geometry"]]],
            ignore_index=True,
        ),
        geometry="geometry",
        crs=country_union.crs,
    )

    combined_locations = {**combined_regions, **{loc: [loc] for loc in iho["location"]}}

    subtables = []
    for habitat in habitats:
        if verbose:
            logger.info({"message": f"loading pre-processed {habitat}"})
        habitat_by_location = read_parquet_from_gcs(
            bucket, by_location_file_pattern.format(habitat=habitat), verbose=verbose
        ).pipe(clean_geometries)
        global_area_km2 = read_json_from_gcs(
            bucket, global_area_file_pattern.format(habitat=habitat)
        )["global_area_km2"]

        if verbose:
            logger.info({"message": f"getting protected {habitat} area by location"})
        protected_habitat, global_protected_km2 = _protected_habitat_all_locations(
            habitat_by_location, locations, all_protected_areas
        )

        habitat_stats = pd.DataFrame(
            [
                get_group_stats(
                    protected_habitat,
                    loc,
                    combined_locations,
                    habitat,
                    global_area_km2,
                    global_protected_km2,
                )
                for loc in combined_locations
            ]
        )
        subtables.append(habitat_stats[habitat_stats["total_area"] > 0])

    return pd.concat(subtables, axis=0, ignore_index=True)


def _rollup_corals_subtable(
    total_stats: pd.DataFrame,
    protected_stats: pd.DataFrame,
    combined_regions: dict,
    habitats: tuple = CLIMATE_RESILIENT_CORALS_HABITATS,
    global_total: dict | None = None,
    global_protected: dict | None = None,
) -> pd.DataFrame:
    """Roll per-location class areas up to combined_regions and reshape into subtable rows.

    Location rows are summed from their member locations, so a
    reef that sits in an EEZ with overlapping claims is attributed to every claimant
    (intentional over-attribution). The GLOB row must NOT inherit that double count,
    so when `global_total`/`global_protected` are supplied (deduplicated global class
    areas computed once over the whole reef extent) they are used for GLOB instead of
    summing the per-location rows. If they are omitted, GLOB falls back to the location
    sum (legacy behaviour, used by callers that have no deduplicated global to pass).
    """

    def _sum(df: pd.DataFrame, locs: list | None, habitat: str) -> float:
        if habitat not in df.columns or df.empty:
            return 0.0
        if locs is None:
            return float(df[habitat].sum())
        return float(df.loc[df["location"].isin(locs), habitat].sum())

    def _global(stats: dict | None, habitat: str) -> float:
        return float(stats.get(habitat, 0.0)) if stats else 0.0

    rows = []
    for habitat in habitats:
        for loc in combined_regions:
            if loc == "GLOB" and (global_total is not None or global_protected is not None):
                protected_area = _global(global_protected, habitat)
                total_area = _global(global_total, habitat)
            else:
                members = None if loc == "GLOB" else combined_regions[loc]
                protected_area = _sum(protected_stats, members, habitat)
                total_area = _sum(total_stats, members, habitat)
            rows.append(
                {
                    "location": loc,
                    "habitat": habitat,
                    "environment": "marine",
                    "protected_area": protected_area,
                    "total_area": total_area,
                }
            )
    return pd.DataFrame(rows)


def create_climate_resilient_corals_subtable(
    marine_protected_areas: gpd.GeoDataFrame,
    combined_regions: dict,
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    coral_source_file: str = CLIMATE_RES_CORAL_SOURCE_FILE,
    terrestrial_protected_areas: gpd.GeoDataFrame | None = None,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    tolerance: float = marine_tolerance,
    bucket: str = BUCKET,
    n_jobs: int = -1,
    verbose: bool = True,
) -> pd.DataFrame:
    """Compute climate-resilient-coral and other-coral protection per country/region.

    Runs a total pass and a protected pass over the coral raster and rolls the
    results up to `combined_regions`. Regions are the land∪EEZ union so reefs
    fringing coastlines just outside the simplified EEZ are still attributed.

    The protected pass uses the full WDPA/OECM estate — marine PAs
    (`marine_protected_areas`) plus terrestrial-flagged PAs clipped to the reef
    extent — since coastal reefs are often inside PAs WDPA flags MARINE=0. Only
    reef pixels inside a PA are counted, so this can't over-count.
    """
    if verbose:
        logger.info({"message": "loading GADM/EEZ union for coral coverage"})
    gadm_eez_union_file_name = add_tolerance_suffix(gadm_eez_union_file_name, tolerance)
    regions = read_json_df(bucket, gadm_eez_union_file_name, verbose=verbose)

    if verbose:
        logger.info({"message": "loading IHO sea areas for coral coverage"})
    iho = load_iho_regions(buffer=True)

    if verbose:
        logger.info({"message": f"downloading coral raster from {coral_source_file}"})
    local_raster_path = coral_source_file.split("/")[-1]
    download_file_from_gcs(bucket, coral_source_file, local_raster_path, verbose=False)
    with rasterio.open(local_raster_path) as src:
        raster_crs = src.crs
        raster_bounds = src.bounds
    # The raster's footprint in 4326 (a ~±34° band); terrestrial PAs outside it
    # can't touch a reef, so drop them before the costly dissolve.
    coral_extent = gpd.GeoSeries([box(*raster_bounds)], crs=raster_crs).to_crs("EPSG:4326").iloc[0]

    if verbose:
        logger.info({"message": "combining marine + terrestrial PAs (full WDPA/OECM estate)"})
    if terrestrial_protected_areas is None:
        terrestrial_pa_file_name = add_tolerance_suffix(terrestrial_pa_file_name, tolerance)
        terrestrial_raw = read_json_df(bucket, terrestrial_pa_file_name, verbose=verbose).pipe(
            filter_protected_planet
        )
        terrestrial_raw = terrestrial_raw[terrestrial_raw.intersects(coral_extent)]
        terrestrial_protected_areas = (
            dissolve_multipolygons(terrestrial_raw[["ISO3", "WDPAID", "geometry"]])
            .rename(columns={"ISO3": "location", "WDPAID": "wdpa_id"})
            .pipe(clean_geometries)
        )
    # Marine and terrestrial PAs share no WDPAIDs (MARINE is a partition), so concat.
    protected_areas = gpd.GeoDataFrame(
        pd.concat([marine_protected_areas, terrestrial_protected_areas], ignore_index=True),
        geometry="geometry",
        crs=marine_protected_areas.crs,
    )

    # Drop regions and (marine) PAs outside the reef band before the expensive
    # reproject/validate/union — they can't touch a reef pixel.
    regions = regions[regions.intersects(coral_extent)]
    iho = iho[iho.intersects(coral_extent)]
    protected_areas = protected_areas[protected_areas.intersects(coral_extent)]

    # rasterio.mask runs in the raster CRS without reprojecting; re-validate after
    # to_crs since reprojection can self-intersect (e.g. JPN) and break unions.
    if verbose:
        logger.info(
            {"message": f"reprojecting region, PA geometries, and IHO areas to {raster_crs}"}
        )
    regions = regions.to_crs(raster_crs)
    regions["geometry"] = regions.geometry.apply(make_valid)
    protected_areas = protected_areas.to_crs(raster_crs)
    protected_areas["geometry"] = protected_areas.geometry.apply(make_valid)
    iho = iho.to_crs(raster_crs)
    iho["geometry"] = iho.geometry.apply(make_valid)

    if verbose:
        logger.info({"message": "computing total coral class areas per country"})
    total_stats = compute_class_areas_by_location(
        raster_path=local_raster_path,
        regions_gdf=regions,
        class_map=CLIMATE_RESILIENT_CORALS_CLASS_MAP,
        region_col="location",
        polygons_gdf=None,
        include_zero=True,
        n_jobs=n_jobs,
        verbose=verbose,
    )

    if verbose:
        logger.info({"message": "computing protected coral class areas per country"})
    protected_stats = compute_class_areas_by_location(
        raster_path=local_raster_path,
        regions_gdf=regions,
        class_map=CLIMATE_RESILIENT_CORALS_CLASS_MAP,
        region_col="location",
        polygons_gdf=protected_areas,
        polygon_location_col="location",
        include_zero=True,
        n_jobs=n_jobs,
        verbose=verbose,
    )

    if verbose:
        logger.info({"message": "computing total coral class areas per IHO region"})
    iho_total = compute_class_areas_by_location(
        raster_path=local_raster_path,
        regions_gdf=iho,
        class_map=CLIMATE_RESILIENT_CORALS_CLASS_MAP,
        region_col="location",
        polygons_gdf=None,
        include_zero=True,
        n_jobs=n_jobs,
        verbose=verbose,
    )

    if verbose:
        logger.info({"message": "tagging protected areas to IHO regions"})
    pas_iho = gpd.sjoin(
        protected_areas[["geometry"]],
        iho[["location", "geometry"]],
        how="inner",
        predicate="intersects",
    )

    if verbose:
        logger.info({"message": "computing protected coral class areas per IHO region"})
    iho_protected = compute_class_areas_by_location(
        raster_path=local_raster_path,
        regions_gdf=iho,
        class_map=CLIMATE_RESILIENT_CORALS_CLASS_MAP,
        region_col="location",
        polygons_gdf=pas_iho,
        polygon_location_col="location",  # now the IHO MRGID, matching regions_gdf
        include_zero=True,
        n_jobs=n_jobs,
        verbose=verbose,
    )

    if verbose:
        logger.info({"message": f"computed IHO coral stats for {len(iho_total)} region(s)"})

    total_stats = pd.concat([total_stats, iho_total], ignore_index=True)
    protected_stats = pd.concat([protected_stats, iho_protected], ignore_index=True)

    # Per-country rows double-count reefs in overlapping EEZ claims, so compute
    # the GLOB row over the dissolved union of all regions (each reef pixel once).
    if verbose:
        logger.info({"message": "computing deduplicated global coral class areas"})
    global_geom = robust_unary_union(regions["geometry"].values)
    global_total = (
        compute_location_class_areas(
            location="GLOB",
            location_geom=global_geom,
            raster_path=local_raster_path,
            class_map=CLIMATE_RESILIENT_CORALS_CLASS_MAP,
            polygons_gdf=None,
            include_zero=True,
        )
        or {}
    )
    global_protected = (
        compute_location_class_areas(
            location="GLOB",
            location_geom=global_geom,
            raster_path=local_raster_path,
            class_map=CLIMATE_RESILIENT_CORALS_CLASS_MAP,
            polygons_gdf=protected_areas,
            include_zero=True,
        )
        or {}
    )

    if verbose:
        logger.info({"message": "rolling up coral stats by region"})
    return _rollup_corals_subtable(
        total_stats,
        protected_stats,
        {**combined_regions, **{loc: [loc] for loc in iho["location"]}},
        global_total=global_total,
        global_protected=global_protected,
    )


def dissolve_multipolygons(gdf: gpd.GeoDataFrame, key: str = "WDPAID") -> gpd.GeoDataFrame:
    counts = gdf[key].value_counts()

    singles = gdf[gdf[key].isin(counts[counts == 1].index)]
    multiples = gdf[gdf[key].isin(counts[counts > 1].index)]

    dissolved = multiples.dissolve(by=key)
    dissolved = dissolved.reset_index()
    result = pd.concat([singles, dissolved], ignore_index=True)

    return result


def _load_and_dissolve_pas(
    pa_file_name: str,
    bucket: str,
    verbose: bool,
) -> gpd.GeoDataFrame:
    """Read one WDPA/OECM geojson and dissolve its multi-part records into one row per PA,
    filtered by status according to Protected Planet methods.
    """
    pas = read_json_df(bucket, pa_file_name, verbose=verbose).pipe(filter_protected_planet)
    return (
        dissolve_multipolygons(pas[["ISO3", "WDPAID", "geometry"]])
        .rename(columns={"ISO3": "location", "WDPAID": "wdpa_id"})
        .pipe(clean_geometries)
    )


def load_marine_terrestrial_pa(
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    bucket: str = BUCKET,
    tolerance: float = marine_tolerance,
    verbose: bool = True,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load the dissolved marine PAs, the dissolved terrestrial PAs, and the full estate.

    Returns (marine_protected_areas, terrestrial_protected_areas, all_protected_areas).
    The intertidal and coastal habitats (saltmarshes and mangroves) are frequently
    designated inside PAs that WDPA flags MARINE=0, so intersecting them against only the
    marine PAs undercounts their protection. Habitats that can sit on land therefore use
    the full terrestrial + marine areas; seamounts, which are deep-sea by definition,
    stay on the marine PAs.
    """
    if verbose:
        logger.info({"message": "getting marine protected areas"})
    marine_protected_areas = _load_and_dissolve_pas(marine_pa_file_name, bucket, verbose)

    if verbose:
        logger.info({"message": "getting terrestrial protected areas"})
    terrestrial_protected_areas = _load_and_dissolve_pas(
        add_tolerance_suffix(terrestrial_pa_file_name, tolerance), bucket, verbose
    )

    all_protected_areas = gpd.GeoDataFrame(
        pd.concat([marine_protected_areas, terrestrial_protected_areas], ignore_index=True),
        geometry="geometry",
        crs=marine_protected_areas.crs,
    )

    return marine_protected_areas, terrestrial_protected_areas, all_protected_areas


def process_marine_habitats(
    combined_regions,
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    bucket: str = BUCKET,
    tolerance: float = marine_tolerance,
    verbose: bool = True,
):
    marine_protected_areas, terrestrial_protected_areas, all_protected_areas = (
        load_marine_terrestrial_pa(
            marine_pa_file_name=marine_pa_file_name,
            terrestrial_pa_file_name=terrestrial_pa_file_name,
            bucket=bucket,
            tolerance=tolerance,
            verbose=verbose,
        )
    )

    if verbose:
        logger.info({"message": "getting habitat subtable"})
    habitat_subtable = create_habitat_subtable(
        all_protected_areas,
        combined_regions,
        gadm_eez_union_file_name=gadm_eez_union_file_name,
        tolerance=tolerance,
        bucket=bucket,
        verbose=verbose,
    )

    if verbose:
        logger.info({"message": "getting seamounts subtable"})
    seamounts_subtable = create_seamounts_subtable(
        marine_protected_areas,
        combined_regions,
        tolerance=tolerance,
        bucket=bucket,
        verbose=verbose,
    )

    del all_protected_areas
    gc.collect()

    if verbose:
        logger.info({"message": "getting climate-resilient corals subtable"})

    corals_subtable = create_climate_resilient_corals_subtable(
        marine_protected_areas,
        combined_regions,
        gadm_eez_union_file_name=gadm_eez_union_file_name,
        terrestrial_protected_areas=terrestrial_protected_areas,
        terrestrial_pa_file_name=terrestrial_pa_file_name,
        tolerance=tolerance,
        bucket=bucket,
        verbose=verbose,
    )

    marine_habitats = pd.concat((habitat_subtable, seamounts_subtable, corals_subtable), axis=0)

    return marine_habitats
