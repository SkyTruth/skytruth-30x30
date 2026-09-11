"""The (protected area, IHO sea area) pairs the pipeline reads.

Two files are written, each one row per (feature, sea area) pair carrying the
feature clipped to that sea: the WDPA pairs and the MPAtlas pairs. Both exist so
their consumers can measure protected area within a sea without re-running the
clip; a consumer that only needs to know which sea a feature lies in, or that
clips against the seas itself, should join in place rather than read these.
"""

import geopandas as gpd
import pandas as pd
from tqdm.auto import tqdm

from src.core.commons import (
    add_tolerance_suffix,
    load_iho_regions,
    polygonal_parts,
    read_mpatlas_from_gcs,
)
from src.core.params import (
    BUCKET,
    MPATLAS_FILE_NAME,
    MPATLAS_SEA_PAIRS_FILE_NAME,
    TOLERANCE,
    WDPA_MARINE_FILE_NAME,
    WDPA_SEA_PAIRS_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
)
from src.utils.gcp import read_json_df, upload_gdf
from src.utils.logger import Logger

logger = Logger()

WDPA_ENVIRONMENTS = (
    ("marine", WDPA_MARINE_FILE_NAME),
    ("terrestrial", WDPA_TERRESTRIAL_FILE_NAME),
)

tqdm.pandas()


def intersect_with_iho(
    features: gpd.GeoDataFrame,
    keep_cols: list[str],
    buffer: bool = False,
    with_geometry: bool = True,
) -> gpd.GeoDataFrame | pd.DataFrame:
    """One row per (feature, IHO sea area) pair the feature intersects.

    Parameters
    ----------
    features : gpd.GeoDataFrame
        Features to assign to sea areas — protected areas, MPAtlas zones, etc.
        Must be in the IHO CRS (EPSG:4326).
    keep_cols : list[str]
        Column(s) of ``features`` to carry through onto the pairs. Everything
        else is dropped; callers either merge their own attributes back on or
        ask for them here.
    buffer : bool
        Join against the near-shore buffered sea areas rather than the
        published IHO boundaries. See ``load_iho_regions``.
    with_geometry : bool
        Also return each pair's intersection: the feature clipped to that one
        sea. A point feature has no area to clip, so it keeps its membership
        with a null geometry; an areal feature with no polygonal intersection
        merely touched the sea boundary and that pair is dropped as a clipping
        artifact. Callers measuring area filter on ``geometry.notna()``, though
        ``union_all``, ``difference`` and ``dissolve`` all ignore nulls.

    Returns
    -------
    gpd.GeoDataFrame | pd.DataFrame
        ``[*keep_cols, "location"]``, plus ``geometry`` when ``with_geometry``.
    """

    # load IHO sea areas, optionally buffered to catch near-shore features
    iho = load_iho_regions(buffer=buffer)[["location", "geometry"]].reset_index(drop=True)

    # keep relevant columns and make geometries valid
    features = features[[*keep_cols, "geometry"]].copy()
    features["geometry"] = features.geometry.make_valid()

    # match features to IHO sea areas by intersection, dropping any that don't intersect
    logger.info({"message": f"matching {len(features)} features to {len(iho)} IHO sea areas"})
    pairs = features.sjoin(iho, predicate="intersects").reset_index(drop=True)
    logger.info({"message": f"found {len(pairs)} feature / IHO sea overlaps"})

    # If clipped geometry is not needed, skip computing the intersections.
    if not with_geometry:
        return pd.DataFrame(pairs[[*keep_cols, "location"]])

    # Identify the point PAs so they are not dropped when they have no polygonal
    # intersection with the sea. Taken before clipping replaces the geometry.
    point_feature = pairs.geom_type.isin(("Point", "MultiPoint"))

    # Clip each feature to the IHO sea area it intersects, reducing each result
    # to its polygonal content.
    seas = gpd.GeoSeries(iho.geometry.loc[pairs["index_right"]].to_numpy(), crs=iho.crs)
    cut = pairs.geometry.intersection(seas, align=False).progress_apply(polygonal_parts)
    pairs = pairs.set_geometry(cut)

    # Keep pairs that have a polygonal intersection or are point features
    # (which have no area to intersect).
    keep = pairs.geometry.notna() | point_feature

    logger.info(
        {
            "message": (
                f"dropping {int((~keep).sum())} pair(s) touching a sea without overlapping it, "
                f"keeping {int(point_feature.sum())} point pair(s) with no geometry"
            )
        }
    )

    return pairs[keep][[*keep_cols, "location", "geometry"]].reset_index(drop=True)


def intersect_wdpa_with_iho(
    bucket: str = BUCKET,
    tolerance: float = TOLERANCE,
    pa_file_name: str = WDPA_MARINE_FILE_NAME,
    buffer: bool = False,
    with_geometry: bool = True,
) -> pd.DataFrame:
    """One row per (PA, IHO sea) pair the PA overlaps, keyed on WDPA_PID.

    Pass ``pa_file_name`` to read the terrestrial PAs instead of the marine
    ones, and ``buffer`` to join against the near-shore seas.

    Four attributes ride along so consumers need not re-read the protected areas
    file: ``WDPAID``, each parcel's parent site; ``PA_DEF``, which separates
    protected areas from OECMs; and ``STATUS`` and ``DESIG_ENG``, the site's
    designation state and type.
    """
    pa_file = add_tolerance_suffix(pa_file_name, tolerance)
    logger.info({"message": f"loading PAs from gs://{bucket}/{pa_file}"})

    keep_cols = ["WDPA_PID", "WDPAID", "PA_DEF", "STATUS", "DESIG_ENG"]
    pas = read_json_df(bucket_name=bucket, filename=pa_file)[[*keep_cols, "geometry"]]

    return intersect_with_iho(pas, keep_cols, buffer=buffer, with_geometry=with_geometry)


def intersect_mpatlas_with_iho(
    bucket: str = BUCKET,
    mpa_file_name: str = MPATLAS_FILE_NAME,
    buffer: bool = False,
    with_geometry: bool = True,
) -> pd.DataFrame:
    """One row per (MPAtlas zone, IHO sea) pair the zone overlaps, keyed on zone_id.

    ``protection_mpaguide_level`` rides along, the zone's protection level on the
    MPAtlas guide's scale.
    """
    logger.info({"message": f"loading MPAtlas zones from gs://{bucket}/{mpa_file_name}"})

    keep_cols = ["zone_id", "protection_mpaguide_level"]
    mpa = read_mpatlas_from_gcs(bucket, mpa_file_name)[[*keep_cols, "geometry"]]

    return intersect_with_iho(mpa, keep_cols, buffer=buffer, with_geometry=with_geometry)


def generate_iho_pa_intersections(
    tolerance: float = TOLERANCE,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """Join every protected area dataset to the IHO sea areas and save the pairs."""

    def wdpa_pairs():
        """Marine and terrestrial PAs, labelled, so a consumer can take either or both."""
        return pd.concat(
            [
                intersect_wdpa_with_iho(
                    bucket=bucket,
                    tolerance=tolerance,
                    pa_file_name=pa_file_name,
                    with_geometry=True,
                ).assign(environment=environment)
                for environment, pa_file_name in WDPA_ENVIRONMENTS
            ],
            ignore_index=True,
        )

    def save(pairs, file_name):
        if verbose:
            logger.info({"message": f"saving {len(pairs)} pair(s) to gs://{bucket}/{file_name}"})
        upload_gdf(bucket_name=bucket, gdf=pairs, destination_blob_name=file_name, verbose=verbose)

    # The WDPA names take a tolerance because the PAs they were built from were
    # simplified to it. MPAtlas is read as published, so its name does not.
    save(wdpa_pairs(), add_tolerance_suffix(WDPA_SEA_PAIRS_FILE_NAME, tolerance))
    save(intersect_mpatlas_with_iho(bucket=bucket, with_geometry=True), MPATLAS_SEA_PAIRS_FILE_NAME)
