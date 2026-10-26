# Plant Heat Exposure Explorer (config only)

A no-LLM explorer served at `/explorer/`, beside the map-and-chat app at `/`. Pick a species and
set three controls: a leaf thermal threshold (the species' Tcrit or T50), a leaf-to-air offset and
a climate period. The panel then shows how many days a year the daily maximum air temperature
reaches the resulting air threshold across the species' range, and how much of the range lies in
30x30 conserved areas. The map colours the range by either, on the H3 resolution-7 LOCA2 grid, and
can outline the conserved areas. A link with no `#…` opens on *Pinus ponderosa* (`default_area`).

The app is configuration, SQL and a few small generated files. The machinery comes from
[glen-charts](https://github.com/SchmidtDSE/glen-charts), pinned in `index.html` (v0.2.5, which added `default_area` and `tracts.line_width`). Do not
write JavaScript here: features go into glen-charts.

## Status

The climate data is the LOCA2-Hybrid exceedance table from
[data-workflows#669](https://github.com/boettiger-lab/data-workflows/issues/669), phase 1: three
models (GFDL-ESM4, MPI-ESM1-2-HR, ACCESS-CM2) and SSP3-7.0 only. The paths in `scripts/build-sql.py` are the
catalog's (`loca2-hybrid-tasmax-exceedance`, `loca2-hybrid-tasmax-annual-max`). Add SSP2-4.5 and
SSP5-8.5 to `PERIODS` when phase 2 lands.

The leaf threshold is a slider the reader sets, because the team's Tcrit and T50 table
([data-workflows#673](https://github.com/boettiger-lab/data-workflows/issues/673)) is not
published yet. Once it is, the slider becomes a Tcrit / T50 switch read from that table (see
*Next steps*).

The offset defaults to 10 °C and the leaf threshold to 47 °C, because glen-charts needs a default
for every param. Neither is a recommendation: the offset range is still an open question for the
partner (DATA-PLAN.md, question 4).

## Controls and tokens

| Token | Control | Values |
|---|---|---|
| `{{ID}}` | species search box | six-letter Calflora code, from `data/lists/species.json` |
| `{{TLEAF}}` | Leaf threshold in °C | 40 to 57 in steps of 1 |
| `{{OFFSET}}` | Leaf-to-air offset in °C | 0 to 15 in steps of 1 |
| `{{PERIOD}}` | Climate period | `hist` (1985–2014), `ssp370-mid` (2040–2069), `ssp370-end` (2070–2099) |

The air threshold is `TLEAF − OFFSET`. Both are whole degrees, so it always lands on the
exceedance table's 0.5 °C grid and is read exactly, with no interpolation. Every query runs live on
the MCP server, since 18 × 16 × 3 parameter combinations are too many to precompute; a species
takes a few seconds.

## Themes

| Theme | Contents |
|---|---|
| `exposure` | Mean days a year at or above the threshold over the range, the share of the range with at least one and with ten or more days, and the largest margin of the mean annual maximum over the threshold; bars by period (whole range and recorded cells), by class of days and by offset; the map |
| `conserved` | Share of the whole range in each GAP status (30x30 terrestrial conserved areas, 2025, `hex-weights-res8`), and mean days above the threshold on GAP 1–2 land against the rest of the range; a map of each cell's GAP 1–2 share |
| `models` | The mean days recomputed with each cell's lowest, mean and highest of the three models |

The range is every cell present in the Calflora hex for the species, zeros included. Each range
cell (H3 resolution 8) takes the value of the LOCA2 cell (resolution 7) that contains it. A missing
exceedance row means zero days, as the table suppresses zeros. Means and shares are weighted by
area over the range cells inside the LOCA2 domain (98.8% of range res-7 cells; the domain ends near
29.6°N, so some Baja California cells drop out), and numerator and denominator always use the same
cells.

**Edit `scripts/build-sql.py`, not the `.sql` files.** Every query starts with the same two CTEs
(range cells joined to the LOCA2 exceedance and annual-maximum tables), and the script writes them once:

```bash
python3 explorer/scripts/build-sql.py
```

## Generated files

| File | Built by |
|---|---|
| `data/h7-grid.pmtiles` | `scripts/build-map-tiles.sh`: every H3 res-7 cell holding part of any range, keyed by `h7`, which the map colours. Res 7 is the LOCA2 grid, the finest the day counts have. The species boundary points at the same tiles with a filter that matches nothing, since overlapping range outlines made the hover name the wrong species |
| `data/lists/species.json` | `node <glen-charts>/scripts/precompute.mjs --site explorer lists` |
| `data/sources.json` | the same, with `sources`; the Calflora assets have no STAC record in the public catalog, by design (licence) |

The PMTiles file is derived from the published range hex and is served from the site. It belongs
in `s3://public-ca-ccca5/` with the range collection when the next data-workflows pass touches it.

## Local preview

The PMTiles need HTTP range requests, which `python -m http.server` does not serve. Any static
server that does (nginx, `npx http-server`) works; then open `/explorer/` from the repository root.

## Next steps

- **Tcrit / T50 switch.** When #673 lands, replace the `tleaf` slider with a `metric` param
  (`Tcrit`, `T50`) and read the value from `thermal-tolerance/species.parquet` in the CTE. With two
  metrics and 16 offsets, all 32 combinations can be precomputed for all 109 species, which also
  allows a leaderboard tab ranking species by exposed share.
- **Finer thresholds.** A half-degree slider step would still land on the grid. A finer step would
  need linear interpolation between grid rows, never extrapolation past 60 °C.
