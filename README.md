# Librescoot Valhalla Tiles

Routing tiles for Librescoot's offline navigation, generated from OpenStreetMap data using [Valhalla](https://github.com/valhalla/valhalla). Configured for motor vehicle routing with speed data from [OpenStreetMapSpeeds](https://github.com/OpenStreetMapSpeeds/schema).

Part of the [Librescoot](https://librescoot.org/) open-source platform.

## Generated Files

Monthly CI builds produce one `.tar` file per region. German states use per-state extracts; Benelux uses country-level extracts; France is added at region granularity (just Île-de-France for now). Berlin and Brandenburg are combined into a single package — the Geofabrik Brandenburg extract is a superset of Berlin, so feeding both files to `valhalla_build_tiles` would produce duplicate edges.

| Region | Approx. Size |
|--------|-------------|
| `valhalla_tiles_baden-wuerttemberg.tar` | 174 MB |
| `valhalla_tiles_bayern.tar` | 257 MB |
| `valhalla_tiles_belgium.tar` | 132 MB |
| `valhalla_tiles_berlin_brandenburg.tar` | 69 MB |
| `valhalla_tiles_bremen.tar` | 4 MB |
| `valhalla_tiles_hamburg.tar` | 10 MB |
| `valhalla_tiles_hessen.tar` | 90 MB |
| `valhalla_tiles_ile-de-france.tar` | 59 MB |
| `valhalla_tiles_luxembourg.tar` | 10 MB |
| `valhalla_tiles_mecklenburg-vorpommern.tar` | 28 MB |
| `valhalla_tiles_netherlands.tar` | 191 MB |
| `valhalla_tiles_niedersachsen.tar` | 123 MB |
| `valhalla_tiles_nordrhein-westfalen.tar` | 183 MB |
| `valhalla_tiles_rheinland-pfalz.tar` | 76 MB |
| `valhalla_tiles_saarland.tar` | 11 MB |
| `valhalla_tiles_sachsen.tar` | 68 MB |
| `valhalla_tiles_sachsen-anhalt.tar` | 39 MB |
| `valhalla_tiles_schleswig-holstein.tar` | 37 MB |
| `valhalla_tiles_thueringen.tar` | 43 MB |

Sizes are from the most recent release and vary slightly between builds as OSM data changes.

German state sizes dropped substantially in the build that landed alongside the Benelux+France expansion. The previous workflow bundled the shared admin SQLite (built from full `germany-latest.osm.pbf`, containing every L4/L6/L8/L9 polygon in Germany) into every state `.tar`. The current workflow uses a tiny `admin-overlays/west-europe.osm.pbf` (~10 KB of country-level L2 polygons for DE/FR/NL/BE/LU) instead — admin attributes are baked per-edge during `valhalla_build_tiles`, so the source admin DB isn't needed at runtime.

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

Test changes on a small region (Bremen at 4 MB, Luxembourg at 10 MB) before running the full set.

### Admin Overlay

`admin-overlays/west-europe.osm.pbf` is a tiny (~10 KB) synthetic PBF carrying L2 country polygons for DE/FR/NL/BE/LU with the right `ISO3166-1` codes. Passed to `valhalla_build_admins` alongside any regional PBF, it gives Valhalla the country attribution it needs without downloading the full country PBF (5 GB for Germany, 1.5 GB for France).

Regenerate via `tools/build-admin-overlay.py` (requires `osmium-tool`). Country borders move ~never, so refresh only when adding a new country or doing a clean-room verification.

## Automated Builds

GitHub Actions generates routing tiles for all 19 regions monthly on the 1st ([workflow](.github/workflows/generate-tiles.yml)). Each region runs in parallel on a self-hosted runner using the official Valhalla Docker image. Results are published as a GitHub release tagged `latest`.

Manual trigger: Actions → "Automatic Tile Generation and Release - Germany + Benelux + France" → Run workflow.

## Technical Details

- **Format**: Valhalla tile archive (`.tar` of the binary tile graph)
- **Routing profiles**: motor vehicle only (bicycle and pedestrian disabled)
- **Speed data**: [OpenStreetMapSpeeds](https://github.com/OpenStreetMapSpeeds/schema) community defaults applied via `valhalla_assign_speeds`
- **Admin boundaries**: built from `admin-overlays/west-europe.osm.pbf` (L2 country) + regional PBF (L4/L6/L8 sub-national)
- **Source**: [Geofabrik](https://download.geofabrik.de/europe/) regional extracts of [OpenStreetMap](https://www.openstreetmap.org)
- **Generator**: [Valhalla](https://github.com/valhalla/valhalla) 3.6.3

## License

Generated tiles contain OpenStreetMap data under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).

This project is dual-licensed. The source code is available under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].
The maintainers reserve the right to grant separate licenses for commercial distribution; please contact the maintainers to discuss commercial licensing.

