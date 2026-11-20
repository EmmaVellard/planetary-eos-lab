from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

import run_perplex


def fake_program(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fake_werami"
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.mark.skipif(os.name == "nt", reason="shell script stand-in for a Perple_X program")
def test_a_program_waiting_for_input_is_stopped_with_its_last_prompt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLANETARY_EOS_PERPLEX_TIMEOUT", "1")
    program = fake_program(tmp_path, 'echo "Select operational mode:"; sleep 30')
    with pytest.raises(run_perplex.PipelineError, match="did not finish within 1 s.*Select operational mode"):
        run_perplex.run_command(program, "x\n", tmp_path, tmp_path / "werami.log", "WERAMI")
    assert "Select operational mode" in (tmp_path / "werami.log").read_text()


@pytest.mark.skipif(os.name == "nt", reason="shell script stand-in for a Perple_X program")
def test_a_failing_program_reports_its_last_prompt(tmp_path: Path) -> None:
    program = fake_program(tmp_path, 'echo "Enter the project name:"; exit 3')
    with pytest.raises(run_perplex.PipelineError, match="return code 3.*Enter the project name"):
        run_perplex.run_command(program, "x\n", tmp_path, tmp_path / "build.log", "BUILD")


def test_a_one_node_werami_table_is_rejected(tmp_path: Path) -> None:
    tab = tmp_path / "rock_1.tab"
    tab.write_text("|6.6.6\nrock_1.tab\n 2\nP(bar)\n 40000\n Infinity\n 1\nT(K)\n 500\n -1500\n 0\n 8\n")
    with pytest.raises(run_perplex.PipelineError, match="1 x 0 nodes"):
        run_perplex.check_werami_grid(tab)
    tab.write_text("|6.6.6\nrock_1.tab\n 2\nP(bar)\n 40000\n 167.2\n 300\nT(K)\n 500\n 5.01\n 300\n 9\n")
    run_perplex.check_werami_grid(tab)  # a normal header passes


def test_file_names_longer_than_perplex_reads_are_refused() -> None:
    long_name = "/Users/someone/" + "x" * 80 + "/datafiles/stx24ver.dat"
    with pytest.raises(run_perplex.PipelineError, match="at most 100 characters"):
        run_perplex.check_perplex_file_names(f"project\n{long_name}\n\nn\n")
    run_perplex.check_perplex_file_names("project\n/Users/someone/perplex/datafiles/stx24ver.dat\n")


def test_cleaning_a_project_leaves_options_and_other_projects(tmp_path: Path) -> None:
    names = ["p.dat", "p.blk", "p_1.tab", "p_12.tab", "p_auto_refine.txt", "p_seismic_data.txt",
             "perplex_option.dat", "p_other.dat", "p_other_1.tab", "p.json.bak"]
    for name in names:
        (tmp_path / name).write_text("x")
    run_perplex.clean_project_work_files(tmp_path, "p")
    assert sorted(f.name for f in tmp_path.iterdir()) == ["p.json.bak", "p_other.dat", "p_other_1.tab", "perplex_option.dat"]
