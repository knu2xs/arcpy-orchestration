from __future__ import annotations

from datetime import datetime
from pathlib import Path
import logging

from arcpy_orchestration.config import PROJECT_ROOT
from arcpy_orchestration.utils import get_logger


def get_orchestration_logger(
    name: str,
    level: str | int = "INFO",
    add_stream_handler: bool = True,
) -> logging.Logger:
    """Create a logger configured for orchestration scripts with file output."""
    log_dir = PROJECT_ROOT / "reports" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logfile = log_dir / f"{name}_{datetime.now().strftime('%Y%m%dT%H%M%S')}.log"
    return get_logger(
        name,
        level=level,
        logfile_path=logfile,
        add_stream_handler=add_stream_handler,
    )
