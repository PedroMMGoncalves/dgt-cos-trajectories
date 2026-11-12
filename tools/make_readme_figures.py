"""Maintainer tool: figures of the README from a run on ``examples/demo_points.gpkg``.

Usage (from the repository root, after a linked run with ``--run-id demo``)::

    python tools/make_readme_figures.py 03_Resultados/demo 01_COS

Writes ``docs/img/demo_map.png`` and ``docs/img/demo_trajectories.png``.
Colour encodes the level-1 class; every polygon and cell also carries its
class code, so the figures do not depend on colour alone.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cos_trajectories import catalog, io  # noqa: E402

LEVEL1 = {  # level-1 code: (colour, English name)
    "1": ("#e34948", "Artificial"), "2": ("#eda100", "Agriculture"), "3": ("#1baf7a", "Pasture"),
    "4": ("#eb6834", "Agroforestry"), "5": ("#008300", "Forest"), "6": ("#6250d6", "Shrubland"),
    "7": ("#e87ba4", "Bare / sparse"), "8": ("#8a8a85", "Wetland"), "9": ("#2a78d6", "Water"),
}
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "text.color": INK, "axes.edgecolor": MUTED,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def l1(code):
    return str(code).split(".")[0]


def read_history(run_dir):
    h = pd.read_csv(Path(run_dir) / "samples_cos_history.csv", dtype=str, keep_default_na=False)
    g = io.read_layer(Path(run_dir) / "samples_cos_history.gpkg", layer="samples_cos_history")
    return h, g


def figure_map(run_dir, cos_dir, grid, out):
    h, g = read_history(run_dir)
    g = g[g["SAMPLE_ID"].str.startswith(grid)]
    b = g.total_bounds
    pad = 130
    view = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    found, _ = catalog.discover(cos_dir)
    sel = catalog.select(found, "S1")
    first, last = sel.sources[0], sel.sources[-1]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.9), constrained_layout=True)
    present = set()
    for ax, src in zip(axes, (first, last)):
        cos = io.read_layer(src.path, layer=src.layer, bbox=view, columns=[src.id_field, src.code_field])
        cos["cls"] = [sel.harmonise(c.strip(), src) for c in cos[src.code_field]]
        present.update(l1(c) for c in cos["cls"])
        cos.plot(ax=ax, color=[LEVEL1[l1(c)][0] for c in cos["cls"]], alpha=0.30, edgecolor="none")
        cos.boundary.plot(ax=ax, color=MUTED, linewidth=0.7)
        clipped = cos.clip(view)
        for _, r in clipped[clipped.area > 14000].iterrows():
            p = r.geometry.representative_point()
            ax.annotate(r["cls"], (p.x, p.y), ha="center", va="center", fontsize=7, color=INK,
                        bbox={"boxstyle": "round,pad=0.15", "fc": SURFACE, "ec": "none", "alpha": 0.8})
        changed = g["n_changes_S1"].astype(float) > 0
        near = g["near_boundary_S1"].astype(float) == 1
        ax.scatter(g.geometry.x[near], g.geometry.y[near], s=95, facecolor="none", edgecolor=INK, linewidth=0.9,
                   zorder=3)
        ax.scatter(g.geometry.x[~changed], g.geometry.y[~changed], s=26, facecolor=SURFACE, edgecolor=INK,
                   linewidth=1.0, zorder=4)
        ax.scatter(g.geometry.x[changed], g.geometry.y[changed], s=26, facecolor=INK, edgecolor=SURFACE,
                   linewidth=0.8, zorder=4)
        ax.set_xlim(view[0], view[2])
        ax.set_ylim(view[1], view[3])
        ax.set_aspect("equal")
        ax.set_title(f"COS{src.edition} (Series 1, COS1995 nomenclature)", fontsize=9, loc="left")
        ax.set_xlabel("x (m, EPSG:3763)")
        ax.ticklabel_format(style="plain", useOffset=False)
        ax.tick_params(labelsize=6.5)
    axes[0].set_ylabel("y (m, EPSG:3763)")
    present = sorted(present)
    handles = [Patch(facecolor=LEVEL1[k][0], alpha=0.30, edgecolor=MUTED, label=f"{k} {LEVEL1[k][1]}") for k in present]
    handles += [
        Line2D([], [], marker="o", ls="", mfc=SURFACE, mec=INK, ms=5.5, label="sample, stable 1995–2018"),
        Line2D([], [], marker="o", ls="", mfc=INK, mec=SURFACE, ms=6, label="sample, class changed"),
        Line2D([], [], marker="o", ls="", mfc="none", mec=INK, ms=10, label="near_boundary = 1 (< 25 m)"),
    ]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, frameon=False, fontsize=7.5)
    fig.savefig(out, dpi=170)
    plt.close(fig)


def figure_trajectories(run_dir, out):
    h, _ = read_history(run_dir)
    cols = [c for c in h.columns if c.startswith("cls_")]
    s1 = [c for c in cols if c.endswith("_S1")]
    s2 = [c for c in cols if c.endswith("_S2")]
    xs = {c: i for i, c in enumerate(s1)}
    xs.update({c: len(s1) + 0.6 + i for i, c in enumerate(s2)})
    grids = sorted(h["SAMPLE_ID"].str[0].unique())
    fig, axes = plt.subplots(1, len(grids), figsize=(11.5, 6.4), constrained_layout=True)
    for ax, grid in zip(axes, grids):
        d = h[h["SAMPLE_ID"].str.startswith(grid)].reset_index(drop=True)
        for i, r in d.iterrows():
            for c, x in xs.items():
                code = r[c]
                ax.add_patch(Rectangle((x + 0.03, i + 0.06), 0.94, 0.88, facecolor=LEVEL1[l1(code)][0], alpha=0.38,
                                       edgecolor="none"))
                ax.text(x + 0.5, i + 0.5, code, ha="center", va="center", fontsize=5.6, color=INK)
            mark = ("●" if r["n_changes_S1"] != "0" or r["n_changes_S2"] != "0" else "") + \
                   ("  b" if "1" in (r["near_boundary_S1"], r["near_boundary_S2"]) else "") + \
                   ("  ≠" if r["agree_l1_2018"] == "0" else "")
            ax.text(max(xs.values()) + 1.12, i + 0.5, mark, ha="left", va="center", fontsize=6, color=INK)
        ax.set_xlim(0, max(xs.values()) + 1.9)
        ax.set_ylim(len(d), 0)
        ax.set_xticks([x + 0.5 for x in xs.values()])
        ax.set_xticklabels([c.split("_")[1] for c in xs], fontsize=6.5)
        ax.set_yticks([i + 0.5 for i in range(len(d))])
        ax.set_yticklabels(d["SAMPLE_ID"], fontsize=6)
        ax.tick_params(length=0)
        ax.xaxis.tick_top()
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(f"Grid {grid}", fontsize=9, loc="left", pad=22)
        ax.text(len(s1) / 2, -1.25, "Series 1", ha="center", fontsize=7, color=MUTED)
        ax.text(len(s1) + 0.6 + len(s2) / 2, -1.25, "Series 2", ha="center", fontsize=7, color=MUTED)
    present = sorted({l1(c) for c in h[cols].values.ravel() if c})
    handles = [Patch(facecolor=LEVEL1[k][0], alpha=0.38, label=f"{k} {LEVEL1[k][1]}") for k in present]
    handles += [Line2D([], [], ls="", label="●  class changed within a series"),
                Line2D([], [], ls="", label="b  near_boundary = 1"),
                Line2D([], [], ls="", label="≠  agree_l1_2018 = 0")]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, frameon=False, fontsize=7.5, handlelength=1.2)
    fig.savefig(out, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    run_dir, cos_dir = sys.argv[1], sys.argv[2]
    img = ROOT / "docs" / "img"
    img.mkdir(parents=True, exist_ok=True)
    figure_map(run_dir, cos_dir, "C", img / "demo_map.png")
    figure_trajectories(run_dir, img / "demo_trajectories.png")
    print("wrote", img)
