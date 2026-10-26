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
-- Share of the whole range in each GAP status, by area.
SELECT * FROM (VALUES
  ('GAP 1', 1, (SELECT sum(r.km2 * coalesce(w.w1, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 2', 2, (SELECT sum(r.km2 * coalesce(w.w2, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 3', 3, (SELECT sum(r.km2 * coalesce(w.w3, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('GAP 4', 4, (SELECT sum(r.km2 * coalesce(w.w4, 0)) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8))),
  ('Not conserved', 5, (SELECT sum(r.km2 * (1 - coalesce(w.w1 + w.w2 + w.w3 + w.w4, 0))) / sum(r.km2) FROM r LEFT JOIN w USING (h0, h8)))
) t(gap, ord, share) ORDER BY ord
