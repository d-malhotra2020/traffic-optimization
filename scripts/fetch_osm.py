#!/usr/bin/env python3
"""
Refetch signalized intersections for the configured bounding box from
OpenStreetMap via the Overpass API and overwrite data/sf_intersections.json.

Why this exists as a script rather than a startup fetch:
- Honest dependency surface: the dashboard works offline against a
  committed snapshot. We don't depend on Overpass being reachable at
  Railway boot.
- Reproducibility: anyone can re-run this to update the snapshot,
  and the snapshot has a clear provenance trail (timestamp, generator,
  query, license).

Usage:
    python -m scripts.fetch_osm

Outputs:
    data/sf_intersections.json   — committed snapshot

License of fetched data: ODbL — © OpenStreetMap contributors.
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "drewmalhotra-portfolio/1.0 (https://drewmalhotra.com)"

# Downtown San Francisco — financial district + SoMa + Embarcadero.
# Roughly Powell/Market east to Embarcadero, and Brannan St north to Broadway.
BBOX = {
    "south": 37.7700,
    "west": -122.4250,
    "north": 37.8050,
    "east": -122.3900,
    "description": "Downtown San Francisco — financial district + SoMa + Embarcadero",
}

QUERY_TEMPLATE = (
    '[out:json][timeout:25];'
    'node["highway"="traffic_signals"]({south},{west},{north},{east});'
    'out body;'
)


def fetch_overpass(query: str, timeout: int = 60) -> dict:
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_ENDPOINT,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_snapshot(raw: dict, query: str) -> dict:
    nodes = [e for e in raw.get("elements", []) if e.get("type") == "node"]
    clean = [
        {
            "id": f"osm_{n['id']}",
            "osm_node_id": n["id"],
            "lat": n["lat"],
            "lon": n["lon"],
            "kind": (n.get("tags") or {}).get("traffic_signals", "traffic_signals"),
        }
        for n in nodes
    ]
    return {
        "source": "OpenStreetMap via Overpass API",
        "license": "ODbL — © OpenStreetMap contributors",
        "overpass_generator": raw.get("generator"),
        "osm_timestamp": (raw.get("osm3s") or {}).get("timestamp_osm_base"),
        "bbox": BBOX,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "intersection_count": len(clean),
        "intersections": clean,
    }


def main() -> int:
    query = QUERY_TEMPLATE.format(**BBOX)
    print(f"→ Querying Overpass for traffic_signals in {BBOX['description']}…")
    raw = fetch_overpass(query)
    snapshot = build_snapshot(raw, query)

    out_path = Path(__file__).resolve().parent.parent / "data" / "sf_intersections.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2))

    print(f"✓ Wrote {out_path.relative_to(out_path.parent.parent)}")
    print(f"  intersections : {snapshot['intersection_count']}")
    print(f"  bbox          : {BBOX['description']}")
    print(f"  osm_timestamp : {snapshot['osm_timestamp']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
