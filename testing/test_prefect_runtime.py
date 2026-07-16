"""Tests for Prefect runtime logging environment mapping."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure local src/ package is importable when tests run from repo root.
DIR_TEST = Path(__file__).parent
DIR_PRJ = DIR_TEST.parent
DIR_SRC = DIR_PRJ / "src"
sys.path.insert(0, str(DIR_SRC))

from arcpy_orchestration.config import ConfigNode
from arcpy_orchestration.orchestration.prefect_runtime import resolve_prefect_runtime_config


def _base_prefect_config() -> ConfigNode:
    return ConfigNode(
        {
            "orchestration": {
                "prefect": {
                    "home_path": "prefect_home",
                    "api_database_connection_url": "sqlite+aiosqlite:///prefect_home/prefect.db",
                    "local_storage_path": "prefect_home/storage",
                    "results_persist_by_default": True,
                    "api_url": "http://127.0.0.1:4200/api",
                }
            }
        },
        node_path="config",
    )


def test_prefect_runtime_env_includes_logging_defaults(tmp_path: Path) -> None:
    """Default runtime resolution should include API logging for the Prefect logger."""
    runtime = resolve_prefect_runtime_config(config_node=_base_prefect_config(), project_root=tmp_path)

    env = runtime.to_prefect_env()
    assert env["PREFECT_LOGGING_TO_API_ENABLED"] == "true"
    assert env["PREFECT_LOGGING_LEVEL"] == "INFO"
    assert env["PREFECT_LOGGING_LOGGERS_PREFECT_LEVEL"] == "INFO"
    assert env["PREFECT_LOGGING_EXTRA_LOGGERS"] == "arcpy_orchestration"
    assert env["PREFECT_LOGGING_LOGGERS_ARCPY_ORCHESTRATION_LEVEL"] == "INFO"
    assert "PREFECT_LOGGING_LOGGERS_ARCPY_ORCHESTRATION_FLOOD_ZONE_SUMMARY_LEVEL" not in env


def test_prefect_runtime_env_honors_logging_overrides(tmp_path: Path) -> None:
    """Configured Prefect logging settings should be reflected in exported env."""
    cfg = _base_prefect_config()
    cfg.orchestration.prefect.logging_to_api_enabled = False
    cfg.orchestration.prefect.logging_level = "DEBUG"
    cfg.orchestration.prefect.logging_extra_loggers = "prefect,my_app"

    runtime = resolve_prefect_runtime_config(config_node=cfg, project_root=tmp_path)

    env = runtime.to_prefect_env()
    assert env["PREFECT_LOGGING_TO_API_ENABLED"] == "false"
    assert env["PREFECT_LOGGING_LEVEL"] == "DEBUG"
    assert env["PREFECT_LOGGING_LOGGERS_PREFECT_LEVEL"] == "DEBUG"
    assert env["PREFECT_LOGGING_EXTRA_LOGGERS"] == "my_app"
    assert env["PREFECT_LOGGING_LOGGERS_MY_APP_LEVEL"] == "DEBUG"


def test_prefect_runtime_env_deduplicates_parent_child_loggers(tmp_path: Path) -> None:
    """When parent and child logger names are configured, keep only parent namespaces."""
    cfg = _base_prefect_config()
    cfg.orchestration.prefect.logging_extra_loggers = (
        "arcpy_orchestration.flood_zone_summary,arcpy_orchestration,prefect"
    )

    runtime = resolve_prefect_runtime_config(config_node=cfg, project_root=tmp_path)

    env = runtime.to_prefect_env()
    assert env["PREFECT_LOGGING_EXTRA_LOGGERS"] == "arcpy_orchestration"
    assert env["PREFECT_LOGGING_LOGGERS_ARCPY_ORCHESTRATION_LEVEL"] == "INFO"
    assert "PREFECT_LOGGING_LOGGERS_ARCPY_ORCHESTRATION_FLOOD_ZONE_SUMMARY_LEVEL" not in env


def test_prefect_runtime_env_omits_prefect_from_extra_loggers(tmp_path: Path) -> None:
    """Prefect should not be re-added via extra loggers because it is already API-logged."""
    cfg = _base_prefect_config()
    cfg.orchestration.prefect.logging_extra_loggers = "prefect"

    runtime = resolve_prefect_runtime_config(config_node=cfg, project_root=tmp_path)

    env = runtime.to_prefect_env()
    assert env["PREFECT_LOGGING_EXTRA_LOGGERS"] == ""
    assert env["PREFECT_LOGGING_LOGGERS_PREFECT_LEVEL"] == "INFO"
    assert not any(
        key.startswith("PREFECT_LOGGING_LOGGERS_") and key.endswith("_LEVEL")
        and key != "PREFECT_LOGGING_LOGGERS_PREFECT_LEVEL"
        for key in env
    )
