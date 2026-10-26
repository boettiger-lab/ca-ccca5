#!/usr/bin/env bash
# Builds explorer/data/{h6,h7}-grid.pmtiles from the published range hex.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build data
rm -f build/*.geojson
duckdb < scripts/build-map-tiles.sql
# every cell keeps its own polygon and id at every zoom, or the low-zoom colours are lost
tippecanoe -q -f -o data/h7-grid.pmtiles -l h7-grid -Z4 -z10 --no-feature-limit --no-tile-size-limit --no-tiny-polygon-reduction build/h7-grid.geojson
tippecanoe -q -f -o data/h6-grid.pmtiles -l h6-grid -Z2 -z9 --no-feature-limit --no-tile-size-limit --no-tiny-polygon-reduction build/h6-grid.geojson
rm -rf build
ls -l data/*.pmtiles
