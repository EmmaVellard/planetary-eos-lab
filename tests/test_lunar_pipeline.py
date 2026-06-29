from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import make_compositions
import plot_comparisons
import run_perplex


PIPELINE_DIR = Path(__file__).resolve().parents[1]
PROJECT = "test_project"

VALID_TAB = """\
|fake
test_project_1.tab
2
P(bar)
1000.0
1000.0
2
T(K)
1200.0
100.0
2
9
P(bar) T(K) rho_kgm3 VP_kms VS_kms Cp_Jm3K alpha_pK KS_bar GS_bar
1000 1200 3300 8.0 4.5 4000000 3.0E-5 1300000 800000
2000 1300 3400 8.1 4.6 4100000 3.1E-5 1400000 810000
"""


def write_executable(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(path.stat().st_mode | 0o111)


def make_fake_perplex(
    tmp_path: Path,
    *,
    tab_text: str = VALID_TAB,
    werami_log: str = "",
    no_tab: bool = False,
    omit: str | None = None,
) -> Path:
    perplex_dir = tmp_path / "fake_perplex"
    bin_dir = perplex_dir / "bin"
    bin_dir.mkdir(parents=True)

    if omit != "build":
        write_executable(
            bin_dir / "build",
            """
from pathlib import Path
import sys

project = sys.stdin.readline().strip()
Path(f"{project}.dat").write_text("fake dat\\n")
print("build ok")
""",
        )

    if omit != "vertex":
        write_executable(
            bin_dir / "vertex",
            """
import sys

sys.stdin.read()
print("vertex ok")
""",
        )

    if omit != "werami":
        if no_tab:
            werami_body = f"""
import sys

sys.stdin.read()
print({werami_log!r})
"""
        else:
            werami_body = f"""
from pathlib import Path
import sys

lines = sys.stdin.read().splitlines()
project = lines[0] if lines else "unknown"
expected = ["2", "38", "1", "2", "13", "14", "3", "4", "10", "11", "0", "n", "1", "0"]
if lines[1:] != expected:
    print(f"unexpected WERAMI input: {{lines[1:]!r}}", file=sys.stderr)
    raise SystemExit(2)
Path(f"{{project}}_1.tab").write_text({tab_text!r})
print({werami_log!r})
"""
        write_executable(bin_dir / "werami", werami_body)

    return perplex_dir


def make_config(tmp_path: Path, perplex_dir: Path, *, build_input: bool = True) -> tuple[Path, Path]:
    composition_file = tmp_path / "composition.json"
    composition_file.write_text("{}\n")

    build_input_file = tmp_path / "build.in"
    if build_input:
        build_input_file.write_text(f"{PROJECT}\n${{PERPLEX_DIR}}/datafiles/example.dat\n")

    output_dir = tmp_path / "outputs" / PROJECT
    config = {
        "perplex_dir": str(perplex_dir),
        "models": [
            {
                "project": PROJECT,
                "composition_file": str(composition_file),
                "build_input_file": str(build_input_file),
                "output_dir": str(output_dir),
            }
        ],
    }
    config_path = tmp_path / "models.json"
    config_path.write_text(json.dumps(config))
    return config_path, output_dir


def run_pipeline(config_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PIPELINE_DIR / "run_perplex.py"), "--config", str(config_path)],
        cwd=str(PIPELINE_DIR),
        text=True,
        capture_output=True,
    )


def run_full_pipeline(config_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PIPELINE_DIR / "run_full_pipeline.py"),
            "--config",
            str(config_path),
            "--skip-compositions",
            "--skip-plots",
        ],
        cwd=str(PIPELINE_DIR),
        text=True,
        capture_output=True,
    )


def test_lunar_models_use_literature_proxy_values() -> None:
    models = {model.project: model for model in make_compositions.lunar_models()}

    far = models["moon_far_dry_mantle"]
    assert far.raw_wt_percent["Al2O3"] == 24.0
    assert far.raw_wt_percent["FeO"] == 5.9
    assert far.raw_wt_percent["CaO"] == 15.9

    near = models["moon_near_pkt_mantle"]
    assert near.raw_wt_percent["Al2O3"] == 14.9
    assert near.raw_wt_percent["FeO"] == 14.1
    assert near.raw_wt_percent["TiO2"] == 3.9

    near_normalized = make_compositions.normalize_wt_percent(near.raw_wt_percent)
    assert math.isclose(near_normalized["SiO2"], 45.44544545, rel_tol=0, abs_tol=1e-8)


def test_render_build_input_expands_bulk_values_from_composition(tmp_path: Path) -> None:
    composition_file = tmp_path / "composition.json"
    composition_file.write_text(
        json.dumps(
            {
                "composition_normalized": {
                    "SiO2": 45.44544545,
                    "TiO2": 3.90390390,
                    "Al2O3": 14.91491491,
                    "FeO": 14.11411411,
                    "MgO": 9.20920921,
                    "CaO": 11.81181181,
                    "Na2O": 0.60060060,
                    "K2O": 0.0,
                    "P2O5": 0.0,
                }
            }
        )
        + "\n"
    )
    build_input_file = tmp_path / "build.in"
    build_input_file.write_text("${PERPLEX_DIR}\n${PERPLEX_BULK_VALUES}\n")

    model = run_perplex.ModelConfig(
        project=PROJECT,
        composition_file=composition_file,
        build_input_file=build_input_file,
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
    )

    rendered = run_perplex.render_build_input(tmp_path / "fake_perplex", model)

    assert str(tmp_path / "fake_perplex") in rendered
    assert "0.60060060 9.20920921 14.91491491 45.44544545 11.81181181 14.11411411" in rendered


def test_omitted_oxide_warning_mentions_nonzero_dropped_oxides(tmp_path: Path) -> None:
    composition_file = tmp_path / "composition.json"
    composition_file.write_text(
        json.dumps(
            {
                "oxide_order": ["SiO2", "TiO2", "Al2O3", "FeO", "MgO", "CaO", "Na2O", "K2O", "P2O5"],
                "composition_normalized": {
                    "SiO2": 45.0,
                    "TiO2": 3.5,
                    "Al2O3": 15.0,
                    "FeO": 14.0,
                    "MgO": 9.0,
                    "CaO": 12.0,
                    "Na2O": 0.5,
                    "K2O": 0.0,
                    "P2O5": 1.0,
                },
            }
        )
        + "\n"
    )

    warning = run_perplex.omitted_oxide_warning(composition_file)

    assert warning is not None
    assert "TiO2=3.50000000 wt%" in warning
    assert "P2O5=1.00000000 wt%" in warning
    assert "K2O" not in warning


def test_plot_comparisons_writes_svg_files(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    models = []
    for project, sio2, feo, output_name in [
        ("far_project", 45.5, 5.9, "far"),
        ("near_project", 45.4, 14.1, "near"),
    ]:
        composition_file = tmp_path / f"{project}.json"
        composition_file.write_text(
            json.dumps(
                {
                    "composition_normalized": {
                        "SiO2": sio2,
                        "TiO2": 0.0,
                        "Al2O3": 15.0,
                        "FeO": feo,
                        "MgO": 10.0,
                        "CaO": 12.0,
                        "Na2O": 0.5,
                        "K2O": 0.0,
                        "P2O5": 0.0,
                    }
                }
            )
            + "\n"
        )
        output_dir = tmp_path / "outputs" / output_name
        output_dir.mkdir(parents=True)
        (output_dir / f"{project}_planetprofile.tab").write_text(VALID_TAB)
        models.append(
            {
                "project": project,
                "composition_file": str(composition_file),
                "build_input_file": str(tmp_path / f"{project}.build.in"),
                "output_dir": str(output_dir),
            }
        )

    config_path = tmp_path / "models.json"
    config_path.write_text(json.dumps({"perplex_dir": str(perplex_dir), "models": models}) + "\n")
    output_dir = tmp_path / "comparison_plots"

    result = plot_comparisons.main(["--config", str(config_path), "--output-dir", str(output_dir)])

    assert result == 0
    assert "<svg" in (output_dir / "composition_oxides.svg").read_text()
    assert "<svg" in (output_dir / "planetprofile_properties.svg").read_text()


def test_successful_run_validates_with_fake_perplex(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode == 0, result.stderr + result.stdout
    planetprofile_tab = output_dir / f"{PROJECT}_planetprofile.tab"
    assert (output_dir / f"{PROJECT}_raw_werami.tab").exists()
    assert planetprofile_tab.exists()
    assert planetprofile_tab.read_text().splitlines()[0].split()[:2] == ["T(K)", "P(bar)"]
    assert (output_dir / "work" / "perplex_option.dat").exists()
    assert (output_dir / "work" / f"{PROJECT}.dat").exists()
    assert not (perplex_dir / "perplex_option.dat").exists()
    assert not (perplex_dir / f"{PROJECT}.dat").exists()
    build_log = (output_dir / "build.log").read_text()
    assert "${PERPLEX_DIR}" not in build_log
    assert str(perplex_dir / "datafiles" / "example.dat") in build_log
    assert "STATUS: PASS" in (output_dir / "validation_report.txt").read_text()


def test_full_pipeline_entrypoint_runs_with_fake_perplex(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_full_pipeline(config_path)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Running Perple_X pipeline" in result.stdout
    assert (output_dir / f"{PROJECT}_planetprofile.tab").exists()
    assert "STATUS: PASS" in (output_dir / "validation_report.txt").read_text()


def test_missing_dat_file_fails_before_vertex(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, _ = make_config(tmp_path, perplex_dir, build_input=False)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "Missing Perple_X .dat file" in result.stderr


def test_missing_executable_fails_clearly(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path, omit="vertex")
    config_path, _ = make_config(tmp_path, perplex_dir, build_input=False)
    output_dir = tmp_path / "outputs" / PROJECT
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True)
    (work_dir / f"{PROJECT}.dat").write_text("fake dat\n")

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "Missing VERTEX executable" in result.stderr


def test_werami_missing_tab_fails(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path, no_tab=True)
    config_path, _ = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "expected table was not found" in result.stderr


def test_solution_model_not_requested_log_fails_validation(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(
        tmp_path,
        werami_log="Reading solution models from file: not requested",
    )
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    report = (output_dir / "validation_report.txt").read_text()
    assert "STATUS: FAIL" in report
    assert "Reading solution models from file: not requested" in report


def test_warning_ver177_log_fails_validation(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path, werami_log="warning ver177")
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "warning ver177" in (output_dir / "validation_report.txt").read_text()


def test_bad_number_sentinel_in_tab_fails_validation(tmp_path: Path) -> None:
    bad_tab = VALID_TAB.replace("4100000", "0.100000E+100")
    perplex_dir = make_fake_perplex(tmp_path, tab_text=bad_tab)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "bad-number" in (output_dir / "validation_report.txt").read_text()


def test_zero_only_alpha_column_fails_validation(tmp_path: Path) -> None:
    zero_alpha_tab = VALID_TAB.replace("3.0E-5", "0.0").replace("3.1E-5", "0.0")
    perplex_dir = make_fake_perplex(tmp_path, tab_text=zero_alpha_tab)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "Zero-only alpha column" in (output_dir / "validation_report.txt").read_text()
