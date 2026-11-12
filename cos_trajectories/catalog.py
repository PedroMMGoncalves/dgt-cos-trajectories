"""Discovery, identification and selection of DGT COS layers.

Identification is by the DGT file-name convention ``COS<year>v<version>``,
optionally followed by ``-S<series>`` (case-insensitive: DGT ships both
``COS2018v2-S1.gpkg`` and ``cos2018v4.gpkg``). The (edition, version) pair is
looked up in ``catalog.json``, which gives the series, layer name, class and
id fields and the nomenclature. A schema check (class and id fields present)
confirms the identification; a mismatch is a hard error. Files that do not
follow the convention (e.g. COS conjuntural, ``COSc2020``) are ignored.

Comparability rules:

- Series 1 and Series 2 are never mixed: DGT states that maps of different
  series should not be compared (different concepts, nomenclature
  structure and geometric detail).
- Editions flagged ``obsolete`` in the catalog are excluded (currently
  COS2023v1: DGT states that only COS2018v4 and COS2025v1 are comparable).
- If the selected editions use different nomenclatures, all are recoded to a
  common one through a DGT crosswalk (Series 1 with COS1995: the 83-class
  nomenclature of 2007-2018 is recoded to the 44-class COS1995 nomenclature,
  DGT 2022, Anexo 3). Without a crosswalk the run stops.
"""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import io

PKG_DIR = Path(__file__).resolve().parent
CATALOG_PATH = PKG_DIR / "catalog.json"
NOMENCLATURE_DIR = PKG_DIR / "nomenclature"
SERIES = ("S1", "S2")
VECTOR_SUFFIXES = (".gpkg", ".shp")
NAME_RE = re.compile(r"^COS(\d{4})v(\d+)(?:-S(\d))?$", re.IGNORECASE)


class InputError(Exception):
    """Invalid user input or data; the run cannot continue. Message is user-facing."""


class CatalogError(InputError):
    """Inconsistent or unsupported COS input."""


@dataclass
class CosSource:
    path: Path
    layer: str
    product: dict
    code_field: str
    id_field: str

    @property
    def edition(self):
        return self.product["edition"]

    @property
    def name(self):
        p = self.product
        return f"COS{p['edition']}v{p['version']}-{p['series']}"


@dataclass
class Selection:
    sources: list
    series: str
    nomenclature: str
    max_level: int
    crosswalks: dict = field(default_factory=dict)  # source nomenclature -> {code: code}
    excluded: list = field(default_factory=list)  # (CosSource, reason)

    @property
    def years(self):
        return [s.edition for s in self.sources]

    def harmonise(self, code, source):
        """Level-4 code of ``source`` expressed in the selection's nomenclature."""
        nom = source.product["nomenclature"]
        if nom == self.nomenclature:
            return code
        try:
            return self.crosswalks[nom][code]
        except KeyError:
            raise CatalogError(
                f"{source.name}: class code {code!r} has no correspondence in "
                f"crosswalk {nom}->{self.nomenclature}"
            ) from None

    @property
    def levels(self):
        return tuple(range(1, self.max_level + 1))

    def labels(self):
        return load_labels(self.nomenclature)

    def crosswalk_sources(self, catalog):
        """``{crosswalk name: source}`` of the correspondence tables applied."""
        return {f"{n}->{self.nomenclature}": catalog["crosswalks"][f"{n}->{self.nomenclature}"]["source"]
                for n in self.crosswalks}


def load_catalog(path=CATALOG_PATH):
    return io.read_json(path)


def load_labels(nomenclature):
    """``{(level, code): label}`` for a packaged nomenclature."""
    text = io.read_text(NOMENCLATURE_DIR / f"{nomenclature}.csv")
    return {(int(r["level"]), r["code"]): r["label"] for r in csv.DictReader(text.splitlines())}


def recode(code, level):
    """Truncate a dotted COS code to ``level`` (``"2.3.1.1"``, 2 -> ``"2.3"``)."""
    return ".".join(str(code).split(".")[:level])


def _match_field(fields, wanted):
    by_lower = {f.lower(): f for f in fields}
    return by_lower.get(wanted.lower())


def discover(cos_dir, catalog=None):
    """Identify COS layers in ``cos_dir``.

    Returns ``(found, ignored)``: a list of :class:`CosSource` and a list of
    ``(path, reason)`` for files that were skipped.
    """
    catalog = catalog or load_catalog()
    cos_dir = Path(cos_dir)
    if not cos_dir.is_dir():
        raise CatalogError(f"COS directory not found: {cos_dir}")
    found, ignored = [], []
    for path in io.list_files(cos_dir):
        if path.name.startswith(".") or path.name.lower() == "readme.md":
            continue  # repository placeholders
        if path.suffix.lower() not in VECTOR_SUFFIXES:
            if path.suffix.lower() not in (".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".xml"):
                ignored.append((path, "not a GeoPackage or shapefile"))
            continue
        m = NAME_RE.match(path.stem)
        if not m:
            ignored.append((path, "name does not follow the DGT COS convention COS<year>v<version>[-S<n>]"))
            continue
        edition, version = int(m.group(1)), int(m.group(2))
        file_series = f"S{m.group(3)}" if m.group(3) else None
        candidates = [p for p in catalog["products"] if p["edition"] == edition and p["version"] == version]
        if not candidates:
            ignored.append((path, f"COS{edition}v{version} is not in the catalog (catalog.json)"))
            continue
        if file_series:
            matching = [p for p in candidates if p["series"] == file_series]
            if not matching:
                raise CatalogError(
                    f"{path.name}: file name says series {file_series} but the catalog lists "
                    f"COS{edition}v{version} as series {candidates[0]['series']}"
                )
            candidates = matching
        if len(candidates) > 1:
            raise CatalogError(f"{path.name}: ambiguous; add the -S<n> series suffix to the file name")
        prod = candidates[0]
        found.append(_check_schema(path, prod))
    return found, ignored


def _check_schema(path, prod):
    if path.suffix.lower() == ".shp":
        layer = path.stem
    else:
        layers = io.list_layers(path)
        layer = next((lyr for lyr in layers if lyr.lower() == prod["layer"].lower()), None)
        if layer is None:
            raise CatalogError(f"{path.name}: expected layer {prod['layer']!r}, found {layers}")
    fields = io.layer_info(path, layer)["fields"]
    code_field = _match_field(fields, prod["code_field"])
    id_field = _match_field(fields, prod["id_field"])
    missing = [w for w, f in ((prod["code_field"], code_field), (prod["id_field"], id_field)) if f is None]
    if missing:
        raise CatalogError(
            f"{path.name} (layer {layer}): expected field(s) {missing} not found; the file name "
            f"identifies it as COS{prod['edition']}v{prod['version']}. Fields present: {fields}"
        )
    return CosSource(path=path, layer=layer, product=prod, code_field=code_field, id_field=id_field)


def select(found, series, catalog=None):
    """Choose the editions of ``series`` to compare and the common nomenclature."""
    catalog = catalog or load_catalog()
    if series not in SERIES:
        raise CatalogError(f"series must be S1 or S2, got {series!r}")
    in_series = [s for s in found if s.product["series"] == series]
    excluded = [(s, s.product.get("obsolete_reason", "obsolete")) for s in in_series if s.product.get("obsolete")]
    sources = sorted((s for s in in_series if not s.product.get("obsolete")), key=lambda s: s.edition)
    years = [s.edition for s in sources]
    dups = sorted({y for y in years if years.count(y) > 1})
    if dups:
        names = [s.path.name for s in sources if s.edition in dups]
        raise CatalogError(f"more than one version of edition(s) {dups} in series {series}: {names}. "
                           "Keep only one version per edition in the COS directory.")
    if len(sources) < 2:
        raise CatalogError(f"at least two editions of series {series} are needed, found {len(sources)}: "
                           f"{[s.name for s in sources]}")
    noms = sorted({s.product["nomenclature"] for s in sources})
    crosswalks, target = {}, noms[0]
    if len(noms) > 1:
        cws = catalog.get("crosswalks", {})
        targets = [t for t in noms if all(f"{n}->{t}" in cws for n in noms if n != t)]
        if not targets:
            raise CatalogError(f"editions of series {series} use different nomenclatures {noms} and the "
                               "catalog has no crosswalk to a common nomenclature")
        target = targets[0]
        crosswalks = {n: cws[f"{n}->{target}"]["map"] for n in noms if n != target}
    nom = catalog["nomenclatures"][target]
    max_level = min([nom["levels"]] + [s.product["code_level"] for s in sources])
    return Selection(sources=sources, series=series, nomenclature=target, max_level=max_level,
                     crosswalks=crosswalks, excluded=excluded)
