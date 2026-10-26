-- Range: every cell present for the species, observed or not (n_observations 0 = in range, unobserved).
-- Climate: LOCA2-Hybrid daily maximum air temperature, three CMIP6 models (GFDL-ESM4,
-- MPI-ESM1-2-HR, ACCESS-CM2), summarised per H3 res-7 cell as mean days a year at or
-- above each threshold on a 0.5 °C grid.
WITH r AS (
  SELECT h0, h8, h3_cell_to_parent(h8, 7) AS h7, n_observations, h3_cell_area(h8, 'km^2') AS km2
  FROM read_parquet('s3://public-ca-ccca5/calflora-ranges/hex/h0=*/data_0.parquet', hive_partitioning = true)
  WHERE species_code = '{{ID}}'
),
periods AS (
  SELECT * FROM (VALUES
    ('hist', 'historical', '1985-2014', 'Historical 1985–2014', 1),
    ('ssp370-mid', 'ssp370', '2040-2069', 'SSP3-7.0 2040–2069', 2),
    ('ssp370-end', 'ssp370', '2070-2099', 'SSP3-7.0 2070–2099', 3)
  ) t(period_key, scenario, period, period_label, ord)
),
amax AS (
  SELECT a.h7, p.period_key, a.tmax_mean_annual_max_c
  FROM read_parquet('s3://public-caladapt/loca2-hybrid/tasmax-annual-max/hex/h0=*/data_0.parquet', hive_partitioning = true) a
  JOIN periods p USING (scenario, period)
  SEMI JOIN r USING (h0, h7)
),
ex AS (
  SELECT e.h7, p.period_key, e.days_mean, e.days_min, e.days_max
  FROM read_parquet('s3://public-caladapt/loca2-hybrid/tasmax-exceedance/hex/h0=*/data_0.parquet', hive_partitioning = true) e
  JOIN periods p USING (scenario, period)
  SEMI JOIN r USING (h0, h7)
  WHERE e.threshold_c = {{TLEAF}} - {{OFFSET}}
),
c AS (
  SELECT p.period_key, p.period_label, p.ord, r.h8, r.h7, r.n_observations, r.km2,
         a.tmax_mean_annual_max_c AS tmax,
         coalesce(ex.days_mean, 0) AS days, coalesce(ex.days_min, 0) AS days_lo, coalesce(ex.days_max, 0) AS days_hi,
         {{TLEAF}} - {{OFFSET}} AS tau
  FROM r CROSS JOIN periods p
  JOIN amax a ON a.h7 = r.h7 AND a.period_key = p.period_key
  LEFT JOIN ex ON ex.h7 = r.h7 AND ex.period_key = p.period_key
)
-- Share of the range in each class of mean days a year above the threshold, per period.
SELECT period_label,
       coalesce(sum(km2) FILTER (WHERE days < 0.1), 0) / sum(km2) AS d0,
       coalesce(sum(km2) FILTER (WHERE days >= 0.1 AND days < 1), 0) / sum(km2) AS d01,
       coalesce(sum(km2) FILTER (WHERE days >= 1 AND days < 5), 0) / sum(km2) AS d1,
       coalesce(sum(km2) FILTER (WHERE days >= 5 AND days < 10), 0) / sum(km2) AS d5,
       coalesce(sum(km2) FILTER (WHERE days >= 10 AND days < 30), 0) / sum(km2) AS d10,
       coalesce(sum(km2) FILTER (WHERE days >= 30), 0) / sum(km2) AS d30
FROM c GROUP BY period_label, ord ORDER BY ord
