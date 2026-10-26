-- Range: every cell present for the species, observed or not.
-- Conserved areas: 30x30 terrestrial conserved areas (2025), each res-8 cell's share of
-- California land in GAP status 1 to 4; a range cell with no row counts as not conserved.
WITH r AS (
  SELECT h0, h8, h3_cell_to_parent(h8, 7) AS h7, h3_cell_area(h8, 'km^2') AS km2
  FROM read_parquet('s3://public-ca-ccca5/calflora-ranges/hex/h0=*/data_0.parquet', hive_partitioning = true)
  WHERE species_code = '{{ID}}'
),
w AS (
  SELECT h0, h8, w1, w2, w3, w4
  FROM read_parquet('s3://public-ca30x30/conserved-areas-terrestrial-2025/hex-weights-res8/h0=*/data_0.parquet', hive_partitioning = true)
  SEMI JOIN r USING (h0, h8)
)
-- Per res-7 cell: share of the species' range cells in it that is GAP 1 or 2.
SELECT h3_h3_to_string(r.h7) AS h7,
       sum(r.km2 * coalesce(w.w1 + w.w2, 0)) / sum(r.km2) AS share_gap12
FROM r LEFT JOIN w USING (h0, h8)
GROUP BY 1
