"""Maintainer tool: extract COS nomenclature tables from the DGT GeoPackages.

Not used at run time. Re-run only when a new COS edition is added to
``cos_trajectories/catalog.json``. It reads the distinct (code, label) pairs
of every level field directly from the GeoPackage attribute tables (SQLite,
read-only) and writes one CSV per nomenclature to
``cos_trajectories/nomenclature/<nomenclature>.csv`` with columns
``level,code,label``. Codes are written in dotted form at every level
(``1.1.1``), derived by truncating the level-4 code, because some editions
store the level 1-3 codes without dots (``111``).

Usage (from the repository root)::

    python tools/extract_nomenclature.py 01_COS

Editions sharing a nomenclature are merged (union of the classes present in
each one); conflicting labels for the same code abort the script.
"""
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "cos_trajectories"


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def main(cos_dir):
    cat = json.loads((PKG / "catalog.json").read_text(encoding="utf-8"))
    files = {p.stem.lower(): p for p in Path(cos_dir).glob("*.gpkg")}
    tables = {}
    for prod in cat["products"]:
        stem = next((s for s in files if s.startswith(prod["layer"].lower())), None)
        if stem is None:
            print("not found, skipped:", prod["layer"])
            continue
        con = sqlite3.connect(f"file:{files[stem]}?mode=ro", uri=True)
        table = tables.setdefault(prod["nomenclature"], {})
        code4 = prod["code_field"]
        label4 = prod["label_field"]
        level_fields = prod.get("level_fields", {})
        rows = con.execute(f'SELECT DISTINCT "{code4}", "{label4}" FROM "{prod["layer"]}"')
        pairs = [(4, c.strip(), norm(l)) for c, l in rows]
        for lvl, (cf, lf) in level_fields.items():
            q = f'SELECT DISTINCT "{code4}", "{cf}", "{lf}" FROM "{prod["layer"]}"'
            for c4, c, l in con.execute(q):
                dotted = ".".join(c4.strip().split(".")[: int(lvl)])
                if c.replace(".", "").strip() != dotted.replace(".", ""):
                    raise SystemExit(f"{prod['layer']}: {cf}={c!r} is not a prefix of {c4!r}")
                pairs.append((int(lvl), dotted, norm(l)))
        con.close()
        for lvl, c, l in pairs:
            old = table.get((lvl, c))
            if old is not None and old != l:
                raise SystemExit(f"{prod['nomenclature']}: label conflict for {c}: {old!r} vs {l!r}")
            table[(lvl, c)] = l
        print("read", prod["layer"], "->", prod["nomenclature"], len(pairs), "pairs")
    for nom, table in tables.items():
        out = PKG / "nomenclature" / f"{nom}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["level", "code", "label"])
            for (lvl, c), l in sorted(table.items()):
                w.writerow([lvl, c, l])
        print("wrote", out, len(table), "rows")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "01_COS")
