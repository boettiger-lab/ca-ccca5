#!/usr/bin/env bash
# Builds explorer/data/{h6-grid,species-ranges}.pmtiles from the published range hex.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build data
rm -f build/*.geojson
duckdb < scripts/build-map-tiles.sql
tippecanoe -q -f -o data/h6-grid.pmtiles -l h6-grid -Z2 -z9 --no-feature-limit --no-tile-size-limit build/h6-grid.geojson
tippecanoe -q -f -o data/species-ranges.pmtiles -l species-ranges -Z2 -z9 --no-tile-size-limit build/species-ranges.geojson
rm -rf build
ls -l data/*.pmtiles
