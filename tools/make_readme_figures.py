"""Maintainer tool: figures of the documentation from a run on ``examples/demo_points.gpkg``.

Usage (from the repository root, after a run with ``--series S1 --run-id demo``)::

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
UNCERTAIN = ("near_boundary", "flip_flop")
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
    _, g = read_history(run_dir)
    g = g[g["SAMPLE_ID"].str.startswith(grid)]
    b = g.total_bounds
    pad = 130
    view = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    found, _ = catalog.discover(cos_dir)
    sel = catalog.select(found, "S1")
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.9), constrained_layout=True)
    present = set()
    for ax, src in zip(axes, (sel.sources[0], sel.sources[-1])):
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
        kind = g["interpretation"]
        for mask, fc, ec in ((kind == "stable", SURFACE, INK), (kind.isin(UNCERTAIN), "#9a9994", INK),
                             (kind == "change", INK, SURFACE)):
            ax.scatter(g.geometry.x[mask], g.geometry.y[mask], s=30, facecolor=fc, edgecolor=ec, linewidth=1.0,
                       zorder=4)
        ax.set_xlim(view[0], view[2])
        ax.set_ylim(view[1], view[3])
        ax.set_aspect("equal")
        ax.set_title(f"COS{src.edition} (Series 1, COS1995 nomenclature)", fontsize=9, loc="left")
        ax.set_xlabel("x (m, EPSG:3763)")
        ax.ticklabel_format(style="plain", useOffset=False)
        ax.tick_params(labelsize=6.5)
    axes[0].set_ylabel("y (m, EPSG:3763)")
    handles = [Patch(facecolor=LEVEL1[k][0], alpha=0.30, edgecolor=MUTED, label=f"{k} {LEVEL1[k][1]}")
               for k in sorted(present)]
    handles += [
        Line2D([], [], marker="o", ls="", mfc=SURFACE, mec=INK, ms=5.5, label="interpretation: stable"),
        Line2D([], [], marker="o", ls="", mfc="#9a9994", mec=INK, ms=5.5,
               label="interpretation: near_boundary or flip_flop"),
        Line2D([], [], marker="o", ls="", mfc=INK, mec=SURFACE, ms=6.5, label="interpretation: change"),
    ]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, frameon=False, fontsize=7.5)
    fig.savefig(out, dpi=170)
    plt.close(fig)


def figure_trajectories(run_dir, out):
    h, _ = read_history(run_dir)
    cols = [c for c in h.columns if c.startswith("cls_")]
    xs = {c: i for i, c in enumerate(cols)}
    right = max(xs.values()) + 1.15
    grids = sorted(h["SAMPLE_ID"].str[0].unique())
    fig, axes = plt.subplots(1, len(grids), figsize=(11.0, 6.4), constrained_layout=True)
    for ax, grid in zip(axes, grids):
        d = h[h["SAMPLE_ID"].str.startswith(grid)].reset_index(drop=True)
        for i, r in d.iterrows():
            for c, x in xs.items():
                code = r[c]
                ax.add_patch(Rectangle((x + 0.03, i + 0.06), 0.94, 0.88, facecolor=LEVEL1[l1(code)][0],
                                       alpha=0.38, edgecolor="none"))
                ax.text(x + 0.5, i + 0.5, code, ha="center", va="center", fontsize=5.4, color=INK)
            ax.text(right, i + 0.5, r["interpretation"].replace("_", " "), ha="left", va="center", fontsize=5.6,
                    color=INK if r["interpretation"] != "stable" else MUTED)
        ax.set_xlim(0, right + 2.6)
        ax.set_ylim(len(d), 0)
        ax.set_xticks([x + 0.5 for x in xs.values()])
        ax.set_xticklabels([c.split("_")[1] for c in xs], fontsize=6.5)
        ax.set_yticks([i + 0.5 for i in range(len(d))])
        ax.set_yticklabels(d["SAMPLE_ID"], fontsize=6)
        ax.tick_params(length=0)
        ax.xaxis.tick_top()
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(f"Grid {grid}", fontsize=9, loc="left", pad=8)
    present = sorted({l1(c) for c in h[cols].values.ravel() if c})
    handles = [Patch(facecolor=LEVEL1[k][0], alpha=0.38, label=f"{k} {LEVEL1[k][1]}") for k in present]
    handles.append(Line2D([], [], ls="", label="right of each row: interpretation"))
    fig.legend(handles=handles, loc="outside lower center", ncol=6, frameon=False, fontsize=7.5, handlelength=1.2)
    fig.savefig(out, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    run_dir, cos_dir = sys.argv[1], sys.argv[2]
    img = ROOT / "docs" / "img"
    img.mkdir(parents=True, exist_ok=True)
    figure_map(run_dir, cos_dir, "C", img / "demo_map.png")
    figure_trajectories(run_dir, img / "demo_trajectories.png")
    print("wrote", img)
