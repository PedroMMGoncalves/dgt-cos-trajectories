# 03_Resultados: outputs

Each run writes a subfolder named by its start time (`YYYYMMDD-HHMMSS`) or `--run-id`, with
`samples_cos_history.csv`, `samples_cos_history.gpkg`, `transitions_<a>_<b>.csv`,
`group_summary.csv` (if a group field is given), `manifest.json`, `data_dictionary.md` and
`run.log`. A run never overwrites an existing subfolder.

Everything in this folder except this file is git-ignored.
