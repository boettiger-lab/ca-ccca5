# Plant Heat Exposure Explorer (config only)

A no-LLM explorer served at `/explorer/`, beside the map-and-chat app at `/`. Pick a species and
set three controls: a leaf thermal threshold (the species' Tcrit or T50), a leaf-to-air offset and
a climate period. The panel then shows how much of the species' range lies above the resulting air
threshold, and the map colours the range by that share.

The app is configuration, SQL and a few small generated files. The machinery comes from
[glen-charts](https://github.com/SchmidtDSE/glen-charts), pinned in `index.html` (v0.2.4). Do not
write JavaScript here: features go into glen-charts.

## Status

This explorer uses the interim measure from `system-prompt.md`. The measure it is designed for, the
mean number of days a year above the threshold, needs the LOCA2 exceedance curves
([data-workflows#669](https://github.com/boettiger-lab/data-workflows/issues/669)). Until those
exist, each range cell is compared on CHELSA 2.1 `bio5`, the mean daily maximum of the warmest month,
so every share is a lower bound.

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
| `{{PERIOD}}` | Climate period | `obs` (1981–2010), `ssp370-mid` (2041–2070), `ssp370-end` and `ssp585-end` (2071–2100) |

The air threshold is `TLEAF − OFFSET`. Every query runs live on the MCP server, since 18 × 16 × 4
parameter combinations are too many to precompute; a species takes a few seconds.

## Themes

| Theme | Contents |
|---|---|
| `exposure` | Share and area of the range above the threshold in the chosen period, the air threshold and the largest margin; bars by period (whole range and recorded cells), by margin class and by offset; the map |
| `models` | The future shares recomputed with each cell's lowest, median and highest bio5 across the five CHELSA models |

The range is every cell present in the Calflora hex for the species, zeros included. Shares are by
area over the range cells that CHELSA covers, and numerator and denominator always use the same
cells.

**Edit `scripts/build-sql.py`, not the `.sql` files.** Every query starts with the same two CTEs
(range cells joined to the four CHELSA periods), and the script writes them once:

```bash
python3 explorer/scripts/build-sql.py
```

## Generated files

| File | Built by |
|---|---|
| `data/species-ranges.pmtiles` | `scripts/build-map-tiles.sh`: one outline per species, the union of its H3 res-6 cells, used to outline the selected species |
| `data/h6-grid.pmtiles` | the same script: every res-6 cell holding part of any range, keyed by `h6`, which the map colours |
| `data/lists/species.json` | `node <glen-charts>/scripts/precompute.mjs --site explorer lists` |
| `data/sources.json` | the same, with `sources`; the Calflora assets have no STAC record in the public catalog, by design (licence) |

The two PMTiles are derived from the published range hex and are served from the site. They belong
in `s3://public-ca-ccca5/` with the range collection when the next data-workflows pass touches it.

## Local preview

The PMTiles need HTTP range requests, which `python -m http.server` does not serve. Any static
server that does (nginx, `npx http-server`) works; then open `/explorer/` from the repository root.

## Next steps

- **Tcrit / T50 switch.** When #673 lands, replace the `tleaf` slider with a `metric` param
  (`Tcrit`, `T50`) and read the value from `thermal-tolerance/species.parquet` in the CTE. With two
  metrics and 16 offsets, all 32 combinations can be precomputed for all 109 species, which also
  allows a leaderboard tab ranking species by exposed share.
- **Days above threshold.** When the LOCA2 curves land, swap the CHELSA CTE for the exceedance-curve
  table, interpolating between grid thresholds, and report mean days a year.
