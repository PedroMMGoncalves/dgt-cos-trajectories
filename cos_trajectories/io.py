"""All file I/O of the package.

The default ArcGIS Pro environment (``arcgispro-py3``) ships geopandas with
fiona but *without* pyogrio. Vector reading/writing therefore goes through
``geopandas`` with ``engine="fiona"``; layer listing and schema inspection try
pyogrio first and fall back to fiona. If Esri changes the bundled engines,
only this module needs to change.
"""
import hashlib
import json
from pathlib import Path

import geopandas as gpd

ENGINE = "fiona"


def _pyogrio():
    try:
        import pyogrio  # noqa: F401
        return pyogrio
    except ImportError:
        return None


def list_layers(path):
    """Layer names of a vector data source (a shapefile has a single layer)."""
    pg = _pyogrio()
    if pg is not None:
        return [str(name) for name, _ in pg.list_layers(path)]
    import fiona
    return list(fiona.listlayers(str(path)))


def layer_info(path, layer=None):
    """Return ``{"fields", "geometry_type", "crs", "n_features"}`` for a layer.

    ``crs`` is a ``pyproj.CRS`` (or ``None``); ``n_features`` may be ``None``
    if the driver cannot count cheaply.
    """
    from pyproj import CRS
    pg = _pyogrio()
    if pg is not None:
        info = pg.read_info(path, layer=layer)
        return {
            "fields": [str(f) for f in info["fields"]],
            "geometry_type": info["geometry_type"],
            "crs": CRS.from_user_input(info["crs"]) if info["crs"] else None,
            "n_features": int(info["features"]),
        }
    import fiona
    with fiona.open(str(path), layer=layer) as src:
        crs = src.crs
        return {
            "fields": list(src.schema["properties"].keys()),
            "geometry_type": src.schema["geometry"],
            "crs": CRS.from_wkt(crs.to_wkt()) if crs else None,
            "n_features": len(src),
        }


def read_layer(path, layer=None, bbox=None, columns=None):
    """Read a vector layer into a GeoDataFrame.

    ``bbox`` is ``(minx, miny, maxx, maxy)`` in the layer CRS; features whose
    envelope intersects it are returned whole. ``columns`` limits attributes.
    """
    kwargs = {"engine": ENGINE}
    if layer is not None:
        kwargs["layer"] = layer
    if bbox is not None:
        kwargs["bbox"] = tuple(float(v) for v in bbox)
    if columns is not None:
        kwargs["columns"] = list(columns)
    return gpd.read_file(path, **kwargs)


def write_gpkg(gdf, path, layer):
    """Write a GeoDataFrame to a new GeoPackage layer (overwrites the file)."""
    path = Path(path)
    if path.exists():
        path.unlink()
    gdf.to_file(path, layer=layer, driver="GPKG", engine=ENGINE)


def write_shapefile(gdf, path, field_names):
    """Write a shapefile with the given ``{column: short name}`` mapping (UTF-8, with .cpg).

    Shapefile field names are limited to 10 characters; the mapping makes the
    shortening explicit instead of leaving it to the driver.
    """
    path = Path(path)
    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        path.with_suffix(ext).unlink(missing_ok=True)
    gdf.rename(columns=field_names).to_file(path, driver="ESRI Shapefile", engine=ENGINE, encoding="utf-8")


def write_xlsx(df, path, sheet_name="data"):
    """Excel workbook with one sheet holding the table (openpyxl)."""
    df.to_excel(path, sheet_name=sheet_name, index=False, engine="openpyxl")


def write_csv(df, path, index=False):
    """CSV in UTF-8 with BOM so that Excel shows Portuguese labels correctly."""
    df.to_csv(path, index=index, encoding="utf-8-sig", lineterminator="\n")


def write_text(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def write_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def list_files(directory):
    """Regular files in ``directory`` (not recursive), sorted by name."""
    return sorted((p for p in Path(directory).iterdir() if p.is_file()), key=lambda p: p.name.lower())


def make_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def file_fingerprint(path, with_hash=True, chunk=8 * 1024 * 1024):
    """Size, modification time and (optionally) SHA-256 of a file."""
    p = Path(path)
    st = p.stat()
    out = {"path": str(p.resolve()), "size_bytes": st.st_size, "mtime": st.st_mtime}
    if with_hash:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(chunk), b""):
                h.update(block)
        out["sha256"] = h.hexdigest()
    return out
