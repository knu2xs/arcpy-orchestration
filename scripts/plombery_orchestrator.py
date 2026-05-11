# import core Python libraries
from datetime import datetime
import importlib.util
from pathlib import Path
from random import randint
import sys

# import third-party libraries
from apscheduler.triggers.interval import IntervalTrigger
from plombery import task, get_logger as get_plombery_logger, Trigger, register_pipeline

# path to the root of the project
DIR_PRJ = Path(__file__).parent.parent

# if the project package is not installed in the environment, add the source directory to the system path
if importlib.util.find_spec('arcpy_orchestration') is None:
    
    # get the relative path to where the source directory is located
    src_dir = DIR_PRJ / 'src'

    # throw an error if the source directory cannot be located
    if not src_dir.exists():
        raise EnvironmentError('Unable to import arcpy_orchestration.')

    # add the source directory to the paths searched when importing
    sys.path.insert(0, str(src_dir))

# import arcpy_orchestration
from arcpy_orchestration.utils import get_logger
from arcpy_orchestration.config import LOG_LEVEL, INPUT_DATA, OUTPUT_DATA

# Create Plombery Tasks here using the `@task` decorator. 
# You can have as many tasks as you want in a pipeline and they can be as complex as you need. 
# The only requirement is that they must be decorated with `@task` and that they must be async functions.

@task
async def fetch_raw_sales_data():
    """Fetch latest 50 sales of the day"""

    # using Plombery logger your logs will be stored
    # and accessible on the web UI
    logger = get_plombery_logger()

    logger.debug("Fetching sales data...")

    sales = [
        {
            "price": randint(1, 1000),
            "store_id": randint(1, 10),
            "date": datetime.today(),
            "sku": randint(1, 50),
        }
        for _ in range(50)
    ]

    logger.info("Fetched %s sales data rows", len(sales))

    # Return the results of your task to have it stored
    # and accessible on the web UI
    # If you have other tasks, the output of a task is
    # passed to the following one
    return sales

register_pipeline(
    id="sales_pipeline",
    description="Aggregate sales activity from all stores across the country",
    tasks = [fetch_raw_sales_data],
    triggers = [
        Trigger(
            id="daily",
            name="Daily",
            description="Run the pipeline every day",
            schedule=IntervalTrigger(days=1),
        ),
    ],
)