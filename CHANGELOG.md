# Changelog

## 0.2.0 (2026-11-13)

- Result table also written as a shapefile and as an Excel workbook.
- Classes at all four levels (`cls_<year>_L<k>`) and number of changes per level
  (`n_changes_L<k>`) written in every run.
- Result tables named after the sample layer, the series and the comparison level:
  `<samples>_COS_<series>_L<level>`
  (`.xlsx`, `.csv`, `.gpkg`, `.shp`). Shapefile field names are shortened to 10 characters
  with a fixed mapping, listed in the data dictionary.
- Affiliation, DOI and badges added to the metadata and README.

## 0.1.0 (2026-11-13)

First release.

- Identification of COS editions by the DGT file-name convention and a product catalogue.
- Series 1 (COS1995v2, COS2007v3, COS2010v2, COS2015v2, COS2018v2), with recoding of the
  2007–2018 classes to the COS1995 nomenclature (DGT 2022, Anexo 3).
- Series 2 (COS2018v4, COS2025v1); COS2023v1 excluded as not comparable.
- Point-in-polygon assignment, distance to the polygon boundary, class at comparison levels 1–4.
- Metrics per sample: trajectory, number of changes, stability index, modal persistence,
  time-weighted persistence, year of last change, flip-flop, boundary flag, samples per polygon.
- Interpretation category per sample and summary table.
- Transition matrices, optional group summary, provenance manifest with SHA-256 checksums and
  data dictionary per run.
- ArcGIS Pro toolbox (runs the analysis in a separate Python process) and command-line interface.
- Documentation of the methods, with sources, and an interpretation guide.
