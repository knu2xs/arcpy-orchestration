"""Useful utility functions for arcpy_orchestration."""

from ._logging import get_logger

# set up module-level logger
logger = get_logger("arcpy_orchestration.utils", level="DEBUG", add_stream_handler=False)
