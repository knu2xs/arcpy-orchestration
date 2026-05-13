"""
Park accessibility analysis.

Reusable building blocks for a "parcels within walking distance of a public park"
workflow. Each function does one thing, takes explicit inputs, and emits log
messages at the appropriate level so that progress is visible in any consumer
(scripts, ArcGIS Pro toolboxes, or Dagster ops).
"""

from __future__ import annotations

import os
from pathlib import Path

import arcpy
import pandas as pd

from .utils import get_logger, with_temp_fgdb

logger = get_logger("arcpy_orchestration.park_access", level="DEBUG", add_stream_handler=False)


def _ensure_projected(fc: str | os.PathLike[str], working_wkid: int) -> None:
    """
    Validate that a feature class is in the expected projected CRS.

    Distance and area calculations require a projected CRS appropriate for the
    area of interest. This guards against the common bug of measuring in
    geographic coordinates (e.g. WGS 84).

    Args:
        fc: Path to the feature class to validate.
        working_wkid: Expected projected CRS WKID (read from `config.spatial`).

    Raises:
        ValueError: If the feature class has no spatial reference or its WKID
            does not match `working_wkid`.
    """
    sr = arcpy.Describe(fc).spatialReference
    if sr is None or sr.factoryCode == 0:
        msg = f"Feature class '{fc}' has no defined spatial reference."
        logger.error(msg)
        raise ValueError(msg)
    if sr.factoryCode != working_wkid:
        msg = (
            f"Feature class '{fc}' is in WKID {sr.factoryCode} "
            f"({sr.name}); expected projected WKID {working_wkid}."
        )
        logger.error(msg)
        raise ValueError(msg)


def project_to_working_crs(
    in_fc: str | os.PathLike[str],
    out_fc: str | os.PathLike[str],
    working_wkid: int,
) -> str:
    """
    Project a feature class into the working projected CRS.

    Args:
        in_fc: Path to the input feature class.
        out_fc: Path to the output projected feature class.
        working_wkid: WKID of the target projected CRS.

    Returns:
        str: Path to the projected output feature class.
    """
    target_sr = arcpy.SpatialReference(working_wkid)
    src_sr = arcpy.Describe(in_fc).spatialReference
    logger.info(
        f"Projecting '{in_fc}' from WKID {src_sr.factoryCode} "
        f"to WKID {working_wkid}."
    )

    with arcpy.EnvManager(overwriteOutput=True):
        arcpy.management.Project(
            in_dataset=in_fc,
            out_dataset=str(out_fc),
            out_coor_system=target_sr,
        )
        
    return str(out_fc)


@with_temp_fgdb
def parcels_within_walking_distance(
    parks_fc: str | os.PathLike[str],
    parcels_fc: str | os.PathLike[str],
    out_fc: str | os.PathLike[str],
    walk_distance_m: float,
    working_wkid: int,
) -> str:
    """
    Find parcels that fall within walking distance of any park.

    Buffers each park by `walk_distance_m`, then selects parcels that intersect
    the union of those buffers. The buffer is written to a temporary file
    geodatabase managed by [`with_temp_fgdb`][arcpy_orchestration.utils.with_temp_fgdb]
    and discarded automatically.

    !!! note
        Both inputs must already be in the working projected CRS. Call
        [`project_to_working_crs`][arcpy_orchestration.park_access.project_to_working_crs]
        upstream if needed.

    Args:
        parks_fc: Park polygons in the working projected CRS.
        parcels_fc: Parcel polygons in the working projected CRS.
        out_fc: Path to the output feature class of selected parcels.
        walk_distance_m: Buffer distance in meters.
        working_wkid: WKID of the working projected CRS (used for validation).

    Returns:
        str: Path to the output feature class.
    """
    _ensure_projected(parks_fc, working_wkid)
    _ensure_projected(parcels_fc, working_wkid)

    # Intermediate buffer goes into the temp FGDB set as the workspace by the decorator
    buffer_fc = "park_walk_buffer"
    logger.info(f"Buffering parks by {walk_distance_m:,.0f} m.")
    arcpy.analysis.Buffer(
        in_features=str(parks_fc),
        out_feature_class=buffer_fc,
        buffer_distance_or_field=f"{walk_distance_m} Meters",
        dissolve_option="ALL",
    )

    logger.info("Selecting parcels intersecting the park buffer.")
    parcels_layer = arcpy.management.MakeFeatureLayer(
        in_features=str(parcels_fc),
        out_layer="parcels_layer",
    )[0]
    arcpy.management.SelectLayerByLocation(
        in_layer=parcels_layer,
        overlap_type="INTERSECT",
        select_features=buffer_fc,
        selection_type="NEW_SELECTION",
    )

    selected_count = int(arcpy.management.GetCount(parcels_layer)[0])
    logger.info(f"Selected {selected_count:,} parcels within walking distance.")

    if arcpy.Exists(out_fc):
        logger.warning(f"Output feature class '{out_fc}' already exists and will be overwritten.")
        arcpy.management.Delete(out_fc)

    arcpy.management.CopyFeatures(
        in_features=parcels_layer,
        out_feature_class=str(out_fc),
    )
    return str(out_fc)


def summarize_parcels(
    parcels_fc: str | os.PathLike[str],
    value_field: str,
) -> pd.DataFrame:
    """
    Compute an overall summary of selected parcels.

    Reads the selected-parcels feature class into a DataFrame and returns a
    single-row summary with parcel count and total/mean of `value_field`.

    Args:
        parcels_fc: Feature class of parcels (typically the output of
            [`parcels_within_walking_distance`][arcpy_orchestration.park_access.parcels_within_walking_distance]).
        value_field: Name of the numeric field to summarize (e.g. assessed value).

    Returns:
        pd.DataFrame: One-row summary with `parcel_count`, `total_value`, and
        `mean_value` columns.
    """
    logger.debug(f"Reading field '{value_field}' from '{parcels_fc}'.")
    rows = [row[0] for row in arcpy.da.SearchCursor(str(parcels_fc), [value_field])]
    df = pd.DataFrame({value_field: rows})

    summary = pd.DataFrame(
        [
            {
                "parcel_count": len(df),
                "total_value": float(df[value_field].sum()),
                "mean_value": float(df[value_field].mean()) if len(df) else 0.0,
            }
        ]
    )
    logger.info(
        f"Summarized {len(df):,} parcels: "
        f"total {value_field}={summary.loc[0, 'total_value']:,.0f}."
    )
    return summary


def export_summary(summary_df: pd.DataFrame, out_path: str | os.PathLike[str]) -> str:
    """
    Write a parcel summary to an Excel workbook.

    Args:
        summary_df: Summary DataFrame produced by
            [`summarize_parcels`][arcpy_orchestration.park_access.summarize_parcels].
        out_path: Destination ``.xlsx`` file path.

    Returns:
        str: The output path as a string.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_excel(out_path, sheet_name="summary", index=False)
    logger.info(f"Wrote summary ({len(summary_df):,} rows) to '{out_path}'.")
    return str(out_path)
