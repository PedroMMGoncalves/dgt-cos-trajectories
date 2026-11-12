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

### 2.3 Series 1 + Series 2: merged classes

Let $`K_{S2}`$ be the 102 level-4 classes of COS2018v4/COS2025v1. DGT (2026, Anexo 3) relates each
Series 1 class to zero, one or several Series 2 classes: a relation
$`R \subseteq K_{07} \times K_{S2}`$.

Define an undirected graph $`G = (V, E)`$:

- vertices $`V`$: the level-4 classes of every nomenclature in use, $`K_{95} \cup K_{07} \cup K_{S2}`$
  (each tagged with its nomenclature; $`K_{95}`$ only if COS1995 is used);
- edges $`E`$:
  1. $`\lbrace a, f(a) \rbrace`$ for $`a \in K_{07}`$ (section 2.2), if COS1995 is used;
  2. $`\lbrace a, b \rbrace`$ for $`(a, b) \in R`$;
  3. for each COS1995 class with a zero element (`1.0.0.0`, `3.0.0.0`, `7.1.1.0`), an edge to every
     $`b \in K_{S2}`$ sharing its non-zero prefix. A zero element means "not subdivided", so the
     class contains every class under that prefix. This rule is defined by the tool.

A **merged class** is a connected component of $`G`$. Two classes are in the same merged class if
and only if a chain of correspondences links them, that is, if at least one edition cannot tell
them apart. The merged-class function is

```math
g : V \to \mathcal{M}, \qquad g(a) = \text{the component of } G \text{ containing } a ,
```

and $`c_t(p) = g(k_t(p))`$ at the detailed level. The partition into components is the finest
classification in which every correspondence maps a class to itself.

Codes of merged classes (for a component with Series 2 members $`B`$):

| Case | Code | Designation |
|---|---|---|
| $`\lvert B \rvert = 1`$ | the Series 2 code | the Series 2 designation |
| $`B`$ = all Series 2 classes under a common prefix | the prefix (`2.2.3`, `1`) | designation of that level 1–3 class |
| otherwise | `<common prefix>.m<n>` | the Series 2 designations joined by ` + ` |
| $`B = \varnothing`$ | `<Series 1 code>(S1)` | Series 1 designation, marked as without Series 2 counterpart |

Every merged class lies within one level-1 class, so the coarse level is
$`c_t^{(1)} = \mathrm{trunc}_1(g(k_t))`$. Levels 2 and 3 are not defined for merged classes, because
the two series arrange these levels differently (Series 1 `1.3` *Infraestruturas* is Series 2 `1.4`).

Functions: `catalog.merged_classes`, `catalog.MergedSelection.harmonise`.

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

Let $`O = \lbrace t : c_t \neq \varnothing \rbrace`$ be the observed editions, $`m = \lvert O \rvert`$,
re-indexed $`j = 1,\dots,m`$ in time order with classes $`c_{(j)}`$ and years $`y_{(j)}`$. A change
indicator for each consecutive observed pair is

```math
\delta_j = \mathbb{1}\left[ c_{(j)} \neq c_{(j-1)} \right], \qquad j = 2,\dots,m .
```

If $`m < 2`$ the metrics of 4.2–4.8 are missing.

**4.1 `trajectory`, `n_missing`.** The string $`c_1 \mid c_2 \mid \dots \mid c_T`$ with `NA` for
$`\varnothing`$; $`n_{\text{missing}} = T - m`$.

**4.2 `n_changes`.**

```math
N = \sum_{j=2}^{m} \delta_j
```

**4.3 `stable`.** $`S = \mathbb{1}[N = 0]`$.

**4.4 `stability_index`.** Share of consecutive pairs without change:

```math
SI = 1 - \frac{N}{m - 1} \in [0, 1]
```

**4.5 `modal_persistence`.** Share of observed editions in the most frequent class:

```math
P = \max_{a} \ \frac{1}{m} \sum_{j=1}^{m} \mathbb{1}\left[ c_{(j)} = a \right] \in \left[ \tfrac{1}{m}, 1 \right]
```

**4.6 `time_weighted_persistence`.** Share of the observed time span without change. With
$`\Delta_j = y_{(j)} - y_{(j-1)}`$:

```math
P_w = \frac{\sum_{j=2}^{m} \Delta_j \, (1 - \delta_j)}{\sum_{j=2}^{m} \Delta_j} = \frac{\sum_{j=2}^{m} \Delta_j \, (1 - \delta_j)}{y_{(m)} - y_{(1)}} \in [0, 1]
```

An interval counts as unchanged if the classes at its two ends are equal; the date of a change
within an interval is unknown. $`SI`$ is the special case of $`P_w`$ with all $`\Delta_j`$ equal.

**4.7 `last_change_year`.**

```math
y^{*} = \max \lbrace y_{(j)} : \delta_j = 1 \rbrace
```

missing if $`N = 0`$. The last change occurred in the interval $`(y_{(j-1)}, y_{(j)}]`$.

**4.8 `flip_flop`.**

```math
F = \mathbb{1}\left[ \exists\, j \in \lbrace 1,\dots,m-2 \rbrace : c_{(j)} \neq c_{(j+1)} \ \wedge \ c_{(j+2)} = c_{(j)} \right]
```

**4.9 `min_boundary_dist_m`, `near_boundary`.** With threshold $`\tau`$ (default 25 m):

```math
d_{\min} = \min_{t \in O} d_t, \qquad B = \mathbb{1}\left[ d_{\min} < \tau \right]
```

The default is of the order of the COS minimum distance between lines (20 m) plus its positional
accuracy (5.5 m).

**4.10 `pts_in_poly_<y_T>`.** Number of samples in the polygon of the last edition:

```math
\pi(p) = \left\lvert \lbrace q : P_T(q) = P_T(p) \rbrace \right\rvert
```

Functions: `metrics.sample_metrics`, `metrics.compute_metrics`.

### Worked example

Series 1, years 1995, 2007, 2010, 2015, 2018; $`\Delta = (12, 3, 5, 3)`$, span 23 years.
Trajectory `3.0.0.0|1.0.0.0|1.0.0.0|1.0.0.0|1.0.0.0`: $`\delta = (1, 0, 0, 0)`$, so

```math
N = 1, \quad SI = 1 - \tfrac{1}{4} = 0.75, \quad P = \tfrac{4}{5} = 0.8, \quad P_w = \tfrac{3 + 5 + 3}{23} = 0.478, \quad y^{*} = 2007, \quad F = 0 .
```

Trajectory `2.1.1.1|2.1.1.1|2.1.1.1|2.1.1.1|2.2.3.1`: $`\delta = (0, 0, 0, 1)`$, so
$`SI = 0.75`$ again but $`P_w = \tfrac{12 + 3 + 5}{23} = 0.870`$ and $`y^{*} = 2018`$.

## 5. Series 1 + Series 2

### 5.1 Trajectory

Let $`y_J`$ be the year of the first Series 2 edition (2018). The trajectory is the Series 1
editions with $`y < y_J`$ followed by the Series 2 editions:

```math
(1995, 2007, 2010, 2015)_{S1} \ \Vert \ (2018, 2025)_{S2},
```

with all classes expressed as merged classes (section 2.3). The metrics of section 4 are computed
on this trajectory. The pair $`(2015_{S1}, 2018_{S2})`$ is the **junction**.

### 5.2 Series check

The Series 1 map of $`y_J`$ (COS2018v2) is not part of the trajectory. Its merged class at the
point is $`c^{S1}_{J}`$ (column `cls_2018_S1`), and

```math
a_J = \mathbb{1}\left[ c^{S1}_{J} = c_{J} \right]
```

(column `series_check_2018`; missing if either class is missing). Both maps describe the same
year, so $`a_J = 0`$ is a difference between the series, not a change.

### 5.3 Series-switch change

A change at the junction is attributed to the switch of series when Series 1 alone shows no
change over the same interval. With $`j_J`$ the observed index of year $`y_J`$:

```math
\sigma = \mathbb{1}\left[ \delta_{j_J} = 1 \ \wedge \ c^{S1}_{J} = c_{(j_J - 1)} \right]
```

If $`\sigma = 1`$, Series 1 gives the same class in 2015 and 2018, and Series 2 gives a different
class in 2018: the two series describe the same land differently. If Series 1 also changed between
2015 and 2018 ($`c^{S1}_{J} \neq c_{(j_J-1)}`$), the change is kept as a change.

## 6. Interpretation category

Column `interpretation`; the first rule that applies:

| Order | Condition | Category |
|---|---|---|
| 1 | $`m < 2`$ | `insufficient_data` |
| 2 | $`N = 0`$ | `stable` |
| 3 | $`N = 1`$ and $`\sigma = 1`$ (every change is a series-switch change) | `series_difference` |
| 4 | $`F = 1`$ | `flip_flop` |
| 5 | $`B = 1`$ | `near_boundary` |
| 6 | otherwise | `change` |

Rule 3 applies only to `S1+S2` runs. The categories are mutually exclusive and exhaustive.
`change` therefore means: at least one change, not explained by the switch of series, no A–B–A
pattern, and the point at least $`\tau`$ from every polygon boundary in every edition.

Functions: `metrics.interpret`, `metrics.interpret_table`.

## 7. Aggregated outputs

**7.1 Transition matrix** (`transitions_<a>_<b>.csv`) between consecutive editions $`t-1`$ and
$`t`$, with $`\varnothing`$ kept as the category `NA`:

```math
M_{ab} = \left\lvert \lbrace p : c_{t-1}(p) = a \ \wedge \ c_t(p) = b \rbrace \right\rvert, \qquad \sum_{a,b} M_{ab} = n .
```

The diagonal counts samples without change in the interval. These are counts of samples, not
estimates of area.

**7.2 Interpretation summary** (`interpretation_summary.csv`). For each category $`v`$:

```math
n_v = \left\lvert \lbrace p : \text{interpretation}(p) = v \rbrace \right\rvert, \qquad s_v = \frac{n_v}{n} .
```

**7.3 Group summary** (`group_summary.csv`), for a group $`G`$ of samples:

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

## 8. Numerical conventions

- $`SI`$, $`P`$, $`P_w`$ and the proportions are rounded to 4 decimals; distances to 0.01 m.
- Rows are sorted by sample identifier in natural order (digit runs compared as integers:
  `A2` < `A10`); classes in matrices are sorted by code, `NA` last.
- File checksums in `manifest.json` are SHA-256.

## References

- Direção-Geral do Território (2022). *Especificações técnicas da Carta de Uso e Ocupação do Solo
  (COS) de Portugal Continental para 1995, 2007, 2010, 2015 e 2018*. Relatório Técnico.
- Direção-Geral do Território (2026). *Especificações técnicas da Série 2 da Carta de Uso e
  Ocupação do Solo (COS) de Portugal Continental*. Relatório Técnico.
