import pytest

from cos_trajectories import catalog
from helpers import two_halves, write_cos


@pytest.fixture
def cos_dir(tmp_path):
    sq = two_halves()
    write_cos(tmp_path / "COS1995v2-S1.gpkg", "COS1995v2", sq, ["1.0.0.0", "3.0.0.0"])
    write_cos(tmp_path / "COS2007v3-S1.gpkg", "COS2007v3", sq, ["1.1.1.1", "3.1.2.1"])
    write_cos(tmp_path / "COS2018v2-S1.gpkg", "COS2018v2", sq, ["1.1.1.1", "2.4.1.1"])
    write_cos(tmp_path / "cos2018v4.gpkg", "cos2018v4", sq, ["1.1.1.1", "2.1.1.1"])
    write_cos(tmp_path / "COS2023v1-S2.gpkg", "COS2023v1", sq, ["1.1.1.1", "2.1.1.1"])
    write_cos(tmp_path / "cos2025v1.gpkg", "cos2025v1", sq, ["1.1.1.1", "2.1.1.1"])
    (tmp_path / "COSc2020.tif").write_bytes(b"")
    (tmp_path / ".gitkeep").write_bytes(b"")
    (tmp_path / "README.md").write_text("x")
    write_cos(tmp_path / "COSc2021.gpkg", "COS2007v3", sq, ["1", "2"])  # COSc never matches
    return tmp_path


def test_discover_identifies_dgt_names_including_lowercase_without_series(cos_dir):
    found, ignored = catalog.discover(cos_dir)
    names = sorted((s.product["edition"], s.product["version"], s.product["series"]) for s in found)
    assert names == [(1995, 2, "S1"), (2007, 3, "S1"), (2018, 2, "S1"), (2018, 4, "S2"),
                     (2023, 1, "S2"), (2025, 1, "S2")]
    assert {p.name for p, _ in ignored} == {"COSc2020.tif", "COSc2021.gpkg"}


def test_discover_resolves_layer_and_fields(cos_dir):
    found, _ = catalog.discover(cos_dir)
    s = next(s for s in found if s.product["layer"] == "cos2025v1")
    assert s.layer == "cos2025v1"
    assert s.code_field == "cos25v1_n4_c"
    assert s.id_field == "ID"


def test_discover_missing_class_field_is_hard_error(tmp_path):
    write_cos(tmp_path / "COS2010v2-S1.gpkg", "COS2010v2", two_halves(), ["1.1.1.1", "2.1.1.1"],
              drop_field="COS10n4_C")
    with pytest.raises(catalog.CatalogError, match="COS10n4_C"):
        catalog.discover(tmp_path)


def test_discover_series_suffix_conflicting_with_catalog_is_hard_error(tmp_path):
    write_cos(tmp_path / "COS2010v2-S2.gpkg", "COS2010v2", two_halves(), ["1.1.1.1", "2.1.1.1"])
    with pytest.raises(catalog.CatalogError, match="series"):
        catalog.discover(tmp_path)


def test_discover_unknown_version_is_ignored(tmp_path):
    write_cos(tmp_path / "COS2010v9-S1.gpkg", "COS2010v2", two_halves(), ["1.1.1.1", "2.1.1.1"])
    found, ignored = catalog.discover(tmp_path)
    assert found == []
    assert "catalog" in ignored[0][1]


def test_select_s1_harmonises_to_1995_when_present(cos_dir):
    found, _ = catalog.discover(cos_dir)
    sel = catalog.select(found, "S1")
    assert [s.product["edition"] for s in sel.sources] == [1995, 2007, 2018]
    assert sel.nomenclature == "S1-1995"
    assert sel.max_level == 4
    s2007 = sel.sources[1]
    assert sel.harmonise("1.1.1.1", s2007) == "1.0.0.0"
    assert sel.harmonise("3.1.2.1", s2007) == "3.0.0.0"
    assert sel.harmonise("2.4.1.1", s2007) == "2.1.1.1"
    assert sel.harmonise("5.1.1.6", s2007) == "5.1.1.7"
    assert sel.harmonise("1.0.0.0", sel.sources[0]) == "1.0.0.0"


def test_select_s1_without_1995_keeps_native_nomenclature(cos_dir):
    found, _ = catalog.discover(cos_dir)
    found = [s for s in found if s.product["edition"] != 1995]
    sel = catalog.select(found, "S1")
    assert sel.nomenclature == "S1-2007"
    assert sel.harmonise("1.1.1.1", sel.sources[0]) == "1.1.1.1"


def test_select_s2_excludes_obsolete_cos2023v1(cos_dir):
    found, _ = catalog.discover(cos_dir)
    sel = catalog.select(found, "S2")
    assert [s.product["edition"] for s in sel.sources] == [2018, 2025]
    assert sel.nomenclature == "S2-2025"
    assert [s.product["edition"] for s, _ in sel.excluded] == [2023]


def test_select_unharmonisable_nomenclatures_is_hard_error(cos_dir):
    found, _ = catalog.discover(cos_dir)
    for s in found:
        s.product = dict(s.product, obsolete=False)
    with pytest.raises(catalog.CatalogError, match="nomenclature"):
        catalog.select(found, "S2")


def test_select_two_versions_of_same_edition_is_hard_error(tmp_path):
    write_cos(tmp_path / "COS2018v2-S1.gpkg", "COS2018v2", two_halves(), ["1.1.1.1", "2.1.1.1"])
    write_cos(tmp_path / "COS2007v3-S1.gpkg", "COS2007v3", two_halves(), ["1.1.1.1", "2.1.1.1"])
    found, _ = catalog.discover(tmp_path)
    dup = found[1]
    dup2 = catalog.CosSource(path=dup.path, layer=dup.layer, product=dict(dup.product, version=1),
                             code_field=dup.code_field, id_field=dup.id_field)
    with pytest.raises(catalog.CatalogError, match="2018"):
        catalog.select(found + [dup2], "S1")


def test_select_needs_two_editions(tmp_path):
    write_cos(tmp_path / "COS2018v2-S1.gpkg", "COS2018v2", two_halves(), ["1.1.1.1", "2.1.1.1"])
    found, _ = catalog.discover(tmp_path)
    with pytest.raises(catalog.CatalogError, match="two editions"):
        catalog.select(found, "S1")


def test_invalid_series_rejected(cos_dir):
    found, _ = catalog.discover(cos_dir)
    with pytest.raises(catalog.CatalogError, match="S1 or S2"):
        catalog.select(found, "S3")


def test_recode_truncates_dotted_code():
    assert catalog.recode("2.3.1.1", 2) == "2.3"
    assert catalog.recode("1.0.0.0", 1) == "1"
    assert catalog.recode("5.1.2.3", 4) == "5.1.2.3"


def test_labels_from_packaged_nomenclature():
    labels = catalog.load_labels("S1-1995")
    assert labels[(1, "5")] == "Florestas"
    assert labels[(4, "3.0.0.0")] == "Pastagens"
    s2 = catalog.load_labels("S2-2025")
    assert s2[(3, "1.1.1")] == "Áreas edificadas residenciais contínuas"


def test_packaged_crosswalk_covers_all_83_classes():
    cat = catalog.load_catalog()
    cw = cat["crosswalks"]["S1-2007->S1-1995"]["map"]
    labels07 = catalog.load_labels("S1-2007")
    labels95 = catalog.load_labels("S1-1995")
    codes07 = {c for (lvl, c) in labels07 if lvl == 4}
    assert set(cw) == codes07 and len(codes07) == 83
    assert {c for (lvl, c) in labels95 if lvl == 4} == set(cw.values())


def test_select_merged_editions_and_check(cos_dir):
    found, _ = catalog.discover(cos_dir)
    m = catalog.select_merged(found)
    assert [(s.edition, s.product["series"]) for s in m.sources] == [(1995, "S1"), (2007, "S1"), (2018, "S2"),
                                                                    (2025, "S2")]
    assert [s.name for s in m.check] == ["COS2018v2-S1"]
    assert m.levels == (1, 4)


def test_merged_classes_with_1995_follow_both_correspondences(cos_dir):
    found, _ = catalog.discover(cos_dir)
    m = catalog.select_merged(found)
    by = {s.name: s for s in list(m.sources) + list(m.check)}
    # all artificial classes collapse (COS1995 has a single artificial class)
    assert m.harmonise("1.0.0.0", by["COS1995v2-S1"]) == "1"
    assert m.harmonise("1.6.1.1", by["COS2007v3-S1"]) == "1"
    assert m.harmonise("1.2.3.2", by["COS2025v1-S2"]) == "1"  # Series 2 class without Series 1 counterpart
    assert m.class_labels["1"] == "Territórios artificializados"
    # olive: S1 2.2.3.1 and (via COS1995) 2.3.1.3 <-> S2 2.2.3.1-3 and 2.3.1.3
    olive = m.harmonise("2.2.3.1", by["COS2007v3-S1"])
    assert olive == m.harmonise("2.2.3.3", by["COS2025v1-S2"]) == m.harmonise("2.3.1.3", by["COS2025v1-S2"])
    # eucalyptus changed code between series
    assert m.harmonise("5.1.1.5", by["COS2007v3-S1"]) == m.harmonise("5.1.1.6", by["COS2025v1-S2"]) == "5.1.1.6"
    # Series 1 class without Series 2 counterpart
    assert m.harmonise("2.3.2.1", by["COS2007v3-S1"]) == "2.3.2.1(S1)"
    # every class of every nomenclature involved has a merged class
    for nom in ("S1-1995", "S1-2007", "S2-2025"):
        codes = {c for (lvl, c) in catalog.load_labels(nom) if lvl == 4}
        assert codes == {c for (n, c) in m.classes if n == nom}


def test_merged_classes_without_1995_keep_more_detail(cos_dir):
    found, _ = catalog.discover(cos_dir)
    m = catalog.select_merged([s for s in found if s.edition != 1995] + [
        catalog.CosSource(path=s.path, layer=s.layer, product=dict(s.product, edition=2010), code_field=s.code_field,
                          id_field=s.id_field) for s in found if s.edition == 2007])
    src07 = next(s for s in m.sources if s.edition == 2007)
    assert m.harmonise("1.6.1.1", src07) == "1.3.3.3"   # golf courses, one-to-one
    assert m.harmonise("2.2.3.1", src07) == "2.2.3"     # olive groves: all Series 2 classes under 2.2.3
    assert m.class_labels["2.2.3"] == "Olivais"
    assert len(m.class_labels) > 80


def test_bridge_in_catalog_covers_series1_and_targets_exist():
    cat = catalog.load_catalog()
    b = cat["bridges"]["S1-2007<->S2-2025"]
    s1 = {c for (lvl, c) in catalog.load_labels("S1-2007") if lvl == 4}
    s2 = {c for (lvl, c) in catalog.load_labels("S2-2025") if lvl == 4}
    assert set(b["map"]) == s1
    assert {t for v in b["map"].values() for t in v} <= s2
