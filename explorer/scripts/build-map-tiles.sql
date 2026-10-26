-- Map geometry for the explorer, built from the published Calflora range hex.
--   h7-grid.geojson         every H3 res-7 cell that holds part of any species' range;
--                           the theme maps colour these by `h7` (hex string) from zoom 7 in.
--                           Res 7 is the LOCA2 climate grid, the finest the day counts have.
--   h6-grid.geojson         their res-6 parents, keyed by `h6`, drawn below zoom 7, where res-7
--                           cells are a pixel or two wide and slow to draw.
-- Run with: bash scripts/build-map-tiles.sh
INSTALL h3 FROM community; LOAD h3; LOAD spatial;
SET s3_endpoint = 's3-west.nrp-nautilus.io'; SET s3_url_style = 'path';
SET geometry_always_xy = true;

CREATE TABLE cells AS
SELECT DISTINCT h7
FROM read_parquet('s3://public-ca-ccca5/calflora-ranges/hex/h0=*/data_0.parquet', hive_partitioning = true);

COPY (
  SELECT h3_h3_to_string(h7) AS h7, ST_GeomFromText(h3_cell_to_boundary_wkt(h7)) AS geom
  FROM cells
) TO 'build/h7-grid.geojson' WITH (FORMAT gdal, DRIVER 'GeoJSON');

COPY (
  SELECT h3_h3_to_string(h6) AS h6, ST_GeomFromText(h3_cell_to_boundary_wkt(h6)) AS geom
  FROM (SELECT DISTINCT h3_cell_to_parent(h7, 6) AS h6 FROM cells)
) TO 'build/h6-grid.geojson' WITH (FORMAT gdal, DRIVER 'GeoJSON');
