<p align="center"><img src="docs/img/logo.png" alt="dgt-cos-trajectories logo" width="180"></p>

# dgt-cos-trajectories

Land-use/land-cover history of point samples from the *Carta de Uso e Ocupação do Solo* (COS) of
mainland Portugal, published by the Direção-Geral do Território (DGT).

Given a layer of sample points, the tool reads the COS class at each point in every edition and
returns one row per sample with the class history, stability metrics and an interpretation
category. It runs as an ArcGIS Pro toolbox or from the command line.

| Document | Content |
|---|---|
| This page | What the tool does, how to run it, what it writes |
| [docs/METHODS.md](docs/METHODS.md) | Mathematical definition of every calculation |
| [docs/INTERPRETATION.md](docs/INTERPRETATION.md) | How to read and use the results |

![COS polygons and sample points of one demonstration grid in 1995 and 2025](docs/img/demo_map.png)

*Figure 1. Demonstration grid C (synthetic points, 100 m spacing) over COS1995 (Series 1) and
COS2025 (Series 2), in merged classes. Marker fill: interpretation category of each sample.*

## 1. Three products

| `--series` | Editions | Period | Classes | Purpose |
|---|---|---|---|---|
| `S1` | COS1995v2, COS2007v3, COS2010v2, COS2015v2, COS2018v2 | 1995–2018 | COS1995 nomenclature (44 classes) | Long history within one consistent series |
| `S2` | COS2018v4, COS2025v1 | 2018–2025 | Series 2 nomenclature (102 classes) | Recent change at the highest thematic and geometric detail |
| `S1+S2` | COS1995v2 … COS2015v2 (S1), then COS2018v4, COS2025v1 (S2) | 1995–2025 | Merged classes | One history over the whole period |

Notes:

- **`S1`.** COS1995 has fewer classes than the later editions. The 2007–2018 classes are recoded to
  the COS1995 classes with the DGT correspondence table (DGT 2022, Anexo 3), so that a code means
  the same in all five editions. Without COS1995 in the folder, the 83-class nomenclature is used.
- **`S2`.** COS2023v1 is excluded: it follows an earlier Series 2 specification in which several
  codes denote other classes, and DGT states that only COS2018v4 and COS2025v1 are comparable.
- **`S1+S2`.** The two series have different nomenclatures. Classes that DGT relates to each other
  (DGT 2026, Anexo 3) are grouped into merged classes, in which both series can be expressed
  ([METHODS 2.3](docs/METHODS.md#23-series-1--series-2-merged-classes)). DGT advises against
  comparing the two series, because definitions, production method and mapping unit differ. The
  tool therefore also reads the Series 1 map of 2018 and uses it to recognise apparent changes at
  2018 that are differences between the series
  ([INTERPRETATION 4](docs/INTERPRETATION.md#4-reading-an-s1s2-result)).

## 2. Running

### Requirements

The default ArcGIS Pro Python environment (`arcgispro-py3`: Python 3.13, geopandas, shapely, fiona,
pandas, numpy, pyproj) with no additional package. Outside ArcGIS,
`conda env create -f environment.yml` gives an equivalent environment.

### Data

1. Download the COS GeoPackages from DGT ([00_ZIP/README.md](00_ZIP/README.md)) and unzip them into
   `01_COS/` without renaming. Editions are identified by the DGT file name
   (`COS<year>v<version>[-S<series>]`) through [`cos_trajectories/catalog.json`](cos_trajectories/catalog.json).
2. Provide the samples as a point layer (shapefile or GeoPackage) with a unique identifier field,
   in any coordinate reference system.

### ArcGIS Pro

*Catalog → Toolboxes → Add Toolbox* → `COSTrajectories.pyt` → **COS land-use history of sample
points**. The analysis runs in a separate Python process of the active environment; messages
appear in the geoprocessing pane and the result layer is added to the map.

### Command line

```shell
python -m cos_trajectories --series S1 --samples 02_Amostras/samples.shp --id-field SAMPLE_ID
python -m cos_trajectories --series S1+S2 --samples examples/demo_points.gpkg \
    --samples-layer demo_points --id-field SAMPLE_ID --group-field GRID --run-id demo
```

With ArcGIS Pro installed, `python` is
`"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"`.

### Parameters

| Toolbox parameter | CLI option | Default | Description |
|---|---|---|---|
| COS folder | `--cos-dir` | `01_COS` | Folder with the unzipped COS GeoPackages. |
| COS series | `--series` | required | `S1`, `S2` or `S1+S2`. |
| Sample points | `--samples`, `--samples-layer` | required | Point layer; shapefile or GeoPackage layer. |
| Sample ID field | `--id-field` | required | Unique, non-empty identifier. |
| Group field | `--group-field` | none | Adds `group_summary.csv`. |
| Comparison level | `--level` | most detailed | 1 to 4 for `S1` and `S2`; 1 or 4 (merged classes) for `S1+S2`. |
| Boundary threshold | `--threshold` | 25 | Metres; sets `near_boundary`. |
| Output folder | `--out-dir` | `03_Resultados` | One subfolder per run; never overwritten. |
| (none) | `--run-id` | start time | Name of the run subfolder. |
| (none) | `--no-hash` | off | Skip the SHA-256 checksums of the COS files. |

Invalid input (non-point geometry, duplicated or empty identifiers, missing CRS, unavailable
level, fewer than two editions) stops the run with a message; exit code 2.

## 3. Outputs

Written to `<output folder>/<run id>/`:

| File | Content |
|---|---|
| `samples_cos_history.csv` | One row per sample. |
| `samples_cos_history.gpkg` | Same table with point geometry (EPSG:3763). |
| `interpretation_summary.csv` | Number and share of samples per interpretation category. |
| `transitions_<a>_<b>.csv` | Samples per class in edition `a` (rows) and edition `b` (columns), consecutive editions. |
| `group_summary.csv` | One row per group, if a group field is given. |
| `data_dictionary.md` | Columns, classes, correspondence tables and limitations of the run. |
| `manifest.json` | Parameters, input files with SHA-256, software versions, counts. |
| `run.log` | Processing messages. |

### Fields of `samples_cos_history`

`<year>` is each edition year of the trajectory. Formulas: [docs/METHODS.md](docs/METHODS.md).

| Field | Description | METHODS |
|---|---|---|
| *identifier* | Sample identifier, with the name it has in the input layer. | |
| `cls_<year>` | Class code at the comparison level. Empty if no polygon contains the point. | 2, 3.3 |
| `label_<year>` | DGT class designation. | |
| `poly_<year>` | Polygon identifier `<year>_<DGT ID>`. | 3.3 |
| `dist_<year>` | Distance from the point to the polygon boundary (m). | 3.4 |
| `cls_2018_S1` | `S1+S2` only: class of the Series 1 map of 2018 (check, not part of the trajectory). | 5.2 |
| `series_check_2018` | `S1+S2` only: 1 if the Series 1 and Series 2 maps of 2018 give the same class. | 5.2 |
| `trajectory` | Classes in time order separated by <code>&#124;</code>; `NA` if missing. | 4.1 |
| `n_missing` | Editions without a polygon at the point. | 4.1 |
| `stable` | 1 if the class never changes. | 4.3 |
| `n_changes` | Number of changes between consecutive editions. | 4.2 |
| `stability_index` | Share of intervals without change. | 4.4 |
| `modal_persistence` | Share of editions in the most frequent class. | 4.5 |
| `time_weighted_persistence` | Share of the years without change. | 4.6 |
| `last_change_year` | Year of the edition in which the last change is observed. | 4.7 |
| `flip_flop` | 1 if the class goes A → B → A in consecutive editions. | 4.8 |
| `min_boundary_dist_m` | Smallest `dist_<year>`. | 4.9 |
| `near_boundary` | 1 if `min_boundary_dist_m` is below the threshold. | 4.9 |
| `pts_in_poly_<last year>` | Samples sharing the polygon of the last edition. | 4.10 |
| `interpretation` | `stable`, `change`, `near_boundary`, `flip_flop`, `series_difference` or `insufficient_data`. | 6 |

### `interpretation`

| Category | Meaning |
|---|---|
| `stable` | Same class in every edition. |
| `change` | Class changed; no artefact indicator applies. |
| `near_boundary` | Class changed, but the point is near a polygon boundary: possibly a difference in delineation. |
| `flip_flop` | Class changed and returned: probable interpretation artefact. |
| `series_difference` | `S1+S2` only: the only change is at the junction between series and Series 1 shows no change. |
| `insufficient_data` | Fewer than two editions with a class. |

Use and caveats of each category: [docs/INTERPRETATION.md](docs/INTERPRETATION.md).

## 4. Example

[`examples/demo_points.gpkg`](examples/demo_points.gpkg) holds 75 synthetic points: three 5 × 5
grids with 100 m spacing at arbitrary locations. They are not sampling locations of any study. The
second command of section 2 gives:

`interpretation_summary.csv`:

| interpretation | n_samples | share |
|---|---|---|
| stable | 26 | 0.347 |
| change | 27 | 0.360 |
| near_boundary | 17 | 0.227 |
| flip_flop | 4 | 0.053 |
| series_difference | 1 | 0.013 |
| insufficient_data | 0 | 0.000 |

![Class of each demonstration sample in every edition, with its interpretation](docs/img/demo_trajectories.png)

*Figure 2. Merged class of the 75 demonstration samples in each edition of the `S1+S2` trajectory
(colour: level-1 class), the Series 1 map of 2018 used as a check (paler column) and the
interpretation category. Grid A: annual crops (`2.m1`) converted to olive groves (`2.m4`). Grid B:
maritime pine (`5.1.2.1`) replaced by eucalyptus (`5.1.1.6`). Grid C: urban expansion over pasture
and cropland.*

Selected rows of `samples_cos_history.csv`:

| SAMPLE_ID | `trajectory` | `cls_2018_S1` | `series_check_2018` | `n_changes` | `time_weighted_persistence` | `last_change_year` | `min_boundary_dist_m` | `interpretation` |
|---|---|---|---|---|---|---|---|---|
| B7 | <code>5.1.2.1&#124;5.1.2.1&#124;5.1.2.1&#124;5.1.2.1&#124;5.1.2.1&#124;5.1.2.1</code> | 5.1.2.1 | 1 | 0 | 1.0 | | 52.57 | stable |
| A1 | <code>2.m1&#124;2.m1&#124;2.m1&#124;2.m1&#124;2.m4&#124;2.m4</code> | 2.m4 | 1 | 1 | 0.9 | 2018 | 157.12 | change |
| B3 | <code>5.1.2.1&#124;5.1.1.6&#124;5.1.1.6&#124;5.1.1.6&#124;5.1.1.6&#124;5.1.1.6</code> | 5.1.1.6 | 1 | 1 | 0.6 | 2007 | 3.08 | near_boundary |
| C3 | <code>3.1&#124;3.1&#124;1&#124;1&#124;6.1.1.1&#124;1</code> | 1 | 0 | 3 | 0.5667 | 2025 | 2.19 | flip_flop |
| B10 | <code>5.1.2.1&#124;5.1.2.1&#124;5.1.2.1&#124;5.1.2.1&#124;5.1.1.6&#124;5.1.1.6</code> | 5.1.2.1 | 0 | 1 | 0.9 | 2018 | 25.23 | series_difference |

- A1: the change at 2018 is shown by both series (`cls_2018_S1` = `2.m4`), far from any boundary.
- B3: a change in 1995–2007 at 3 m from a boundary; it may be a difference in delineation.
- C3: artificial in Series 1 since 2010, shrubland in the Series 2 map of 2018 and artificial again
  in 2025; the shrubland step is not supported by Series 1.
- B10: maritime pine in every Series 1 edition including 2018, eucalyptus in Series 2; the two
  series classify the stand differently, so no change is inferred.

`group_summary.csv` (selected columns):

| GRID | `n_points` | `n_polygons_2025` | `prop_changed` | `prop_near_boundary` | `prop_change_supported` |
|---|---|---|---|---|---|
| A | 25 | 2 | 1.00 | 0.04 | 0.96 |
| B | 25 | 7 | 0.36 | 0.60 | 0.12 |
| C | 25 | 14 | 0.60 | 0.88 | 0.00 |

In grid A all 25 points changed, but they lie in 2 polygons: two observations of change, not 25.
In grid C, 60 % of the points changed and none of the changes is supported, because the points
lie close to polygon boundaries in a fragmented urban fabric.

The figures are reproduced with `python tools/make_readme_figures.py 03_Resultados/demo 01_COS`.

## 5. Limitations

- COS maps units of at least 1 ha (0.5 ha in COS2018v4/COS2025v1) and 20 m wide; the class at a
  point is that of the mapped unit.
- Nothing before 1995 (`S1`, `S1+S2`) or 2018 (`S2`) is represented; a change is located only to
  the interval between two editions.
- Differences in polygon delineation between editions produce apparent changes near boundaries.
- Thematic accuracy of COS is ≥ 85 % by specification; classification errors are not modelled.
- Samples in the same polygon share its class and are not independent observations; transition
  matrices are counts of samples, not areas.
- `S1+S2`: DGT states that the series should not be compared. The merged trajectory is an
  approximation, merged classes are coarser than either nomenclature, and changes at 2018 are the
  least reliable.
- Only point samples are supported. Samples spread over a large extent require most of each
  national layer to be read.

## 6. Software

```text
cos_trajectories/        core package (no arcpy)
  catalog.json           COS products, nomenclatures, correspondence tables
  nomenclature/*.csv     class code -> designation
  catalog.py             identification of editions, selection, harmonisation, merged classes
  io.py                  all file reading and writing
  core.py                spatial assignment and run pipeline
  metrics.py             metrics, interpretation, transition matrices, group summary
  report.py              manifest and data dictionary
  cli.py                 command-line interface
COSTrajectories.pyt      ArcGIS Pro toolbox (runs the CLI in a subprocess)
docs/                    methods, interpretation guide, figures
tools/                   maintainer scripts (nomenclature extraction, demonstration data, figures)
tests/                   pytest suite on synthetic GeoPackages
```

| Function | Purpose | METHODS |
|---|---|---|
| `catalog.discover` | Identify COS layers by file name and check their fields. | |
| `catalog.select` | Editions and common nomenclature of one series. | 2.2 |
| `catalog.select_merged`, `catalog.merged_classes` | Editions and merged classes for `S1+S2`. | 2.3, 5.1 |
| `catalog.recode` | Truncation of a code to a level. | 2.1 |
| `core.prepare_samples` | Validation of the sample layer. | |
| `core.join_edition` | Containing polygon and distance to its boundary. | 3 |
| `core.run` | Full pipeline. | |
| `metrics.sample_metrics`, `metrics.compute_metrics` | Metrics per sample. | 4 |
| `metrics.interpret`, `metrics.interpret_table` | Interpretation category. | 5.3, 6 |
| `metrics.transition_matrix`, `metrics.group_summary` | Aggregated tables. | 7 |
| `report.build_manifest`, `report.data_dictionary` | Provenance and documentation of a run. | |

Tests: `python -m pytest` (synthetic data; runs without ArcGIS). Adding a COS edition: add it to
`catalog.json`, unzip it into `01_COS/`, run `python tools/extract_nomenclature.py 01_COS`, run
the tests.

## 7. References, citation and licence

- Direção-Geral do Território (2022). *Especificações técnicas da Carta de Uso e Ocupação do Solo
  (COS) de Portugal Continental para 1995, 2007, 2010, 2015 e 2018*. Relatório Técnico.
  <https://www.dgterritorio.gov.pt/sites/default/files/documentos-publicos/ET-COS-1995-2007-2010-2015-2018-v1.pdf>
- Direção-Geral do Território (2026). *Especificações técnicas da Série 2 da Carta de Uso e
  Ocupação do Solo (COS) de Portugal Continental*. Relatório Técnico.
- Direção-Geral do Território. *Carta de Uso e Ocupação do Solo (COS) – Série 2 – (2018v4 – 2025v1)*.
  <https://dados.gov.pt/pt/datasets/carta-de-uso-e-ocupacao-do-solo-cos-serie-2-2018v4-2025v1>

COS data © Direção-Geral do Território; not distributed with this repository. The figures are
derived from COS1995v2, COS2007v3, COS2010v2, COS2015v2, COS2018v2, COS2018v4 and COS2025v1.

Citation: [CITATION.cff](CITATION.cff). Licence: [Apache License 2.0](LICENSE).
