-- Range: every cell present for the species, observed or not (n_observations 0 = in range, unobserved).
-- Temperature: CHELSA 2.1 bio5, the mean daily maximum air temperature of the warmest month (°C).
WITH r AS (
  SELECT h0, h8, n_observations
  FROM read_parquet('s3://public-ca-ccca5/calflora-ranges/hex/h0=*/data_0.parquet', hive_partitioning = true)
  WHERE species_code = '{{ID}}'
),
clim AS (
  SELECT 'obs' AS period, 'Observed 1981–2010' AS period_label, 1 AS ord, h0, h8,
         bio5 AS t, bio5 AS t_lo, bio5 AS t_hi
  FROM read_parquet('s3://public-bioclimate/chelsa-2-1/baseline-1981-2010/hex/h0=*/data_0.parquet', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
  UNION ALL
  SELECT 'ssp370-mid' AS period, 'SSP3-7.0 2041–2070' AS period_label, 2 AS ord, h0, h8,
         bio5_median AS t, bio5_min AS t_lo, bio5_max AS t_hi
  FROM read_parquet('s3://public-bioclimate/chelsa-2-1/ssp370-2041-2070/hex/h0=*/data_0.parquet', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
  UNION ALL
  SELECT 'ssp370-end' AS period, 'SSP3-7.0 2071–2100' AS period_label, 3 AS ord, h0, h8,
         bio5_median AS t, bio5_min AS t_lo, bio5_max AS t_hi
  FROM read_parquet('s3://public-bioclimate/chelsa-2-1/ssp370-2071-2100/hex/h0=*/data_0.parquet', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
  UNION ALL
  SELECT 'ssp585-end' AS period, 'SSP5-8.5 2071–2100' AS period_label, 4 AS ord, h0, h8,
         bio5_median AS t, bio5_min AS t_lo, bio5_max AS t_hi
  FROM read_parquet('s3://public-bioclimate/chelsa-2-1/ssp585-2071-2100/hex/h0=*/data_0.parquet', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
),
c AS (
  SELECT clim.*, r.n_observations, h3_cell_area(h8, 'km^2') AS km2,
         {{TLEAF}} - {{OFFSET}} AS tau
  FROM clim JOIN r USING (h0, h8)
)
-- The selected period at a fixed set of offsets, holding the leaf threshold.
SELECT format('Offset {} °C, air {} °C', o, {{TLEAF}} - o) AS offset_label,
       coalesce(sum(km2) FILTER (WHERE t > {{TLEAF}} - o), 0) / sum(km2) AS share_over
FROM c, (SELECT unnest([0, 2.5, 5, 7.5, 10, 12.5, 15]) AS o)
WHERE period = '{{PERIOD}}'
GROUP BY o ORDER BY o
