-- Map geometry for the explorer, built from the published Calflora range hex.
--   h6-grid.geojson         every H3 res-6 cell that holds part of any species' range;
--                           the theme maps colour these by `h6` (hex string)
--   species-ranges.geojson  one outline per species: the union of its res-6 cells
-- Run with: bash scripts/build-map-tiles.sh
INSTALL h3 FROM community; LOAD h3; LOAD spatial;
SET s3_endpoint = 's3-west.nrp-nautilus.io'; SET s3_url_style = 'path';
SET geometry_always_xy = true;

CREATE TABLE cells AS
SELECT DISTINCT species_code, h3_cell_to_parent(h8, 6) AS h6
FROM read_parquet('s3://public-ca-ccca5/calflora-ranges/hex-parts/species_code=*/h0=*/data_0.parquet', hive_partitioning = true);

COPY (
  SELECT h3_h3_to_string(h6) AS h6, ST_GeomFromText(h3_cell_to_boundary_wkt(h6)) AS geom
  FROM (SELECT DISTINCT h6 FROM cells)
) TO 'build/h6-grid.geojson' WITH (FORMAT gdal, DRIVER 'GeoJSON');

COPY (
  SELECT c.species_code, s.scientific_name,
         ST_SimplifyPreserveTopology(ST_Union_Agg(ST_GeomFromText(h3_cell_to_boundary_wkt(c.h6))), 0.002) AS geom
  FROM cells c
  JOIN read_parquet('s3://public-ca-ccca5/calflora-ranges/species.parquet') s USING (species_code)
  GROUP BY ALL
) TO 'build/species-ranges.geojson' WITH (FORMAT gdal, DRIVER 'GeoJSON');
