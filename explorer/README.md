# Plant Heat Exposure Explorer (config only)

A no-LLM explorer served at `/explorer/`, beside the map-and-chat app at `/`. Pick a species and
set the heat tolerance (Tcrit or T50), the leaf threshold, a leaf-to-air offset and a climate
period. The leaf threshold slider starts at the team's measured value for the species and can be
moved 5 °C either way. The panel then shows how many days a year the daily maximum air temperature
reaches the resulting air threshold across the species' range, and how much of the range lies in
30x30 conserved areas. The map colours the range by either, on H3 resolution 6 when zoomed out and
the resolution-7 LOCA2 grid from zoom 7 in, and can shade the conserved areas by GAP status. A link with no `#…` opens on *Pinus ponderosa* (`default_area`).

The app is configuration, SQL and a few small generated files. The machinery comes from
[glen-charts](https://github.com/SchmidtDSE/glen-charts), pinned in `index.html` (v0.2.7; 0.2.5 added `default_area` and `tracts.line_width`, 0.2.6 grids that swap by zoom, 0.2.7 a search box that lists every species when one is already chosen, 0.2.8 sliders relative to an area's own value). Do not
write JavaScript here: features go into glen-charts.

## Status

The climate data is the LOCA2-Hybrid exceedance table from
[data-workflows#669](https://github.com/boettiger-lab/data-workflows/issues/669), phase 1: three
models (GFDL-ESM4, MPI-ESM1-2-HR, ACCESS-CM2) and SSP3-7.0 only. The paths in `scripts/build-sql.py` are the
catalog's (`loca2-hybrid-tasmax-exceedance`, `loca2-hybrid-tasmax-annual-max`). Add SSP2-4.5 and
SSP5-8.5 to `PERIODS` when phase 2 lands.

Tcrit and T50 come from the project team's table, committed at
`../data/species_T50_Tcrit_means.csv` and read from its raw GitHub URL. It lives with the app rather
than in the data catalog; DATA-PLAN.md section C gives the reason. The values are provisional
pre-publication means with no reported spread, and the page says so.

The offset defaults to 10 °C because glen-charts needs a default for every param. It is not a
recommendation: the offset range is still an open question for the partner (DATA-PLAN.md,
question 4).

## Controls and tokens

| Token | Control | Values |
|---|---|---|
| `{{ID}}` | species search box | six-letter Calflora code, from `data/lists/species.json` |
| `{{METRIC}}` | Heat tolerance | `tcrit` or `t50`, looked up for the species |
| `{{ADJUST}}` | Leaf threshold in °C | an offset from the team's value, −5 to +5 in steps of 0.5, default 0. The slider is labelled in absolute degrees (glen-charts `relative` param, base from `exposure/base.sql`); the Tcrit against T50 chart ignores it |
| `{{OFFSET}}` | Leaf-to-air offset in °C | 0 to 15 in steps of 1 |
| `{{PERIOD}}` | Climate period | `hist` (1985–2014), `ssp370-mid` (2040–2069), `ssp370-end` (2070–2099) |

The air threshold is the species' Tcrit or T50, plus `ADJUST`, minus `OFFSET`. It rarely falls on the exceedance
table's 0.5 °C grid, so each cell's day count is interpolated linearly between the two grid rows
around it, and a threshold outside 20–60 °C gives no value rather than an extrapolation. Every query
runs live on the MCP server; a species takes a few seconds.

## Themes

| Theme | Contents |
|---|---|
| `exposure` | The leaf and air thresholds; mean days a year at or above the threshold over the range, the share of the range with at least one and with ten or more days, and the largest margin of the mean annual maximum over the threshold; bars by period (whole range and recorded cells), Tcrit against T50, by class of days and by offset; the map |
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
| `data/h7-grid.pmtiles` | `scripts/build-map-tiles.sh`: every H3 res-7 cell holding part of any range, keyed by `h7`, drawn from zoom 7 in. Res 7 is the LOCA2 grid, the finest the day counts have. The species boundary points at the same tiles with a filter that matches nothing, since overlapping range outlines made the hover name the wrong species |
| `data/h6-grid.pmtiles` | the same script: their res-6 parents, keyed by `h6`, drawn below zoom 7, where res-7 cells are a pixel wide and slow to draw. The `map-h6.sql` queries average the res-7 values into them by area |
| `data/lists/species.json` | `node <glen-charts>/scripts/precompute.mjs --site explorer lists` |
| `data/sources.json` | the same, with `sources`; the Calflora assets have no STAC record in the public catalog, by design (licence) |

The PMTiles files are derived from the published range hex and are served from the site. They belong
in `s3://public-ca-ccca5/` with the range collection when the next data-workflows pass touches it.

## Local preview

The PMTiles need HTTP range requests, which `python -m http.server` does not serve. Any static
server that does (nginx, `npx http-server`) works; then open `/explorer/` from the repository root.

## Next steps

- **Leaderboard.** With two metrics, 16 offsets and three periods, the per-species results are few
  enough to precompute for all 109 species, which would allow a tab ranking species by exposure.

