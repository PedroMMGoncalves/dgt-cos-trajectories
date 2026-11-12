"""Run manifest (machine-readable provenance) and data dictionary (for non-GIS users).

The data dictionary describes every column, the classes, the correspondence
tables applied, how to read the ``interpretation`` column and the
limitations of the method. The mathematical definitions are in
``docs/METHODS.md`` of the repository.
"""
from pathlib import Path

from . import __version__, catalog, io, metrics

BOUNDARY_WARNING = (
    "> A class change at a point flagged `near_boundary` may reflect polygon\n"
    "> delineation differences between editions, not a real land-use change."
)


def _merged(selection):
    return selection.series == catalog.MERGED


def build_manifest(run_id, started, params, selection, ignored, cat, samples_path, samples_layer,
                   sample_crs, n_samples, counts, software, outputs, with_hash=True):
    layers = []
    for role, sources in (("trajectory", selection.sources), ("series check", selection.check)):
        for s in sources:
            fp = io.file_fingerprint(s.path, with_hash=with_hash)
            layers.append({
                "role": role, "edition": s.edition, "version": s.product["version"],
                "series": s.product["series"], "layer": s.layer, "class_field": s.code_field,
                "id_field": s.id_field, "nomenclature": s.product["nomenclature"], **fp,
            })
    return {
        "run_id": run_id,
        "started": started.isoformat(timespec="seconds"),
        "tool": "cos_trajectories",
        "tool_version": __version__,
        "parameters": params,
        "series": selection.series,
        "classes": selection.nomenclature,
        "correspondences_applied": selection.crosswalk_sources(cat),
        "levels_available": list(selection.levels),
        "cos_layers": layers,
        "excluded_cos_layers": [{"file": s.path.name, "reason": r} for s, r in selection.excluded],
        "ignored_files": [{"file": p.name, "reason": r} for p, r in ignored],
        "samples": {
            "path": str(Path(samples_path).resolve()), "layer": samples_layer,
            "crs": sample_crs.to_string() if sample_crs is not None else None,
            "n_features": int(n_samples),
        },
        "counts": counts,
        "software": software,
        "outputs": outputs,
    }


def _table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _eds(sources):
    return ", ".join(f"COS{s.edition}v{s.product['version']} ({s.product['series']})" for s in sources)


def data_dictionary(selection, cat, labels, level, id_field, group_field, threshold, counts, run_id,
                    used_codes):
    sel = selection
    merged = _merged(sel)
    years = sel.years
    last = years[-1]
    thr = f"{threshold:g}"
    n = counts["n_samples_out"]
    out = [
        "# Data dictionary: COS land-use history of the samples",
        BOUNDARY_WARNING,
        f"Run `{run_id}`, produced by `cos_trajectories` {__version__}. Exact inputs, file checksums "
        "and software versions are in `manifest.json`; processing messages are in `run.log`.",
        "## What this is",
        "For every sample (one row per sample ID) the files give the land-use/land-cover class of the "
        "DGT *Carta de Uso e Ocupação do Solo* (COS) polygon that contains the sample point in each "
        "COS edition, and simple measures of how stable that class was over time. The table can be "
        f"joined to external tables through the column `{id_field}`. No soil or laboratory data is included.",
        "## How to read the results",
        "Start with the column `interpretation`. It summarises, for each sample, whether the class changed "
        "and how far the change can be trusted:",
        _table(["`interpretation`", "Samples", "Share", "Meaning", "Suggested use"], [
            [f"`{k}`", counts["interpretation"][k], f"{counts['interpretation'][k] / n:.1%}" if n else "",
             metrics.INTERPRETATION_MEANING[k], _USE[k]] for k in metrics.INTERPRETATION]),
        "The categories are assigned in this order: `insufficient_data`, `stable`, `series_difference`, "
        "`flip_flop`, `near_boundary`, `change`; a sample receives the first that applies. Then use "
        "`trajectory` to see which classes are involved, `last_change_year` for when, and "
        f"`pts_in_poly_{last}` to see how many samples share one polygon (they are not independent "
        "observations).",
        "## COS editions and classes used",
        _table(["Item", "Value"], [
            ["Series", sel.series + (" (both series merged in one trajectory)" if merged else "")],
            ["Editions in the trajectory", _eds(sel.sources)],
        ] + ([["Edition used only as a check", _eds(sel.check)]] if sel.check else []) + [
            ["Classes", sel.nomenclature if merged else
             f"{sel.nomenclature}: {cat['nomenclatures'][sel.nomenclature]['description']}"],
            ["Comparison level", f"{level} (available: {', '.join(map(str, sel.levels))}; 1 = coarsest)"],
            ["Boundary threshold", f"{thr} m"],
        ]),
    ]
    notes = sel.crosswalk_sources(cat)
    if merged:
        out.append(
            "Series 1 and Series 2 use different nomenclatures. Their classes were grouped into *merged "
            "classes*: classes that DGT relates to each other (" + "; ".join(notes.values()) + ") form one "
            "merged class, so that the same code means the same thing in every edition. Detail that exists "
            "in only some editions is lost (for example the Series 2 olive-grove types become one class). "
            "The table of merged classes is at the end of this document.")
        for y, c in counts.get("series_check", {}).items():
            out.append(
                f"**Junction between the series.** The trajectory uses the Series 1 maps up to the edition "
                f"before {y} and the Series 2 maps from {y}. DGT advises against comparing the two series, "
                f"because definitions, production method and mapping unit differ. As a check, the Series 1 "
                f"map of {y} was also read (`cls_{y}_S1`): it gives the same merged class as the Series 2 "
                f"map of {y} at {c['agree']} of {c['compared']} samples (`series_check_{y}`). Where the two "
                f"disagree and Series 1 shows no change, an apparent change at {y} is a difference between "
                "series; such samples have `interpretation` = `series_difference`.")
    elif notes:
        out.append(
            f"Editions with a more detailed nomenclature were recoded to `{sel.nomenclature}` with the official "
            f"DGT correspondence table ({'; '.join(notes.values())}), so that the same code means the same "
            "class in every edition. The full correspondence is listed at the end of this document.")
    if sel.excluded:
        out.append("Editions found but **not used**:\n\n" + "\n".join(
            f"- `{s.path.name}`: {r}" for s, r in sel.excluded))

    out += ["## Files", _table(["File", "Content"], [
        ["`samples_cos_history.csv`", "Main table, one row per sample. UTF-8; opens in Excel."],
        ["`samples_cos_history.gpkg`", "Same table with the sample points (GIS format, "
                                       "EPSG:3763 PT-TM06/ETRS89)."],
        ["`interpretation_summary.csv`", "Number and share of samples in each `interpretation` category."],
        ["`transitions_<a>_<b>.csv`", "Number of samples going from each class in edition a (rows) to "
                                      "each class in edition b (columns), for consecutive editions. "
                                      "`NA` = no COS polygon."],
        ["`group_summary.csv`", f"Summary per group (`{group_field}`)." if group_field else
         "Not produced (no group field given)."],
        ["`manifest.json`", "Provenance: parameters, input files with SHA-256 checksums, software versions."],
        ["`run.log`", "Processing messages and warnings."],
    ])]

    cols = [[f"`{id_field}`", "Sample ID (from the input sample layer).", "text"]]
    for k, d, t in (
        ("cls", "Class code at the comparison level. Empty if the point is outside every COS polygon.", "text"),
        ("label", "Class name (Portuguese, DGT designations).", "text"),
        ("poly", "COS polygon identifier, `<year>_<DGT ID>`. Samples with the same value share the "
                 "same polygon, hence the same class by construction.", "text"),
        ("dist", "Distance from the point to the edge of its COS polygon.", "m"),
    ):
        cols.append([f"`{k}_<year>`", d, t])
    for y in counts.get("series_check", {}):
        cols += [
            [f"`cls_{y}_S1`", f"Class of the Series 1 map of {y} (not part of the trajectory).", "text"],
            [f"`series_check_{y}`", f"1 if the Series 1 and Series 2 maps of {y} give the same class at the "
                                    "point, 0 if not.", "0/1"],
        ]
    cols += [
        ["`trajectory`", "Classes in time order joined by `|`; `NA` = no polygon in that edition.", "text"],
        ["`n_missing`", "Editions without a COS polygon at the point.", "count"],
        ["`stable`", "1 if the class is the same in all observed editions, else 0.", "0/1"],
        ["`n_changes`", "Number of changes between consecutive observed editions.", "count"],
        ["`stability_index`", "1 − n_changes / (number of observed editions − 1). 1 = never changed, "
                              "0 = changed at every edition.", "0–1"],
        ["`modal_persistence`", "Share of observed editions in the most frequent class.", "0–1"],
        ["`time_weighted_persistence`", "Share of the years between the first and last observed "
                                        "edition during which the class did not change (intervals "
                                        "between editions are unequal, so this differs from "
                                        "`stability_index`).", "0–1"],
        ["`last_change_year`", "Year of the edition in which the last change was observed. Empty if "
                               "stable.", "year"],
        ["`flip_flop`", "1 if the class goes A → B → A in three consecutive observed editions, often "
                        "an interpretation artefact rather than a real change.", "0/1"],
        ["`min_boundary_dist_m`", "Smallest `dist_<year>` over all editions.", "m"],
        ["`near_boundary`", f"1 if `min_boundary_dist_m` < {thr} m. See the warning at the top.", "0/1"],
        [f"`pts_in_poly_{last}`", f"Number of samples in the same COS polygon in {last}.", "count"],
        ["`interpretation`", "Summary category; see “How to read the results”.", "text"],
    ]
    out += ["## Columns of `samples_cos_history.csv`",
            f"`<year>` is each edition year: {', '.join(map(str, years))}.",
            _table(["Column", "Meaning", "Unit"], cols),
            "Metrics use only the *observed* editions (those where the point falls in a COS polygon). "
            "With fewer than two observed editions the change-based metrics are empty. No composite "
            "index is given: each metric answers a different question."]
    if group_field:
        out += [f"## Columns of `group_summary.csv` (one row per `{group_field}`)", _table(
            ["Column", "Meaning"], [
                ["`n_points`", "Number of samples in the group."],
                ["`n_polygons_<year>`", "Number of distinct COS polygons containing the group's samples."],
                ["`prop_changed`", "Share of samples with at least one change (samples with ≥ 2 observed "
                                   "editions)."],
                ["`n_trajectories`", "Number of distinct trajectories."],
                ["`prop_near_boundary`", "Share of samples with `near_boundary` = 1."],
                ["`prop_change_supported`", "Share of samples with `interpretation` = `change`."],
            ])]

    out += ["## Summary of this run", _table(["Item", "Value"], [
        ["Samples", n],
        ["Stable samples", counts["stable"]],
        ["Samples near a boundary", counts["near_boundary"]],
        ["Samples with flip-flop", counts["flip_flop"]],
        ["Samples outside COS, per edition", ", ".join(f"{y}: {v}" for y, v in counts["outside_coverage"].items())],
        ["Samples on a shared polygon edge, per edition",
         ", ".join(f"{y}: {v}" for y, v in counts["shared_edge_points"].items())],
    ])]

    level_codes = sorted((c for (lvl, c) in labels if lvl == level), key=metrics.natural_key)
    member_noms = sorted({k for m in sel.members.values() for k in m}) if merged and level == 4 else []
    rows = []
    for c in level_codes:
        row = [c, labels[(level, c)], "yes" if c in used_codes else ""]
        row += [", ".join(sel.members.get(c, {}).get(k, [])) for k in member_noms]
        rows.append(row)
    out += [f"## Classes at level {level}" + (" (merged classes)" if member_noms else f" (`{sel.nomenclature}`)"),
            "“In data” marks the classes that occur at the samples in this run."
            + (" Codes ending in `.m<n>` group several Series 2 classes; codes ending in `(S1)` are "
               "Series 1 classes without a Series 2 counterpart, so they cannot occur in a Series 2 edition."
               if member_noms else ""),
            _table(["Code", "Class", "In data"] + [f"{k} codes" for k in member_noms], rows)]

    out += ["## Limitations", _limitations(sel, cat, merged)]

    if not merged:
        for src, cw in sel.crosswalks.items():
            src_labels = catalog.load_labels(src)
            rows = [[c, src_labels.get((4, c), ""), t, labels.get((4, t), "")]
                    for c, t in sorted(cw.items(), key=lambda kv: metrics.natural_key(kv[0]))]
            out += [f"## Correspondence {src} → {sel.nomenclature} (level 4)",
                    notes[f"{src}->{sel.nomenclature}"] + ".",
                    _table([f"{src} code", f"{src} class", f"{sel.nomenclature} code",
                            f"{sel.nomenclature} class"], rows)]

    noms = sorted({s.product["nomenclature"] for s in list(sel.sources) + list(sel.check)})
    out += ["## Sources", "\n".join([f"- {k}: {cat['nomenclatures'][k]['source']}" for k in noms]
                                     + [f"- {k}: {v}" for k, v in notes.items()])]
    return "\n\n".join(p for p in out if p) + "\n"


_USE = {
    "stable": "Use as unchanged land use over the period covered.",
    "change": "Use as changed land use; the interval is given by `last_change_year` and `trajectory`.",
    "near_boundary": "Treat the change as uncertain; verify on imagery or analyse separately.",
    "flip_flop": "Treat as uncertain; the intermediate class is probably an artefact.",
    "series_difference": "Treat as unchanged; the two series describe the place differently.",
    "insufficient_data": "Exclude from change analysis.",
}


def _limitations(selection, cat, merged):
    sources = list(selection.sources) + list(selection.check)
    mmus = sorted({cat["nomenclatures"][s.product["nomenclature"]]["mmu_ha"] for s in sources})
    mmu = " / ".join(f"{m:g} ha" for m in mmus)
    items = [
        f"COS minimum mapping unit {mmu}, minimum distance between lines 20 m (DGT): smaller features "
        "are not mapped, and samples in the same polygon share the same history by construction.",
        f"Nothing before {selection.years[0]} is captured: older land-use legacies are invisible.",
        "Changes at points near a polygon boundary may be delineation differences between editions.",
        "A → B → A trajectories between close editions are often interpretation artefacts.",
        "Samples are clustered (e.g. in grids) and are not independent observations; transition "
        "counts are counts of samples, not area estimates.",
    ]
    if merged:
        items += [
            "DGT states that Series 1 and Series 2 should not be compared. The merged trajectory is an "
            "approximation: a change at the junction between series may be caused by different class "
            "definitions, production method or mapping unit even when `series_check` = 1.",
            "Merged classes are coarser than the original nomenclatures; Series 1 classes without a Series 2 "
            "counterpart always appear to change at the junction.",
        ]
    else:
        items.append("Series 1 and Series 2 of the COS are not comparable (DGT); this table uses one series only.")
        if selection.crosswalks:
            items.append("Recoding to the coarser common nomenclature removes detail present in the more "
                         "detailed editions (e.g. all artificial surfaces become 1.0.0.0 and all pastures "
                         "3.0.0.0, as in COS1995).")
    return "\n".join(f"- {i}" for i in items)
