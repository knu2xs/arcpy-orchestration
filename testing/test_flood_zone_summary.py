"""Tests for flood-zone summary data preparation helpers."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

DIR_TEST = Path(__file__).parent
DIR_PRJ = DIR_TEST.parent
DIR_SRC = DIR_PRJ / "src"
sys.path.insert(0, str(DIR_SRC))

from arcpy_orchestration import flood_zone_summary


def test_download_feature_service_refreshes_empty_existing_feature_class(
    monkeypatch,
) -> None:
    """An existing zero-row feature class should be deleted and downloaded again."""
    deleted_paths: list[str] = []
    exported_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(flood_zone_summary.arcpy, "Exists", lambda path: path == "raw.gdb/flood_zones")
    monkeypatch.setattr(
        flood_zone_summary.arcpy,
        "management",
        SimpleNamespace(
            GetCount=lambda path: ["0"],
            Delete=lambda path: deleted_paths.append(path),
        ),
    )
    monkeypatch.setattr(
        flood_zone_summary.arcpy,
        "conversion",
        SimpleNamespace(
            ExportFeatures=lambda in_features, out_features: exported_calls.append(
                (in_features, out_features)
            )
        ),
    )

    output_path = flood_zone_summary._download_feature_service(
        service_url="https://example.test/FeatureServer/0",
        out_gdb="raw.gdb",
        out_name="flood_zones",
    )

    assert output_path == "raw.gdb/flood_zones"
    assert deleted_paths == ["raw.gdb/flood_zones"]
    assert exported_calls == [
        ("https://example.test/FeatureServer/0", "raw.gdb/flood_zones")
    ]


def test_download_feature_service_falls_back_to_api_when_export_fails(
    monkeypatch,
) -> None:
    """A direct ArcPy export failure should fall back to the API query downloader."""
    api_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(flood_zone_summary.arcpy, "Exists", lambda path: False)
    monkeypatch.setattr(
        flood_zone_summary.arcpy,
        "conversion",
        SimpleNamespace(
            ExportFeatures=lambda in_features, out_features: (_ for _ in ()).throw(
                RuntimeError("server export failed")
            )
        ),
    )
    monkeypatch.setattr(
        flood_zone_summary,
        "_download_feature_service_via_api",
        lambda service_url, out_fc: api_calls.append((service_url, out_fc)) or out_fc,
    )

    output_path = flood_zone_summary._download_feature_service(
        service_url="https://example.test/FeatureServer/0",
        out_gdb="raw.gdb",
        out_name="flood_zones",
    )

    assert output_path == "raw.gdb/flood_zones"
    assert api_calls == [("https://example.test/FeatureServer/0", "raw.gdb/flood_zones")]