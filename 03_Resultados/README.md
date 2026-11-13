# 03_Resultados: outputs

Each run writes a subfolder named by its start time (`YYYYMMDD-HHMMSS`) or `--run-id`, with
the result table as `<samples>_COS_<series>` in four formats (`.xlsx`, `.csv`, `.gpkg`, `.shp`),
`interpretation_summary.csv`, `transitions_<a>_<b>.csv`,
`group_summary.csv` (if a group field is given), `manifest.json`, `data_dictionary.md` and
`run.log`. A run never overwrites an existing subfolder.

Everything in this folder except this file is git-ignored.
