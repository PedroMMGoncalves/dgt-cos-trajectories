"""Run manifest (machine-readable provenance) and data dictionary (for non-GIS users).

The data dictionary repeats the methodological limitations of the method
(see README): minimum mapping unit, no information before the first edition,
boundary and flip-flop artefacts, clustered samples, and non-comparability of
COS Series 1 and Series 2 (in linked mode the two series are side by side,
never merged).
"""
from pathlib import Path

from . import __version__, catalog, io, metrics

BOUNDARY_WARNING = (
    "> A class change at a point flagged `near_boundary` may reflect polygon\n"
    "> delineation differences between editions, not a real land-use change."
)


def build_manifest(run_id, started, params, selections, ignored, cat, samples_path, samples_layer,
                   sample_crs, n_samples, counts, software, outputs, with_hash=True):
    series = []
    for sel in selections:
        layers = []
        for s in sel.sources:
            fp = io.file_fingerprint(s.path, with_hash=with_hash)
            layers.append({
                "edition": s.edition, "version": s.product["version"], "series": s.product["series"],
                "layer": s.layer, "class_field": s.code_field, "id_field": s.id_field,
                "nomenclature": s.product["nomenclature"], **fp,
            })
        series.append({
            "series": sel.series,
            "nomenclature": sel.nomenclature,
            "crosswalks_applied": {n: cat["crosswalks"][f"{n}->{sel.nomenclature}"]["source"]
                                   for n in sel.crosswalks},
            "max_common_level": sel.max_level,
            "cos_layers": layers,
            "excluded_cos_layers": [{"file": s.path.name, "reason": r} for s, r in sel.excluded],
        })
    return {
        "run_id": run_id,
        "started": started.isoformat(timespec="seconds"),
        "tool": "cos_trajectories",
        "tool_version": __version__,
        "parameters": params,
        "linked_series": len(selections) > 1,
        "series": series,
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


def _eds(sel):
    return ", ".join(f"COS{s.edition}v{s.product['version']}" for s in sel.sources)


def data_dictionary(selections, labels, used_codes, cat, level, id_field, group_field, threshold, counts,
                    run_id, linked=False, bridge_years=()):
    thr = f"{threshold:g}"
    sx = (lambda sel: f"_{sel.series}") if linked else (lambda sel: "")
    yr = "<year>_S1" if linked else "<year>"
    out = [
        "# Data dictionary: COS land-use history of the samples",
        BOUNDARY_WARNING,
        f"Run `{run_id}`, produced by `cos_trajectories` {__version__}. Exact inputs, file checksums "
        "and software versions are in `manifest.json`; processing messages are in `run.log`.",
        "## What this is",
        "For every sample (one row per sample ID) the files give the land-use/land-cover class of the "
        "DGT *Carta de Uso e Ocupação do Solo* (COS) polygon that contains the sample point in each "
        "COS edition, and simple measures of how stable that class was over time. The table can be joined to "
        f"external tables through the column `{id_field}`. No soil or laboratory data is included.",
    ]
    if linked:
        out += _linked_section(selections, counts, bridge_years)

    out.append("## COS editions and classes used")
    for sel in selections:
        nom = cat["nomenclatures"][sel.nomenclature]
        if linked:
            out.append(f"### Series {sel.series} (columns ending in `_{sel.series}`)")
        out.append(_table(["Item", "Value"], [
            ["Series", sel.series + ("" if linked else " (Series 1 and Series 2 are never mixed: DGT "
                                                        "states they are not comparable)")],
            ["Editions", _eds(sel)],
            ["Nomenclature", f"{sel.nomenclature}: {nom['description']}"],
            ["Comparison level", f"{level} of {sel.max_level} (1 = coarsest, 4 = most detailed)"],
            ["Boundary threshold", f"{thr} m"],
        ]))
        if sel.crosswalks:
            src = next(iter(sel.crosswalks))
            out.append(
                f"Editions with a more detailed nomenclature were recoded to `{sel.nomenclature}` with the "
                f"official DGT correspondence table ({cat['crosswalks'][src + '->' + sel.nomenclature]['source']}), "
                "so that the same code means the same class in every edition of this series. The full "
                "correspondence is listed at the end of this document.")
        if sel.excluded:
            out.append("Editions found but **not used**:\n\n" + "\n".join(
                f"- `{s.path.name}`: {r}" for s, r in sel.excluded))

    trans = ("`transitions_<series>_<a>_<b>.csv`" if linked else "`transitions_<a>_<b>.csv`")
    files = [
        ["`samples_cos_history.csv`", "Main table, one row per sample. UTF-8; opens in Excel."],
        ["`samples_cos_history.gpkg`", "Same table with the sample points (GIS format, "
                                       "EPSG:3763 PT-TM06/ETRS89)."],
        [trans, "Number of samples going from each class in edition a (rows) to each class in edition b "
                "(columns), for consecutive editions" + (" of the same series" if linked else "") +
                ". `NA` = no COS polygon."],
    ]
    for y in bridge_years:
        files.append([f"`bridge_{y}_level1.csv`", f"Level-1 class of the {y} map of Series 1 (rows) against "
                      f"the {y} map of Series 2 (columns) at the samples. Same year: off-diagonal counts "
                      "are differences between the two series, not changes."])
    files += [
        ["`group_summary.csv`", f"Summary per group (`{group_field}`)." if group_field else
         "Not produced (no group field given)."],
        ["`manifest.json`", "Provenance: parameters, input files with SHA-256 checksums, software versions."],
        ["`run.log`", "Processing messages and warnings."],
    ]
    out += ["## Files", _table(["File", "Content"], files)]

    out += ["## Columns of `samples_cos_history.csv`"]
    if linked:
        out.append("Every column except the sample ID and `agree_l1_<year>` exists once per series and ends "
                   "in `_S1` or `_S2`; the table below shows the `_S1` names. "
                   + " ".join(f"For `_{sel.series}`, `<year>` is {', '.join(map(str, sel.years))}."
                              for sel in selections))
    else:
        out.append(f"`<year>` is each edition year: {', '.join(map(str, selections[0].years))}.")
    s = "_S1" if linked else ""
    last = "<last year>" if linked else str(selections[0].years[-1])
    cols = [[f"`{id_field}`", "Sample ID (from the input sample layer).", "text"]]
    for k, d, t in (
        ("cls", "COS class code at the comparison level (hierarchical: `2.1` is inside `2`). "
                "Empty if the point is outside every COS polygon.", "text"),
        ("label", "Class name (Portuguese, DGT nomenclature).", "text"),
        ("poly", "COS polygon identifier, `<year>_<DGT ID>`. Samples with the same value share the "
                 "same polygon, hence the same class by construction.", "text"),
        ("dist", "Distance from the point to the edge of its COS polygon.", "m"),
    ):
        cols.append([f"`{k}_{yr}`", d, t])
    within = " Computed within the series only." if linked else ""
    cols += [
        [f"`trajectory{s}`", "Classes in time order joined by `|`; `NA` = no polygon in that edition.", "text"],
        [f"`n_missing{s}`", "Editions without a COS polygon at the point.", "count"],
        [f"`stable{s}`", "1 if the class is the same in all observed editions, else 0." + within, "0/1"],
        [f"`n_changes{s}`", "Number of changes between consecutive observed editions." + within, "count"],
        [f"`stability_index{s}`", "1 − n_changes / (number of observed editions − 1). 1 = never changed, "
                                  "0 = changed at every edition.", "0–1"],
        [f"`modal_persistence{s}`", "Share of observed editions in the most frequent class.", "0–1"],
        [f"`time_weighted_persistence{s}`", "Share of the years between the first and last observed "
                                            "edition during which the class did not change (intervals "
                                            "between editions are unequal, so this differs from "
                                            "`stability_index`).", "0–1"],
        [f"`last_change_year{s}`", "Year of the edition in which the last change was observed. Empty if "
                                   "stable.", "year"],
        [f"`flip_flop{s}`", "1 if the class goes A → B → A in three consecutive observed editions, often "
                            "an interpretation artefact rather than a real change.", "0/1"],
        [f"`min_boundary_dist_m{s}`", f"Smallest `dist_{yr}` over the editions.", "m"],
        [f"`near_boundary{s}`", f"1 if `min_boundary_dist_m{s}` < {thr} m. See the warning at the top.", "0/1"],
        [f"`pts_in_poly_{last}{s}`", "Number of samples in the same COS polygon in the last edition.", "count"],
    ]
    for y in bridge_years:
        cols.append([f"`agree_l1_{y}`", f"1 if the {y} maps of Series 1 and Series 2 give the same level-1 "
                     "class at the point, 0 if not, empty if either is missing. Not a change: both maps are "
                     f"of {y}. Use it to judge whether the Series 1 history at the point is described in "
                     "comparable terms by Series 2.", "0/1"])
    out += [_table(["Column", "Meaning", "Unit"], cols),
            "Metrics use only the *observed* editions (those where the point falls in a COS polygon). "
            "With fewer than two observed editions the change-based metrics are empty. No composite "
            "index is given: each metric answers a different question."]

    if group_field:
        grows = [
            ["`n_points`", "Number of samples in the group."],
            [f"`n_polygons_{yr}`", "Number of distinct COS polygons containing the group's samples."],
            [f"`prop_changed{s}`", "Share of samples with at least one change (samples with ≥ 2 observed "
                                   "editions)."],
            [f"`n_trajectories{s}`", "Number of distinct trajectories."],
            [f"`prop_near_boundary{s}`", f"Share of samples with `near_boundary{s}` = 1."],
        ]
        for y in bridge_years:
            grows.append([f"`prop_agree_l1_{y}`", f"Share of samples with `agree_l1_{y}` = 1."])
        out += [f"## Columns of `group_summary.csv` (one row per `{group_field}`)",
                ("Columns other than the group, `n_points` and `prop_agree_l1_<year>` exist once per "
                 "series (`_S1`, `_S2`)." if linked else ""), _table(["Column", "Meaning"], grows)]

    rows = [["Samples", counts["n_samples_out"]]]
    for sel in selections:
        c = counts["by_series"][sel.series]
        tag = f" ({sel.series})" if linked else ""
        rows += [
            [f"Stable samples{tag}", c["stable"]],
            [f"Samples near a boundary{tag}", c["near_boundary"]],
            [f"Samples with flip-flop{tag}", c["flip_flop"]],
            [f"Samples outside COS, per edition{tag}",
             ", ".join(f"{y}: {n}" for y, n in c["outside_coverage"].items())],
            [f"Samples on a shared polygon edge, per edition{tag}",
             ", ".join(f"{y}: {n}" for y, n in c["shared_edge_points"].items())],
        ]
    for y, b in counts.get("bridge", {}).items():
        rows.append([f"Same level-1 class in the S1 and S2 maps of {y}", f"{b['agree_l1']} of {b['compared']}"])
    out += ["## Summary of this run", _table(["Item", "Value"], rows)]

    for sel, lab, used in zip(selections, labels, used_codes):
        level_codes = sorted((c for (lvl, c) in lab if lvl == level), key=metrics.natural_key)
        out += [f"## Classes at level {level} (`{sel.nomenclature}`" + (f", Series {sel.series})" if linked else ")"),
                "“In data” marks the classes that occur at the samples in this run.",
                _table(["Code", "Class (DGT)", "In data"],
                       [[c, lab[(level, c)], "yes" if c in used else ""] for c in level_codes])]

    out += ["## Limitations", _limitations(selections, cat, linked)]

    for sel, lab in zip(selections, labels):
        for src, cw in sel.crosswalks.items():
            src_labels = catalog.load_labels(src)
            rows = [[c, src_labels.get((4, c), ""), t, lab.get((4, t), "")]
                    for c, t in sorted(cw.items(), key=lambda kv: metrics.natural_key(kv[0]))]
            out += [f"## Correspondence {src} → {sel.nomenclature} (level 4)",
                    cat["crosswalks"][f"{src}->{sel.nomenclature}"]["source"] + ".",
                    _table([f"{src} code", f"{src} class", f"{sel.nomenclature} code",
                            f"{sel.nomenclature} class"], rows)]

    noms = sorted({s.product["nomenclature"] for sel in selections for s in sel.sources})
    out += ["## Sources", "\n".join(f"- {n}: {cat['nomenclatures'][n]['source']}" for n in noms)]
    return "\n\n".join(p for p in out if p) + "\n"


def _linked_section(selections, counts, bridge_years):
    s1, s2 = selections
    text = [
        "## Two COS series, linked side by side (not merged)",
        f"Series 1 ({_eds(s1)}) and Series 2 ({_eds(s2)}) are in the same table, one block of columns "
        "each (`_S1`, `_S2`). DGT states that the two series cannot be compared: Series 2 changed the "
        "nomenclature and the concepts of the classes. Therefore **no change, trajectory or stability "
        "metric is computed across the two series**: read the Series 1 history and the Series 2 history "
        "separately.",
    ]
    for y in bridge_years:
        b = counts["bridge"][str(y)]
        n_diff = b["compared"] - b["agree_l1"]
        text.append(
            f"Both series include a map of {y}. At {n_diff} of {b['compared']} samples the two {y} maps give "
            f"a different level-1 class even though they describe the same year: that is the size of the "
            f"break between the series at these points. A Series 1 → Series 2 difference is therefore not "
            f"evidence of land-use change. `agree_l1_{y}` flags each point.")
    return text


def _limitations(selections, cat, linked):
    sources = [s for sel in selections for s in sel.sources]
    mmus = sorted({cat["nomenclatures"][s.product["nomenclature"]]["mmu_ha"] for s in sources})
    mmu = " / ".join(f"{m:g} ha" for m in mmus)
    firsts = ", ".join(f"{sel.years[0]} ({sel.series})" for sel in selections) if linked else str(selections[0].years[0])
    items = [
        f"COS minimum mapping unit {mmu}, minimum distance between lines 20 m (DGT): smaller features "
        "are not mapped, and samples in the same polygon share the same history by construction.",
        f"Nothing before {firsts} is captured: older land-use legacies are invisible.",
        "Changes at points near a polygon boundary may be delineation differences between editions.",
        "A → B → A trajectories between close editions are often interpretation artefacts.",
        "Samples are clustered (e.g. quadrats) and are not independent observations; transition "
        "counts are counts of samples, not area estimates.",
        ("Series 1 and Series 2 of the COS are not comparable (DGT): they are shown side by side and "
         "never merged; differences between them are not land-use changes." if linked else
         "Series 1 and Series 2 of the COS are not comparable (DGT); this table uses one series only."),
    ]
    for sel in selections:
        if sel.crosswalks:
            example = (" (e.g. all artificial surfaces become 1.0.0.0 and all pastures 3.0.0.0, as in COS1995)"
                       if sel.nomenclature == "S1-1995" else "")
            items.append(f"Recoding Series {sel.series} to its coarser common nomenclature removes detail present "
                         f"in the more detailed editions{example}.")
    return "\n".join(f"- {i}" for i in items)
