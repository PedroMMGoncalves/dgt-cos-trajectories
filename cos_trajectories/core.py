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
"""
import logging
import platform
import re
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


@dataclass
class RunResult:
    out_dir: Path
    history: pd.DataFrame
    selection: catalog.Selection
    base_name: str = ""  # result tables are <base_name>.csv/.xlsx/.gpkg/.shp


SHAPEFILE_NAMES = {  # columns longer than the 10 characters a shapefile field name allows
    "stability_index": "stab_index",
    "modal_persistence": "modal_pers",
    "time_weighted_persistence": "tw_persist",
    "last_change_year": "last_chg_y",
    "min_boundary_dist_m": "min_bdist",
    "near_boundary": "near_bound",
    "interpretation": "interpret",
}


def output_base_name(samples_path, samples_layer, series, level):
    """Base name of the result tables: ``<sample layer name>_COS_<series>_L<level>``.

    The sample layer name is the GeoPackage layer if one is given, otherwise
    the file name without extension; characters other than letters, digits,
    ``_`` and ``-`` are replaced by ``_``.
    """
    source = samples_layer or Path(samples_path).stem
    source = re.sub(r"[^0-9A-Za-z_-]+", "_", source).strip("_") or "samples"
    return f"{source}_COS_{series}_L{level}"


def shapefile_field_names(columns):
    """``{column: field name of at most 10 characters}``, unique, in the order of ``columns``."""
    out, used = {}, set()
    for col in columns:
        m = re.fullmatch(r"cls_(\d{4})_L(\d)", col)
        if m:
            name = f"c{m.group(1)}_L{m.group(2)}"
        elif col.startswith("n_changes_L"):
            name = "n_chg_L" + col[len("n_changes_L"):]
        elif col.startswith("pts_in_poly_"):
            name = "pts_in_pol"
        else:
            name = SHAPEFILE_NAMES.get(col, col[:10])
        n = 1
        while name in used:  # collision after shortening: number the last characters
            n += 1
            name = f"{col[:10 - len(str(n))]}{n}"
        used.add(name)
        out[col] = name
    return out


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


def _select(found, series, cat):
    if series in catalog.SERIES:
        return catalog.select(found, series, cat)
    raise InputError(f"series must be S1 or S2, got {series!r}")


def _classify(sel, source, samples, bbox, year_tag):
    """Join one edition; returns (join table, harmonised level-4 codes, n shared-edge points)."""
    cos = io.read_layer(source.path, layer=source.layer, bbox=bbox, columns=[source.id_field, source.code_field])
    log.info("%s: %d polygons read around the samples", source.name, len(cos))
    j, n_shared = join_edition(samples, cos, source.code_field, source.id_field, year_tag)
    if n_shared:
        log.warning("%s: %d sample(s) on a shared polygon edge; kept the polygon with the lowest ID",
                    source.name, n_shared)
    n_out = int(j["code"].isna().sum())
    if n_out:
        log.warning("%s: %d sample(s) outside every COS polygon", source.name, n_out)
    code4 = [pd.NA if pd.isna(c) else sel.harmonise(c, source) for c in j["code"]]
    return j, pd.Series(pd.array(code4, dtype="object"), index=samples.index), n_shared


def _history(sel, samples, bbox, level, threshold, order):
    """History table (rows in ``order``), class labels and counts."""
    years = sel.years
    labels = sel.labels()
    hist = pd.DataFrame(index=samples.index)
    shared, missing_labels, by_level = {}, set(), {}
    for s in sel.sources:
        y = s.edition
        j, code4, shared[str(y)] = _classify(sel, s, samples, bbox, y)
        for k in sel.levels:  # class at every level, side by side
            by_level[f"cls_{y}_L{k}"] = code4.map(lambda c, k=k: c if pd.isna(c) else catalog.recode(c, k))
        cls = by_level[f"cls_{y}_L{level}"]
        missing_labels.update(c for c in cls.dropna() if (level, c) not in labels)
        hist[f"cls_{y}"] = cls
        hist[f"label_{y}"] = pd.array([pd.NA if pd.isna(c) else labels.get((level, c), pd.NA) for c in cls],
                                      dtype="object")
        hist[f"poly_{y}"] = j["poly"].astype("object")
        hist[f"dist_{y}"] = j["dist"].round(2)
    if missing_labels:
        log.warning("no label in %s for code(s) %s", sel.nomenclature, sorted(missing_labels))
    hist["min_boundary_dist_m"] = hist[[f"dist_{y}" for y in years]].min(axis=1, skipna=True)
    hist = metrics.compute_metrics(hist, years, threshold)

    hist["interpretation"] = metrics.interpret_table(hist, years)
    levels = pd.DataFrame(by_level, index=hist.index)
    for k in sel.levels:  # number of changes at every level
        n = [metrics.sample_metrics([r[f"cls_{y}_L{k}"] for y in years], years)["n_changes"]
             for r in levels.to_dict("records")]
        levels[f"n_changes_L{k}"] = pd.array(n, dtype="Int64")
    hist = pd.concat([hist, levels], axis=1)

    hist = hist.loc[order]
    per_year = [f"{k}_{y}" for y in years for k in ("cls", "label", "poly", "dist")]
    tail = metrics.METRIC_COLUMNS + ["min_boundary_dist_m", "near_boundary", f"pts_in_poly_{years[-1]}"]
    level_cls = [f"cls_{y}_L{k}" for y in years for k in sel.levels]
    level_n = [f"n_changes_L{k}" for k in sel.levels]
    hist = hist[per_year + level_cls + tail + level_n + ["interpretation"]]
    for col in ("stability_index", "modal_persistence", "time_weighted_persistence"):
        hist[col] = hist[col].round(FLOAT_DECIMALS)
    counts = {
        "editions": years,
        "shared_edge_points": shared,
        "outside_coverage": {str(y): int(hist[f"cls_{y}"].isna().sum()) for y in years},
        "near_boundary": int(hist["near_boundary"].fillna(0).sum()),
        "stable": int(hist["stable"].fillna(0).sum()),
        "flip_flop": int(hist["flip_flop"].fillna(0).sum()),
        "interpretation": {k: int((hist["interpretation"] == k).sum()) for k in metrics.INTERPRETATION},
    }
    return hist, labels, counts


def _run(cos_dir, series, samples_path, samples_layer, id_field, group_field, level,
         threshold, run_dir, run_id, started, with_hash):
    log.info("cos_trajectories %s, run %s", __version__, run_id)
    cat = catalog.load_catalog()
    found, ignored = catalog.discover(cos_dir, cat)
    for path, reason in ignored:
        log.info("ignored %s: %s", path.name, reason)
    sel = _select(found, series, cat)
    for s, reason in sel.excluded:
        log.warning("excluded %s: %s", s.name, reason)
    years = sel.years
    log.info("series %s, editions %s, nomenclature %s", sel.series, [s.name for s in sel.sources], sel.nomenclature)
    for name, source in sel.crosswalk_sources(cat).items():
        log.info("correspondence %s: %s", name, source)
    level = sel.max_level if level is None else int(level)
    if level not in sel.levels:
        raise InputError(f"comparison level must be one of {list(sel.levels)} for series {sel.series}, "
                         f"got {level}")
    log.info("comparison level %d", level)

    raw = io.read_layer(samples_path, layer=samples_layer)
    sample_crs = raw.crs
    samples = prepare_samples(raw, id_field, group_field)
    log.info("%d samples read from %s", len(samples), Path(samples_path).name)
    cos_crs = _check_cos_crs(sel.sources)
    if samples.crs != cos_crs:
        log.info("reprojecting samples from %s to %s", samples.crs.to_string(), cos_crs.to_string())
        samples = samples.to_crs(cos_crs)
    b = samples.total_bounds
    bbox = (b[0] - BBOX_BUFFER_M, b[1] - BBOX_BUFFER_M, b[2] + BBOX_BUFFER_M, b[3] + BBOX_BUFFER_M)
    order = sorted(samples.index, key=metrics.natural_key)

    hist, labels, counts = _history(sel, samples, bbox, level, threshold, order)
    hist.index.name = id_field
    table = hist.reset_index()

    base = output_base_name(samples_path, samples_layer, sel.series, level)
    io.write_csv(table, run_dir / f"{base}.csv")
    geo = gpd.GeoDataFrame(table, geometry=samples.geometry.loc[order].values, crs=samples.crs)
    io.write_gpkg(geo, run_dir / f"{base}.gpkg", layer=base)
    shp_names = shapefile_field_names(list(table.columns))
    io.write_shapefile(geo, run_dir / f"{base}.shp", shp_names)
    io.write_xlsx(table, run_dir / f"{base}.xlsx")
    outputs = [f"{base}{ext}" for ext in (".csv", ".xlsx", ".gpkg", ".shp", ".shx", ".dbf", ".prj", ".cpg")]
    outputs += ["interpretation_summary.csv", "data_dictionary.md", "run.log"]
    for a, b2 in zip(years[:-1], years[1:]):
        tm = metrics.transition_matrix(hist[f"cls_{a}"], hist[f"cls_{b2}"])
        tm.index.name = f"{a}\\{b2}"
        name = f"transitions_{a}_{b2}.csv"
        io.write_csv(tm, run_dir / name, index=True)
        outputs.append(name)
    n = len(hist)
    summary = pd.DataFrame({"interpretation": list(metrics.INTERPRETATION),
                            "n_samples": [counts["interpretation"][k] for k in metrics.INTERPRETATION]})
    summary["share"] = (summary["n_samples"] / n).round(FLOAT_DECIMALS)
    summary["meaning"] = [metrics.INTERPRETATION_MEANING[k] for k in metrics.INTERPRETATION]
    io.write_csv(summary, run_dir / "interpretation_summary.csv")
    if group_field:
        groups = samples[group_field].loc[order].values
        gs = metrics.group_summary(hist.assign(**{group_field: groups}), group_field, years)
        props = ["prop_changed", "prop_near_boundary", "prop_change_supported"]
        gs[props] = gs[props].round(FLOAT_DECIMALS)
        io.write_csv(gs, run_dir / "group_summary.csv")
        outputs.append("group_summary.csv")

    counts = {"n_samples_in": int(len(raw)), "n_samples_out": int(len(table)), **counts}
    params = {
        "cos_dir": str(Path(cos_dir).resolve()), "series": series,
        "samples_path": str(Path(samples_path).resolve()), "samples_layer": samples_layer,
        "id_field": id_field, "group_field": group_field, "comparison_level": level,
        "boundary_threshold_m": threshold, "out_dir": str(run_dir.resolve()),
    }
    if with_hash:
        log.info("computing SHA-256 of %d COS files for the manifest", len(sel.sources))
    manifest = report.build_manifest(
        run_id=run_id, started=started, params=params, selection=sel, ignored=ignored, cat=cat,
        samples_path=samples_path, samples_layer=samples_layer, sample_crs=sample_crs,
        n_samples=len(raw), counts=counts, software=_software_versions(), with_hash=with_hash,
        outputs=sorted(outputs),
    )
    io.write_json(run_dir / "manifest.json", manifest)
    used = set()
    for y in years:
        used.update(c for c in hist[f"cls_{y}"] if not pd.isna(c))
    io.write_text(run_dir / "data_dictionary.md", report.data_dictionary(
        selection=sel, cat=cat, labels=labels, level=level, id_field=id_field, group_field=group_field,
        threshold=threshold, counts=counts, run_id=run_id, used_codes=used, shapefile_names=shp_names, base_name=base))
    log.info("done: %d samples written to %s", len(table), run_dir)
    return RunResult(out_dir=run_dir, history=table, selection=sel, base_name=base)
