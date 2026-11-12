import math

import pandas as pd
import pytest

from cos_trajectories import metrics

YEARS_S1 = [1995, 2007, 2010, 2015, 2018]  # intervals 12, 3, 5, 3


def test_stable_trajectory():
    m = metrics.sample_metrics(["5", "5", "5", "5", "5"], YEARS_S1)
    assert m["trajectory"] == "5|5|5|5|5"
    assert m["stable"] == 1
    assert m["n_changes"] == 0
    assert m["stability_index"] == 1.0
    assert m["modal_persistence"] == 1.0
    assert m["time_weighted_persistence"] == 1.0
    assert m["last_change_year"] is None
    assert m["flip_flop"] == 0
    assert m["n_missing"] == 0


def test_single_change_unequal_intervals():
    # change between 1995 and 2007 (12 of 23 years)
    m = metrics.sample_metrics(["2", "5", "5", "5", "5"], YEARS_S1)
    assert m["stable"] == 0
    assert m["n_changes"] == 1
    assert m["stability_index"] == pytest.approx(0.75)
    assert m["modal_persistence"] == pytest.approx(0.8)
    assert m["time_weighted_persistence"] == pytest.approx(11 / 23)
    assert m["last_change_year"] == 2007
    assert m["flip_flop"] == 0


def test_time_weighted_differs_from_stability_index():
    # change between 2015 and 2018 (3 of 23 years)
    m = metrics.sample_metrics(["2", "2", "2", "2", "5"], YEARS_S1)
    assert m["stability_index"] == pytest.approx(0.75)
    assert m["time_weighted_persistence"] == pytest.approx(20 / 23)
    assert m["last_change_year"] == 2018


def test_flip_flop_detected():
    m = metrics.sample_metrics(["5", "6", "5", "5", "5"], YEARS_S1)
    assert m["flip_flop"] == 1
    assert m["n_changes"] == 2
    assert m["last_change_year"] == 2010


def test_return_after_two_editions_is_not_flip_flop():
    m = metrics.sample_metrics(["5", "6", "6", "5", "5"], YEARS_S1)
    assert m["flip_flop"] == 0


def test_modal_persistence_with_three_classes():
    m = metrics.sample_metrics(["2", "3", "5", "5", "6"], YEARS_S1)
    assert m["modal_persistence"] == pytest.approx(0.4)
    assert m["n_changes"] == 3


def test_missing_edition_is_skipped():
    m = metrics.sample_metrics(["2", None, "2", "2", "5"], YEARS_S1)
    assert m["trajectory"] == "2|NA|2|2|5"
    assert m["n_missing"] == 1
    assert m["n_changes"] == 1
    assert m["stability_index"] == pytest.approx(1 - 1 / 3)
    assert m["modal_persistence"] == pytest.approx(3 / 4)
    # intervals over observed editions: 1995->2010 (15), 2010->2015 (5), 2015->2018 (3)
    assert m["time_weighted_persistence"] == pytest.approx(20 / 23)


def test_flip_flop_across_missing_edition():
    m = metrics.sample_metrics(["5", None, "6", "5", "5"], YEARS_S1)
    assert m["flip_flop"] == 1


def test_fewer_than_two_observed_editions_gives_na():
    m = metrics.sample_metrics([None, None, "5", None, None], YEARS_S1)
    assert m["n_missing"] == 4
    for k in ("stable", "n_changes", "stability_index", "modal_persistence",
              "time_weighted_persistence", "flip_flop"):
        assert m[k] is None or (isinstance(m[k], float) and math.isnan(m[k]))
    assert m["last_change_year"] is None


def test_transition_matrix_counts_and_na():
    a = pd.Series(["5", "5", "2", None], index=["p1", "p2", "p3", "p4"])
    b = pd.Series(["5", "6", "2", "2"], index=["p1", "p2", "p3", "p4"])
    tm = metrics.transition_matrix(a, b)
    assert list(tm.index) == ["2", "5", "NA"]
    assert list(tm.columns) == ["2", "5", "6"]
    assert tm.loc["5", "6"] == 1
    assert tm.loc["NA", "2"] == 1
    assert tm.to_numpy().sum() == 4


def test_natural_sort_key_orders_sample_ids():
    ids = ["A10", "A2", "B1", "A1"]
    assert sorted(ids, key=metrics.natural_key) == ["A1", "A2", "A10", "B1"]


def test_natural_sort_key_handles_numbers():
    assert sorted([10, 2, 1], key=metrics.natural_key) == [1, 2, 10]


def _history():
    return pd.DataFrame(
        {
            "SAMPLE_ID": ["A1", "A2", "A3", "B1", "B2"],
            "quadrat": ["A", "A", "A", "B", "B"],
            "cls_2015": ["5", "5", "6", None, "2"],
            "cls_2018": ["5", "6", "6", "2", "2"],
            "poly_2015": ["2015_1", "2015_1", "2015_2", None, "2015_9"],
            "poly_2018": ["2018_1", "2018_3", "2018_2", "2018_9", "2018_9"],
            "min_boundary_dist_m": [40.0, 3.0, 50.0, 60.0, 70.0],
        }
    )


def test_compute_metrics_adds_columns_per_sample():
    h = _history()
    out = metrics.compute_metrics(h, [2015, 2018], boundary_threshold_m=25)
    assert list(out["trajectory"]) == ["5|5", "5|6", "6|6", "NA|2", "2|2"]
    assert out["n_changes"].isna().tolist() == [False, False, False, True, False]
    assert out["n_changes"].dropna().tolist() == [0, 1, 0, 0]
    assert out["n_missing"].tolist() == [0, 0, 0, 1, 0]
    assert list(out["near_boundary"]) == [0, 1, 0, 0, 0]
    # A1 and A2 share no 2018 polygon; B1 and B2 share 2018_9
    assert list(out["pts_in_poly_2018"]) == [1, 1, 1, 2, 2]


def test_group_summary():
    h = metrics.compute_metrics(_history(), [2015, 2018], boundary_threshold_m=25)
    gs = metrics.group_summary(h, "quadrat", [2015, 2018])
    gs = gs.set_index("quadrat")
    assert gs.loc["A", "n_points"] == 3
    assert gs.loc["A", "n_polygons_2015"] == 2
    assert gs.loc["A", "n_polygons_2018"] == 3
    assert gs.loc["A", "prop_changed"] == pytest.approx(1 / 3)
    assert gs.loc["A", "n_trajectories"] == 3
    assert gs.loc["A", "prop_near_boundary"] == pytest.approx(1 / 3)
    assert gs.loc["B", "n_polygons_2018"] == 1
    # B1 has only one observed edition: excluded from prop_changed denominator
    assert gs.loc["B", "prop_changed"] == pytest.approx(0.0)


Y6 = [1995, 2007, 2010, 2015, 2018, 2025]


def test_interpret_stable_change_and_artefact_flags():
    assert metrics.interpret(["5"] * 5, YEARS_S1, 0, 0) == "stable"
    assert metrics.interpret(["2", "5", "5", "5", "5"], YEARS_S1, 0, 0) == "change"
    assert metrics.interpret(["2", "5", "5", "5", "5"], YEARS_S1, 0, 1) == "near_boundary"
    assert metrics.interpret(["5", "6", "5", "5", "5"], YEARS_S1, 1, 1) == "flip_flop"
    assert metrics.interpret([None, None, "5", None, None], YEARS_S1, 0, 0) == "insufficient_data"


def test_interpret_series_difference_only_when_series1_shows_no_change():
    seq = ["3", "3", "3", "3", "2", "2"]  # change into 2018, the first Series 2 edition
    assert metrics.interpret(seq, Y6, 0, 1, junction_year=2018, check_class="3") == "series_difference"
    # Series 1 also changed by 2018: a real change, whatever class Series 1 gives
    assert metrics.interpret(seq, Y6, 0, 0, junction_year=2018, check_class="2") == "change"
    assert metrics.interpret(seq, Y6, 0, 0, junction_year=2018, check_class="6") == "change"
    assert metrics.interpret(seq, Y6, 0, 0, junction_year=2018, check_class=None) == "change"


def test_interpret_series_switch_plus_other_change_is_not_series_difference():
    seq = ["3", "5", "5", "5", "2", "2"]
    assert metrics.interpret(seq, Y6, 0, 0, junction_year=2018, check_class="5") == "change"
