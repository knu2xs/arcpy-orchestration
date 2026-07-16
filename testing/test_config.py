"""Tests for configuration and secrets loading behavior."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import warnings

import pytest

# Ensure local src/ package is importable when tests run from repo root.
DIR_TEST = Path(__file__).parent
DIR_PRJ = DIR_TEST.parent
DIR_SRC = DIR_PRJ / "src"
sys.path.insert(0, str(DIR_SRC))

import arcpy_orchestration.config as config_module


def test_confignode_missing_key_error_is_descriptive() -> None:
    """Undefined keys should raise with path and available key context."""
    cfg = config_module.ConfigNode(
        data={"alpha": 1, "nested": {"beta": 2}},
        node_path="config",
    )

    with pytest.raises(AttributeError) as exc_info:
        _ = cfg.missing_key

    msg = str(exc_info.value)
    assert "Undefined configuration key 'config.missing_key'" in msg
    assert "Available keys at 'config': alpha, nested" in msg


def test_nested_confignode_missing_key_reports_nested_path() -> None:
    """Nested missing-key errors should include full dotted path context."""
    cfg = config_module.ConfigNode(
        data={"orchestration": {"prefect": {"api_url": "http://127.0.0.1:4200/api"}}},
        node_path="config",
    )

    with pytest.raises(AttributeError) as exc_info:
        _ = cfg.orchestration.prefect.not_a_real_key

    msg = str(exc_info.value)
    assert "Undefined configuration key 'config.orchestration.prefect.not_a_real_key'" in msg
    assert "Available keys at 'config.orchestration.prefect': api_url" in msg


def test_empty_secrets_confignode_missing_key_includes_secrets_hint() -> None:
    """Missing keys on empty secrets should suggest adding a secrets file."""
    secrets = config_module.ConfigNode(node_path="secrets")

    with pytest.raises(AttributeError) as exc_info:
        _ = secrets.esri

    msg = str(exc_info.value)
    assert "Undefined configuration key 'secrets.esri'" in msg
    assert "Secrets are currently empty" in msg
    assert "config/secrets.yml or config/secrets.yaml" in msg


def test_load_secrets_uses_yaml_when_yml_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_secrets should fall back to secrets.yaml if secrets.yml is absent."""
    (tmp_path / "secrets.yaml").write_text(
        "esri:\n  gis_url: 'https://example.com'\n  gis_profile: 'test_profile'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)

    secrets = config_module.load_secrets()

    assert secrets.esri.gis_url == "https://example.com"
    assert secrets.esri.gis_profile == "test_profile"


def test_load_secrets_prefers_yml_when_both_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_secrets should prefer secrets.yml when both YAML file names exist."""
    (tmp_path / "secrets.yml").write_text(
        "esri:\n  gis_profile: 'from_yml'\n",
        encoding="utf-8",
    )
    (tmp_path / "secrets.yaml").write_text(
        "esri:\n  gis_profile: 'from_yaml'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)

    secrets = config_module.load_secrets()

    assert secrets.esri.gis_profile == "from_yml"


def test_module_import_warns_when_no_secrets_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Import-time initialization should warn (not crash) when no secrets file exists."""
    module_path = Path(config_module.__file__).resolve()
    original_exists = Path.exists

    def _exists_without_secrets(self: Path) -> bool:
        if self.name in {"secrets.yml", "secrets.yaml"}:
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", _exists_without_secrets)

    spec = importlib.util.spec_from_file_location("_config_missing_secrets_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spec.loader.exec_module(module)

    messages = [str(w.message) for w in caught]
    assert any(
        "Neither config/secrets.yml nor config/secrets.yaml was found." in message
        for message in messages
    )
