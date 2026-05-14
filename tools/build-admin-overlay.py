#!/usr/bin/env python3
"""Build a synthetic admin overlay PBF for valhalla_build_admins.

Fetches Natural Earth 1:50m country boundaries for DE/FR/NL/BE/LU, clips them
to the European bounding box (drops overseas territories), and emits an OSM
PBF containing one admin_level=2 relation per country with the correct
ISO3166-1 codes. Valhalla picks up drive_on_right and country-specific
defaults (motorway speeds, etc.) from those tags.

The output is committed at admin-overlays/west-europe.osm.pbf and passed to
valhalla_build_admins alongside the regional PBF in CI. This replaces the
former approach of downloading germany-latest.osm.pbf (5 GB) to build admins.

Run this only when refreshing the overlay — country borders move ~never.

Usage:
    python3 tools/build-admin-overlay.py

Requires: osmium-tool (apt install osmium-tool).
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path


NATURAL_EARTH_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_50m_admin_0_countries.geojson"
)

# ISO_A2 → admin relation name. Valhalla tags the admin relation with
# ISO3166-1=<code> and looks up drive_on_right + country defaults from there.
#
# France is named "France métropolitaine" rather than "France" because
# Valhalla's adminbuilder explicitly filters out relations named "France" —
# the real OSM `France` relation (id 1403916) is the EU-style France that
# includes overseas territories (Réunion, Guadeloupe, …) and produces a
# globe-spanning polygon that's useless for country attribution. The
# metropolitan-only relation is named "France métropolitaine" by OSM
# convention, so we match.
COUNTRIES = {
    "DE": "Germany",
    "FR": "France métropolitaine",
    "NL": "Netherlands",
    "BE": "Belgium",
    "LU": "Luxembourg",
}

# European bounding box used to strip overseas territories (French Guiana,
# Réunion, the Dutch Caribbean, etc.). Anything whose first vertex is outside
# this box gets dropped.
EUROPE_BBOX = (-15.0, 35.0, 35.0, 65.0)  # min_lon, min_lat, max_lon, max_lat


def fetch_geojson(url):
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def in_europe(lon, lat):
    lo_lon, lo_lat, hi_lon, hi_lat = EUROPE_BBOX
    return lo_lon <= lon <= hi_lon and lo_lat <= lat <= hi_lat


def european_polygons(geom):
    """Return list of polygons (each a list of rings) within Europe."""
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return []
    out = []
    for poly in polys:
        if poly and poly[0] and in_europe(poly[0][0][0], poly[0][0][1]):
            out.append(poly)
    return out


def find_feature(geojson, iso):
    """Natural Earth marks France/Norway/Kosovo with ISO_A2='-99' because of
    historical ISO disputes. ISO_A2_EH ('Extended Hack') fills those in."""
    for f in geojson["features"]:
        props = f["properties"]
        for key in ("ISO_A2", "ISO_A2_EH"):
            if props.get(key) == iso:
                return f
    return None


def xml_escape(s):
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def emit_osm(countries, out_path):
    """countries: list of (iso, name, [polygon, ...]). Writes OSM XML."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<osm version="0.6" generator="librescoot-admin-overlay">',
    ]

    node_id = -1
    way_id = -1
    rel_id = -1
    node_lines = []
    way_lines = []
    rel_lines = []

    for iso, name, polys in countries:
        members = []
        for poly in polys:
            for ring_idx, ring in enumerate(poly):
                role = "outer" if ring_idx == 0 else "inner"
                # GeoJSON rings are closed (last == first). Drop the duplicate;
                # close the way by re-referencing the first node ID at the end.
                coords = ring[:-1] if ring[0] == ring[-1] else ring
                first_id = node_id
                way_nd = []
                for lon, lat in coords:
                    node_lines.append(
                        f'  <node id="{node_id}" lat="{lat:.6f}" '
                        f'lon="{lon:.6f}" version="1"/>'
                    )
                    way_nd.append(node_id)
                    node_id -= 1
                way_nd.append(first_id)
                nds = "".join(f'<nd ref="{nid}"/>' for nid in way_nd)
                way_lines.append(
                    f'  <way id="{way_id}" version="1">{nds}</way>'
                )
                members.append(
                    f'<member type="way" ref="{way_id}" role="{role}"/>'
                )
                way_id -= 1

        tags = (
            '<tag k="type" v="boundary"/>'
            '<tag k="boundary" v="administrative"/>'
            '<tag k="admin_level" v="2"/>'
            f'<tag k="name" v="{xml_escape(name)}"/>'
            f'<tag k="ISO3166-1" v="{iso}"/>'
            f'<tag k="ISO3166-1:alpha2" v="{iso}"/>'
        )
        rel_lines.append(
            f'  <relation id="{rel_id}" version="1">'
            f'{"".join(members)}{tags}</relation>'
        )
        rel_id -= 1

    parts.extend(node_lines)
    parts.extend(way_lines)
    parts.extend(rel_lines)
    parts.append("</osm>")
    out_path.write_text("\n".join(parts) + "\n")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "admin-overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    osm_path = out_dir / "west-europe.osm"
    pbf_path = out_dir / "west-europe.osm.pbf"

    print(f"Fetching {NATURAL_EARTH_URL}")
    gj = fetch_geojson(NATURAL_EARTH_URL)

    countries = []
    for iso, name in COUNTRIES.items():
        feat = find_feature(gj, iso)
        if not feat:
            print(f"  WARN: no feature for {iso}", file=sys.stderr)
            continue
        polys = european_polygons(feat["geometry"])
        if not polys:
            print(f"  WARN: no European polygons for {iso}", file=sys.stderr)
            continue
        nodes = sum(len(ring) for poly in polys for ring in poly)
        print(f"  {iso} {name}: {len(polys)} polygon(s), {nodes} nodes")
        countries.append((iso, name, polys))

    emit_osm(countries, osm_path)
    print(f"Wrote {osm_path}")

    subprocess.run(
        ["osmium", "cat", str(osm_path), "-o", str(pbf_path), "--overwrite"],
        check=True,
    )
    print(f"Wrote {pbf_path} ({pbf_path.stat().st_size} bytes)")

    osm_path.unlink()


if __name__ == "__main__":
    main()
