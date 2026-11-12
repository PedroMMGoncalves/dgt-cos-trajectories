# 01_COS: unzipped COS GeoPackages (tool input)

Unzip each `*-gpkg.zip` from `00_ZIP/` here, without renaming the `.gpkg` files: the tool
identifies each edition by the DGT file name (`COS<year>v<version>[-S<series>].gpkg`, any case),
e.g. `COS2018v2-S1.gpkg`, `cos2025v1.gpkg`. Files that do not follow the convention are ignored.

Known products are listed in `cos_trajectories/catalog.json`. Keep only one version per
edition and series (e.g. not both COS2018v1 and COS2018v2 of Series 1).

Reading GeoPackages through the zip (`/vsizip/`) is not supported; unzip first.

Everything in this folder except this file is git-ignored.
