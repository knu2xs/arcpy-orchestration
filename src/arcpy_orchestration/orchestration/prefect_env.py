from __future__ import annotations

import os
from typing import Mapping

from .prefect_runtime import PrefectRuntimeConfig


def build_prefect_environment(runtime_config: PrefectRuntimeConfig) -> dict[str, str]:
    """Build required PREFECT_* environment variables from resolved config."""
    return runtime_config.to_prefect_env()


def export_prefect_environment(
    env_map: Mapping[str, str],
    overwrite: bool = True,
) -> dict[str, str]:
    """Export PREFECT_* values to the current process environment."""
    exported: dict[str, str] = {}
    for key, value in env_map.items():
        if overwrite or key not in os.environ:
            os.environ[key] = str(value)
            exported[key] = str(value)
    return exported
