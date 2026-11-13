# Methods: mathematical definitions

This document defines every quantity computed by `cos_trajectories`. Section numbers are cited in
the README. Each definition names the output column and the function that implements it.

## 1. Notation

| Symbol | Meaning |
|---|---|
| $`p`$ | a sample point; $`n`$ is the number of samples |
| $`t = 1,\dots,T`$ | the COS editions of the trajectory, in time order |
| $`y_t`$ | reference year of edition $`t`$, with $`y_1 < \dots < y_T`$ |
| $`P_t(p)`$ | the polygon of edition $`t`$ assigned to $`p`$ (section 3) |
| $`k_t(p)`$ | level-4 class code of $`P_t(p)`$ as stored by DGT |
| $`c_t(p)`$ | class of $`p`$ at edition $`t`$ after harmonisation, at the comparison level; $`\varnothing`$ if no polygon contains $`p`$ |
| $`\mathbb{1}[\cdot]`$ | indicator: 1 if the condition holds, 0 otherwise |

The subscript $`p`$ is omitted where one sample is considered.

## 2. Classes

### 2.1 Hierarchical truncation

A COS code is a sequence of up to four elements, $`k = (k^1, k^2, k^3, k^4)`$, written `k1.k2.k3.k4`.
The class at level $`L`$ is the prefix

```math
\mathrm{trunc}_L(k) = (k^1,\dots,k^L), \qquad L \in \lbrace 1,2,3,4 \rbrace .
```

Function: `catalog.recode`.

### 2.2 Series 1: recoding to the COS1995 nomenclature

Let $`K_{07}`$ be the 83 level-4 classes of COS2007–2018 and $`K_{95}`$ the 44 classes of COS1995.
DGT (2022, Anexo 3) defines a many-to-one correspondence

```math
f : K_{07} \to K_{95} .
```

When COS1995 is among the editions, the harmonised code is

```math
h_t(p) = \begin{cases} k_t(p) & \text{edition } t \text{ uses } K_{95} \\ f(k_t(p)) & \text{edition } t \text{ uses } K_{07} \end{cases}
```

and $`c_t(p) = \mathrm{trunc}_L(h_t(p))`$. Without COS1995, $`h_t = k_t`$. In Series 2 runs (COS2018v4,
COS2025v1) all editions share one nomenclature and $`h_t = k_t`$.

Function: `catalog.Selection.harmonise`.

### 2.3 Series 1 and Series 2 are not combined

DGT (2026) states that maps of different series should not be compared: Series 2 changed the base
concepts of the classification, the structure of the nomenclature and the geometric detail
(minimum mapping unit 0.5 ha). Each run therefore uses one series, and no quantity in this
document involves classes of both series.

## 3. Spatial assignment

### 3.1 Coordinates

Samples are transformed to the coordinate reference system of the COS layers (ETRS89/PT-TM06,
EPSG:3763) with PROJ. All distances are planar distances in metres in that system.

### 3.2 Polygons read

Let $`[x_{\min}, x_{\max}] \times [y_{\min}, y_{\max}]`$ be the bounding box of all samples. Only
polygons whose envelope intersects the box enlarged by $`\beta = 100`$ m are read. This does not
affect any result: the polygon containing a sample always intersects the box.

### 3.3 Containing polygon

```math
\mathcal{P}_t(p) = \lbrace P \in \text{edition } t : p \in P \rbrace
```

where $`P`$ is closed (its boundary belongs to it). COS is a partition, so
$`\lvert \mathcal{P}_t(p) \rvert = 1`$ for an interior point; $`\lvert \mathcal{P}_t(p) \rvert > 1`$
only if $`p`$ lies exactly on a shared edge; $`\lvert \mathcal{P}_t(p) \rvert = 0`$ outside the map.

```math
P_t(p) = \arg\min_{P \in \mathcal{P}_t(p)} \mathrm{ID}(P), \qquad c_t(p) = \varnothing \ \text{ if } \ \mathcal{P}_t(p) = \varnothing .
```

Columns: `cls_<year>`, `label_<year>`, `poly_<year>` (`<year>_<ID>`). The number of points with
$`\lvert \mathcal{P}_t \rvert > 1`$ is reported per edition.

### 3.4 Distance to the polygon boundary

```math
d_t(p) = \min_{q \in \partial P_t(p)} \lVert p - q \rVert_2
```

where $`\partial P`$ is the union of the exterior ring and all interior rings. Column:
`dist_<year>` (rounded to 0.01 m).

Function: `core.join_edition`.

## 4. Metrics per sample

Let $`c_t`$ be the class of the sample at edition $`t = 1,\dots,T`$ and $`\Delta_t = y_t - y_{t-1}`$
the number of years between editions $`t-1`$ and $`t`$. Editions in which the point has no class
are left out, and $`T`$ then counts the editions that remain. With fewer than two such editions
the metrics 4.2 to 4.7 are empty.

### 4.1 Trajectory

```math
\text{trajectory} = c_1 \mid c_2 \mid \dots \mid c_T
```

The sequence of classes in time order (`NA` where there is no class). `n_missing` is the number of
editions without a class.

### 4.2 Simple stability

```math
S = \begin{cases} 1 & \text{if } c_1 = c_2 = \dots = c_T \\ 0 & \text{otherwise} \end{cases}
```

Column `stable`. The easiest to communicate, but it keeps no information about the changes.

### 4.3 Number of changes and stability index

```math
N = \sum_{t=2}^{T} \mathbb{1}\left[ c_t \neq c_{t-1} \right], \qquad SI = 1 - \frac{N}{T - 1}
```

Columns `n_changes` and `stability_index`. $`SI = 1`$ means the point never changed; $`SI = 0`$
means it changed at every edition.

### 4.4 Modal persistence

```math
P = \max_{k} \ \frac{1}{T} \sum_{t=1}^{T} \mathbb{1}\left[ c_t = k \right]
```

Column `modal_persistence`: the share of editions spent in the most frequent class. It separates
cases that $`N`$ confuses. The trajectories `A B A B A` and `A B C D E` both have $`N = 4`$; in the
first $`P = 3/5 = 0.6`$, in the second $`P = 1/5 = 0.2`$.

### 4.5 Time-weighted persistence

The intervals between editions are unequal: 12, 3, 5 and 3 years in Series 1
(1995 → 2007 → 2010 → 2015 → 2018). A change between 1995 and 2007 summarises 12 years, one
between 2015 and 2018 only 3. To take this into account:

```math
P_w = \frac{\sum_{t=2}^{T} \Delta_t \cdot \mathbb{1}\left[ c_t = c_{t-1} \right]}{\sum_{t=2}^{T} \Delta_t}
```

Column `time_weighted_persistence`: the fraction of the total period (23 years in Series 1) during
which the point stayed in the same class. An interval counts as unchanged when the classes at its
two ends are equal; the date of a change inside an interval is unknown. With equal intervals,
$`P_w = SI`$.

Example with the Series 1 intervals. One change in 1995–2007 (`B A A A A`):

```math
SI = 1 - \tfrac{1}{4} = 0.75, \qquad P_w = \frac{3 + 5 + 3}{23} = 0.478
```

One change in 2015–2018 (`A A A A B`):

```math
SI = 1 - \tfrac{1}{4} = 0.75, \qquad P_w = \frac{12 + 3 + 5}{23} = 0.870
```

### 4.6 Year of the last change

```math
y^{*} = \max \lbrace y_t : c_t \neq c_{t-1} \rbrace
```

Column `last_change_year`; empty if $`N = 0`$. The change occurred between $`y_{t-1}`$ and $`y_t`$,
not necessarily in year $`y_t`$.

### 4.7 Flip-flop

```math
F = \begin{cases} 1 & \text{if } c_{t-1} \neq c_t \ \text{ and } \ c_{t+1} = c_{t-1} \ \text{ for some } t \\ 0 & \text{otherwise} \end{cases}
```

Column `flip_flop`: a return trip A → B → A. In COS, a return trip between close editions often
indicates an interpretation error in one edition and not a real change.

### 4.8 Distance to the boundary

```math
d_{\min} = \min_{t} d_t, \qquad B = \begin{cases} 1 & \text{if } d_{\min} < \tau \\ 0 & \text{otherwise} \end{cases}
```

Columns `min_boundary_dist_m` and `near_boundary`, with $`d_t`$ from section 3.4 and $`\tau`$ the
boundary threshold (default 25 m, of the order of the COS minimum distance between lines, 20 m,
plus its positional accuracy, 5.5 m). A change at a point with $`B = 1`$ may be a difference in
how the boundary was drawn.

### 4.9 Samples per polygon

```math
\pi(p) = \left\lvert \lbrace q : P_T(q) = P_T(p) \rbrace \right\rvert
```

Column `pts_in_poly_<last year>`: the number of samples in the same polygon as $`p`$ in the last
edition. Samples in one polygon have the same class by construction and are not independent
observations.

No composite index is computed: each metric answers a different question.

Functions: `metrics.sample_metrics`, `metrics.compute_metrics`.

## 5. Interpretation category

Column `interpretation`; the first rule that applies:

| Order | Condition | Category |
|---|---|---|
| 1 | fewer than two editions with a class | `insufficient_data` |
| 2 | $`N = 0`$ | `stable` |
| 3 | $`F = 1`$ | `flip_flop` |
| 4 | $`B = 1`$ | `near_boundary` |
| 5 | otherwise | `change` |

The categories are mutually exclusive and exhaustive. `change` therefore means: at least one
change, no return trip, and the point at least $`\tau`$ from every polygon boundary in every edition.

Functions: `metrics.interpret`, `metrics.interpret_table`.

## 6. Aggregated outputs

**6.1 Transition matrix** (`transitions_<a>_<b>.csv`) between consecutive editions $`t-1`$ and
$`t`$, with $`\varnothing`$ kept as the category `NA`:

```math
M_{ab} = \left\lvert \lbrace p : c_{t-1}(p) = a \ \wedge \ c_t(p) = b \rbrace \right\rvert, \qquad \sum_{a,b} M_{ab} = n .
```

The diagonal counts samples without change in the interval. These are counts of samples, not
estimates of area.

**6.2 Interpretation summary** (`interpretation_summary.csv`). For each category $`v`$:

```math
n_v = \left\lvert \lbrace p : \text{interpretation}(p) = v \rbrace \right\rvert, \qquad s_v = \frac{n_v}{n} .
```

**6.3 Group summary** (`group_summary.csv`), for a group $`G`$ of samples:

```math
n_G = \lvert G \rvert, \qquad
\text{n\_polygons}_t = \left\lvert \lbrace P_t(p) : p \in G \rbrace \right\rvert, \qquad
\text{n\_trajectories} = \left\lvert \lbrace \text{trajectory}(p) : p \in G \rbrace \right\rvert
```

```math
\text{prop\_changed} = \frac{\lvert \lbrace p \in G : N_p > 0 \rbrace \rvert}{\lvert \lbrace p \in G : m_p \geq 2 \rbrace \rvert}, \qquad
\text{prop\_near\_boundary} = \frac{1}{n_G} \sum_{p \in G} B_p, \qquad
\text{prop\_change\_supported} = \frac{\lvert \lbrace p \in G : \text{interpretation}(p) = \texttt{change} \rbrace \rvert}{n_G}
```

$`n_G / \text{n\_polygons}_t`$ is the mean number of samples per polygon: an indication of how
many independent observations of land use the group contains.

Functions: `metrics.transition_matrix`, `metrics.group_summary`.

## 7. Numerical conventions

- $`SI`$, $`P`$, $`P_w`$ and the proportions are rounded to 4 decimals; distances to 0.01 m.
- Rows are sorted by sample identifier in natural order (digit runs compared as integers:
  `A2` < `A10`); classes in matrices are sorted by code, `NA` last.
- File checksums in `manifest.json` are SHA-256.

## 8. Sources of the definitions

The quantities are of two kinds: those taken from the literature, and simple summaries defined for
this tool. The table states which is which. A definition marked "defined here" is not attributed
to the works cited beside it; those works are the related literature.

| Quantity | Section | Status | Source or related literature |
|---|---|---|---|
| Hierarchical classes, truncation | 2.1 | From the data specification | DGT (2022, 2026) |
| Recoding to the COS1995 nomenclature | 2.2 | From the data specification | DGT (2022), Anexo 3 |
| Series not combined | 2.3 | From the data specification | DGT (2026) |
| Point-in-polygon assignment, boundary, distance | 3.3, 3.4 | Standard geometric operations | Herring (2011) |
| Lowest-ID rule for points on a shared edge | 3.3 | Defined here | |
| Trajectory (sequence of classes per location) | 4.1 | From the literature | Mertens and Lambin (2000); Swetnam (2007) |
| Number of changes $`N`$ | 4.3 | From the literature | Pontius et al. (2017), who count the times the category of a unit changes across time intervals; Swetnam (2007) uses a turnover index |
| Simple stability $`S`$, stability index $`SI`$ | 4.2, 4.3 | Defined here, as normalisations of $`N`$ | Pontius et al. (2017) |
| Modal persistence $`P`$ | 4.4 | Defined here | Pontius et al. (2017) summarise the same aspect by the number of categories a unit occupies |
| Time-weighted persistence $`P_w`$ | 4.5 | Defined here | The weighting by interval duration follows the reasoning of Aldwaik and Pontius (2012), who express change per year so that intervals of unequal duration are comparable |
| Flip-flop $`F`$ | 4.7 | Defined here | Pontius and Lippitt (2006) and Pontius et al. (2017) on telling real change from map error |
| Boundary distance and `near_boundary` | 4.8 | Defined here | Threshold derived from the COS specification, DGT (2022, 2026); Pontius and Lippitt (2006) on map error as a cause of apparent change |
| Samples per polygon | 4.9 | Defined here | Hurlbert (1984) on non-independent replicates |
| Interpretation category | 5 | Defined here | Decision rule combining 4.3, 4.7 and 4.8 |
| Transition matrix; diagonal as persistence | 6.1 | From the literature | Pontius et al. (2004) |
| Counts of samples are not area estimates | 6.1 | From the literature | Olofsson et al. (2014) |
| Group proportions | 6.3 | Defined here | |

Intensity analysis (Aldwaik and Pontius 2012) is not computed: it applies to cross-tabulation
matrices that represent areas, which counts of clustered sample points do not.

## References

- Aldwaik, S. Z. and Pontius, R. G. Jr. (2012). Intensity analysis to unify measurements of size
  and stationarity of land changes by interval, category, and transition. *Landscape and Urban
  Planning*, 106(1), 103–114. <https://doi.org/10.1016/j.landurbplan.2012.02.010>
- Direção-Geral do Território (2022). *Especificações técnicas da Carta de Uso e Ocupação do Solo
  (COS) de Portugal Continental para 1995, 2007, 2010, 2015 e 2018*. Relatório Técnico.
  <https://www.dgterritorio.gov.pt/sites/default/files/documentos-publicos/ET-COS-1995-2007-2010-2015-2018-v1.pdf>
- Direção-Geral do Território (2026). *Especificações técnicas da Série 2 da Carta de Uso e
  Ocupação do Solo (COS) de Portugal Continental*. Relatório Técnico.
  <https://www.dgterritorio.gov.pt/sites/default/files/documentos-publicos/COS-Serie2-EspecificacoesTecnicas-2026.pdf.pdf>
- Herring, J. R. (ed.) (2011). *OpenGIS Implementation Standard for Geographic information – Simple
  feature access – Part 1: Common architecture*, version 1.2.1. Open Geospatial Consortium,
  document 06-103r4.
- Hurlbert, S. H. (1984). Pseudoreplication and the design of ecological field experiments.
  *Ecological Monographs*, 54(2), 187–211. <https://doi.org/10.2307/1942661>
- Mertens, B. and Lambin, E. F. (2000). Land-cover-change trajectories in southern Cameroon.
  *Annals of the Association of American Geographers*, 90(3), 467–494.
  <https://doi.org/10.1111/0004-5608.00205>
- Olofsson, P., Foody, G. M., Herold, M., Stehman, S. V., Woodcock, C. E. and Wulder, M. A. (2014).
  Good practices for estimating area and assessing accuracy of land change. *Remote Sensing of
  Environment*, 148, 42–57. <https://doi.org/10.1016/j.rse.2014.02.015>
- Pontius, R. G. Jr., Krithivasan, R., Sauls, L., Yan, Y. and Zhang, Y. (2017). Methods to
  summarize change among land categories across time intervals. *Journal of Land Use Science*,
  12(4), 218–230. <https://doi.org/10.1080/1747423X.2017.1338768>
- Pontius, R. G. Jr. and Lippitt, C. D. (2006). Can error explain map differences over time?
  *Cartography and Geographic Information Science*, 33(2), 159–171.
  <https://doi.org/10.1559/152304006777681706>
- Pontius, R. G. Jr., Shusas, E. and McEachern, M. (2004). Detecting important categorical land
  changes while accounting for persistence. *Agriculture, Ecosystems and Environment*, 101(2–3),
  251–268. <https://doi.org/10.1016/j.agee.2003.09.008>
- Swetnam, R. D. (2007). Rural land use in England and Wales between 1930 and 1998: Mapping
  trajectories of change with a high resolution spatio-temporal dataset. *Landscape and Urban
  Planning*, 81(1–2), 91–103. <https://doi.org/10.1016/j.landurbplan.2006.10.013>
