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
| `series_difference` | `S1+S2` only. The only change is between the last Series 1 edition and the first Series 2 edition, and the Series 1 map of that year shows no change. | Treat as unchanged. Series 1 and Series 2 classify the place differently. |
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
| `S1` | 1995–2018 (5 editions) | COS1995 nomenclature, 44 classes | The long history matters and one consistent series is required. |
| `S2` | 2018–2025 (2 editions) | 102 classes, 0.5 ha mapping unit | Recent change and the most detailed classes are needed. |
| `S1+S2` | 1995–2025 (6 editions) | Merged classes (coarser) | One history over the whole period is needed and the junction caveat below is acceptable. |

`S1` and `S2` are the products that DGT considers internally consistent. `S1+S2` joins them.

## 4. Reading an `S1+S2` result

The trajectory is 1995, 2007, 2010, 2015 from Series 1, then 2018 and 2025 from Series 2, in merged
classes. Three things are specific to this mode.

**Merged classes.** The two series use different class lists. Classes that DGT relates to each
other are grouped, so that a code means the same in every edition. The price is detail:

- with COS1995 included, all artificial surfaces are one class (`1`) and all pastures one class (`3.1`);
- the Series 2 orchard and olive types (low density, high density, hedge) become one class each;
- codes ending in `.m<n>` group several Series 2 classes; the `label_<year>` column and the class
  table of `data_dictionary.md` list them;
- codes ending in `(S1)` are Series 1 classes with no Series 2 counterpart (complex cultivation
  mosaics, agriculture with natural areas, mixed agroforestry, intertidal flats). A point in such
  a class always appears to change at 2018.

**The junction.** DGT advises against comparing the two series: definitions, production method
and minimum mapping unit differ. The step from 2015 (Series 1) to 2018 (Series 2) therefore mixes
real change with differences between the series. To separate them, the tool also reads the Series 1
map of 2018:

- `cls_2018_S1` is the class of the Series 1 map of 2018;
- `series_check_2018` is 1 if it equals `cls_2018`, the class of the Series 2 map of 2018.

| 2015 (S1) | 2018 (S1) | 2018 (S2) | Reading | `interpretation` |
|---|---|---|---|---|
| A | A | A | No change; the series agree. | `stable` (if no other change) |
| A | A | B | Series 1 sees no change; Series 2 names the place differently. | `series_difference` (if no other change) |
| A | B | B | Both series show B in 2018: change between 2015 and 2018. | `change`, or `near_boundary` |
| A | B | C | Series 1 shows a change; the series disagree about the new class. | `change`, or `near_boundary`; read `cls_2018_S1` as well |

**What remains uncertain.** `series_check_2018 = 1` does not prove that a later comparison is
exact: a Series 1 class and a Series 2 class in the same merged class may still have different
definitions. Changes at 2018 are the least reliable in the table; changes within 1995–2015 and
2018–2025 are within one series each.

## 5. Common mistakes

- **Counting every changed sample as a land-use change.** Use `interpretation = change`; treat
  `near_boundary` and `flip_flop` as uncertain.
- **Treating samples as independent.** Samples in the same polygon have the same class by
  construction. Twenty changed points in one polygon are one observation of change. Check
  `pts_in_poly` and, with a group field, `n_polygons_<year>` in `group_summary.csv`.
- **Reading transition matrices as areas.** They count samples.
- **Reading the class as the land use at the exact point.** COS maps units of at least 1 ha
  (0.5 ha in COS2018v4 and COS2025v1). A small feature at the point is absorbed into the
  surrounding class.
- **Assuming nothing happened before the first edition.** The history starts in 1995 (`S1`,
  `S1+S2`) or 2018 (`S2`).
- **Dating a change to a year.** `last_change_year = 2007` means between 1995 and 2007.

## 6. A possible analysis sequence

1. Open `interpretation_summary.csv`: how many samples are stable, changed, uncertain.
2. Join `samples_cos_history.csv` to the sample table by the identifier.
3. Use `interpretation` as a grouping factor, keeping `stable` and `change` as the reliable groups.
4. Within `change`, group by `trajectory` or by the first and last class.
5. Account for shared polygons (`poly_<last year>`) when samples are treated as replicates.
6. Report the series, comparison level and boundary threshold of the run; they are in
   `manifest.json`.
