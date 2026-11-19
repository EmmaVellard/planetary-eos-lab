from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planetary_eos_lab.cli import selftest
from test_lunar_pipeline import make_fake_perplex


@pytest.mark.skipif(not os.environ.get("PERPLEX_DIR"), reason="needs a real Perple_X install (set PERPLEX_DIR)")
def test_selftest_with_real_perplex() -> None:
    assert selftest.main(["--perplex-dir", os.environ["PERPLEX_DIR"]]) == 0


def test_python_check_passes_in_test_environment() -> None:
    report = selftest.Report()
    selftest.check_python(report)
    assert not report.failed


def test_perplex_check_fails_on_missing_dir(tmp_path: Path, capsys) -> None:
    report = selftest.Report()
    assert selftest.check_perplex(report, tmp_path / "nowhere") is None
    assert report.failed and "FAIL  Perple_X directory" in capsys.readouterr().out


def test_perplex_check_fails_on_missing_executable(tmp_path: Path, capsys) -> None:
    report = selftest.Report()
    assert selftest.check_perplex(report, make_fake_perplex(tmp_path, omit="vertex")) is None
    assert "FAIL  executable vertex" in capsys.readouterr().out


def test_perplex_check_warns_when_version_unknown(tmp_path: Path, capsys) -> None:
    report = selftest.Report()
    assert selftest.check_perplex(report, make_fake_perplex(tmp_path)) == "unknown"
    assert not report.failed and "WARN  Perple_X version" in capsys.readouterr().out


def test_database_check_warns_for_optional_and_fails_for_stx21(tmp_path: Path, capsys) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    report = selftest.Report()
    assert selftest.check_databases(report, perplex_dir)
    assert not report.failed and "WARN  database stx24" in capsys.readouterr().out

    (perplex_dir / "datafiles" / "stx21ver.dat").unlink()
    report = selftest.Report()
    assert not selftest.check_databases(report, perplex_dir)
    assert report.failed and "FAIL  database stx21" in capsys.readouterr().out


def test_main_writes_then_matches_reference(tmp_path: Path, capsys) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    reference = tmp_path / "reference.json"
    args = ["--perplex-dir", str(perplex_dir), "--reference", str(reference)]

    assert selftest.main(args + ["--write-reference"]) == 0
    data = json.loads(reference.read_text())
    assert len(data["nodes"]) == 3 and data["perplex_version"] == "unknown"
    assert selftest.main(args) == 0

    data["nodes"][1]["rho_kgm3"] *= 1.05
    reference.write_text(json.dumps(data))
    assert selftest.main(args) == 1
    assert "FAIL  reference node" in capsys.readouterr().out


def test_main_fails_without_reference_file(tmp_path: Path) -> None:
    args = ["--perplex-dir", str(make_fake_perplex(tmp_path)), "--reference", str(tmp_path / "missing.json")]
    assert selftest.main(args) == 1


def test_main_fails_when_werami_writes_no_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(selftest.tempfile, "tempdir", str(tmp_path))  # failed runs keep their logs
    assert selftest.main(["--perplex-dir", str(make_fake_perplex(tmp_path, no_tab=True))]) == 1
