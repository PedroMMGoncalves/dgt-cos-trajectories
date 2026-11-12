from cos_trajectories import cli
from helpers import two_halves, write_cos, write_samples


def _project(tmp_path):
    cos = tmp_path / "01_COS"
    cos.mkdir()
    write_cos(cos / "COS2015v2-S1.gpkg", "COS2015v2", two_halves(), ["2.1.1.1", "5.1.1.1"])
    write_cos(cos / "COS2018v2-S1.gpkg", "COS2018v2", two_halves(), ["2.1.1.1", "6.1.1.1"])
    pts = write_samples(tmp_path / "pts.shp", [(30, 50), (150, 50)], ["A1", "A2"])
    return cos, pts


def test_cli_runs_and_writes_run_folder(tmp_path, capsys):
    cos, pts = _project(tmp_path)
    out = tmp_path / "res"
    code = cli.main(["--cos-dir", str(cos), "--series", "S1", "--samples", str(pts), "--id-field", "SAMPLE_ID",
                     "--out-dir", str(out), "--level", "2", "--no-hash"])
    assert code == 0
    runs = list(out.iterdir())
    assert len(runs) == 1 and (runs[0] / "samples_cos_history.csv").exists()
    assert str(runs[0]) in capsys.readouterr().out


def test_cli_input_error_returns_2_with_message(tmp_path, capsys):
    cos, pts = _project(tmp_path)
    code = cli.main(["--cos-dir", str(cos), "--series", "S1", "--samples", str(pts), "--id-field", "NOPE",
                     "--out-dir", str(tmp_path / "res")])
    assert code == 2
    assert "NOPE" in capsys.readouterr().err
