"""Flood zone parcel impact analysis helpers.

This module contains reusable workflow steps for identifying parcels intersecting
FEMA flood zones, summarizing impact by flood zone type, and exporting a
multi-sheet Excel report.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import warnings

import arcpy
import pandas as pd

from .config import PROJECT_ROOT, config
from .utils import get_logger

logger = get_logger(__name__, level="DEBUG", add_stream_handler=False)

PARCELS_URL: str = (
    "https://tconline.co.thurston.wa.us/server/rest/services/"
    "Common_Layers/Parcels/FeatureServer/4"
)

FLOOD_ZONES_URL: str = (
    "https://map.co.thurston.wa.us/arcgis/rest/services/"
    "Thurston/FEMAFloodZones2020/FeatureServer/0"
)


def _extract_fgdb_path(dataset_path: Path) -> Path | None:
    """Return the first ``*.gdb`` segment from a dataset path, if present."""
    parts = list(dataset_path.parts)
    for idx, part in enumerate(parts):
        if part.lower().endswith(".gdb"):
            return Path(*parts[: idx + 1])
    return None


def _ensure_raw_gdb(gdb_path: Path) -> str:
    """Create raw file geodatabase if needed and return its path."""
    if arcpy.Exists(str(gdb_path)):
        return str(gdb_path)

    gdb_path.parent.mkdir(parents=True, exist_ok=True)
    arcpy.management.CreateFileGDB(
        out_folder_path=str(gdb_path.parent),
        out_name=gdb_path.name,
    )
    return str(gdb_path)


def _create_fgdb_if_missing(gdb_path: Path) -> None:
    """Create a file geodatabase if it does not already exist."""
    if arcpy.Exists(str(gdb_path)):
        return

    gdb_path.parent.mkdir(parents=True, exist_ok=True)
    arcpy.management.CreateFileGDB(
        out_folder_path=str(gdb_path.parent),
        out_name=gdb_path.name,
    )


def _download_feature_service(service_url: str, out_gdb: str, out_name: str) -> str:
    """Download a feature service layer into a geodatabase when missing."""
    out_fc = f"{out_gdb}/{out_name}"
    if arcpy.Exists(out_fc):
        record_count = int(arcpy.management.GetCount(out_fc)[0])
        if record_count > 0:
            logger.info(f"'{out_fc}' already exists with {record_count} records; skipping download.")
            return out_fc

        logger.warning(
            "'%s' already exists but contains no records; deleting stale dataset and re-downloading.",
            out_fc,
        )
        arcpy.management.Delete(out_fc)

    logger.info(f"Downloading '{service_url}' -> '{out_fc}'.")
    try:
        arcpy.conversion.ExportFeatures(
            in_features=service_url,
            out_features=out_fc,
        )
    except Exception as exc:
        logger.warning(
            "Direct ArcPy export failed for '%s'; falling back to ArcGIS API query download: %s",
            service_url,
            exc,
        )
        if arcpy.Exists(out_fc):
            arcpy.management.Delete(out_fc)
        _download_feature_service_via_api(service_url=service_url, out_fc=out_fc)

    return out_fc


def _download_feature_service_via_api(
    service_url: str,
    out_fc: str | os.PathLike[str],
) -> str:
    """Download a feature service via the ArcGIS Python API query path."""
    from arcgis.features import FeatureLayer
    from urllib3.exceptions import InsecureRequestWarning

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureRequestWarning)
        feature_layer = FeatureLayer(service_url)
        feature_set = feature_layer.query(where="1=1", return_all_records=True)

    logger.info(
        "ArcGIS API query returned %s features for '%s'.",
        len(feature_set.features),
        service_url,
    )
    feature_set.sdf.spatial.to_featureclass(location=str(out_fc), sanitize_columns=False)
    return str(out_fc)


def ensure_raw_data(
    raw_gdb: str | os.PathLike[str],
    parcels_fc_name: str = "parcels",
    flood_zones_fc_name: str = "flood_zones",
) -> tuple[str, str]:
    """Ensure parcels and flood-zone source datasets exist in the raw geodatabase."""
    raw_gdb_path = Path(raw_gdb)
    logger.info(f"Ensuring raw data in '{raw_gdb_path}'.")

    gdb = _ensure_raw_gdb(raw_gdb_path)
    parcels_fc = _download_feature_service(PARCELS_URL, gdb, parcels_fc_name)
    flood_zones_fc = _download_feature_service(FLOOD_ZONES_URL, gdb, flood_zones_fc_name)
    return parcels_fc, flood_zones_fc


def prepare_data_directories(project_dir: str | os.PathLike[str] | None = None) -> None:
    """Create configured directories/geodatabases for the flood workflow.

    Args:
        project_dir: Optional project root (parent directory that contains
            ``data/``). Defaults to ``PROJECT_ROOT``.
    """
    project_root = Path(project_dir).resolve() if project_dir is not None else PROJECT_ROOT
    cfg = config.flood_zone_summary

    flood_zones_fc_path = project_root / str(cfg.flood_zones_fc)
    parcels_fc_path = project_root / str(cfg.parcels_fc)
    output_parcels_fc_path = project_root / str(cfg.output_parcels_fc)
    output_summary_path = project_root / str(cfg.output_summary_path)

    output_summary_path.parent.mkdir(parents=True, exist_ok=True)

    gdb_paths: list[Path] = []
    for dataset_path in (flood_zones_fc_path, parcels_fc_path, output_parcels_fc_path):
        gdb_path = _extract_fgdb_path(dataset_path)
        if gdb_path is not None:
            gdb_paths.append(gdb_path)

    gdb_paths.append(project_root / "data" / "interim" / "interim.gdb")

    seen: set[str] = set()
    for gdb_path in gdb_paths:
        key = str(gdb_path).lower()
        if key in seen:
            continue
        seen.add(key)
        _create_fgdb_if_missing(gdb_path)

    logger.info("Data directories and geodatabases are ready.")


def download_raw_data_if_missing(raw_gdb: str | os.PathLike[str] | None = None) -> tuple[str, str]:
    """Download raw parcels/flood-zone inputs when missing.

    Args:
        raw_gdb: Optional destination raw file geodatabase path. When omitted,
            inferred from ``config.flood_zone_summary.flood_zones_fc``.

    Returns:
        tuple[str, str]: Paths to ``(parcels_fc, flood_zones_fc)``.
    """
    cfg = config.flood_zone_summary
    flood_zones_fc_path = PROJECT_ROOT / str(cfg.flood_zones_fc)
    parcels_fc_path = PROJECT_ROOT / str(cfg.parcels_fc)

    if raw_gdb is None:
        inferred_raw_gdb = _extract_fgdb_path(flood_zones_fc_path)
        if inferred_raw_gdb is None:
            raise ValueError(
                "Invalid flood_zones_fc path; expected a path containing a .gdb segment."
            )
        raw_gdb_path = inferred_raw_gdb
    else:
        raw_gdb_path = Path(raw_gdb).resolve()

    return ensure_raw_data(
        raw_gdb=raw_gdb_path,
        parcels_fc_name=parcels_fc_path.name,
        flood_zones_fc_name=flood_zones_fc_path.name,
    )


def _ensure_projected(fc: str | os.PathLike[str], working_wkid: int) -> None:
    """Validate that a feature class is in the expected projected CRS."""
    sr = arcpy.Describe(fc).spatialReference
    if sr is None or sr.factoryCode == 0:
        raise ValueError(f"Feature class '{fc}' has no defined spatial reference.")
    if sr.factoryCode != working_wkid:
        raise ValueError(
            f"Feature class '{fc}' is in WKID {sr.factoryCode} ({sr.name}); "
            f"expected projected WKID {working_wkid}."
        )


def project_to_working_crs(
    in_fc: str | os.PathLike[str],
    out_fc: str | os.PathLike[str],
    working_wkid: int,
) -> str:
    """Project a feature class into the configured working projected CRS."""
    target_sr = arcpy.SpatialReference(working_wkid)
    with arcpy.EnvManager(overwriteOutput=True):
        arcpy.management.Project(
            in_dataset=str(in_fc),
            out_dataset=str(out_fc),
            out_coor_system=target_sr,
        )
    return str(out_fc)


def _resolve_field_name(feature_class: str | os.PathLike[str], candidate_name: str) -> str | None:
    """Resolve a field name case-insensitively in a feature class."""
    candidates = {fld.name.lower(): fld.name for fld in arcpy.ListFields(str(feature_class))}
    return candidates.get(candidate_name.lower())


def _normalize_field_token(field_name: str) -> str:
    """Normalize field names for resilient schema matching."""
    return re.sub(r"[^a-z0-9]", "", field_name.lower())


def _resolve_flood_zone_field(
    feature_class: str | os.PathLike[str],
    preferred_name: str,
) -> str:
    """Resolve the flood-zone field with sensible fallbacks and clear diagnostics."""
    preferred = _resolve_field_name(feature_class, preferred_name)
    if preferred is not None:
        return preferred

    # Common FEMA schema variants observed in county datasets.
    fallback_names = ["FloodZoneType", "FloodZoneCode", "FLD_ZONE"]
    for fallback in fallback_names:
        resolved = _resolve_field_name(feature_class, fallback)
        if resolved is not None:
            logger.warning(
                "Configured flood-zone field '%s' was not found in '%s'; using '%s' instead.",
                preferred_name,
                feature_class,
                resolved,
            )
            return resolved

    fields = [fld.name for fld in arcpy.ListFields(str(feature_class))]
    raise ValueError(
        f"Flood zone field '{preferred_name}' was not found in '{feature_class}'. "
        f"Available fields: {fields}."
    )


def _resolve_join_output_field(
    feature_class: str | os.PathLike[str],
    source_field_name: str,
) -> str | None:
    """Resolve a joined output field even when ArcGIS appends numeric suffixes."""
    direct = _resolve_field_name(feature_class, source_field_name)
    if direct is not None:
        return direct

    target_token = _normalize_field_token(source_field_name)
    matches: list[str] = []
    for fld in arcpy.ListFields(str(feature_class)):
        base_name = re.sub(r"_\d+$", "", fld.name)
        if _normalize_field_token(base_name) == target_token:
            matches.append(fld.name)

    if not matches:
        return None

    # Prefer unsuffixed names, then shortest deterministic candidate.
    matches = sorted(matches, key=lambda name: (0 if not re.search(r"_\d+$", name) else 1, len(name), name))
    return matches[0]


def parcels_affected_by_flood_zones(
    parcels_fc: str | os.PathLike[str],
    flood_zones_fc: str | os.PathLike[str],
    out_fc: str | os.PathLike[str],
    working_wkid: int,
    flood_zone_field: str,
) -> tuple[str, str]:
    """Create an output of parcels intersecting flood zones.

    Uses a one-to-many spatial join so a parcel can appear multiple times when it
    intersects multiple flood-zone polygons.

    Returns:
        tuple[str, str]: ``(output_feature_class_path, resolved_flood_zone_field)``.
    """
    _ensure_projected(parcels_fc, working_wkid)
    _ensure_projected(flood_zones_fc, working_wkid)

    resolved_source_zone_field = _resolve_flood_zone_field(
        flood_zones_fc,
        flood_zone_field,
    )

    with arcpy.EnvManager(overwriteOutput=True):
        arcpy.analysis.SpatialJoin(
            target_features=str(parcels_fc),
            join_features=str(flood_zones_fc),
            out_feature_class=str(out_fc),
            join_operation="JOIN_ONE_TO_MANY",
            join_type="KEEP_COMMON",
            match_option="INTERSECT",
        )

    resolved_zone_field = _resolve_join_output_field(out_fc, resolved_source_zone_field)
    if resolved_zone_field is None:
        available_fields = [fld.name for fld in arcpy.ListFields(str(out_fc))]
        raise ValueError(
            f"Flood zone field '{flood_zone_field}' (resolved source field '{resolved_source_zone_field}') "
            f"was not found in joined output '{out_fc}'. Available fields: {available_fields}."
        )

    return str(out_fc), resolved_zone_field


def _feature_class_to_dataframe(feature_class: str | os.PathLike[str]) -> pd.DataFrame:
    """Load a feature class into a DataFrame using all non-geometry fields."""
    fields = [
        fld.name
        for fld in arcpy.ListFields(str(feature_class))
        if fld.type not in {"Geometry", "Raster", "Blob"}
    ]
    if not fields:
        return pd.DataFrame()

    rows = [row for row in arcpy.da.SearchCursor(str(feature_class), fields)]
    return pd.DataFrame(rows, columns=fields)


def summarize_flood_impacts(
    affected_parcels_fc: str | os.PathLike[str],
    flood_zone_field: str,
    value_field: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build summary and detail tables for affected parcels.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: ``(summary_df, affected_parcels_df)``
    """
    details_df = _feature_class_to_dataframe(affected_parcels_fc)
    if details_df.empty:
        summary_df = pd.DataFrame(
            columns=["flood_zone_type", "affected_parcel_count", "potential_dollar_amount"]
        )
        return summary_df, details_df

    zone_field = _resolve_field_name(affected_parcels_fc, flood_zone_field)
    if zone_field is None:
        raise ValueError(f"Flood zone field '{flood_zone_field}' not found in affected parcels output.")

    details_df[zone_field] = details_df[zone_field].fillna("UNKNOWN").astype(str)

    summary_df = (
        details_df.groupby(zone_field, dropna=False)
        .size()
        .reset_index(name="affected_parcel_count")
        .rename(columns={zone_field: "flood_zone_type"})
    )

    resolved_value_field = _resolve_field_name(affected_parcels_fc, value_field)
    if resolved_value_field is not None:
        numeric_value = pd.to_numeric(details_df[resolved_value_field], errors="coerce")
        dollar_df = (
            pd.DataFrame({"flood_zone_type": details_df[zone_field], "_value": numeric_value})
            .groupby("flood_zone_type", dropna=False)["_value"]
            .sum(min_count=1)
            .reset_index()
            .rename(columns={"_value": "potential_dollar_amount"})
        )
        summary_df = summary_df.merge(dollar_df, on="flood_zone_type", how="left")
    else:
        summary_df["potential_dollar_amount"] = pd.NA

    summary_df = summary_df.sort_values(by="affected_parcel_count", ascending=False).reset_index(drop=True)
    return summary_df, details_df


def export_flood_impact_report(
    summary_df: pd.DataFrame,
    affected_parcels_df: pd.DataFrame,
    out_path: str | os.PathLike[str],
) -> str:
    """Write a two-sheet workbook with summary and affected parcel details."""
    output_path = Path(out_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary_by_zone", index=False)
        affected_parcels_df.to_excel(writer, sheet_name="affected_parcels", index=False)

    logger.info(f"Wrote flood impact report to '{output_path}'.")
    return str(output_path)
