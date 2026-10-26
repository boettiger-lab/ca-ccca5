-- Thresholds: the project team's provisional mean Tcrit and T50 for the species (°C),
-- plus the reader's adjustment where the query uses one.
-- Range: every cell present for the species, observed or not (n_observations 0 = in range, unobserved).
-- Climate: LOCA2-Hybrid daily maximum air temperature, three CMIP6 models (GFDL-ESM4,
-- MPI-ESM1-2-HR, ACCESS-CM2), as mean days a year at or above each threshold on a
-- 0.5 °C grid, per H3 res-7 cell.
WITH tol AS (
  SELECT Tcrit AS tcrit, T50 AS t50
  FROM read_csv('https://raw.githubusercontent.com/boettiger-lab/ca-ccca5/main/data/species_T50_Tcrit_means.csv')
  WHERE species_code = '{{ID}}'
),
r AS (
  SELECT h0, h8, h3_cell_to_parent(h8, 7) AS h7, n_observations, h3_cell_area(h8, 'km^2') AS km2
  FROM read_parquet('s3://public-ca-ccca5/calflora-ranges/hex/h0=*/data_0.parquet', hive_partitioning = true)
  WHERE species_code = '{{ID}}'
),
r7 AS (
  SELECT any_value(r.h0) AS h0, r.h7, sum(r.km2) AS km2,
         sum(r.km2) FILTER (WHERE r.n_observations > 0) AS km2_obs
  FROM r
  GROUP BY r.h7
),
periods AS (
  SELECT * FROM (VALUES
    ('hist', 'historical', '1985-2014', 'Historical 1985–2014', 1),
    ('ssp370-mid', 'ssp370', '2040-2069', 'SSP3-7.0 2040–2069', 2),
    ('ssp370-end', 'ssp370', '2070-2099', 'SSP3-7.0 2070–2099', 3)
  ) t(period_key, scenario, period, period_label, ord)
),
thr AS (
  SELECT m.metric, o.offset_c, team, leaf, leaf - o.offset_c AS tau, floor((leaf - o.offset_c) * 2) / 2 AS lo
  FROM (SELECT unnest(['{{METRIC}}']) AS metric) m, (SELECT unnest([{{OFFSET}}]) AS offset_c) o, tol,
       LATERAL (SELECT CASE m.metric WHEN 'tcrit' THEN tol.tcrit ELSE tol.t50 END AS team),
       LATERAL (SELECT team + {{ADJUST}} AS leaf)
),
amax AS (
  SELECT a.h7, p.period_key, a.tmax_mean_annual_max_c AS tmax
  FROM read_parquet('s3://public-caladapt/loca2-hybrid/tasmax-annual-max/hex/h0=*/data_0.parquet', hive_partitioning = true) a
  JOIN periods p USING (scenario, period)
  SEMI JOIN r7 USING (h0, h7)
),
ex AS (
  SELECT e.h7, p.period_key, e.threshold_c, e.days_mean, e.days_min, e.days_max
  FROM read_parquet('s3://public-caladapt/loca2-hybrid/tasmax-exceedance/hex/h0=*/data_0.parquet', hive_partitioning = true) e
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
-- The selected metric, offset and period. Means and shares are by area over the range cells LOCA2 covers.
SELECT any_value(team) AS team_c,
       any_value(leaf) AS leaf_c,
       any_value(tau) AS tau_c,
       sum(km2 * days) / sum(km2) AS mean_days,
       coalesce(sum(km2) FILTER (WHERE days >= 1), 0) / sum(km2) AS share_1day,
       coalesce(sum(km2) FILTER (WHERE days >= 10), 0) / sum(km2) AS share_10days,
       max(tmax) - any_value(tau) AS max_margin_c
FROM c WHERE period_key = '{{PERIOD}}'
