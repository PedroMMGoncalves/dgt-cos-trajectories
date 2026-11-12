"""Temporal-stability metrics per sample, transition matrices and group summaries.

Pure pandas; no file I/O.

Definitions (c_t = class at edition t, years y_t, only *observed* editions,
i.e. editions where the sample fell inside a COS polygon, are used):

- ``stable``: 1 if all observed classes are equal.
- ``n_changes``: number of consecutive observed pairs with different class.
- ``stability_index``: 1 - n_changes / (T_obs - 1).
- ``modal_persistence``: share of observed editions in the most frequent class.
- ``time_weighted_persistence``: years between consecutive observed editions
  without change, divided by the years spanned by the observed editions.
- ``last_change_year``: year of the later edition of the last change.
- ``flip_flop``: 1 if three consecutive observed editions follow A -> B -> A.
  Often an interpretation artefact rather than a real change.
- ``n_missing``: editions without a containing polygon.

Limitations: with fewer than two observed editions every change-based metric
is missing (NA). Metrics are descriptive; no composite index is computed
(each metric answers a different question).
"""
import re
from collections import Counter

import numpy as np
import pandas as pd

NA_TOKEN = "NA"

METRIC_COLUMNS = [
    "trajectory",
    "n_missing",
    "stable",
    "n_changes",
    "stability_index",
    "modal_persistence",
    "time_weighted_persistence",
    "last_change_year",
    "flip_flop",
]


def _is_missing(v):
    return v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA


def natural_key(value):
    """Sort key so that ``A2`` sorts before ``A10``; numbers sort numerically."""
    if isinstance(value, (int, float, np.integer, np.floating)):
        return ((0, value),)
    parts = re.split(r"(\d+)", str(value))
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts if p != "")


def sample_metrics(classes, years):
    """Metrics for one sample. ``classes`` and ``years`` are aligned, sorted by year."""
    classes = [None if _is_missing(c) else str(c) for c in classes]
    obs = [(y, c) for y, c in zip(years, classes) if c is not None]
    out = {
        "trajectory": "|".join(NA_TOKEN if c is None else c for c in classes),
        "n_missing": len(classes) - len(obs),
        "stable": None,
        "n_changes": None,
        "stability_index": None,
        "modal_persistence": None,
        "time_weighted_persistence": None,
        "last_change_year": None,
        "flip_flop": None,
    }
    if len(obs) < 2:
        return out
    cls = [c for _, c in obs]
    yrs = [y for y, _ in obs]
    pairs = list(zip(range(1, len(cls)), cls[:-1], cls[1:]))
    changes = [i for i, a, b in pairs if a != b]
    span = yrs[-1] - yrs[0]
    kept = sum(yrs[i] - yrs[i - 1] for i, a, b in pairs if a == b)
    out.update(
        stable=int(not changes),
        n_changes=len(changes),
        stability_index=1 - len(changes) / (len(cls) - 1),
        modal_persistence=Counter(cls).most_common(1)[0][1] / len(cls),
        time_weighted_persistence=kept / span if span > 0 else None,
        last_change_year=yrs[changes[-1]] if changes else None,
        flip_flop=int(any(cls[i] != cls[i + 1] and cls[i + 2] == cls[i] for i in range(len(cls) - 2))),
    )
    return out


def compute_metrics(history, years, boundary_threshold_m):
    """Add metric columns to a per-sample history table.

    ``history`` must have ``cls_<year>`` and ``poly_<year>`` columns for each
    year and a ``min_boundary_dist_m`` column. Returns a new DataFrame.
    """
    h = history.copy()
    rows = [
        sample_metrics([r[f"cls_{y}"] for y in years], years)
        for r in h[[f"cls_{y}" for y in years]].to_dict("records")
    ]
    m = pd.DataFrame(rows, index=h.index, columns=METRIC_COLUMNS)
    for col in ("n_missing", "stable", "n_changes", "last_change_year", "flip_flop"):
        m[col] = pd.array(m[col].tolist(), dtype="Int64")
    for col in ("stability_index", "modal_persistence", "time_weighted_persistence"):
        m[col] = m[col].astype("float64")
    h = pd.concat([h, m], axis=1)
    d = h["min_boundary_dist_m"]
    h["near_boundary"] = pd.array(
        [pd.NA if pd.isna(v) else int(v < boundary_threshold_m) for v in d], dtype="Int64"
    )
    last = years[-1]
    poly = h[f"poly_{last}"]
    counts = poly.map(poly.value_counts())
    h[f"pts_in_poly_{last}"] = pd.array(
        [pd.NA if pd.isna(p) else int(c) for p, c in zip(poly, counts)], dtype="Int64"
    )
    return h


def transition_matrix(a, b):
    """Point counts from classes ``a`` (rows) to ``b`` (columns); NA kept as ``"NA"``."""
    a = a.astype("object").where(a.notna(), NA_TOKEN).astype(str)
    b = b.astype("object").where(b.notna(), NA_TOKEN).astype(str)
    tm = pd.crosstab(a, b)
    tm = tm.reindex(index=sorted(tm.index, key=_class_key), columns=sorted(tm.columns, key=_class_key))
    tm.index.name = None
    tm.columns.name = None
    return tm


def _class_key(code):
    # Class codes in hierarchical order; "NA" last.
    return (code == NA_TOKEN, natural_key(code))


def group_summary(history, group_field, years):
    """Per-group summary of a history table that already has metric columns."""
    rows = []
    for g, d in history.groupby(group_field, sort=False, dropna=False):
        row = {group_field: g, "n_points": len(d)}
        for y in years:
            row[f"n_polygons_{y}"] = d[f"poly_{y}"].nunique(dropna=True)
        observed = d["n_changes"].dropna()
        row["prop_changed"] = float((observed > 0).mean()) if len(observed) else np.nan
        row["n_trajectories"] = d["trajectory"].nunique()
        nb = d["near_boundary"].dropna()
        row["prop_near_boundary"] = float(nb.mean()) if len(nb) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values(group_field, key=lambda s: s.map(natural_key)).reset_index(drop=True)
