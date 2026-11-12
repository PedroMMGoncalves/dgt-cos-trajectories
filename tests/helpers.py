"""Synthetic COS fixtures (tiny GeoPackages with the real DGT field names)."""
import geopandas as gpd
from shapely.geometry import Point, box

from cos_trajectories import catalog

CRS = "EPSG:3763"


def product(layer):
    cat = catalog.load_catalog()
    return next(p for p in cat["products"] if p["layer"].lower() == layer.lower())


def write_cos(path, layer, polygons, codes, ids=None, drop_field=None):
    """Write a COS-like layer. ``polygons``: shapely geometries; ``codes``: level-4 codes."""
    p = product(layer)
    ids = ids or list(range(1, len(polygons) + 1))
    data = {p["id_field"]: ids, p["code_field"]: codes, p["label_field"]: ["x"] * len(codes)}
    if drop_field:
        data.pop(drop_field)
    gdf = gpd.GeoDataFrame(data, geometry=polygons, crs=CRS)
    gdf.to_file(path, layer=p["layer"], driver="GPKG", engine="fiona")
    return path


def two_halves():
    """Two adjacent 100 x 100 m squares sharing the edge x = 100."""
    return [box(0, 0, 100, 100), box(100, 0, 200, 100)]


def write_samples(path, points, ids, crs=CRS, layer=None, extra=None):
    data = {"SAMPLE_ID": ids}
    if extra:
        data.update(extra)
    gdf = gpd.GeoDataFrame(data, geometry=[Point(xy) for xy in points], crs=crs)
    driver = "GPKG" if str(path).endswith(".gpkg") else "ESRI Shapefile"
    gdf.to_file(path, layer=layer, driver=driver, engine="fiona")
    return path
