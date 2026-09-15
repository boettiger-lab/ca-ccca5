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
| A | Species current ranges | Calflora climate-model GeoTIFF exports, 107 files, in `import-data/` | **99 cleaned + published** to `s3://public-ca-ccca5/`; hex build pending |
| B | Daily max air temperature exceedance curves | LOCA2-Hybrid via Cal-Adapt `s3://cadcat/` | public, not yet ingested |
| C | Species thermal tolerance (Tcrit, T50) | Project team measurements, 109 species | **received 2026-09-15**, embargoed until the team's paper publishes |

---

## A. Calflora species range rasters

### What is actually in `import-data/SppRange_Project/`

Verified by reading the files directly:

- **107 GeoTIFFs**, one per species, named by six-letter code (3 letters genus + 3 letters species).
- EPSG:4326, Float32, DEFLATE, striped (not tiled), **no `nodata` tag set** — NaN is the fill.
- Pixel ≈ 0.00833° (30 arcsec, ~1/120°); the x-scale varies slightly file to file (0.00829–0.00833),
  so **the rasters are not on a shared grid**. Each is clipped to its own bounding box.
- Values are NaN or integers 0–9 — **observation counts**, not a suitability rank (see the resolved
  range definition below). Pooled across all 107 files: 7,525,075 non-NaN pixels, of which only
  **162,396 (2.16%) are greater than zero**. The full distribution:

  | value | pixels | share of non-NaN |
  |---|---:|---:|
  | 0 | 7,362,679 | 97.842% |
  | 1 | 115,088 | 1.529% |
  | 2 | 27,847 | 0.370% |
  | 3 | 7,870 | 0.105% |
  | 4 | 4,939 | 0.066% |
  | 5 | 1,966 | 0.026% |
  | 6 | 1,520 | 0.020% |
  | 7 | 822 | 0.011% |
  | 8 | 604 | 0.008% |
  | 9 | 1,740 | 0.023% |

  **9 is a saturating bin, not a count of nine.** The counts fall monotonically from 1 to 8 and then
  jump — 1,740 nines against 604 eights — which is what a "9 or more" clamp looks like, and no file
  anywhere exceeds 9. Treat the top class as censored: the app may say "9 or more observations", never
  "9 observations", and must not average the raw values across cells as if the scale were linear at
  the top. Confirm with Calflora when the team next writes.
- `Download_list_SppDist.xlsx` lists 109 species; the protocol document (`Protocol_SppDis_20250627`)
  documents the manual Calflora download procedure — Plant Range → by Climate Model → download as
  GeoTIFF → rename to the species code.

### Defects — status after the team's 2026-09-15 reply

The team has answered every outstanding question about these files. **The corrected downloads have
not arrived in `import-data/` yet** — the directory still holds the original 107 files including both
`(1)` duplicates, and still has no `ERIDIS`. Nothing below is verified against a new file; chase the
delivery before the preprocess job runs.

1. **Three pairs of byte-identical files** (`HESWHI` = `HETARB`, `ATRITOR` = `BACPIL`,
   `ERIUMB` = `FOUSPL`) — **resolved by re-download.** The team re-pulled all six species rather than
   adjudicating which member of each pair was the impostor, which is the right call. `ATRITOR` was
   also renamed to the correct six-letter code `ATRTOR`. *Awaiting the files.*

2. **Two `(1)` duplicate-download files** (`ENCFAR(1).tif`, `ERIUMB(1).tif`) — **resolved.** The team
   removed both and re-downloaded `ENCFAR` and `ERIUMB`. *Awaiting the files;* until they land, do not
   ingest a `(1)` filename and do not trust the unsuffixed namesakes either.

3. **17 files carry a single stray pixel near the equator**, which stretches the declared raster to
   ~5,040–5,055 rows of almost-entirely NaN:
   `ABICON ALNRHO ARCPAT ARCVIS ARTTRI CALDEC CEACOR CEAINT CORNUT PINLAM PINPON PURTRI QUECHR
   QUEKEL RHOOCC RIBCER SEQGIG`.
   Confirmed as a single valid pixel in the bottom row at lat ≈ 0.008°N — the georeference is
   otherwise correct and the real data sits in the California latitudes. **The team confirmed these
   are artefacts to disregard** and has reported them to Calflora; the Calflora climate model is
   supposed to ignore observations outside California's borders, so the cause is unexplained. The
   preprocess job drops any pixel below 25°N and clips to the remaining valid extent.
   (`ENCFAR(1)` reached 23.3°N and `JUSCAL` reaches 24.1°N — those may be genuine Baja extent; check
   `JUSCAL` before clipping it, and re-check the new `ENCFAR`.)

4. **Four species on the list had no file** — `ERIDIS` **has been added** (*awaiting delivery*).
   `HOLDIS`, `QUEGAR` and `SEQSEM` are **still blocked**: Calflora's export will not generate a
   GeoTIFF for them and the team has filed it as a bug with Calflora. No known reason these three
   differ from the others, so expect them eventually. `SEQSEM` is coast redwood — a conspicuous
   omission, but **do not hold the ingest for it**; publish with the species we have and add the
   remaining three in a later pass.

5. **No `nodata` tag.** Set `nodata=nan` explicitly on the output COGs so downstream tools don't
   read NaN as data.

6. **Species codes are not consistently six letters.** The download list and the raster filenames use
   seven-letter codes for three species where the tolerance table (C) uses the strict 3+3 form:

   | raster / xlsx | tolerance table | species |
   |---|---|---|
   | `ABIBRAC` | `ABIBRA` | *Abies bracteata* |
   | `ATRITOR` | `ATRTOR` | *Atriplex torreyi* |
   | `CLEOARB` | `CLEARB` | *Cleomella arborea* |

   The protocol document and the team's own correction of `ATRITOR` → `ATRTOR` both make the
   **six-letter form canonical**. Normalise filenames through this three-entry map in the preprocess
   job so A and C join cleanly, and carry `scientific_name` in both tables as a check — the codes are
   a convenience, the binomial is the real key.

### Resolved: the values are observation counts, and the range is every non-NaN cell

Calflora's own documentation of these climate-modelled range maps, relayed by the team 2026-09-15:

> If the plant has been observed inside the cell, then the value of the cell is number of
> observations. If the plant has not been observed inside the cell, but the climate factors of the
> cell are within the plant's tolerances, then the value of the cell is 0. Otherwise the value of the
> cell is NaN.

So the field is **not an ordinal suitability score** — it is a count, and the range is defined by the
NaN mask, not by the magnitude:

```
in range   ⟺  value is not NaN            (value ≥ 0)
value > 0  ⟺  observed, and the value is the observation count
value = 0  ⟺  climatically suitable, not observed
NaN        ⟺  outside modelled climatic tolerance
```

The team's reading — "anything that is 0 or higher is part of the plant range, while NaNs are
ignored" — is the definition we use.

**Consequences, and they are large:**

- **The denominator is the non-NaN area, ~45× the `score > 0` area.** Pooled over 107 files there are
  7,525,075 non-NaN pixels and only 162,396 positive ones. Every summary percentage the app reports
  changes by more than an order of magnitude versus the `> 0` reading. The earlier worry that
  *Quercus agrifolia*'s range looked implausibly small was an artefact of that wrong reading; the
  non-NaN footprint is the modelled range and is the right size.
- **The 98%-zero field is no longer a problem to work around** — zeros are signal ("suitable,
  unobserved"), not absence.
- **The reducer stays `max`**, but for a new reason. Presence is now carried by *row existence* (NaN
  pixels produce no row), so the reducer no longer decides range membership at all; it only sets the
  observation count. `max` reports the best-sampled source pixel in the cell. Do not switch to `sum`:
  at res 8 (0.737 km²) against a ~0.69 km² source pixel the aggregation is near 1:1, and summing
  would manufacture counts that vary with how many pixels happen to fall in a cell.
- **Rename the column.** `score` misdescribes a count — publish it as `n_observations`, and say in the
  asset description that 0 means suitable-but-unobserved.
- **Do not zero-suppress this table.** Zero rows are in-range cells and dropping them would delete
  98% of the range. (The suppression note in dataset B applies only to B.)
- **Observation count is sampling effort, not abundance.** It reflects where botanists have looked.
  The app may use it to distinguish observed from modelled-only cells, but must never present it as
  density, cover, or population size.

Write this definition into the STAC description. The app's system prompt states it in every answer
that reports a percentage.

### Proposed ingest

- **Bucket:** `s3://public-ca-ccca5/`
- **Stage raw first** (`raw/`), with the access date recorded — these files came from manual Calflora
  downloads on 2025-06-30/07-01 and there is no stable download URL to re-resolve, so our staged copy
  plus its checksum *is* the provenance.
- **Preprocess job:** drop sub-25°N stray pixels, clip to valid extent, set `nodata=nan`, normalise
  the three seven-letter codes to their six-letter form, and write one clean COG per species to
  `calflora-ranges/cog/{CODE}.tif`. Ingest only the corrected re-downloads for the eight species in
  defects 1–2; a `(1)` filename is never an input.
- **Hex:** one long-form table rather than 107 collections —
  `calflora-ranges/hex/h0={cell}/…` with `species_code`, `h8`, `n_observations`.
  - **Native resolution 8** (0.737 km² vs. the ~0.69 km² source pixel — a near 1:1 match), parents
    `7, 0`. Res 7 is the join key to dataset B.
  - **Reducer `max`**, over non-NaN pixels only. A cell with no non-NaN pixel emits no row, so **row
    presence is the range mask** and the reducer only sets the observation count. `mean` would
    manufacture fractional counts; `sum` would make the count depend on how many source pixels fall
    in a cell. See the resolved range definition above.
  - **Keep zero rows.** They are in-range, suitable-but-unobserved cells and carry 98% of the range.
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

**Received 2026-09-15** as `import-data/species_T50_Tcrit_means.csv` (gitignored — see the embargo
below).

### What is in it

109 rows, one per species, no duplicates, no missing values:

| column | content |
|---|---|
| `species` | scientific binomial |
| `species_code` | six-letter code, strict 3+3 — the canonical spelling (see defect 6) |
| `origin` | `native` for all 109 rows; no variation, so not a useful facet yet |
| `T50` | °C, 44.72–56.85, mean ≈ 50.8 |
| `Tcrit` | °C, 40.26–55.92, mean ≈ 47.1 |

These are **means only** — no sample size, no standard deviation, no population or site, no method.
`Tcrit < T50` holds for every row, as it must.

**Coverage against the rasters is complete**: after normalising the three seven-letter codes, all 107
species with a raster have tolerance values. The seven CSV species with no raster are the four
still-missing downloads (`ERIDIS`, `HOLDIS`, `QUEGAR`, `SEQSEM`) and the three code-spelling variants,
which are not genuinely missing. So the usable species list is governed by dataset A, not C.

### Embargo — this is the binding constraint

The team's values are **unpublished until their paper comes out**. We may process them onto NRP but
**must not distribute the raw data further**. Concretely:

- Stage to a **private** NRP bucket. Nothing goes in `s3://public-ca-ccca5/` and no STAC collection
  for C is published while the embargo holds.
- **Serving these as defaults in the public app is distribution.** The app is public and unauthenticated;
  109 Tcrit/T50 pairs rendered into a browser, one query at a time, is the table. Do not read "process
  on NRP" as permission to ship them to clients.
- The workable reading, and the one the team's own framing supports — these are "just a starting
  point", and the proposal always wanted user-supplied values — is that **the app ships no default
  tolerances until publication.** The user enters Tcrit/T50 (or the app offers the plausible range as
  a slider without attributing a per-species value), and we hold the real table on NRP for our own
  validation. That costs little, because the design already treats these as user-settable.
- **Confirm this reading with the team** before wiring anything. If they are content for per-species
  defaults to appear in the app pre-publication, that is their call to make explicitly — but it should
  be in writing, and we should ask whether they want an acknowledgement or a "provisional, unpublished"
  label attached.
- Once the paper is out: publish with a `LICENSE.md` beside the data recording what was and was not
  granted, link it from the STAC, and add the citation.

### Still worth asking for

Sample size and variance per species, and the measurement method. Without them the app can report a
species' Tcrit but can say nothing about how well constrained it is — and a mean with no spread invites
users to read two species 0.3 °C apart as meaningfully different.

---

## Order of work

1. ~~Settle the range-definition question (A)~~ — settled 2026-09-15: range = non-NaN, value =
   observation count. **Post this to [data-workflows#668](https://github.com/boettiger-lab/data-workflows/issues/668)**,
   which still specifies the `score` column and the old reducer rationale. Chase the corrected and
   added rasters (defects 1, 2, 4); they have not arrived in `import-data/`.
2. ~~File the data-workflows issues~~ — filed:
   [data-workflows#668](https://github.com/boettiger-lab/data-workflows/issues/668) (A, Calflora
   ranges) and [data-workflows#669](https://github.com/boettiger-lab/data-workflows/issues/669)
   (B phase 1, the 3-model ssp370 pilot). **Those issues are the source of truth for scope** — if
   this file and an issue disagree, the issue wins.
3. Build B phase 1 (3-model pilot) and validate it; A is small and can run alongside. Open the
   phase-2 issue only once the pilot's numbers check out.
4. ~~Get C~~ — received. Wire `layers-input.json` and finish `system-prompt.md` against the real
   collection and column names from `list_datasets` / `get_schema`, with **no per-species tolerance
   defaults in the client** until the embargo lifts or the team says otherwise.

## Open questions for the partner

Answered 2026-09-15 and kept only as a record: the meaning of the raster values and the range
definition; which files needed re-downloading; the `(1)` duplicates; the stray equatorial pixels; and
the Tcrit / T50 table itself.

Still open:

1. **Publication timing and what the embargo permits.** Does "don't distribute further" rule out
   showing per-species Tcrit / T50 as defaults in the public app? Our reading is that it does, so we
   plan to require user-entered values until the paper is out — please confirm, and tell us the
   expected publication date and the citation to use.
2. **Sample size, variance and method behind the Tcrit / T50 means**, so the app can say how well
   constrained a value is instead of presenting a bare mean.
3. **`HOLDIS`, `QUEGAR`, `SEQSEM`** — still blocked on the Calflora export bug. We will publish
   without them and add them later; no need to hold anything up, just let us know when they generate.
4. **What leaf-to-air offset range should the control span, and what default (if any)?** Georgia was
   named as the person to advise. *(Unanswered across two rounds — worth asking directly.)*
5. **Scenarios and periods:** does SSP2-4.5 / SSP3-7.0 / SSP5-8.5 with 1985–2014, 2040–2069 and
   2070–2099 windows match what the assessment used? *(Also unanswered twice.)*
6. **The mockup** mentioned in the first email still has not come through — can you resend it?
7. **Is the Calflora observation count capped at 9?** No pixel in any of the 107 files exceeds 9, and
   nines are commoner than eights — which reads as a "9 or more" clamp. If so we will label the top
   class as censored. One for Calflora, alongside the stray-pixel report.
