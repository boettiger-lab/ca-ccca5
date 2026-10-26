#!/usr/bin/env python3
"""Write the theme SQL. Every query opens with the same CTEs, kept here once:

  r       the species' range cells (H3 res 8), with their res-7 parent and area
  cl      range cells inside the LOCA2 domain: those whose res-7 parent has an
          annual-maximum row. Every share and mean is over these cells.
  c       one row per (range cell, period): mean days a year with daily maximum air
          temperature at or above the threshold, as the three-model mean `days`
          and the per-cell lowest (`days_lo`) and highest (`days_hi`) model.
          Exceedance rows of zero are not stored, so a missing row is 0 days.
  amax    the mean annual maximum air temperature per range cell and period.
  w       (conserved-area queries only) each range cell's share in GAP status 1 to 4,
          from the 30x30 conserved areas; cells with no row (outside California land)
          count as not conserved.

The threshold is TLEAF − OFFSET. Both are whole degrees, so it always falls on the
0.5 °C grid of the exceedance table and no interpolation is needed.

Edit this file, not the .sql it writes:  python3 scripts/build-sql.py
"""
import re
from pathlib import Path

RANGE = "s3://public-ca-ccca5/calflora-ranges/hex/h0=*/data_0.parquet"
EXCEED = "s3://public-caladapt/loca2-hybrid/tasmax-exceedance/hex/h0=*/data_0.parquet"
AMAX = "s3://public-caladapt/loca2-hybrid/tasmax-annual-max/hex/h0=*/data_0.parquet"
GAPW = "s3://public-ca30x30/conserved-areas-terrestrial-2025/hex-weights-res8/h0=*/data_0.parquet"
PERIODS = [  # key, scenario, period, label
    ("hist", "historical", "1985-2014", "Historical 1985–2014"),
    ("ssp370-mid", "ssp370", "2040-2069", "SSP3-7.0 2040–2069"),
    ("ssp370-end", "ssp370", "2070-2099", "SSP3-7.0 2070–2099"),
]

PERIOD_ROWS = ",\n    ".join(f"('{k}', '{s}', '{p}', '{l}', {i + 1})" for i, (k, s, p, l) in enumerate(PERIODS))

PRELUDE = f"""-- Range: every cell present for the species, observed or not (n_observations 0 = in range, unobserved).
-- Climate: LOCA2-Hybrid daily maximum air temperature, three CMIP6 models (GFDL-ESM4,
-- MPI-ESM1-2-HR, ACCESS-CM2), summarised per H3 res-7 cell as mean days a year at or
-- above each threshold on a 0.5 °C grid.
WITH r AS (
  SELECT h0, h8, h3_cell_to_parent(h8, 7) AS h7, n_observations, h3_cell_area(h8, 'km^2') AS km2
  FROM read_parquet('{RANGE}', hive_partitioning = true)
  WHERE species_code = '{{{{ID}}}}'
),
periods AS (
  SELECT * FROM (VALUES
    {PERIOD_ROWS}
  ) t(period_key, scenario, period, period_label, ord)
),
amax AS (
  SELECT a.h7, p.period_key, a.tmax_mean_annual_max_c
  FROM read_parquet('{AMAX}', hive_partitioning = true) a
  JOIN periods p USING (scenario, period)
  SEMI JOIN r USING (h0, h7)
),
ex AS (
  SELECT e.h7, p.period_key, e.days_mean, e.days_min, e.days_max
  FROM read_parquet('{EXCEED}', hive_partitioning = true) e
  JOIN periods p USING (scenario, period)
  SEMI JOIN r USING (h0, h7)
  WHERE e.threshold_c = {{{{TLEAF}}}} - {{{{OFFSET}}}}
),
c AS (
  SELECT p.period_key, p.period_label, p.ord, r.h8, r.h7, r.n_observations, r.km2,
         a.tmax_mean_annual_max_c AS tmax,
         coalesce(ex.days_mean, 0) AS days, coalesce(ex.days_min, 0) AS days_lo, coalesce(ex.days_max, 0) AS days_hi,
         {{{{TLEAF}}}} - {{{{OFFSET}}}} AS tau
  FROM r CROSS JOIN periods p
  JOIN amax a ON a.h7 = r.h7 AND a.period_key = p.period_key
  LEFT JOIN ex ON ex.h7 = r.h7 AND ex.period_key = p.period_key
)
"""

QUERIES = {
    "exposure/summary.sql": """
-- The selected period. Means and shares are by area over the range cells LOCA2 covers.
SELECT any_value(tau) AS tau_c,
       (SELECT sum(km2) FROM r) AS range_km2,
       sum(km2) AS covered_km2,
       sum(km2 * days) / sum(km2) AS mean_days,
       sum(km2) FILTER (WHERE days >= 1) / sum(km2) AS share_1day,
       sum(km2) FILTER (WHERE days >= 10) / sum(km2) AS share_10days,
       max(tmax) - any_value(tau) AS max_margin_c
FROM c WHERE period_key = '{{PERIOD}}'
""",
    "exposure/by-period.sql": """
-- Every period at the chosen threshold: the whole range, and the recorded cells alone.
SELECT period_label,
       sum(km2 * days) / sum(km2) AS mean_days,
       sum(km2 * days) FILTER (WHERE n_observations > 0) / sum(km2) FILTER (WHERE n_observations > 0) AS mean_days_observed
FROM c GROUP BY period_label, ord ORDER BY ord
""",
    "exposure/classes.sql": """
-- Share of the range in each class of mean days a year above the threshold, per period.
SELECT period_label,
       sum(km2) FILTER (WHERE days < 0.1) / sum(km2) AS d0,
       sum(km2) FILTER (WHERE days >= 0.1 AND days < 1) / sum(km2) AS d01,
       sum(km2) FILTER (WHERE days >= 1 AND days < 5) / sum(km2) AS d1,
       sum(km2) FILTER (WHERE days >= 5 AND days < 10) / sum(km2) AS d5,
       sum(km2) FILTER (WHERE days >= 10 AND days < 30) / sum(km2) AS d10,
       sum(km2) FILTER (WHERE days >= 30) / sum(km2) AS d30
FROM c GROUP BY period_label, ord ORDER BY ord
""",
    "exposure/map.sql": """
-- Per res-7 cell, the LOCA2 grid: area-weighted mean days a year above the threshold
-- over the species' range cells in it, selected period.
SELECT h3_h3_to_string(h7) AS h7,
       sum(km2 * days) / sum(km2) AS mean_days
FROM c WHERE period_key = '{{PERIOD}}'
GROUP BY 1
""",
    "conserved/by-gap.sql": """
-- Share of the whole range in each GAP status, by area.
SELECT * FROM (VALUES
  ('GAP 1', 1, (SELECT sum(r.km2 * coalesce(w.w1, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 2', 2, (SELECT sum(r.km2 * coalesce(w.w2, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 3', 3, (SELECT sum(r.km2 * coalesce(w.w3, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 4', 4, (SELECT sum(r.km2 * coalesce(w.w4, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('Not conserved', 5, (SELECT sum(r.km2 * (1 - coalesce(w.w1 + w.w2 + w.w3 + w.w4, 0))) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8)))
) t(gap, ord, share) ORDER BY ord
""",
    "conserved/summary.sql": """
-- Share of the whole range in GAP 1 or 2, the land California's 30x30 goal counts.
SELECT sum(r.km2 * coalesce(w.w1 + w.w2, 0)) / sum(r.km2) AS share_gap12,
       sum(r.km2 * coalesce(w.w1 + w.w2, 0)) AS km2_gap12
FROM r LEFT JOIN w USING (h0, h8)
""",
    "conserved/days.sql": """
-- Mean days a year above the threshold on GAP 1-2 land and on the rest of the range, per period.
SELECT period_label,
       sum(km2 * g12 * days) / nullif(sum(km2 * g12), 0) AS days_gap12,
       sum(km2 * (1 - g12) * days) / nullif(sum(km2 * (1 - g12)), 0) AS days_other
FROM (SELECT c.*, coalesce(w.w1 + w.w2, 0) AS g12 FROM c LEFT JOIN w USING (h8))
GROUP BY period_label, ord ORDER BY ord
""",
    "conserved/map.sql": """
-- Per res-7 cell: share of the species' range cells in it that is GAP 1 or 2.
SELECT h3_h3_to_string(r.h7) AS h7,
       sum(r.km2 * coalesce(w.w1 + w.w2, 0)) / sum(r.km2) AS share_gap12
FROM r LEFT JOIN w USING (h0, h8)
GROUP BY 1
""",
    "models/spread.sql": """
-- Mean days a year above the threshold using, in each cell, the lowest, the mean and
-- the highest of the three models.
SELECT period_label,
       sum(km2 * days_lo) / sum(km2) AS days_lo,
       sum(km2 * days) / sum(km2) AS days_mean,
       sum(km2 * days_hi) / sum(km2) AS days_hi
FROM c GROUP BY period_label, ord ORDER BY ord
""",
}

# The offset sweep needs every offset's threshold, so it reads the exceedance table
# without the single-threshold filter.
OFFSETS = "[0, 2.5, 5, 7.5, 10, 12.5, 15]"
BY_OFFSET = PRELUDE.split("ex AS (")[0] + f"""o AS (SELECT unnest({OFFSETS}) AS o)
-- The selected period at a fixed set of offsets, holding the leaf threshold.
SELECT format('Offset {{}} °C, air {{}} °C', o.o, {{{{TLEAF}}}} - o.o) AS offset_label,
       sum(r.km2 * coalesce(e.days_mean, 0)) / sum(r.km2) AS mean_days
FROM r
JOIN amax a ON a.h7 = r.h7 AND a.period_key = '{{{{PERIOD}}}}'
CROSS JOIN o
LEFT JOIN (
  SELECT e.h7, e.threshold_c, e.days_mean
  FROM read_parquet('{EXCEED}', hive_partitioning = true) e
  JOIN periods p USING (scenario, period)
  SEMI JOIN r USING (h0, h7)
  WHERE p.period_key = '{{{{PERIOD}}}}'
) e ON e.h7 = r.h7 AND e.threshold_c = {{{{TLEAF}}}} - o.o
GROUP BY o.o ORDER BY o.o
"""

root = Path(__file__).resolve().parent.parent / "config" / "themes"
for f in root.glob("*/*.sql"):
    f.unlink()
W_CTE = f""",
w AS (
  SELECT h0, h8, w1, w2, w3, w4
  FROM read_parquet('{GAPW}', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
)
"""
outputs = {name: (PRELUDE.rstrip("\n") + W_CTE if name.startswith("conserved/") else PRELUDE) + body.lstrip("\n")
           for name, body in QUERIES.items()}
outputs["exposure/by-offset.sql"] = BY_OFFSET
for name, sql in outputs.items():
    # a filtered sum over no rows is NULL; for a numerator that means none, so 0
    sql = re.sub(r"sum\(km2\) FILTER \(WHERE ([^)]*)\)( /)", r"coalesce(sum(km2) FILTER (WHERE \1), 0)\2", sql)
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(sql)
    print("wrote", p.relative_to(root.parent.parent))
