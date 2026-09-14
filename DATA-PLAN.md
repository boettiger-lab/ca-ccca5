# Data plan — California plant heat vulnerability

Working notes for the `data-workflows` ingest that has to land before this app can do anything.
Everything here that defines *what a dataset task delivers* (extent, resolution, reducer, bucket,
acceptance criteria) belongs in the GitHub issue on `boettiger-lab/data-workflows` before any
cluster job runs — this file is the draft, not the source of truth.

## What the app has to compute

For a species *s*, a thermal tolerance *T* (Tcrit or T50, a **leaf** temperature), a user-chosen
leaf-to-air offset *Δ*, a scenario and a climate period:

```
effective air threshold  τ = T − Δ
map value(cell)          = mean annual count of days with daily max air temperature > τ
restricted to            cells inside species s's current range
```

Plus summary metrics over the range: share of range with ≥1, ≥5, ≥10 exceedance days/yr, and the
largest amount by which projected temperature exceeds τ.

**τ is continuous and chosen at query time.** That is the design constraint. We cannot precompute
a map per threshold, and we cannot ship daily data to the browser. The resolution is to precompute,
per cell, the **exceedance curve**: mean annual days above τ for τ on a fixed grid. The app
interpolates between grid points. A curve is a complete summary of the daily distribution for this
purpose — nothing is lost except sub-grid threshold precision.

## Three datasets

| # | Dataset | Source | Status |
|---|---|---|---|
| A | Species current ranges | Calflora climate-model GeoTIFF exports, 107 files, in `import-data/` | in hand, needs cleaning |
| B | Daily max air temperature exceedance curves | LOCA2-Hybrid via Cal-Adapt `s3://cadcat/` | public, not yet ingested |
| C | Species thermal tolerance (Tcrit, T50) | Project team measurements, 100+ species | **not received** |

---

## A. Calflora species range rasters

### What is actually in `import-data/SppRange_Project/`

Verified by reading the files directly:

- **107 GeoTIFFs**, one per species, named by six-letter code (3 letters genus + 3 letters species).
- EPSG:4326, Float32, DEFLATE, striped (not tiled), **no `nodata` tag set** — NaN is the fill.
- Pixel ≈ 0.00833° (30 arcsec, ~1/120°); the x-scale varies slightly file to file (0.00829–0.00833),
  so **the rasters are not on a shared grid**. Each is clipped to its own bounding box.
- Values are NaN or integers 0–9. Pooled across all 107 files: 7,525,075 non-NaN pixels, of which
  only **162,396 (2.2%) are greater than zero**.
- `Download_list_SppDist.xlsx` lists 109 species; the protocol document (`Protocol_SppDis_20250627`)
  documents the manual Calflora download procedure — Plant Range → by Climate Model → download as
  GeoTIFF → rename to the species code.

### Defects to resolve before ingest

1. **Three pairs of byte-identical files under different species codes** — the same raster was saved
   twice under two names, so one species in each pair has the wrong data:
   `HESWHI` = `HETARB`, `ATRITOR` = `BACPIL`, `ERIUMB` = `FOUSPL`.
   The extents suggest which member is the impostor (e.g. `ERIUMB.tif` covers 29–36°N / −117 to
   −112°E, a Sonoran desert footprint that fits *Fouquieria splendens*, not montane
   *Eriogonum umbellatum*) — but **do not guess**; ask the team to re-download the three affected
   species.

2. **Two `(1)` duplicate-download files** — `ENCFAR(1).tif` and `ERIUMB(1).tif`. Neither is identical
   to its unsuffixed namesake; they are different downloads with different extents. `ERIUMB(1)` has a
   plausible *E. umbellatum* footprint, which reinforces (1) above. Ask which file is authoritative
   for each; do not ingest a `(1)` filename.

3. **17 files carry a single stray pixel near the equator**, which stretches the declared raster to
   ~5,040–5,055 rows of almost-entirely NaN:
   `ABICON ALNRHO ARCPAT ARCVIS ARTTRI CALDEC CEACOR CEAINT CORNUT PINLAM PINPON PURTRI QUECHR
   QUEKEL RHOOCC RIBCER SEQGIG`.
   Confirmed as a single valid pixel in the bottom row at lat ≈ 0.008°N — the georeference is
   otherwise correct and the real data sits in the California latitudes. The preprocess job drops
   any pixel below 25°N and clips to the remaining valid extent.
   (`ENCFAR(1)` reaches 23.3°N and `JUSCAL` 24.1°N — those may be genuine Baja extent; check before
   clipping them.)

4. **Four species on the list have no file**: `ERIDIS` (marked downloaded), and `HOLDIS`, `QUEGAR`,
   `SEQSEM` (marked not downloaded). `SEQSEM` is coast redwood — a conspicuous omission for this app.

5. **No `nodata` tag.** Set `nodata=nan` explicitly on the output COGs so downstream tools don't
   read NaN as data.

### The unresolved question: what do 0–9 mean, and what counts as "the range"?

The proposal says the map covers "the species' current range". The raster does not carry a range
mask — it carries an ordinal 0–9 score from Calflora's climate model, and 98% of the evaluated
(non-NaN) area scores 0. Taken literally, "score > 0" gives *Quercus agrifolia* about 4,600 pixels
(~3,000 km²), which is far smaller than the species' accepted range.

So one of these is true and we need the team (or Calflora) to say which:

- the score is a suitability rank and the intended range is `score ≥ some cutoff`;
- 0 means "modelled, not suitable" and NaN means "not modelled", so the range is `score > 0` and it
  is genuinely this restrictive;
- the export is at a coarser effective resolution than its pixel grid implies.

**This is the single decision that most changes the app's answers**, because the range is the
denominator for every summary percentage. It must be settled before ingest and written into the
STAC description. The app's system prompt already requires the cutoff be stated in every answer.

### Proposed ingest

- **Bucket:** `s3://public-ca-ccca5/`
- **Stage raw first** (`raw/`), with the access date recorded — these files came from manual Calflora
  downloads on 2025-06-30/07-01 and there is no stable download URL to re-resolve, so our staged copy
  plus its checksum *is* the provenance.
- **Preprocess job:** drop sub-25°N stray pixels, clip to valid extent, set `nodata=nan`, drop the
  `(1)` files and the three impostor duplicates, and write one clean COG per species to
  `calflora-ranges/cog/{CODE}.tif`.
- **Hex:** one long-form table rather than 107 collections —
  `calflora-ranges/hex/h0={cell}/…` with `species_code`, `h8`, `score`.
  - **Native resolution 8** (0.737 km² vs. the ~0.69 km² source pixel — a near 1:1 match), parents
    `7, 0`. Res 7 is the join key to dataset B.
  - **Reducer `mode`.** The value is an ordinal class code, not a density or a measurement; `mean`
    would manufacture fractional scores that mean nothing. Because the hex and pixel sizes are so
    close this is nearly a relabelling either way.
  - Expected size: ~7.5M non-NaN pixel-cells pooled across species, so single-digit millions of rows.
    This is a small dataset.
- **Lookup table:** `calflora-ranges/species.parquet` — `species_code`, `scientific_name`, and the
  Calflora list/URL, built from `Download_list_SppDist.xlsx`.
- **Licence:** Calflora's terms need to be checked and recorded; do not assert an SPDX id until a
  terms page is located. If no grant is locatable, say so plainly in the description.

---

## B. LOCA2 daily-tmax exceedance curves

This is the substantial build and the genuinely new product.

### Source, verified against the bucket

- `s3://cadcat/loca2/ucsd/{model}/{experiment}/{member}/day/tasmax/d03/` — Zarr v2, public,
  no credentials. Catalogued in `s3://cadcat/cae-zarr.csv`.
- Grid `d03`: **495 lat × 559 lon** on a regular **1/32° (0.03125°)** lat-lon grid — decoded from
  the coordinate arrays, not assumed. Domain **29.578–45.016 °N, −128.422 to −110.984 °E** (California
  plus Nevada, the margins of Oregon/Idaho/Utah/Arizona, offshore Pacific, and northern Baja).
  ≈3.5 km N–S × 2.8 km E–W at California latitudes, ≈9.6 km² per cell. `float32`, units **Kelvin**,
  chunked `1952 × 123 × 139`.
- The stores' root `.zattrs` are inherited CMIP6 parent-GCM attributes: `nominal_resolution` says
  `250 km` and `grid` names the GCM's native N96 grid. Those describe the parent model, not the
  downscaled product — do not propagate them.
- `historical`: 23,741 days from 1950-01-01 (1950–2014). `ssp*`: 31,411 days from 2015-01-01
  (2015–2100). Calendar `proleptic_gregorian`, leap days included.
- 199 daily-tasmax stores across 15 GCMs and `historical / ssp245 / ssp370 / ssp585`.
- **Licence: CC-BY-4.0** (stated in `cadcat_s3bucket_readme.txt`; CMIP6-derived).
- Produced by UC San Diego Scripps for California's Fifth Climate Change Assessment — the product
  the State asked research teams to use, which is what the partner requested.

### Proposed scope

Built in two phases, so the pipeline is proven before the full ensemble runs.

**Phase 1 — pilot.** Three GCMs at `r1i1p1f1`, `historical` + `ssp370` only:
**GFDL-ESM4**, **MPI-ESM1-2-HR**, **ACCESS-CM2** — chosen to span low, middle and high
equilibrium climate sensitivity so the pilot shows real across-model spread rather than three
near-identical fields. 6 stores, ~270 model-years. Deliverable is a publishable collection with
`n_models = 3`, plus a validation check against Cal-Adapt's own figures.

**Phase 2 — full ensemble** (separate issue, opened once the pilot validates). The 12 GCMs that
carry all four experiments at a single member, one member each:
ACCESS-CM2, CNRM-ESM2-1, EC-Earth3, EC-Earth3-Veg, FGOALS-g3, GFDL-ESM4, INM-CM5-0, IPSL-CM6A-LR,
KACE-1-0-G, MIROC6, MPI-ESM1-2-HR, MRI-ESM2-0 — across `ssp245`, `ssp370` and `ssp585`.
(CESM2-LENS, TaiESM1 and HadGEM3-GC31-LL lack full scenario coverage and are excluded, so every
scenario comparison uses an identical model set.)

- **Scenarios:** phase 1 `ssp370` (the State's primary); phase 2 adds `ssp245` and `ssp585`.
  The historical baseline is built in both.
- **Periods:** baseline **1985–2014** (the historical run ends in 2014, so a 1991–2020 baseline is
  not available from it); **mid-century 2040–2069**; **end-century 2070–2099**. A near-term
  2015–2044 window is cheap to add in the same pass if wanted.
- **Threshold grid:** **20.0–60.0 °C in 0.5 °C steps** (81 values), stored in Celsius. Covers every
  plausible `Tcrit − Δ` and `T50 − Δ` with room to spare; the app refuses to extrapolate past the
  ends.
- **Extent:** California land plus a margin, not the whole `d03` domain — the app is a California
  tool and the domain is considerably larger. Record the exact mask used.

### Computation

One job per (model, scenario). Stream the Zarr along time; for each daily field convert K→°C, bin
into the 0.5 °C grid, and accumulate a per-period integer histogram of shape
`(81, 495, 559)` (90 MB as int32 — memory is a non-issue). The exceedance curve is the reverse
cumulative sum of that histogram, divided by the number of years. In the same pass accumulate the
annual maximum per cell, which gives the "maximum exceedance above threshold" metric for free.

Cost is network, not compute. Phase 1 is ~270 model-years over 6 jobs (~110 GB decompressed);
phase 2 is roughly 2,500 model-years, ~1 TB decompressed, spread over 48 jobs. Reads are from AWS `us-west-2` over `https://`, so this
does **not** follow the usual "stage raw to NRP first" pattern — the raw is 199 Zarr stores we have
no reason to copy. Stage the *derived* histograms to NRP instead.

### Published product

- `s3://public-caladapt/loca2-hybrid/tasmax-exceedance/`
- **Hex, native resolution 7** (5.16 km² vs. the ≈9.6 km² source pixel), parents `6, 0`.
  Res 7 is the finest resolution the 3 km source supports without inventing detail, and it is a
  parent of the res-8 species grid, so the join in A is exact. **This collection cannot carry `h8`** —
  state that in the hex asset description so nobody reads it as broken.
- Row: `h7, scenario, period, threshold_c, days_mean, days_min, days_max, n_models` — the ensemble
  mean plus across-model spread, so the app can report robustness. Suppress all-zero rows.
  Order-of-magnitude: ~82k California res-7 cells × 81 thresholds × 7 scenario-periods ≈ 46M rows
  before zero-suppression. Sub-gigabyte parquet.
- Companion small table `…/annual-max/`: `h7, scenario, period, tmax_mean_annual_max_c,
  tmax_max_c` (~600k rows).
- Per-model curves are retained on S3 as intermediates but not published as a collection unless
  someone asks for them.
- Use `--row-group-size 2000` per the repo's serialization standard.

This is a derived product with a custom reduction, not a plain raster ingest, so it does not fit
`cng-datasets raster-workflow` directly — model it on the custom pipeline in
`catalog/bioclimate/` (the CHELSA scripts), with a `catalog/caladapt/scripts/` of its own.

---

## C. Thermal tolerance table

Not received. The proposal says it was attached to the email; it is not in `import-data/`.

Needed shape: one row per species — `species_code`, `scientific_name`, `tcrit_c`, `t50_c`, and
whatever the team can give on sample size, population/site, and method. The app treats these as
**defaults only**: users can enter their own values, which the proposal explicitly asks for.

The partner says these are unpublished until the manuscript is submitted but that they intend to
share them publicly, and that no login wall is needed. If we publish them before there is any public
terms page, that is the "data contributed directly to us" case: publish a `LICENSE.md` beside the
data that records what was and was not granted, and link it from the STAC.

**Confirm the publication timing with the team before anything goes in a public bucket.**

---

## Order of work

1. Settle the range-definition question (A) and get the corrected/missing rasters. The build is
   not blocked on it — the raw 0-9 score is stored and the cutoff is applied at query time — but
   the STAC description is.
2. ~~File the data-workflows issues~~ — filed:
   [data-workflows#668](https://github.com/boettiger-lab/data-workflows/issues/668) (A, Calflora
   ranges) and [data-workflows#669](https://github.com/boettiger-lab/data-workflows/issues/669)
   (B phase 1, the 3-model ssp370 pilot). **Those issues are the source of truth for scope** — if
   this file and an issue disagree, the issue wins.
3. Build B phase 1 (3-model pilot) and validate it; A is small and can run alongside. Open the
   phase-2 issue only once the pilot's numbers check out.
4. Get C, then wire `layers-input.json` and finish `system-prompt.md` against the real collection
   and column names from `list_datasets` / `get_schema`.

## Open questions for the partner

1. What do the Calflora 0–9 values mean, and what defines "within the species' current range"?
2. `HESWHI`/`HETARB`, `ATRITOR`/`BACPIL`, `ERIUMB`/`FOUSPL` are byte-identical pairs — which of each
   pair needs re-downloading? And which of `ENCFAR` / `ENCFAR(1)` and `ERIUMB` / `ERIUMB(1)` is
   authoritative?
3. Can we get `ERIDIS`, `HOLDIS`, `QUEGAR` and `SEQSEM` (coast redwood)?
4. Could you send the Tcrit / T50 table, and confirm when it may be published?
5. What leaf-to-air offset range should the control span, and what default (if any)? Georgia was
   named as the person to advise.
6. Scenarios and periods: does SSP2-4.5 / SSP3-7.0 / SSP5-8.5 with 1985–2014, 2040–2069 and
   2070–2099 windows match what the assessment used?
7. The mockup mentioned in the email did not come through — can you resend it?
