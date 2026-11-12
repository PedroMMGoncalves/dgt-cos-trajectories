"""Point-in-polygon joins, class recoding, boundary distances and the run pipeline.

For each selected COS edition, every sample point is assigned the polygon
that contains it (``intersects``: a point exactly on a shared edge touches
two polygons; the one with the lowest DGT ``ID`` is kept and the number of
such points is logged). The level-4 class code is harmonised to the common
nomenclature (see :mod:`cos_trajectories.catalog`) and truncated to the
comparison level. ``dist_<year>`` is the distance in metres from the point to
the boundary (outer and inner rings) of its containing polygon.

Limitations: only point samples are supported; polygon samples (dominant
class / % area) are not. Only the COS polygons whose envelope intersects the
bounding box of all samples (plus a buffer) are read, so samples spread over
the whole country read most of each COS layer.

Linked mode (``series="S1+S2"``): both series are processed independently
and written side by side (columns suffixed ``_S1`` / ``_S2``); no change or
trajectory is ever computed across the series break. For each edition year
present in both series (2018), ``agree_l1_<year>`` says whether the two maps
of that same year give the same level-1 class at the point: a disagreement
is a difference of nomenclature/delineation, not a land-use change.
"""
import logging
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from . import __version__, catalog, io, metrics, report
from .catalog import InputError

log = logging.getLogger("cos_trajectories")

BBOX_BUFFER_M = 100.0
DEFAULT_THRESHOLD_M = 25.0
FLOAT_DECIMALS = 4  # metrics in the output tables
LINKED = "S1+S2"  # both series side by side, never merged


@dataclass
class RunResult:
    out_dir: Path
    history: pd.DataFrame
    selections: list  # one catalog.Selection per series


def prepare_samples(gdf, id_field, group_field=None):
    """Validate a sample layer; return a GeoDataFrame indexed by sample ID.

    Keeps only the geometry (and the group field, if any). Single-part
    MultiPoints are converted to Points.
    """
    if id_field not in gdf.columns:
        raise InputError(f"ID field {id_field!r} not found in the sample layer. Fields: "
                         f"{[c for c in gdf.columns if c != gdf.geometry.name]}")
    if group_field and group_field not in gdf.columns:
        raise InputError(f"group field {group_field!r} not found in the sample layer")
    if gdf.crs is None:
        raise InputError("the sample layer has no coordinate reference system (missing .prj?)")
    geom = gdf.geometry
    if geom.isna().any() or geom.is_empty.any():
        raise InputError(f"{int((geom.isna() | geom.is_empty).sum())} sample(s) have no geometry")
    types = set(geom.geom_type)
    if types == {"MultiPoint"} or types == {"Point", "MultiPoint"}:
        multi = geom.geom_type == "MultiPoint"
        if (shapely.get_num_geometries(geom[multi].values) != 1).any():
            raise InputError("only point samples are supported; found multi-part points")
        geom = geom.where(~multi, geom[multi].apply(lambda g: g.geoms[0]))
        types = {"Point"}
    if types != {"Point"}:
        raise InputError(f"only point samples are supported in this version; found {sorted(types)}")
    ids = gdf[id_field]
    if ids.isna().any() or (ids.astype(str).str.strip() == "").any():
        raise InputError(f"ID field {id_field!r} has empty values")
    if not ids.is_unique:
        dups = sorted(ids[ids.duplicated()].astype(str).unique(), key=metrics.natural_key)
        raise InputError(f"ID field {id_field!r} must be unique; duplicated: {dups[:20]}")
    cols = {id_field: ids.values}
    if group_field:
        cols[group_field] = gdf[group_field].values
    out = gpd.GeoDataFrame(cols, geometry=geom.values, crs=gdf.crs)
    return out.set_index(id_field, drop=True)


def join_edition(samples, cos, code_field, id_field, year):
    """Join samples (indexed by ID) to one COS layer.

    Returns ``(DataFrame[code, poly, dist], n_shared_edge)`` indexed like
    ``samples``. Samples outside every polygon get missing values.
    """
    pts = gpd.GeoDataFrame(geometry=samples.geometry.values, crs=samples.crs)
    pts["_order"] = np.arange(len(pts))
    right = cos[[id_field, code_field, cos.geometry.name]].reset_index(drop=True)
    j = gpd.sjoin(pts, right, how="inner", predicate="intersects")
    j = j.sort_values(["_order", id_field])
    n_hits = j.groupby("_order").size()
    n_shared = int((n_hits > 1).sum())
    j = j.drop_duplicates("_order", keep="first")
    poly_geom = right.geometry.values[j["index_right"].to_numpy()]
    dist = shapely.distance(j.geometry.values, shapely.boundary(poly_geom))
    out = pd.DataFrame({"code": pd.Series(pd.NA, index=pts.index, dtype="object"),
                        "poly": pd.Series(pd.NA, index=pts.index, dtype="object"),
                        "dist": np.nan})
    order = j["_order"].to_numpy()
    out.loc[order, "code"] = j[code_field].astype(str).str.strip().to_numpy()
    out.loc[order, "poly"] = [f"{year}_{v}" for v in j[id_field].to_numpy()]
    out.loc[order, "dist"] = np.asarray(dist, dtype=float)
    out.index = samples.index
    return out, n_shared


def _check_cos_crs(sources):
    crss = {}
    for s in sources:
        crs = io.layer_info(s.path, s.layer)["crs"]
        if crs is None or not crs.is_projected:
            raise InputError(f"{s.path.name}: COS layer must have a projected CRS, found {crs}")
        crss[s.name] = crs
    first = next(iter(crss.values()))
    if any(c != first for c in crss.values()):
        raise InputError(f"COS layers have different CRS: { {k: v.to_string() for k, v in crss.items()} }")
    return first


def _software_versions():
    import fiona
    import pyproj
    return {
        "python": platform.python_version(),
        "geopandas": gpd.__version__,
        "shapely": shapely.__version__,
        "fiona": fiona.__version__,
        "gdal": fiona.__gdal_version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "pyproj": pyproj.__version__,
        "cos_trajectories": __version__,
    }


def run(cos_dir, series, samples_path, id_field, out_dir, samples_layer=None, group_field=None,
        level=None, boundary_threshold_m=DEFAULT_THRESHOLD_M, run_id=None, with_hash=True):
    """Full pipeline; writes all outputs to ``out_dir/<run_id>/`` and returns a :class:`RunResult`."""
    started = datetime.now().astimezone()
    run_id = run_id or started.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(out_dir) / run_id
    if run_dir.exists():
        raise InputError(f"output folder already exists: {run_dir}")
    if boundary_threshold_m is None or boundary_threshold_m < 0:
        raise InputError("boundary threshold must be a non-negative number of metres")
    io.make_dir(run_dir)
    handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    if log.level == logging.NOTSET:
        log.setLevel(logging.INFO)
    try:
        return _run(cos_dir, series, samples_path, samples_layer, id_field, group_field, level,
                    float(boundary_threshold_m), run_dir, run_id, started, with_hash)
    except Exception as e:
        log.error("run failed, outputs incomplete: %s", e)
        raise
    finally:
        log.removeHandler(handler)
        handler.close()


def _parse_series(series):
    if series == LINKED:
        return ["S1", "S2"]
    if series in catalog.SERIES:
        return [series]
    raise InputError(f"series must be S1, S2 or {LINKED} (linked side by side), got {series!r}")


def _series_history(sel, samples, bbox, level, threshold, order):
    """History of one series: (table with unsuffixed columns, rows in ``order``; labels; counts)."""
    years = sel.years
    labels = catalog.load_labels(sel.nomenclature)
    hist = pd.DataFrame(index=samples.index)
    shared, missing_labels = {}, set()
    for s in sel.sources:
        y = s.edition
        cos = io.read_layer(s.path, layer=s.layer, bbox=bbox, columns=[s.id_field, s.code_field])
        log.info("%s: %d polygons read around the samples", s.name, len(cos))
        j, n_shared = join_edition(samples, cos, s.code_field, s.id_field, y)
        shared[str(y)] = n_shared
        if n_shared:
            log.warning("%s: %d sample(s) on a shared polygon edge; kept the polygon with the lowest ID",
                        s.name, n_shared)
        n_out = int(j["code"].isna().sum())
        if n_out:
            log.warning("%s: %d sample(s) outside every COS polygon", s.name, n_out)
        cls = [pd.NA if pd.isna(c) else catalog.recode(sel.harmonise(c, s), level) for c in j["code"]]
        lab = []
        for c in cls:
            if pd.isna(c):
                lab.append(pd.NA)
            else:
                if (level, c) not in labels:
                    missing_labels.add(c)
                lab.append(labels.get((level, c), pd.NA))
        hist[f"cls_{y}"] = pd.array(cls, dtype="object")
        hist[f"label_{y}"] = pd.array(lab, dtype="object")
        hist[f"poly_{y}"] = j["poly"].astype("object")
        hist[f"dist_{y}"] = j["dist"].round(2)
    if missing_labels:
        log.warning("no label in nomenclature %s for code(s) %s", sel.nomenclature, sorted(missing_labels))
    hist["min_boundary_dist_m"] = hist[[f"dist_{y}" for y in years]].min(axis=1, skipna=True)
    hist = metrics.compute_metrics(hist, years, threshold).loc[order]
    per_year = [f"{k}_{y}" for y in years for k in ("cls", "label", "poly", "dist")]
    tail = metrics.METRIC_COLUMNS + ["min_boundary_dist_m", "near_boundary", f"pts_in_poly_{years[-1]}"]
    hist = hist[per_year + tail]
    for col in ("stability_index", "modal_persistence", "time_weighted_persistence"):
        hist[col] = hist[col].round(FLOAT_DECIMALS)
    counts = {
        "editions": years,
        "shared_edge_points": shared,
        "outside_coverage": {str(y): int(hist[f"cls_{y}"].isna().sum()) for y in years},
        "near_boundary": int(hist["near_boundary"].fillna(0).sum()),
        "stable": int(hist["stable"].fillna(0).sum()),
        "flip_flop": int(hist["flip_flop"].fillna(0).sum()),
    }
    return hist, labels, counts


def _level1(c):
    return c if pd.isna(c) else catalog.recode(c, 1)


def _level1_agreement(a, b):
    """1 if both classes have the same level-1 code, 0 if not, NA if either is missing."""
    return pd.array([pd.NA if pd.isna(x) or pd.isna(y) else int(_level1(x) == _level1(y))
                     for x, y in zip(a, b)], dtype="Int64")


def _run(cos_dir, series, samples_path, samples_layer, id_field, group_field, level,
         threshold, run_dir, run_id, started, with_hash):
    log.info("cos_trajectories %s, run %s", __version__, run_id)
    series_list = _parse_series(series)
    linked = len(series_list) > 1
    cat = catalog.load_catalog()
    found, ignored = catalog.discover(cos_dir, cat)
    for path, reason in ignored:
        log.info("ignored %s: %s", path.name, reason)
    sels = [catalog.select(found, sr, cat) for sr in series_list]
    for sel in sels:
        for s, reason in sel.excluded:
            log.warning("excluded %s: %s", s.name, reason)
        log.info("series %s, editions %s, nomenclature %s", sel.series, sel.years, sel.nomenclature)
        for nom in sel.crosswalks:
            log.info("recoding %s to %s with the DGT crosswalk", nom, sel.nomenclature)
    if linked:
        log.info("series linked side by side, not merged: no change is computed across the series")
    max_level = min(sel.max_level for sel in sels)
    level = max_level if level is None else int(level)
    if not 1 <= level <= max_level:
        raise InputError(f"comparison level must be between 1 and {max_level} (max level common to "
                         f"all editions), got {level}")
    log.info("comparison level %d", level)

    raw = io.read_layer(samples_path, layer=samples_layer)
    sample_crs = raw.crs
    samples = prepare_samples(raw, id_field, group_field)
    log.info("%d samples read from %s", len(samples), Path(samples_path).name)
    cos_crs = _check_cos_crs([s for sel in sels for s in sel.sources])
    if samples.crs != cos_crs:
        log.info("reprojecting samples from %s to %s", samples.crs.to_string(), cos_crs.to_string())
        samples = samples.to_crs(cos_crs)
    b = samples.total_bounds
    bbox = (b[0] - BBOX_BUFFER_M, b[1] - BBOX_BUFFER_M, b[2] + BBOX_BUFFER_M, b[3] + BBOX_BUFFER_M)
    order = sorted(samples.index, key=metrics.natural_key)

    parts = [_series_history(sel, samples, bbox, level, threshold, order) for sel in sels]

    def sfx(sr):
        return f"_{sr}" if linked else ""

    hist = pd.concat([h.add_suffix(sfx(sel.series)) for sel, (h, _, _) in zip(sels, parts)], axis=1)
    bridge_years = sorted(set(sels[0].years) & set(sels[1].years)) if linked else []
    if linked and not bridge_years:
        log.warning("the two series share no edition year: no agreement flag computed")
    bridge = {}
    for y in bridge_years:
        flag = pd.Series(_level1_agreement(hist[f"cls_{y}_S1"], hist[f"cls_{y}_S2"]), index=hist.index)
        hist[f"agree_l1_{y}"] = flag
        bridge[str(y)] = {"compared": int(flag.notna().sum()), "agree_l1": int(flag.fillna(0).sum())}
        log.info("%d: same level-1 class in S1 and S2 at %d of %d samples (a difference here is a change "
                 "of nomenclature or delineation, not of land use)", y, bridge[str(y)]["agree_l1"],
                 bridge[str(y)]["compared"])
    hist.index.name = id_field
    table = hist.reset_index()

    io.write_csv(table, run_dir / "samples_cos_history.csv")
    geo = gpd.GeoDataFrame(table, geometry=samples.geometry.loc[order].values, crs=samples.crs)
    io.write_gpkg(geo, run_dir / "samples_cos_history.gpkg", layer="samples_cos_history")
    outputs = ["samples_cos_history.csv", "samples_cos_history.gpkg", "data_dictionary.md", "run.log"]
    for sel, (h, _, _) in zip(sels, parts):
        for a, b2 in zip(sel.years[:-1], sel.years[1:]):
            tm = metrics.transition_matrix(h[f"cls_{a}"], h[f"cls_{b2}"])
            tm.index.name = f"{a}\\{b2}"
            name = f"transitions_{sel.series}_{a}_{b2}.csv" if linked else f"transitions_{a}_{b2}.csv"
            io.write_csv(tm, run_dir / name, index=True)
            outputs.append(name)
    for y in bridge_years:
        tm = metrics.transition_matrix(hist[f"cls_{y}_S1"].map(_level1), hist[f"cls_{y}_S2"].map(_level1))
        tm.index.name = f"{y}_S1\\{y}_S2"
        name = f"bridge_{y}_level1.csv"
        io.write_csv(tm, run_dir / name, index=True)
        outputs.append(name)
    if group_field:
        groups = samples[group_field].loc[order].values
        gs = None
        for sel, (h, _, _) in zip(sels, parts):
            g = metrics.group_summary(h.assign(**{group_field: groups}), group_field, sel.years)
            props = ["prop_changed", "prop_near_boundary"]
            g[props] = g[props].round(FLOAT_DECIMALS)
            g = g.rename(columns={c: c + sfx(sel.series) for c in g.columns if c not in (group_field, "n_points")})
            gs = g if gs is None else gs.merge(g.drop(columns="n_points"), on=group_field, how="left", sort=False)
        for y in bridge_years:
            agree = pd.DataFrame({group_field: groups, "a": hist[f"agree_l1_{y}"].astype("Float64").values})
            p = agree.groupby(group_field, dropna=False)["a"].mean()
            gs[f"prop_agree_l1_{y}"] = gs[group_field].map(p).astype("float64").round(FLOAT_DECIMALS)
        io.write_csv(gs, run_dir / "group_summary.csv")
        outputs.append("group_summary.csv")

    counts = {
        "n_samples_in": int(len(raw)),
        "n_samples_out": int(len(table)),
        "by_series": {sel.series: c for sel, (_, _, c) in zip(sels, parts)},
        "bridge": bridge,
    }
    params = {
        "cos_dir": str(Path(cos_dir).resolve()), "series": series,
        "samples_path": str(Path(samples_path).resolve()), "samples_layer": samples_layer,
        "id_field": id_field, "group_field": group_field, "comparison_level": level,
        "boundary_threshold_m": threshold, "out_dir": str(run_dir.resolve()),
    }
    if with_hash:
        log.info("computing SHA-256 of %d COS files for the manifest", sum(len(s.sources) for s in sels))
    manifest = report.build_manifest(
        run_id=run_id, started=started, params=params, selections=sels, ignored=ignored, cat=cat,
        samples_path=samples_path, samples_layer=samples_layer, sample_crs=sample_crs,
        n_samples=len(raw), counts=counts, software=_software_versions(), with_hash=with_hash,
        outputs=sorted(outputs),
    )
    io.write_json(run_dir / "manifest.json", manifest)
    io.write_text(run_dir / "data_dictionary.md", report.data_dictionary(
        selections=sels, labels=[lab for _, lab, _ in parts],
        used_codes=[_used_codes(h, sel.years) for sel, (h, _, _) in zip(sels, parts)],
        cat=cat, level=level, id_field=id_field, group_field=group_field, threshold=threshold,
        counts=counts, run_id=run_id, linked=linked, bridge_years=bridge_years))
    log.info("done: %d samples written to %s", len(table), run_dir)
    return RunResult(out_dir=run_dir, history=table, selections=sels)


def _used_codes(hist, years):
    codes = set()
    for y in years:
        codes.update(c for c in hist[f"cls_{y}"] if not pd.isna(c))
    return codes
