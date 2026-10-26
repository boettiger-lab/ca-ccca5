#!/usr/bin/env python3
"""Write the theme SQL. Every query opens with the same CTEs, kept here once:

  tol     the species' measured Tcrit and T50 (°C), the project team's provisional means
  r       the species' range cells (H3 res 8), with their res-7 parent and area
  r7      the range summed to res 7, the LOCA2 grid: range area, and the area recorded
  thr     the thresholds the query needs: one row per (metric, offset). The leaf threshold
          is the team's value plus the reader's adjustment (ADJUST, 0 by default; the Tcrit
          against T50 chart leaves it out), the air threshold tau = leaf threshold − offset,
          and `lo` is the 0.5 °C grid row just below tau
  amax    the mean annual maximum air temperature per res-7 cell and period; a cell with
          a row is inside the LOCA2 domain, and every share and mean is over those cells
  ex      the exceedance rows at the grid thresholds that bracket each tau
  c       one row per (res-7 cell, period, metric, offset): mean days a year at or above
          tau, interpolated linearly between the two grid rows, as the three-model mean
          `days` and the per-cell lowest (`days_lo`) and highest (`days_hi`) model.
          Exceedance rows of zero are not stored, so a missing row is 0 days. A tau
          outside the 20–60 °C grid gives NULL, never an extrapolation.

Edit this file, not the .sql it writes:  python3 scripts/build-sql.py
"""
import re
from pathlib import Path

TOL = "https://raw.githubusercontent.com/boettiger-lab/ca-ccca5/main/data/species_T50_Tcrit_means.csv"
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

# which (metric, offset) pairs a query needs
ONE = ("['{{METRIC}}']", "[{{OFFSET}}]")
BOTH_METRICS = ("['tcrit', 't50']", "[{{OFFSET}}]")
SWEEP = ("['{{METRIC}}']", "[0, 2.5, 5, 7.5, 10, 12.5, 15]")


def prelude(metrics, offsets, conserved=False, adjust=True):
    w = f"""
w AS (
  SELECT h0, h8, w1, w2, w3, w4
  FROM read_parquet('{GAPW}', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
),""" if conserved else ""
    g12 = ",\n         sum(r.km2 * coalesce(w.w1 + w.w2, 0)) AS km2_g12" if conserved else ""
    wjoin = "\n  LEFT JOIN w USING (h0, h8)" if conserved else ""
    adj = " + {{ADJUST}}" if adjust else ""
    return f"""-- Thresholds: the project team's provisional mean Tcrit and T50 for the species (°C),
-- plus the reader's adjustment where the query uses one.
-- Range: every cell present for the species, observed or not (n_observations 0 = in range, unobserved).
-- Climate: LOCA2-Hybrid daily maximum air temperature, three CMIP6 models (GFDL-ESM4,
-- MPI-ESM1-2-HR, ACCESS-CM2), as mean days a year at or above each threshold on a
-- 0.5 °C grid, per H3 res-7 cell.
WITH tol AS (
  SELECT Tcrit AS tcrit, T50 AS t50
  FROM read_csv('{TOL}')
  WHERE species_code = '{{{{ID}}}}'
),
r AS (
  SELECT h0, h8, h3_cell_to_parent(h8, 7) AS h7, n_observations, h3_cell_area(h8, 'km^2') AS km2
  FROM read_parquet('{RANGE}', hive_partitioning = true)
  WHERE species_code = '{{{{ID}}}}'
),{w}
r7 AS (
  SELECT any_value(r.h0) AS h0, r.h7, sum(r.km2) AS km2,
         sum(r.km2) FILTER (WHERE r.n_observations > 0) AS km2_obs{g12}
  FROM r{wjoin}
  GROUP BY r.h7
),
periods AS (
  SELECT * FROM (VALUES
    {PERIOD_ROWS}
  ) t(period_key, scenario, period, period_label, ord)
),
thr AS (
  SELECT m.metric, o.offset_c, team, leaf, leaf - o.offset_c AS tau, floor((leaf - o.offset_c) * 2) / 2 AS lo
  FROM (SELECT unnest({metrics}) AS metric) m, (SELECT unnest({offsets}) AS offset_c) o, tol,
       LATERAL (SELECT CASE m.metric WHEN 'tcrit' THEN tol.tcrit ELSE tol.t50 END AS team),
       LATERAL (SELECT team{adj} AS leaf)
),
amax AS (
  SELECT a.h7, p.period_key, a.tmax_mean_annual_max_c AS tmax
  FROM read_parquet('{AMAX}', hive_partitioning = true) a
  JOIN periods p USING (scenario, period)
  SEMI JOIN r7 USING (h0, h7)
),
ex AS (
  SELECT e.h7, p.period_key, e.threshold_c, e.days_mean, e.days_min, e.days_max
  FROM read_parquet('{EXCEED}', hive_partitioning = true) e
  JOIN periods p USING (scenario, period)
  SEMI JOIN r7 USING (h0, h7)
  WHERE e.threshold_c IN (SELECT lo FROM thr UNION SELECT lo + 0.5 FROM thr)
),
c AS (
  SELECT t.metric, t.offset_c, t.team, t.leaf, t.tau, p.period_key, p.period_label, p.ord,
         r7.*, a.tmax,
         CASE WHEN t.lo < 20 OR t.lo + 0.5 > 60 THEN NULL ELSE
           coalesce(e0.days_mean, 0) + (coalesce(e1.days_mean, 0) - coalesce(e0.days_mean, 0)) * (t.tau - t.lo) / 0.5 END AS days,
         CASE WHEN t.lo < 20 OR t.lo + 0.5 > 60 THEN NULL ELSE
           coalesce(e0.days_min, 0) + (coalesce(e1.days_min, 0) - coalesce(e0.days_min, 0)) * (t.tau - t.lo) / 0.5 END AS days_lo,
         CASE WHEN t.lo < 20 OR t.lo + 0.5 > 60 THEN NULL ELSE
           coalesce(e0.days_max, 0) + (coalesce(e1.days_max, 0) - coalesce(e0.days_max, 0)) * (t.tau - t.lo) / 0.5 END AS days_hi
  FROM r7 CROSS JOIN periods p CROSS JOIN thr t
  JOIN amax a ON a.h7 = r7.h7 AND a.period_key = p.period_key
  LEFT JOIN ex e0 ON e0.h7 = r7.h7 AND e0.period_key = p.period_key AND e0.threshold_c = t.lo
  LEFT JOIN ex e1 ON e1.h7 = r7.h7 AND e1.period_key = p.period_key AND e1.threshold_c = t.lo + 0.5
)
"""


QUERIES = {
    "exposure/summary.sql": (ONE, False, """
-- The selected metric, offset and period. Means and shares are by area over the range cells LOCA2 covers.
SELECT any_value(team) AS team_c,
       any_value(leaf) AS leaf_c,
       any_value(tau) AS tau_c,
       sum(km2 * days) / sum(km2) AS mean_days,
       sum(km2) FILTER (WHERE days >= 1) / sum(km2) AS share_1day,
       sum(km2) FILTER (WHERE days >= 10) / sum(km2) AS share_10days,
       max(tmax) - any_value(tau) AS max_margin_c
FROM c WHERE period_key = '{{PERIOD}}'
"""),
    "exposure/by-period.sql": (ONE, False, """
-- Every period at the chosen threshold: the whole range, and the recorded cells alone.
SELECT period_label,
       sum(km2 * days) / sum(km2) AS mean_days,
       sum(km2_obs * days) / sum(km2_obs) AS mean_days_observed
FROM c GROUP BY period_label, ord ORDER BY ord
"""),
    "exposure/by-metric.sql": (BOTH_METRICS, False, """
-- Tcrit and T50 side by side in every period, at the team's values and the chosen offset.
SELECT period_label,
       sum(km2 * days) FILTER (WHERE metric = 'tcrit') / sum(km2) FILTER (WHERE metric = 'tcrit') AS days_tcrit,
       sum(km2 * days) FILTER (WHERE metric = 't50') / sum(km2) FILTER (WHERE metric = 't50') AS days_t50
FROM c GROUP BY period_label, ord ORDER BY ord
"""),
    "exposure/classes.sql": (ONE, False, """
-- Share of the range in each class of mean days a year above the threshold, per period.
SELECT period_label,
       sum(km2) FILTER (WHERE days < 0.1) / sum(km2) AS d0,
       sum(km2) FILTER (WHERE days >= 0.1 AND days < 1) / sum(km2) AS d01,
       sum(km2) FILTER (WHERE days >= 1 AND days < 5) / sum(km2) AS d1,
       sum(km2) FILTER (WHERE days >= 5 AND days < 10) / sum(km2) AS d5,
       sum(km2) FILTER (WHERE days >= 10 AND days < 30) / sum(km2) AS d10,
       sum(km2) FILTER (WHERE days >= 30) / sum(km2) AS d30
FROM c GROUP BY period_label, ord ORDER BY ord
"""),
    "exposure/by-offset.sql": (SWEEP, False, """
-- The selected metric and period at a fixed set of offsets.
SELECT format('Offset {} °C, air {} °C', offset_c, round(any_value(tau), 1)) AS offset_label,
       sum(km2 * days) / sum(km2) AS mean_days
FROM c WHERE period_key = '{{PERIOD}}'
GROUP BY offset_c ORDER BY offset_c
"""),
    "exposure/map.sql": (ONE, False, """
-- Per res-7 cell, the LOCA2 grid: mean days a year above the threshold, selected period.
SELECT h3_h3_to_string(h7) AS h7, days AS mean_days
FROM c WHERE period_key = '{{PERIOD}}'
"""),
    "exposure/map-h6.sql": (ONE, False, """
-- Per res-6 cell, for the zoomed-out map: area-weighted mean days a year above the
-- threshold over the res-7 cells in it, selected period.
SELECT h3_h3_to_string(h3_cell_to_parent(h7, 6)) AS h6, sum(km2 * days) / sum(km2) AS mean_days
FROM c WHERE period_key = '{{PERIOD}}'
GROUP BY 1
"""),
    "conserved/by-gap.sql": (None, True, """
-- Share of the whole range in each GAP status, by area.
SELECT * FROM (VALUES
  ('GAP 1', 1, (SELECT sum(r.km2 * coalesce(w.w1, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 2', 2, (SELECT sum(r.km2 * coalesce(w.w2, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 3', 3, (SELECT sum(r.km2 * coalesce(w.w3, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 4', 4, (SELECT sum(r.km2 * coalesce(w.w4, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('Not conserved', 5, (SELECT sum(r.km2 * (1 - coalesce(w.w1 + w.w2 + w.w3 + w.w4, 0))) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8)))
) t(gap, ord, share) ORDER BY ord
"""),
    "conserved/summary.sql": (None, True, """
-- Share of the whole range in GAP 1 or 2, the land California's 30x30 goal counts.
SELECT sum(r.km2 * coalesce(w.w1 + w.w2, 0)) / sum(r.km2) AS share_gap12,
       sum(r.km2 * coalesce(w.w1 + w.w2, 0)) AS km2_gap12
FROM r LEFT JOIN w USING (h0, h8)
"""),
    "conserved/days.sql": (ONE, True, """
-- Mean days a year above the threshold on GAP 1-2 land and on the rest of the range, per period.
SELECT period_label,
       sum(km2_g12 * days) / nullif(sum(km2_g12), 0) AS days_gap12,
       sum((km2 - km2_g12) * days) / nullif(sum(km2 - km2_g12), 0) AS days_other
FROM c GROUP BY period_label, ord ORDER BY ord
"""),
    "conserved/map.sql": (None, True, """
-- Per res-7 cell: share of the species' range cells in it that is GAP 1 or 2.
SELECT h3_h3_to_string(r.h7) AS h7,
       sum(r.km2 * coalesce(w.w1 + w.w2, 0)) / sum(r.km2) AS share_gap12
FROM r LEFT JOIN w USING (h0, h8)
GROUP BY 1
"""),
    "conserved/map-h6.sql": (None, True, """
-- Per res-6 cell, for the zoomed-out map: share of the species' range cells in it that is GAP 1 or 2.
SELECT h3_h3_to_string(h3_cell_to_parent(r.h7, 6)) AS h6,
       sum(r.km2 * coalesce(w.w1 + w.w2, 0)) / sum(r.km2) AS share_gap12
FROM r LEFT JOIN w USING (h0, h8)
GROUP BY 1
"""),
    "models/spread.sql": (ONE, False, """
-- Mean days a year above the threshold using, in each cell, the lowest, the mean and
-- the highest of the three models.
SELECT period_label,
       sum(km2 * days_lo) / sum(km2) AS days_lo,
       sum(km2 * days) / sum(km2) AS days_mean,
       sum(km2 * days_hi) / sum(km2) AS days_hi
FROM c GROUP BY period_label, ord ORDER BY ord
"""),
}


def gap_only_prelude():
    """The conserved-area shares need only the range and the GAP weights."""
    return f"""-- Range: every cell present for the species, observed or not.
-- Conserved areas: 30x30 terrestrial conserved areas (2025), each res-8 cell's share of
-- California land in GAP status 1 to 4; a range cell with no row counts as not conserved.
WITH r AS (
  SELECT h0, h8, h3_cell_to_parent(h8, 7) AS h7, h3_cell_area(h8, 'km^2') AS km2
  FROM read_parquet('{RANGE}', hive_partitioning = true)
  WHERE species_code = '{{{{ID}}}}'
),
w AS (
  SELECT h0, h8, w1, w2, w3, w4
  FROM read_parquet('{GAPW}', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
)
"""


root = Path(__file__).resolve().parent.parent / "config" / "themes"
for f in root.glob("*/*.sql"):
    f.unlink()
BASE = f"""-- The team's provisional mean for the selected metric (°C): the base the threshold slider adjusts.
SELECT CASE '{{{{METRIC}}}}' WHEN 'tcrit' THEN Tcrit ELSE T50 END AS leaf_c
FROM read_csv('{TOL}')
WHERE species_code = '{{{{ID}}}}'
"""

for name, (thr, conserved, body) in QUERIES.items():
    head = gap_only_prelude() if thr is None else prelude(*thr, conserved=conserved, adjust=name != "exposure/by-metric.sql")
    sql = head + body.lstrip("\n")
    # a filtered sum over no rows is NULL; for a numerator that means none, so 0
    sql = re.sub(r"sum\(km2\) FILTER \(WHERE ([^)]*)\)( /)", r"coalesce(sum(km2) FILTER (WHERE \1), 0)\2", sql)
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(sql)
    print("wrote", p.relative_to(root.parent.parent))
(root / "exposure" / "base.sql").write_text(BASE)
print("wrote config/themes/exposure/base.sql")
