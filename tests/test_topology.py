"""
Tests for the committed OSM topology snapshot + the loader path.

Catches regressions where the snapshot becomes malformed, the loader
silently produces zero intersections, or the bbox provenance gets
lost. None of these tests hit Overpass — the snapshot is committed.
"""

from __future__ import annotations

import json

from src.models.traffic_system import SF_INTERSECTIONS_SNAPSHOT, TrafficSystemManager


def test_snapshot_file_exists_and_parses():
    raw = json.loads(SF_INTERSECTIONS_SNAPSHOT.read_text())
    assert raw["source"].startswith("OpenStreetMap")
    assert "license" in raw and "ODbL" in raw["license"]
    assert isinstance(raw["intersections"], list)
    assert raw["intersection_count"] == len(raw["intersections"])


def test_snapshot_contains_real_sf_coords():
    """Every intersection should be inside the SF bbox + ≥100 nodes."""
    raw = json.loads(SF_INTERSECTIONS_SNAPSHOT.read_text())
    bbox = raw["bbox"]
    assert raw["intersection_count"] >= 100, "downtown SF should have ≥100 signals"
    for n in raw["intersections"]:
        assert bbox["south"] <= n["lat"] <= bbox["north"], f"lat out of bbox: {n}"
        assert bbox["west"] <= n["lon"] <= bbox["east"], f"lon out of bbox: {n}"
        assert n["id"].startswith("osm_")


def test_loader_populates_traffic_system_manager():
    """TrafficSystemManager._load_real_intersections should populate from snapshot."""
    mgr = TrafficSystemManager()
    ok = mgr._load_real_intersections()
    assert ok is True
    assert len(mgr.intersections) >= 100
    # Each loaded intersection should have a real lat/lng
    sample = next(iter(mgr.intersections.values()))
    assert sample.id.startswith("osm_")
    assert isinstance(sample.location, tuple) and len(sample.location) == 2
    lat, lon = sample.location
    assert 37.7 < lat < 37.81
    assert -122.43 < lon < -122.38


def test_topology_meta_carries_provenance():
    mgr = TrafficSystemManager()
    mgr._load_real_intersections()
    meta = mgr.get_topology_meta()
    assert "source" in meta and meta["source"].startswith("OpenStreetMap")
    assert "license" in meta and "ODbL" in meta["license"]
    assert "osm_timestamp" in meta
    assert meta["loaded_count"] >= 100
