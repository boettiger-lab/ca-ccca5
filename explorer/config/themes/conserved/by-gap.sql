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
),
w AS (
  SELECT h0, h8, w1, w2, w3, w4
  FROM read_parquet('s3://public-ca30x30/conserved-areas-terrestrial-2025/hex-weights-res8/h0=*/data_0.parquet', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
)
-- Share of the whole range in each GAP status, by area.
SELECT * FROM (VALUES
  ('GAP 1', 1, (SELECT sum(r.km2 * coalesce(w.w1, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 2', 2, (SELECT sum(r.km2 * coalesce(w.w2, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 3', 3, (SELECT sum(r.km2 * coalesce(w.w3, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 4', 4, (SELECT sum(r.km2 * coalesce(w.w4, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('Not conserved', 5, (SELECT sum(r.km2 * (1 - coalesce(w.w1 + w.w2 + w.w3 + w.w4, 0))) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8)))
) t(gap, ord, share) ORDER BY ord
