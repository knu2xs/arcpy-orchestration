"""Main module for arcpy_orchestration package."""
# imports from the standard Python library
# from pathlib import Path

# third-party package imports
# import arcgis

# relative imports from other modules in the package, if needed
from .utils import get_logger

# configure module logging, the same logger as the package-level logger
logger = get_logger("arcpy_orchestration", level="DEBUG", add_stream_handler=False)

# primary location for any functions or classes that are intended to be imported 
# directly from the package root (e.g. `from arcpy_orchestration import example_function`), 
# which is mostly what I do. If you have a lot of code, you can also create submodules and 
# import from those in `__init__.py` as needed to keep this file clean and focused on the 
# public API.
    