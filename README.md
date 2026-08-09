# Librescoot Valhalla Tiles

Routing tiles for Librescoot's offline navigation, generated from OpenStreetMap data using [Valhalla](https://github.com/valhalla/valhalla). Configured for motor vehicle routing with speed data from [OpenStreetMapSpeeds](https://github.com/OpenStreetMapSpeeds/schema).

Part of the [Librescoot](https://librescoot.org/) open-source platform.

## Generated Files

Monthly CI builds produce one `.tar` file per region. German states use per-state extracts; Benelux uses country-level extracts; France is added at region granularity (just Île-de-France for now); Italy uses Geofabrik's macro-area extracts (Nord-Ovest covers Lombardy plus Piedmont, Liguria and Aosta Valley — Geofabrik offers no per-regione extracts). Berlin and Brandenburg are combined into a single package — the Geofabrik Brandenburg extract is a superset of Berlin, so feeding both files to `valhalla_build_tiles` would produce duplicate edges.

| Region | Approx. Size |
|--------|-------------|
| `valhalla_tiles_baden-wuerttemberg.tar` | 485 MB |
| `valhalla_tiles_bayern.tar` | 725 MB |
| `valhalla_tiles_belgium.tar` | 364 MB |
| `valhalla_tiles_berlin_brandenburg.tar` | 202 MB |
| `valhalla_tiles_bremen.tar` | 13 MB |
| `valhalla_tiles_hamburg.tar` | 30 MB |
| `valhalla_tiles_hessen.tar` | 247 MB |
| `valhalla_tiles_ile-de-france.tar` | 167 MB |
| `valhalla_tiles_italy-nord-ovest.tar` | 419 MB |
| `valhalla_tiles_luxembourg.tar` | 27 MB |
| `valhalla_tiles_mecklenburg-vorpommern.tar` | 79 MB |
| `valhalla_tiles_netherlands.tar` | 546 MB |
| `valhalla_tiles_niedersachsen.tar` | 353 MB |
| `valhalla_tiles_nordrhein-westfalen.tar` | 514 MB |
| `valhalla_tiles_rheinland-pfalz.tar` | 206 MB |
| `valhalla_tiles_saarland.tar` | 31 MB |
| `valhalla_tiles_sachsen-anhalt.tar` | 107 MB |
| `valhalla_tiles_sachsen.tar` | 192 MB |
| `valhalla_tiles_schleswig-holstein.tar` | 106 MB |
| `valhalla_tiles_thueringen.tar` | 117 MB |

Sizes are decimal MB from the 2026-08-09 release and vary between builds as OSM data changes.

Admin boundaries come from a tiny `admin-overlays/west-europe.osm.pbf` (~10 KB of country-level L2 polygons for DE/FR/NL/BE/LU/IT) rather than a shared admin SQLite built from the full `germany-latest.osm.pbf`. Admin attributes are baked per-edge during `valhalla_build_tiles`, so the source admin DB isn't needed at runtime and never ships inside a regional `.tar`.

## Installation

Download the `.tar` for your region from the [latest release](../../releases/tag/latest) and extract it to `/data/valhalla/` on the DBC — either via USB update mode or directly via the [data-server](https://github.com/librescoot/data-server) HTTP API.

```bash
tar -xf valhalla_tiles_berlin_brandenburg.tar -C /data/valhalla/
```

## Local Development

```bash
# Download a regional OSM extract
wget https://download.geofabrik.de/europe/germany/brandenburg-latest.osm.pbf

# Fetch community speed data
wget https://raw.githubusercontent.com/OpenStreetMapSpeeds/schema/master/default_speeds.json

# Build Valhalla config (motor vehicle only)
docker run --rm -v "$(pwd):/work" -w /work \
  ghcr.io/valhalla/valhalla:3.6.3 \
  valhalla_build_config \
    --mjolnir-include-bicycle false \
    --mjolnir-include-pedestrian false \
    --mjolnir-default-speeds-config default_speeds.json \
  > valhalla.json

# Bake a per-node timezone so date_time routing can evaluate time-conditional
# restrictions (see "Timezones" below). Brandenburg is Europe/Berlin.
docker run --rm -v "$(pwd):/work" -w /work ghcr.io/valhalla/valhalla:3.6.3 \
  spatialite /work/timezones.sqlite "CREATE TABLE tz_world (id INTEGER PRIMARY KEY AUTOINCREMENT, TZID TEXT);
    SELECT AddGeometryColumn('tz_world','geom',4326,'MULTIPOLYGON',2);
    INSERT INTO tz_world (TZID, geom) VALUES ('Europe/Berlin', CastToMulti(GeomFromText('POLYGON((-12 34,-12 60,30 60,30 34,-12 34))',4326)));
    SELECT CreateSpatialIndex('tz_world','geom');"
python3 -c "import json; c=json.load(open('valhalla.json')); c['mjolnir']['timezone']='/work/timezones.sqlite'; json.dump(c, open('valhalla.json','w'), indent=2)"

# Classify cobbles as their own surface (see "Surfaces" below).
wget -q -O upstream-graph.lua \
  https://raw.githubusercontent.com/valhalla/valhalla/3.6.3/lua/graph.lua
cat upstream-graph.lua lua/librescoot-surface.lua > graph-librescoot.lua
python3 -c "import json; c=json.load(open('valhalla.json')); c['mjolnir']['graph_lua_name']='/work/graph-librescoot.lua'; json.dump(c, open('valhalla.json','w'), indent=2)"

# Build tiles. The synthetic admin overlay provides the L2 country relation
# Valhalla needs for drive_on_right and country defaults — regional Geofabrik
# extracts don't carry it. See admin-overlays/README.md for details.
docker run --rm -v "$(pwd):/work" -w /work \
  ghcr.io/valhalla/valhalla:3.6.3 bash -c "
    valhalla_build_admins -c valhalla.json admin-overlays/west-europe.osm.pbf brandenburg-latest.osm.pbf
    valhalla_build_tiles -c valhalla.json brandenburg-latest.osm.pbf
    valhalla_assign_speeds -c valhalla.json
    valhalla_build_extract -c valhalla.json
  "
```

Output lands in `/data/valhalla/tiles.tar` by default.

Test changes on a small region (Bremen at 13 MB, Luxembourg at 27 MB) before running the full set.

### Admin Overlay

`admin-overlays/west-europe.osm.pbf` is a tiny (~10 KB) synthetic PBF carrying L2 country polygons for DE/FR/NL/BE/LU/IT with the right `ISO3166-1` codes. Passed to `valhalla_build_admins` alongside any regional PBF, it gives Valhalla the country attribution it needs without downloading the full country PBF (5 GB for Germany, 1.5 GB for France).

Regenerate via `tools/build-admin-overlay.py` (requires `osmium-tool`). Country borders move ~never, so refresh only when adding a new country or doing a clean-room verification.

### Timezones

Valhalla bakes a timezone into each node at build time and uses it to evaluate
time-conditional restrictions (`*:conditional` access, timed turn restrictions)
when a `date_time` is supplied at route time. Without it, `node.administrative.time_zone_name`
is empty and those restrictions are ignored.

The upstream `valhalla_build_timezones` downloads the full timezone-boundary
database. We don't need it: every regional extract sits in exactly one IANA zone,
so the build generates a one-polygon `tz_world` sqlite (a West-Europe box tagged
with the region's zone) and points `mjolnir.timezone` at it. The region → zone map
lives in the workflow:

| Region | Zone |
|--------|------|
| German states | `Europe/Berlin` |
| Netherlands | `Europe/Amsterdam` |
| Belgium | `Europe/Brussels` |
| Luxembourg | `Europe/Luxembourg` |
| Île-de-France | `Europe/Paris` |
| Italy Nord-Ovest | `Europe/Rome` |

All six share the CET/CEST offset and EU DST rules, so restriction evaluation is
identical across them; the distinct IANA names are kept for correctness. Adding a
region in another zone (or one that straddles a tz boundary) means extending the
map — or, for a straddling region, falling back to the real `valhalla_build_timezones`.

Note: Valhalla canonicalizes some TZIDs through its internal tz database, so a
Luxembourg node reports `Europe/Brussels` rather than `Europe/Luxembourg`. That's
cosmetic — both are CET/CEST with identical DST, so the baked offset and DST
transitions (which is all restriction evaluation uses) are correct either way.

## Automated Builds

GitHub Actions generates routing tiles for all 20 regions monthly on the 1st ([workflow](.github/workflows/generate-tiles.yml)). Each region runs in parallel on a self-hosted runner using the official Valhalla Docker image. Results are published as a GitHub release tagged `latest`.

Manual trigger: Actions → "Automatic Tile Generation and Release - Germany + Benelux + France + Italy" → Run workflow.

## Technical Details

- **Format**: Valhalla tile archive (`.tar` of the binary tile graph)
- **Routing profiles**: motor vehicle only (bicycle and pedestrian disabled)
- **Speed data**: [OpenStreetMapSpeeds](https://github.com/OpenStreetMapSpeeds/schema) community defaults applied via `valhalla_assign_speeds`
- **Admin boundaries**: built from `admin-overlays/west-europe.osm.pbf` (L2 country) + regional PBF (L4/L6/L8 sub-national)
- **Timezones**: per-node, from a one-polygon `tz_world` overlay tagged with the region's IANA zone (see Timezones above)
- **Source**: [Geofabrik](https://download.geofabrik.de/europe/) regional extracts of [OpenStreetMap](https://www.openstreetmap.org)
- **Surfaces**: `lua/librescoot-surface.lua` (see below)
- **Generator**: [Valhalla](https://github.com/valhalla/valhalla) 3.6.3

## Surfaces

Valhalla's tile format has eight surface classes and no free slot, so these tiles
reserve one. `lua/librescoot-surface.lua` is appended to upstream `lua/graph.lua`
and fed to `valhalla_build_tiles` through `mjolnir.graph_lua_name`. It wraps
`ways_proc` rather than patching it, so a Valhalla bump needs a fresh `graph.lua`
rather than a rebased diff.

What it changes:

- `sett`, `cobblestone`, `unhewn_cobblestone`, `cobblestone:flattened`,
  `paving_stones` and `grass_paver` all become `paved_rough`. Upstream puts sett
  and paving stones in the same class as asphalt, which makes most German
  Kopfsteinpflaster invisible to routing: 258 of the 939 surface-tagged streets
  around Boxhagener Platz are tagged `sett`.
- With no `surface` tag, `smoothness=intermediate` and `tracktype=grade1` become
  `compacted` instead of `paved_rough`. Neither describes stone, and the OSM wiki
  gives "the best unpaved but compacted roads" as its own example for
  `intermediate`.

So in these tiles `paved_rough` means irregular stone and `compacted` means
smooth but unpaved, which lets a costing weigh them separately. Small wheels care
about the difference. Nothing else in the graph changes.

## License

Generated tiles contain OpenStreetMap data under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).

This project is dual-licensed. The source code is available under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].
The maintainers reserve the right to grant separate licenses for commercial distribution; please contact the maintainers to discuss commercial licensing.

