# Librescoot Valhalla Tiles

Routing tiles for Librescoot's offline navigation, generated from OpenStreetMap data using [Valhalla](https://github.com/valhalla/valhalla). Configured for motor vehicle routing with speed data from [OpenStreetMapSpeeds](https://github.com/OpenStreetMapSpeeds/schema).

Part of the [Librescoot](https://librescoot.org/) open-source platform.

## Generated Files

Monthly CI builds produce one `.tar` file per region. Berlin and Brandenburg are combined into a single package — the Geofabrik Brandenburg extract is a superset of Berlin, so feeding both files to `valhalla_build_tiles` would produce duplicate edges.

| Region | Approx. Size |
|--------|-------------|
| `valhalla_tiles_baden-wuerttemberg.tar` | 450 MB |
| `valhalla_tiles_bayern.tar` | 675 MB |
| `valhalla_tiles_berlin_brandenburg.tar` | 189 MB |
| `valhalla_tiles_bremen.tar` | 12 MB |
| `valhalla_tiles_hamburg.tar` | 28 MB |
| `valhalla_tiles_hessen.tar` | 234 MB |
| `valhalla_tiles_mecklenburg-vorpommern.tar` | 75 MB |
| `valhalla_tiles_niedersachsen.tar` | 323 MB |
| `valhalla_tiles_nordrhein-westfalen.tar` | 484 MB |
| `valhalla_tiles_rheinland-pfalz.tar` | 193 MB |
| `valhalla_tiles_saarland.tar` | 29 MB |
| `valhalla_tiles_sachsen.tar` | 182 MB |
| `valhalla_tiles_sachsen-anhalt.tar` | 98 MB |
| `valhalla_tiles_schleswig-holstein.tar` | 101 MB |
| `valhalla_tiles_thueringen.tar` | 111 MB |

Sizes are from the most recent release and vary slightly between builds as OSM data changes.

## Installation

Download the `.tar` for your region from the [latest release](../../releases/tag/latest) and extract it to `/data/valhalla/` on the DBC — either via USB update mode or directly via the [data-server](https://github.com/librescoot/data-server) HTTP API.

```bash
tar -xf valhalla_tiles_berlin_brandenburg.tar -C /data/valhalla/
```

## Local Development

```bash
# Download a regional OSM extract
wget https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf

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

# Build tiles
docker run --rm -v "$(pwd):/work" -w /work \
  ghcr.io/valhalla/valhalla:3.6.3 bash -c "
    valhalla_build_admins -c valhalla.json berlin-latest.osm.pbf
    valhalla_build_tiles -c valhalla.json berlin-latest.osm.pbf
    valhalla_assign_speeds -c valhalla.json
    valhalla_build_extract -c valhalla.json
  "
```

Output lands in `/data/valhalla/tiles.tar` by default.

Test changes on a small region (Bremen at 12 MB) before running the full set.

## Automated Builds

GitHub Actions generates all state tiles monthly on the 1st ([workflow](.github/workflows/generate-tiles.yml)). Each state runs in parallel on a self-hosted runner using the official Valhalla Docker image. Results are published as a GitHub release tagged `latest`.

Manual trigger: Actions → "Automatic Tile Generation and Release - German States" → Run workflow.

## Technical Details

- **Format**: Valhalla tile archive (`.tar` of the binary tile graph)
- **Routing profiles**: motor vehicle only (bicycle and pedestrian disabled)
- **Speed data**: [OpenStreetMapSpeeds](https://github.com/OpenStreetMapSpeeds/schema) community defaults applied via `valhalla_assign_speeds`
- **Admin boundaries**: built per-region for country/state-level routing rules
- **Source**: [Geofabrik](https://download.geofabrik.de/europe/germany.html) regional extracts of [OpenStreetMap](https://www.openstreetmap.org)
- **Generator**: [Valhalla](https://github.com/valhalla/valhalla) 3.6.3

## License

Generated tiles contain OpenStreetMap data under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).

This project is dual-licensed. The source code is available under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].
The maintainers reserve the right to grant separate licenses for commercial distribution; please contact the maintainers to discuss commercial licensing.

