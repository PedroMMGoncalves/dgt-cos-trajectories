import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, box

from cos_trajectories import core
from helpers import CRS, two_halves, write_cos, write_samples


def _samples(points, ids):
    return gpd.GeoDataFrame({"SAMPLE_ID": ids}, geometry=[Point(p) for p in points], crs=CRS)


def _cos(codes, ids=(11, 22)):
    return gpd.GeoDataFrame({"ID": list(ids), "C": codes}, geometry=two_halves(), crs=CRS)


# --- join_edition ------------------------------------------------------------

def test_join_assigns_class_polygon_and_boundary_distance():
    s = core.prepare_samples(_samples([(30, 50), (190, 90)], ["p1", "p2"]), "SAMPLE_ID")
    j, n_shared = core.join_edition(s, _cos(["2.1.1.1", "5.1.1.1"]), "C", "ID", 2007)
    assert j.loc["p1", "code"] == "2.1.1.1"
    assert j.loc["p1", "poly"] == "2007_11"
    assert j.loc["p1", "dist"] == pytest.approx(30.0)
    assert j.loc["p2", "code"] == "5.1.1.1"
    assert j.loc["p2", "dist"] == pytest.approx(10.0)
    assert n_shared == 0


def test_join_point_on_shared_edge_keeps_lowest_polygon_id():
    s = core.prepare_samples(_samples([(100, 50)], ["edge"]), "SAMPLE_ID")
    j, n_shared = core.join_edition(s, _cos(["2.1.1.1", "5.1.1.1"], ids=(22, 11)), "C", "ID", 2007)
    assert j.loc["edge", "poly"] == "2007_11"
    assert j.loc["edge", "code"] == "5.1.1.1"
    assert j.loc["edge", "dist"] == 0
    assert n_shared == 1


def test_join_point_outside_coverage_is_missing():
    s = core.prepare_samples(_samples([(500, 500), (10, 10)], ["out", "in"]), "SAMPLE_ID")
    j, _ = core.join_edition(s, _cos(["2.1.1.1", "5.1.1.1"]), "C", "ID", 2007)
    assert pd.isna(j.loc["out", "code"]) and pd.isna(j.loc["out", "poly"]) and pd.isna(j.loc["out", "dist"])
    assert list(j.index) == ["out", "in"]


def test_join_distance_counts_interior_ring():
    donut = box(0, 0, 100, 100).difference(box(40, 40, 60, 60))
    cos = gpd.GeoDataFrame({"ID": [1], "C": ["5.1.1.1"]}, geometry=[donut], crs=CRS)
    s = core.prepare_samples(_samples([(35, 50)], ["p"]), "SAMPLE_ID")
    j, _ = core.join_edition(s, cos, "C", "ID", 2007)
    assert j.loc["p", "dist"] == pytest.approx(5.0)


# --- prepare_samples -----------------------------------------------------------

def test_prepare_rejects_non_point_geometry():
    g = gpd.GeoDataFrame({"SAMPLE_ID": ["a"]}, geometry=[LineString([(0, 0), (1, 1)])], crs=CRS)
    with pytest.raises(core.InputError, match="point"):
        core.prepare_samples(g, "SAMPLE_ID")


def test_prepare_rejects_duplicate_ids():
    with pytest.raises(core.InputError, match="unique"):
        core.prepare_samples(_samples([(1, 1), (2, 2)], ["a", "a"]), "SAMPLE_ID")


def test_prepare_rejects_empty_ids():
    with pytest.raises(core.InputError, match="empty"):
        core.prepare_samples(_samples([(1, 1), (2, 2)], ["a", None]), "SAMPLE_ID")


def test_prepare_rejects_missing_fields():
    with pytest.raises(core.InputError, match="ID field"):
        core.prepare_samples(_samples([(1, 1)], ["a"]), "SAMPLE")
    with pytest.raises(core.InputError, match="group field"):
        core.prepare_samples(_samples([(1, 1)], ["a"]), "SAMPLE_ID", group_field="quad")


def test_prepare_rejects_missing_crs():
    g = gpd.GeoDataFrame({"SAMPLE_ID": ["a"]}, geometry=[Point(0, 0)])
    with pytest.raises(core.InputError, match="coordinate reference system"):
        core.prepare_samples(g, "SAMPLE_ID")


def test_prepare_accepts_multipoint_with_single_part():
    from shapely.geometry import MultiPoint
    g = gpd.GeoDataFrame({"SAMPLE_ID": ["a"]}, geometry=[MultiPoint([(5, 5)])], crs=CRS)
    out = core.prepare_samples(g, "SAMPLE_ID")
    assert out.geometry.iloc[0].geom_type == "Point"


# --- run (end to end) ----------------------------------------------------------

@pytest.fixture
def project(tmp_path):
    cos = tmp_path / "01_COS"
    cos.mkdir()
    sq = two_halves()
    write_cos(cos / "COS1995v2-S1.gpkg", "COS1995v2", sq, ["2.1.1.1", "3.0.0.0"])
    write_cos(cos / "COS2007v3-S1.gpkg", "COS2007v3", sq, ["2.4.1.1", "3.1.2.1"])
    write_cos(cos / "COS2018v2-S1.gpkg", "COS2018v2", sq, ["5.1.1.6", "3.1.1.1"])
    write_cos(cos / "cos2025v1.gpkg", "cos2025v1", sq, ["1.1.1.1", "2.1.1.1"])
    samples = write_samples(tmp_path / "pts.shp", [(30, 50), (150, 50), (190, 95), (100, 50), (900, 900)],
                            ["A10", "A2", "B1", "B2", "C1"], extra={"quad": ["A", "A", "B", "B", "C"],
                                                                     "pH": [5.1, 5.2, 5.3, 5.4, 5.5]})
    return tmp_path, cos, samples


def _run(project, **kw):
    tmp, cos, samples = project
    args = dict(cos_dir=cos, series="S1", samples_path=samples, id_field="SAMPLE_ID",
                out_dir=tmp / "out", group_field="quad", boundary_threshold_m=25, run_id="test")
    args.update(kw)
    return core.run(**args)


def test_run_writes_all_outputs(project):
    res = _run(project)
    names = sorted(p.name for p in res.out_dir.iterdir())
    assert names == ["data_dictionary.md", "group_summary.csv", "interpretation_summary.csv", "manifest.json",
                     "run.log", "samples_cos_history.csv", "samples_cos_history.gpkg",
                     "transitions_1995_2007.csv", "transitions_2007_2018.csv"]


def test_run_history_rows_columns_and_harmonisation(project):
    res = _run(project)
    h = pd.read_csv(res.out_dir / "samples_cos_history.csv", dtype={"cls_1995": str, "cls_2007": str,
                                                                    "cls_2018": str})
    assert list(h["SAMPLE_ID"]) == ["A2", "A10", "B1", "B2", "C1"]  # natural sort
    assert "pH" not in h.columns and "quad" not in h.columns
    a10 = h.set_index("SAMPLE_ID").loc["A10"]
    # 2007 2.4.1.1 -> 1995 2.1.1.1; 2018 5.1.1.6 -> 5.1.1.7 (DGT crosswalk), level 4
    assert (a10["cls_1995"], a10["cls_2007"], a10["cls_2018"]) == ("2.1.1.1", "2.1.1.1", "5.1.1.7")
    assert a10["trajectory"] == "2.1.1.1|2.1.1.1|5.1.1.7"
    assert a10["last_change_year"] == 2018
    a2 = h.set_index("SAMPLE_ID").loc["A2"]
    assert a2["trajectory"] == "3.0.0.0|3.0.0.0|3.0.0.0" and a2["stable"] == 1
    assert a2["label_2018"] == "Pastagens"
    c1 = h.set_index("SAMPLE_ID").loc["C1"]
    assert c1["trajectory"] == "NA|NA|NA" and c1["n_missing"] == 3
    assert h.set_index("SAMPLE_ID").loc["B2", "near_boundary"] == 1


def test_run_comparison_level(project):
    res = _run(project, level=1)
    h = pd.read_csv(res.out_dir / "samples_cos_history.csv", dtype=str).set_index("SAMPLE_ID")
    assert h.loc["A10", "trajectory"] == "2|2|5"
    assert h.loc["A10", "label_1995"] == "Agricultura"


def test_run_rejects_level_above_max(project):
    with pytest.raises(core.InputError, match="level"):
        _run(project, level=5)


def test_run_transition_row_sums_equal_point_count(project):
    res = _run(project)
    t = pd.read_csv(res.out_dir / "transitions_1995_2007.csv", index_col=0, keep_default_na=False)
    assert int(t.to_numpy().sum()) == 5
    assert "NA" in t.index


def test_run_group_summary(project):
    res = _run(project)
    g = pd.read_csv(res.out_dir / "group_summary.csv").set_index("quad")
    assert list(g.index) == ["A", "B", "C"]
    assert g.loc["A", "n_points"] == 2


def test_run_without_group_field_has_no_group_summary(project):
    res = _run(project, group_field=None)
    assert not (res.out_dir / "group_summary.csv").exists()


def test_run_manifest(project):
    res = _run(project)
    m = json.loads((res.out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert m["parameters"]["series"] == "S1"
    assert m["series"] == "S1" and m["nomenclature"] == "S1-1995"
    assert [c["edition"] for c in m["cos_layers"]] == [1995, 2007, 2018]
    assert all(len(c["sha256"]) == 64 for c in m["cos_layers"])
    assert "Anexo 3" in m["correspondences_applied"]["S1-2007->S1-1995"]
    assert m["samples"]["n_features"] == 5
    assert m["samples"]["crs"].startswith("EPSG:3763")
    assert {"python", "geopandas", "shapely", "fiona", "gdal", "pandas"} <= set(m["software"])
    assert m["counts"]["n_samples_out"] == 5
    assert m["counts"]["shared_edge_points"]["1995"] == 1
    assert sum(m["counts"]["interpretation"].values()) == 5


def test_run_dictionary_opens_with_boundary_warning(project):
    res = _run(project)
    text = (res.out_dir / "data_dictionary.md").read_text(encoding="utf-8")
    first_para = text.split("\n\n")[1]
    assert "near_boundary" in first_para and "delineation" in first_para
    assert "`cls_<year>`" in text and "1995, 2007, 2018" in text and "Anexo 3" in text


def test_run_gpkg_has_geometry_and_same_rows(project):
    res = _run(project)
    g = gpd.read_file(res.out_dir / "samples_cos_history.gpkg", engine="fiona")
    assert len(g) == 5 and g.crs.to_epsg() == 3763
    assert list(g["SAMPLE_ID"]) == ["A2", "A10", "B1", "B2", "C1"]


def test_run_reprojects_geographic_samples(project, tmp_path):
    _, cos, _ = project
    pts = gpd.GeoSeries([Point(30, 50), Point(150, 50)], crs=CRS).to_crs(4326)
    samples = write_samples(tmp_path / "geo.gpkg", [(p.x, p.y) for p in pts], ["x1", "x2"],
                            crs="EPSG:4326", layer="pts")
    res = _run(project, samples_path=samples, samples_layer="pts", group_field=None)
    h = pd.read_csv(res.out_dir / "samples_cos_history.csv", dtype=str).set_index("SAMPLE_ID")
    assert h.loc["x1", "cls_1995"] == "2.1.1.1"
    assert h.loc["x2", "cls_1995"] == "3.0.0.0"


def test_run_s2_skips_obsolete_and_single_edition_fails(project):
    with pytest.raises(core.InputError, match="two editions"):
        _run(project, series="S2", group_field=None)


def test_run_refuses_existing_output_folder(project):
    _run(project)
    with pytest.raises(core.InputError, match="exists"):
        _run(project)


# --- interpretation (single series) ---------------------------------------------

def test_run_interpretation_column_and_summary(project):
    res = _run(project)
    h = pd.read_csv(res.out_dir / "samples_cos_history.csv", dtype=str, keep_default_na=False).set_index("SAMPLE_ID")
    assert h.loc["A2", "interpretation"] == "stable"
    assert h.loc["A10", "interpretation"] == "change"            # 30 m from the boundary
    assert h.loc["B2", "interpretation"] == "near_boundary"      # on the shared edge, class changed
    assert h.loc["C1", "interpretation"] == "insufficient_data"  # outside COS
    assert h.columns[-1] == "interpretation"
    s = pd.read_csv(res.out_dir / "interpretation_summary.csv").set_index("interpretation")
    assert int(s["n_samples"].sum()) == 5 and s.loc["stable", "n_samples"] == 2
    text = (res.out_dir / "data_dictionary.md").read_text(encoding="utf-8")
    assert "## How to read the results" in text and "`near_boundary`" in text


def test_run_rejects_series_other_than_s1_s2(project):
    with pytest.raises(core.InputError, match="S1 or S2"):
        _run(project, series="S1+S2")
