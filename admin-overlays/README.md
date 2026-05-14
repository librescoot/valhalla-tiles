# Admin Overlays

Synthetic OSM PBF files containing admin_level=2 country relations for the
countries we generate tiles for. Passed alongside the regional Geofabrik PBF
to `valhalla_build_admins` so Valhalla has the country polygon it needs to
resolve `drive_on_right` and country-specific defaults (motorway speeds,
turn-lane conventions).

Geofabrik state/regional extracts are clipped to the state/region polygon
and don't carry the country admin relation. Without it, Valhalla can't
resolve `drive_on_right` and every roundabout exit comes out as "2nd exit"
regardless of the actual exit count.

## `west-europe.osm.pbf`

Hand-built polygons for DE/FR/NL/BE/LU, generated from Natural Earth 1:50m
country boundaries. ~10 KB total. Each country gets a relation tagged with
the right `ISO3166-1` code; Valhalla reads `drive_on_right=1` and the
country's default speed table from there.

Note: France's relation is named `France métropolitaine`, not `France`.
Valhalla's adminbuilder filters out relations literally named "France"
because the real OSM `France` relation (id 1403916) is the EU-style France
that includes overseas territories — Réunion, Guadeloupe, French Guiana —
and produces a useless globe-spanning polygon. By convention, mainland-only
France uses `France métropolitaine`, so we match.

## Regenerating

```sh
python3 tools/build-admin-overlay.py
```

Requires `osmium-tool` (`apt install osmium-tool`). Country borders change
~never; run this when adding a new country to the overlay or when
refreshing for completeness.
