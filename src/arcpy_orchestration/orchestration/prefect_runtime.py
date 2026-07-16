from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from arcpy_orchestration.config import PROJECT_ROOT, ConfigNode, config
from arcpy_orchestration.utils import get_logger

logger = get_logger(__name__, level="DEBUG", add_stream_handler=False)

_SQLITE_PREFIX = "sqlite+aiosqlite:///"
_REQUIRED_PREFECT_KEYS = (
    "home_path",
    "api_database_connection_url",
    "local_storage_path",
    "results_persist_by_default",
    "api_url",
)
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _logger_name_to_env_token(logger_name: str) -> str:
    """Convert logger names to PREFECT_LOGGING_LOGGERS_<TOKEN>_LEVEL token form."""
    token = re.sub(r"[^A-Za-z0-9]+", "_", logger_name.strip()).strip("_")
    return token.upper()


def _normalize_extra_loggers(raw_value: str, fallback: str = "") -> str:
    """Normalize extra logger list and drop child loggers when parent namespace is present."""
    names: list[str] = []
    seen: set[str] = set()

    for token in raw_value.split(","):
        name = token.strip()
        if not name:
            continue

        key = name.lower()
        if key == "prefect":
            continue
        if key in seen:
            continue

        seen.add(key)
        names.append(name)

    if not names:
        return fallback

    lower_names = [name.lower() for name in names]
    keep: list[str] = []
    for idx, name in enumerate(names):
        current = lower_names[idx]
        has_parent = any(
            idx != parent_idx and current.startswith(f"{parent}." )
            for parent_idx, parent in enumerate(lower_names)
        )
        if not has_parent:
            keep.append(name)

    return ",".join(keep) if keep else fallback


@dataclass(frozen=True)
class PrefectRuntimeConfig:
    """Runtime-resolved Prefect configuration.

    Attributes:
        home_path: Normalized project-local Prefect home directory.
        api_database_connection_url: Normalized SQLite metadata URL.
        api_database_path: Resolved SQLite database file path.
        local_storage_path: Normalized project-local result storage directory.
        results_persist_by_default: Default Prefect result persistence flag.
        api_url: Prefect API URL.
        worker_type: Local worker type.
        work_pool_name: Local Prefect work pool name.
        logging_to_api_enabled: Whether Prefect logs are sent to the API/UI.
        logging_level: Logging level for Prefect logger hierarchy.
        logging_extra_loggers: Comma-delimited non-Prefect logger names to route through Prefect logging.
    """

    home_path: Path
    api_database_connection_url: str
    api_database_path: Path
    local_storage_path: Path
    results_persist_by_default: bool
    api_url: str
    worker_type: str
    work_pool_name: str
    logging_to_api_enabled: bool
    logging_level: str
    logging_extra_loggers: str

    def to_prefect_env(self) -> dict[str, str]:
        """Map runtime configuration to required PREFECT_* environment variables."""
        env_map = {
            "PREFECT_HOME": str(self.home_path),
            "PREFECT_API_DATABASE_CONNECTION_URL": self.api_database_connection_url,
            "PREFECT_LOCAL_STORAGE_PATH": str(self.local_storage_path),
            "PREFECT_RESULTS_PERSIST_BY_DEFAULT": str(self.results_persist_by_default).lower(),
            "PREFECT_API_URL": self.api_url,
            "PREFECT_LOGGING_TO_API_ENABLED": str(self.logging_to_api_enabled).lower(),
            "PREFECT_LOGGING_LEVEL": self.logging_level,
            "PREFECT_LOGGING_LOGGERS_PREFECT_LEVEL": self.logging_level,
            "PREFECT_LOGGING_EXTRA_LOGGERS": self.logging_extra_loggers,
        }

        for logger_name in filter(None, self.logging_extra_loggers.split(",")):
            token = _logger_name_to_env_token(logger_name)
            if not token:
                continue
            env_map[f"PREFECT_LOGGING_LOGGERS_{token}_LEVEL"] = self.logging_level

        return env_map


def _coerce_bool(value: Any, key_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in {"true", "1", "yes", "y"}:
            return True
        if val in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"Expected boolean value for '{key_name}', got: {value!r}")


def _get_prefect_node(config_node: ConfigNode) -> ConfigNode:
    try:
        node = config_node.orchestration.prefect
    except AttributeError as exc:
        raise ValueError(
            "Missing required 'orchestration.prefect' settings in config.yml."
        ) from exc

    missing = [
        key
        for key in _REQUIRED_PREFECT_KEYS
        if not hasattr(node, key) or getattr(node, key) in (None, "")
    ]
    if missing:
        raise ValueError(
            "Missing required Prefect config keys under 'orchestration.prefect': "
            + ", ".join(missing)
        )
    return node


def _normalize_repo_local_path(path_value: str, field_name: str, project_root: Path) -> Path:
    candidate = Path(path_value)
    normalized = (project_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        normalized.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"'{field_name}' must resolve inside the project root. Resolved path: {normalized}"
        ) from exc
    return normalized


def _parse_sqlite_path(raw: str) -> Path:
    # Handles both '/D:/path.db' and 'D:/path.db' URL payload variants on Windows.
    if re.match(r"^/[A-Za-z]:/", raw):
        return Path(raw[1:])
    return Path(raw)


def _normalize_sqlite_url(url: str, project_root: Path) -> tuple[str, Path]:
    if not url.startswith(_SQLITE_PREFIX):
        raise ValueError(
            "'api_database_connection_url' must use 'sqlite+aiosqlite:///' for local mode."
        )

    raw_db_path = url[len(_SQLITE_PREFIX) :]
    if raw_db_path.strip() == "":
        raise ValueError("'api_database_connection_url' is missing a database file path.")

    parsed = _parse_sqlite_path(raw_db_path)
    db_path = (project_root / parsed).resolve() if not parsed.is_absolute() else parsed.resolve()

    try:
        db_path.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(
            "'api_database_connection_url' must resolve to a SQLite file inside the project root. "
            f"Resolved path: {db_path}"
        ) from exc

    normalized_url = f"{_SQLITE_PREFIX}{db_path.as_posix()}"
    return normalized_url, db_path


def resolve_prefect_runtime_config(
    config_node: ConfigNode | None = None,
    project_root: Path | None = None,
) -> PrefectRuntimeConfig:
    """Resolve and validate Prefect runtime settings from project configuration."""
    cfg = config_node or config
    root = (project_root or PROJECT_ROOT).resolve()

    prefect_node = _get_prefect_node(cfg)

    home_path = _normalize_repo_local_path(prefect_node.home_path, "home_path", root)
    local_storage_path = _normalize_repo_local_path(
        prefect_node.local_storage_path, "local_storage_path", root
    )
    api_database_connection_url, api_database_path = _normalize_sqlite_url(
        prefect_node.api_database_connection_url,
        root,
    )

    logging_level = str(getattr(prefect_node, "logging_level", "INFO")).upper()
    if logging_level not in _VALID_LOG_LEVELS:
        raise ValueError(
            "Invalid Prefect logging level under 'orchestration.prefect.logging_level'. "
            f"Expected one of {sorted(_VALID_LOG_LEVELS)}, got: {logging_level!r}."
        )

    if not str(prefect_node.api_url).startswith(("http://", "https://")):
        raise ValueError("'api_url' must start with 'http://' or 'https://'.")

    return PrefectRuntimeConfig(
        home_path=home_path,
        api_database_connection_url=api_database_connection_url,
        api_database_path=api_database_path,
        local_storage_path=local_storage_path,
        results_persist_by_default=_coerce_bool(
            prefect_node.results_persist_by_default,
            "results_persist_by_default",
        ),
        api_url=str(prefect_node.api_url),
        worker_type=str(getattr(prefect_node, "worker_type", "process")),
        work_pool_name=str(getattr(prefect_node, "work_pool_name", "local-process-pool")),
        logging_to_api_enabled=_coerce_bool(
            getattr(prefect_node, "logging_to_api_enabled", True),
            "logging_to_api_enabled",
        ),
        logging_level=logging_level,
        logging_extra_loggers=_normalize_extra_loggers(
            str(
            getattr(
                prefect_node,
                "logging_extra_loggers",
                "arcpy_orchestration",
            )
            )
        ),
    )


def render_effective_runtime_settings(runtime_config: PrefectRuntimeConfig) -> str:
    """Render resolved runtime settings for setup diagnostics."""
    env = runtime_config.to_prefect_env()
    lines = ["Resolved Prefect runtime settings:"]
    for key in sorted(env):
        lines.append(f"- {key}={env[key]}")
    lines.append(f"- PREFECT_WORKER_TYPE={runtime_config.worker_type}")
    lines.append(f"- PREFECT_WORK_POOL_NAME={runtime_config.work_pool_name}")
    return "\n".join(lines)


def assert_sqlite_health(runtime_config: PrefectRuntimeConfig) -> None:
    """Fail fast if SQLite metadata is locked or corrupted."""
    import sqlite3

    db_path = runtime_config.api_database_path
    if not db_path.exists():
        return

    try:
        with sqlite3.connect(str(db_path)) as connection:
            row = connection.execute("PRAGMA quick_check;").fetchone()
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "locked" in msg:
            raise RuntimeError(
                "Prefect metadata database is locked. Stop other Prefect processes and retry. "
                f"Database path: {db_path}"
            ) from exc
        raise RuntimeError(
            "Unable to read Prefect metadata database. "
            f"Database path: {db_path}. Error: {exc}"
        ) from exc
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(
            "Prefect metadata database failed integrity check. "
            f"Database path: {db_path}. Run recovery by backing up and recreating the database."
        ) from exc

    if not row or row[0] != "ok":
        raise RuntimeError(
            "Prefect metadata database failed integrity check. "
            f"Database path: {db_path}. Run recovery by backing up and recreating the database."
        )
