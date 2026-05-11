__title__ = "arcpy-orchestration"
__version__ = "0.0.0"
__author__ = "Joel McCune (https://github.com/knu2xs)"

__license__ = "Apache 2.0"

__copyright__ = "Copyright 2026 by Joel McCune (https://github.com/knu2xs)"

# add specific imports below if you want to organize your code into modules, which is mostly what I do
from . import config as config
from . import utils
from ._main import example_function, ExampleObject

__all__ = ["config", "example_function", "ExampleObject", "utils"]

# configure package-level logging
# `add_plombery_handler=True` is safe even when Plombery is not installed or no
# pipeline is running — the handler silently discards records in those cases.
logger = utils.get_logger(
    "arcpy_orchestration",
    level="DEBUG",
    add_stream_handler=False,
    add_plombery_handler=True,
)
