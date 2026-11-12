# Interpreting the results

A guide to reading `samples_cos_history.csv` and the files written with it. Definitions and
formulas are in [METHODS.md](METHODS.md).

## 1. Start with `interpretation`

Each sample receives one category. It answers two questions at once: did the COS class at the
point change, and can the change be trusted?

| `interpretation` | What the maps show | How to use the sample |
|---|---|---|
| `stable` | Same class in every edition. | Unchanged land use over the period covered. |
| `change` | The class changed, the point is not near a polygon boundary, and there is no A → B → A pattern. | Changed land use. This is the group to use as evidence of change. |
| `near_boundary` | The class changed, but in at least one edition the point is closer to a polygon boundary than the threshold (default 25 m). | Uncertain. The boundary may have been drawn differently between editions. Check on imagery, or analyse as a separate group. |
| `flip_flop` | The class went A → B → A in consecutive editions. | Uncertain. The intermediate class is probably a photo-interpretation artefact; the land use is probably A throughout. |
| `insufficient_data` | The point is inside a COS polygon in fewer than two editions. | Exclude from change analysis. |

`interpretation_summary.csv` gives the number and share of samples in each category, and the same
table opens `data_dictionary.md`.

## 2. Then read the detail

| Question | Column |
|---|---|
| Which classes, in which order? | `trajectory`, and `cls_<year>` / `label_<year>` |
| When did the last change occur? | `last_change_year` (the change occurred between the previous edition and this year) |
| How many times did the class change? | `n_changes` |
| For what share of the period was the class unchanged? | `time_weighted_persistence` |
| How close is the point to a boundary? | `min_boundary_dist_m`, `dist_<year>` |
| How many samples share the polygon? | `pts_in_poly_<last year>`, `poly_<year>` |

Two metrics look alike and answer different questions:

- `stability_index` counts changes per interval between editions, whatever their length.
- `time_weighted_persistence` weights each interval by its length in years. In Series 1 the first
  interval is 12 years (1995–2007) and the others 3 to 5 years, so one change in 1995–2007 gives
  0.48 while one change in 2015–2018 gives 0.87, with the same `stability_index` of 0.75.

## 3. Choosing the series

| Mode | Period | Classes | Use when |
|---|---|---|---|
| `S1` | 1995–2018 (5 editions) | COS1995 nomenclature, 44 classes, 1 ha mapping unit | The long history matters. |
| `S2` | 2018–2025 (2 editions) | 102 classes, 0.5 ha mapping unit | Recent change and the most detailed classes are needed. |

The two series are not comparable (DGT 2026): class definitions, production method and mapping
unit differ. Both include a map of 2018, and the two maps of 2018 frequently give different
classes for the same place. For this reason the tool does not join them.

To cover 1995–2025, run both modes and join the two tables by the sample identifier. Read them
as two histories:

- a difference between the `S1` class of 2018 and the `S2` class of 2018 is not a change;
- do not count a change from the last `S1` class to the first `S2` class;
- metrics and `interpretation` of one run say nothing about the period of the other.

## 4. Common mistakes

- **Counting every changed sample as a land-use change.** Use `interpretation = change`; treat
  `near_boundary` and `flip_flop` as uncertain.
- **Treating samples as independent.** Samples in the same polygon have the same class by
  construction. Twenty changed points in one polygon are one observation of change. Check
  `pts_in_poly` and, with a group field, `n_polygons_<year>` in `group_summary.csv`.
- **Reading transition matrices as areas.** They count samples.
- **Reading the class as the land use at the exact point.** COS maps units of at least 1 ha
  (0.5 ha in COS2018v4 and COS2025v1). A small feature at the point is absorbed into the
  surrounding class.
- **Assuming nothing happened before the first edition.** The history starts in 1995 (`S1`) or
  2018 (`S2`).
- **Comparing an `S1` result with an `S2` result as if they were one series.** See section 3.
- **Dating a change to a year.** `last_change_year = 2007` means between 1995 and 2007.

## 5. A possible analysis sequence

1. Open `interpretation_summary.csv`: how many samples are stable, changed, uncertain.
2. Join `samples_cos_history.csv` to the sample table by the identifier.
3. Use `interpretation` as a grouping factor, keeping `stable` and `change` as the reliable groups.
4. Within `change`, group by `trajectory` or by the first and last class.
5. Account for shared polygons (`poly_<last year>`) when samples are treated as replicates.
6. Report the series, comparison level and boundary threshold of the run; they are in
   `manifest.json`.
