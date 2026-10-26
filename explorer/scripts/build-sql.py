#!/usr/bin/env python3
"""Write the theme SQL. Every query opens with the same two CTEs, kept here once:

  c    one row per (range cell, period): CHELSA bio5 (°C) as the five-model median
       `t`, with the per-cell lowest (`t_lo`) and highest (`t_hi`) of the five models;
       the observed baseline has one value, repeated in all three.
  tau  the effective air threshold, leaf threshold minus leaf-to-air offset.

Edit this file, not the .sql it writes:  python3 scripts/build-sql.py
"""
import re
from pathlib import Path

RANGE = "s3://public-ca-ccca5/calflora-ranges/hex/h0=*/data_0.parquet"
CHELSA = "s3://public-bioclimate/chelsa-2-1/{}/hex/h0=*/data_0.parquet"
PERIODS = [  # key, label, folder, temperature column, has the model envelope
    ("obs", "Observed 1981–2010", "baseline-1981-2010", "bio5", False),
    ("ssp370-mid", "SSP3-7.0 2041–2070", "ssp370-2041-2070", "bio5_median", True),
    ("ssp370-end", "SSP3-7.0 2071–2100", "ssp370-2071-2100", "bio5_median", True),
    ("ssp585-end", "SSP5-8.5 2071–2100", "ssp585-2071-2100", "bio5_median", True),
]


def clim(key, label, folder, col, env, ord_):
    lo, hi = ("bio5_min", "bio5_max") if env else (col, col)
    return (f"  SELECT '{key}' AS period, '{label}' AS period_label, {ord_} AS ord, h0, h8,\n"
            f"         {col} AS t, {lo} AS t_lo, {hi} AS t_hi\n"
            f"  FROM read_parquet('{CHELSA.format(folder)}', hive_partitioning = true)\n"
            f"  SEMI JOIN r USING (h0, h8)")


PRELUDE = ("-- Range: every cell present for the species, observed or not (n_observations 0 = in range, unobserved).\n"
           "-- Temperature: CHELSA 2.1 bio5, the mean daily maximum air temperature of the warmest month (°C).\n"
           "WITH r AS (\n"
           "  SELECT h0, h8, n_observations\n"
           f"  FROM read_parquet('{RANGE}', hive_partitioning = true)\n"
           "  WHERE species_code = '{{ID}}'\n"
           "),\n"
           "clim AS (\n"
           + "\n  UNION ALL\n".join(clim(*p, i + 1) for i, p in enumerate(PERIODS)) + "\n"
           "),\n"
           "c AS (\n"
           "  SELECT clim.*, r.n_observations, h3_cell_area(h8, 'km^2') AS km2,\n"
           "         {{TLEAF}} - {{OFFSET}} AS tau\n"
           "  FROM clim JOIN r USING (h0, h8)\n"
           ")\n")

QUERIES = {
    "exposure/summary.sql": """
-- The selected period. Shares are of the range cells CHELSA covers.
SELECT any_value(tau) AS tau_c,
       (SELECT sum(h3_cell_area(h8, 'km^2')) FROM r) AS range_km2,
       sum(km2) AS covered_km2,
       sum(km2) FILTER (WHERE t > tau) AS area_over_km2,
       sum(km2) FILTER (WHERE t > tau) / sum(km2) AS share_over,
       max(t) - any_value(tau) AS max_margin_c,
       median(t) AS median_t
FROM c WHERE period = '{{PERIOD}}'
""",
    "exposure/by-period.sql": """
-- Every period at the chosen threshold: the whole range, and the observed cells alone.
SELECT period_label,
       sum(km2) FILTER (WHERE t > tau) / sum(km2) AS share_over,
       sum(km2) FILTER (WHERE t > tau AND n_observations > 0) / sum(km2) FILTER (WHERE n_observations > 0) AS share_over_observed
FROM c GROUP BY period_label, ord ORDER BY ord
""",
    "exposure/margins.sql": """
-- Share of the range in each class of bio5 minus the threshold, per period.
SELECT period_label,
       sum(km2) FILTER (WHERE t - tau <= -5) / sum(km2) AS below_5,
       sum(km2) FILTER (WHERE t - tau > -5 AND t <= tau) / sum(km2) AS below_0,
       sum(km2) FILTER (WHERE t > tau AND t - tau <= 2) / sum(km2) AS above_0,
       sum(km2) FILTER (WHERE t - tau > 2 AND t - tau <= 5) / sum(km2) AS above_2,
       sum(km2) FILTER (WHERE t - tau > 5) / sum(km2) AS above_5
FROM c GROUP BY period_label, ord ORDER BY ord
""",
    "exposure/by-offset.sql": """
-- The selected period at a fixed set of offsets, holding the leaf threshold.
SELECT format('Offset {} °C, air {} °C', o, {{TLEAF}} - o) AS offset_label,
       sum(km2) FILTER (WHERE t > {{TLEAF}} - o) / sum(km2) AS share_over
FROM c, (SELECT unnest([0, 2.5, 5, 7.5, 10, 12.5, 15]) AS o)
WHERE period = '{{PERIOD}}'
GROUP BY o ORDER BY o
""",
    "exposure/map.sql": """
-- Per res-6 cell: share of the species' range cells in it above the threshold, selected period.
SELECT h3_h3_to_string(h3_cell_to_parent(h8, 6)) AS h6,
       sum(km2) FILTER (WHERE t > tau) / sum(km2) AS share_over
FROM c WHERE period = '{{PERIOD}}'
GROUP BY 1
""",
    "models/spread.sql": """
-- Future periods: the share above the threshold using, in each cell, the lowest,
-- the median and the highest bio5 of the five CHELSA models.
SELECT period_label,
       sum(km2) FILTER (WHERE t_lo > tau) / sum(km2) AS share_lo,
       sum(km2) FILTER (WHERE t > tau) / sum(km2) AS share_median,
       sum(km2) FILTER (WHERE t_hi > tau) / sum(km2) AS share_hi
FROM c WHERE period <> 'obs'
GROUP BY period_label, ord ORDER BY ord
""",
}

root = Path(__file__).resolve().parent.parent / "config" / "themes"
for name, body in QUERIES.items():
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    # a filtered sum over no rows is NULL; for a numerator that means none, so 0
    body = re.sub(r"sum\(km2\) FILTER \(WHERE ([^)]*)\)( /| AS)", r"coalesce(sum(km2) FILTER (WHERE \1), 0)\2", body)
    p.write_text(PRELUDE + body.lstrip("\n"))
    print("wrote", p.relative_to(root.parent.parent))
