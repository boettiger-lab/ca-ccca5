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
  FROM read_parquet('s3://public-caladapt/loca2-hybrid/tasmax-annual-max/hex/h0=*/*.parquet', hive_partitioning = true) a
  JOIN periods p USING (scenario, period)
  SEMI JOIN r USING (h0, h7)
),
o AS (SELECT unnest([0, 2.5, 5, 7.5, 10, 12.5, 15]) AS o)
-- The selected period at a fixed set of offsets, holding the leaf threshold.
SELECT format('Offset {} °C, air {} °C', o.o, {{TLEAF}} - o.o) AS offset_label,
       sum(r.km2 * coalesce(e.days_mean, 0)) / sum(r.km2) AS mean_days
FROM r
JOIN amax a ON a.h7 = r.h7 AND a.period_key = '{{PERIOD}}'
CROSS JOIN o
LEFT JOIN (
  SELECT e.h7, e.threshold_c, e.days_mean
  FROM read_parquet('s3://public-caladapt/loca2-hybrid/tasmax-exceedance/hex/h0=*/*.parquet', hive_partitioning = true) e
  JOIN periods p USING (scenario, period)
  SEMI JOIN r USING (h0, h7)
  WHERE p.period_key = '{{PERIOD}}'
) e ON e.h7 = r.h7 AND e.threshold_c = {{TLEAF}} - o.o
GROUP BY o.o ORDER BY o.o
