"""Maintainer tool: write the synthetic demonstration samples ``examples/demo_points.gpkg``.

Three 5 x 5 grids of points with 100 m spacing (EPSG:3763) at arbitrary
locations of mainland Portugal chosen to show different COS histories. The
points are synthetic: they are not sampling locations of any study.

Usage (from the repository root)::

    python tools/make_demo_points.py
"""
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
GRIDS = {"A": (38.035, -8.05), "B": (39.935, -8.20), "C": (38.70, -8.95)}  # grid centre (lat, lon)


def main():
    rows = []
    for grid, (lat, lon) in GRIDS.items():
        c = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(3763).iloc[0]
        cx, cy = round(c.x, -1), round(c.y, -1)
        for i in range(5):
            for j in range(5):
                rows.append({"SAMPLE_ID": f"{grid}{i * 5 + j + 1}", "GRID": grid,
                             "geometry": Point(cx + (j - 2) * 100, cy + (i - 2) * 100)})
    out = ROOT / "examples" / "demo_points.gpkg"
    out.unlink(missing_ok=True)
    gpd.GeoDataFrame(rows, crs=3763).to_file(out, layer="demo_points", driver="GPKG", engine="fiona")
    print("wrote", out, len(rows), "points")


if __name__ == "__main__":
    main()
