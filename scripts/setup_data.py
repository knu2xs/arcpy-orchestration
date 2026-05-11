"""
Download the Thurston County, WA parcels and parks reference datasets from the
Thurston GeoData Center into the project's ``data/raw/raw.gdb`` so the
park-access example pipeline has real inputs to work against.

Sources:

- Parcels — https://gisdata-thurston.opendata.arcgis.com/datasets/thurston::thurston-parcels/about
  Service: https://tconline.co.thurston.wa.us/server/rest/services/Common_Layers/Parcels/FeatureServer/4
- Parks — https://gisdata-thurston.opendata.arcgis.com/datasets/thurston::thurston-parks/about
  Service: https://map.co.thurston.wa.us/arcgis/rest/services/Thurston/Thurston_Parks/FeatureServer/0

Run from the project root:

```text
python scripts/setup_data.py
```

!!! note
    The Thurston parcels layer has ~130k features so the download can take
    several minutes. ``arcpy.conversion.ExportFeatures`` handles pagination
    against the feature service automatically.

!!! warning
    The real field names in the source services almost certainly do not match
    the placeholder ``neighborhood_field`` / ``value_field`` values in
    ``config/config.yml``. After running this script, inspect the output
    feature classes (e.g. in ArcGIS Pro) and update the ``park_access``
    section of ``config/config.yml`` to reference real field names before
    running the pipeline.
"""
# import core Python libraries
from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import sys

# path to the root of the project
DIR_PRJ = Path(__file__).parent.parent

# if the project package is not installed in the environment, add the source directory to the system path
if importlib.util.find_spec("arcpy_orchestration") is None:

    # get the relative path to where the source directory is located
    src_dir = DIR_PRJ / "src"

    # throw an error if the source directory cannot be located
    if not src_dir.exists():
        raise EnvironmentError("Unable to import arcpy_orchestration.")

    # add the source directory to the paths searched when importing
    sys.path.insert(0, str(src_dir))

# Importing the package configures the package-level logger.
import arcpy_orchestration  # noqa: F401, E402
from arcpy_orchestration.utils import get_logger  # noqa: E402

# Source feature service URLs
PARCELS_URL = (
    "https://tconline.co.thurston.wa.us/server/rest/services/"
    "Common_Layers/Parcels/FeatureServer/4"
)
PARKS_URL = (
    "https://map.co.thurston.wa.us/arcgis/rest/services/"
    "Thurston/Thurston_Parks/FeatureServer/0"
)

# Local destinations — must match values in config/config.yml under park_access
RAW_GDB = DIR_PRJ / "data" / "raw" / "raw.gdb"
PARCELS_FC_NAME = "parcels"
PARKS_FC_NAME = "parks"


def _ensure_raw_gdb(gdb_path: Path, logger) -> str:
    """Create ``raw.gdb`` if it does not already exist and return its path."""
    import arcpy

    if arcpy.Exists(str(gdb_path)):
        logger.debug(f"Raw file geodatabase already exists at '{gdb_path}'.")
        return str(gdb_path)

    gdb_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Creating raw file geodatabase at '{gdb_path}'.")
    arcpy.management.CreateFileGDB(
        out_folder_path=str(gdb_path.parent),
        out_name=gdb_path.name,
    )
    return str(gdb_path)


def _download_feature_service(
    service_url: str,
    out_gdb: str,
    out_name: str,
    logger,
) -> str:
    """
    Copy a feature service layer into the local file geodatabase.

    Args:
        service_url: Fully qualified URL to a feature service layer.
        out_gdb: Path to the destination file geodatabase.
        out_name: Output feature class name.
        logger: Configured ``logging.Logger`` instance.

    Returns:
        str: Full path to the output feature class.
    """
    import arcpy

    out_fc = f"{out_gdb}/{out_name}"
    if arcpy.Exists(out_fc):
        logger.warning(
            f"Output '{out_fc}' already exists; deleting before re-download."
        )
        arcpy.management.Delete(out_fc)

    logger.info(f"Downloading '{service_url}' to '{out_fc}'.")
    try:
        arcpy.conversion.ExportFeatures(
            in_features=service_url,
            out_features=out_fc,
        )
    except Exception as e:
        msg = f"Failed to export features from '{service_url}': {e}"
        logger.error(msg)
        raise RuntimeError(msg) from e

    feature_count = int(arcpy.management.GetCount(out_fc)[0])
    logger.info(f"Wrote {feature_count:,} features to '{out_fc}'.")
    return out_fc


if __name__ == "__main__":

    # set up a script-level logger writing to both console and a timestamped logfile
    date_string = datetime.now().strftime("%Y%m%dT%H%M%S")
    log_dir = DIR_PRJ / "reports" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{Path(__file__).stem}_{date_string}.log"

    logger = get_logger(
        level="INFO",
        add_stream_handler=True,
        logfile_path=log_file,
    )

    logger.info(f"Starting Thurston County data download into '{RAW_GDB}'.")

    # late import so logger setup errors surface clearly first
    import arcpy

    # don't allow ArcPy to silently overwrite outputs without going through our delete path
    arcpy.env.overwriteOutput = False

    gdb_path = _ensure_raw_gdb(RAW_GDB, logger)

    _download_feature_service(PARCELS_URL, gdb_path, PARCELS_FC_NAME, logger)
    _download_feature_service(PARKS_URL, gdb_path, PARKS_FC_NAME, logger)

    logger.info("Thurston County data download complete.")
