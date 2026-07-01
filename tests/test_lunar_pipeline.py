from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import export_planetprofile
import make_compositions
import plot_comparisons
import planetprofile_tables
import run_perplex


PIPELINE_DIR = Path(__file__).resolve().parents[1]
PROJECT = "test_project"
FAR_PROJECT = "moon_far_highlands_surface_proxy"
NEAR_PROJECT = "moon_near_maria_surface_proxy"

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
2000 1200 3350 8.05 4.55 4050000 3.1E-5 1350000 805000
1000 1300 3360 8.06 4.56 4060000 3.0E-5 1360000 806000
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


def make_config(
    tmp_path: Path,
    perplex_dir: Path,
    *,
    build_input: bool = True,
    planetprofile_filename: str | None = None,
) -> tuple[Path, Path]:
    composition_file = tmp_path / "composition.json"
    composition_file.write_text("{}\n")

    build_input_file = tmp_path / "build.in"
    if build_input:
        build_input_file.write_text(f"{PROJECT}\n${{PERPLEX_DIR}}/datafiles/example.dat\n")

    output_dir = tmp_path / "outputs" / PROJECT
    model = {
        "project": PROJECT,
        "composition_file": str(composition_file),
        "build_input_file": str(build_input_file),
        "output_dir": str(output_dir),
    }
    if planetprofile_filename:
        model["planetprofile_filename"] = planetprofile_filename

    config = {
        "perplex_dir": str(perplex_dir),
        "models": [model],
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


def run_full_pipeline(config_path: Path, *, skip_compositions: bool = True) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(PIPELINE_DIR / "run_full_pipeline.py"),
        "--config",
        str(config_path),
        "--skip-plots",
    ]
    if skip_compositions:
        command.append("--skip-compositions")
    return subprocess.run(
        command,
        cwd=str(PIPELINE_DIR),
        text=True,
        capture_output=True,
    )


def run_full_pipeline_export(config_path: Path, export_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PIPELINE_DIR / "run_full_pipeline.py"),
            "--config",
            str(config_path),
            "--skip-compositions",
            "--skip-plots",
            "--export-planetprofile",
            "--planetprofile-export-dir",
            str(export_dir),
        ],
        cwd=str(PIPELINE_DIR),
        text=True,
        capture_output=True,
    )


def make_inline_config(tmp_path: Path, perplex_dir: Path) -> tuple[Path, Path]:
    output_dir = tmp_path / "outputs" / PROJECT
    config = {
        "perplex_dir": str(perplex_dir),
        "build_template_file": str(PIPELINE_DIR / "build_inputs" / "lunar_stx21_template.build.in"),
        "models": [
            {
                "project": PROJECT,
                "description": "Inline composition test model",
                "output_dir": str(output_dir),
                "planetprofile_filename": "Inline_Test_PerpleX.tab",
                "scientific_status": "surface_proxy_smoke_test",
                "model_scope": "surface_terrane_proxy",
                "planetprofile_readiness": "mechanically_exportable_not_scientifically_final",
                "composition_interpretation": "Inline surface proxy test composition.",
                "oxides_wt_percent": {
                    "SiO2": 45.4,
                    "TiO2": 3.9,
                    "Al2O3": 14.9,
                    "FeO": 14.1,
                    "MgO": 9.2,
                    "CaO": 11.8,
                    "Na2O": 0.6,
                    "K2O": 0.0,
                    "P2O5": 0.0,
                },
            }
        ],
    }
    config_path = tmp_path / "inline_models.json"
    config_path.write_text(json.dumps(config) + "\n")
    return config_path, output_dir


def test_lunar_models_use_literature_proxy_values() -> None:
    models = {model.project: model for model in make_compositions.lunar_models()}

    far = models[FAR_PROJECT]
    assert far.raw_wt_percent["Al2O3"] == 24.0
    assert far.raw_wt_percent["FeO"] == 5.9
    assert far.raw_wt_percent["CaO"] == 15.9
    assert far.scientific_status == "surface_proxy_smoke_test"
    assert far.model_scope == "surface_terrane_proxy"

    near = models[NEAR_PROJECT]
    assert near.raw_wt_percent["Al2O3"] == 14.9
    assert near.raw_wt_percent["FeO"] == 14.1
    assert near.raw_wt_percent["TiO2"] == 3.9

    near_normalized = make_compositions.normalize_wt_percent(near.raw_wt_percent)
    assert math.isclose(near_normalized["SiO2"], 45.44544545, rel_tol=0, abs_tol=1e-8)


def test_generated_composition_records_scientific_and_omission_metadata(tmp_path: Path) -> None:
    near = [model for model in make_compositions.lunar_models() if model.project == NEAR_PROJECT][0]

    make_compositions.write_composition(near, outdir=tmp_path)

    data = json.loads((tmp_path / f"{NEAR_PROJECT}.json").read_text())
    assert data["scientific_status"] == "surface_proxy_smoke_test"
    assert data["model_scope"] == "surface_terrane_proxy"
    assert data["planetprofile_readiness"] == "mechanically_exportable_not_scientifically_final"
    assert "not a final Ti-bearing mantle EOS" in data["composition_interpretation"]
    omitted = data["omitted_oxides_from_default_build"]
    assert omitted[0]["oxide"] == "TiO2"
    assert math.isclose(omitted[0]["normalized_wt_percent"], 3.90390390, rel_tol=0, abs_tol=1e-8)


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


def test_default_werami_input_sequence_is_backwards_compatible(tmp_path: Path) -> None:
    model = run_perplex.ModelConfig(
        project=PROJECT,
        composition_file=tmp_path / "composition.json",
        build_input_file=tmp_path / "build.in",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
    )

    assert run_perplex.werami_input_text(model) == (
        f"{PROJECT}\n2\n38\n1\n2\n13\n14\n3\n4\n10\n11\n0\nn\n1\n0\n"
    )


def test_planetprofile_native_conversion(tmp_path: Path) -> None:
    source = tmp_path / "source.tab"
    source.write_text(VALID_TAB)
    converted = tmp_path / "converted.tab"

    planetprofile_tables.write_planetprofile_native_table(
        source,
        converted,
        source_name="reference_source_1.tab",
    )

    lines = converted.read_text().splitlines()
    assert lines[0] == "|6.6.6"
    assert lines[1].strip() == "reference_source_1.tab"
    assert lines[3].strip() == "T(K)"
    assert lines[7].strip() == "P(bar)"
    assert lines[11].strip() == "9"
    assert lines[12].startswith("T(K)")


def test_export_planetprofile_copies_native_tables_with_manifest(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, output_dir = make_config(
        tmp_path,
        perplex_dir,
        planetprofile_filename="Custom_PlanetProfile_EOS.tab",
    )
    run_result = run_pipeline(config_path)
    assert run_result.returncode == 0, run_result.stderr + run_result.stdout

    export_dir = tmp_path / "planetprofile_export"
    result = export_planetprofile.main(
        [
            "--config",
            str(config_path),
            "--planetprofile-export-dir",
            str(export_dir),
        ]
    )

    exported = export_dir / "Custom_PlanetProfile_EOS.tab"
    manifest = export_dir / "planetprofile_export_manifest.json"
    assert result == 0
    assert exported.exists()
    assert exported.read_text().startswith("|6.6.6\n")
    assert manifest.exists()
    manifest_data = json.loads(manifest.read_text())
    assert manifest_data["schema_version"] == 2
    assert "does not imply scientific readiness" in manifest_data["export_warning"]
    table = manifest_data["tables"][0]
    assert table["exported_filename"] == "Custom_PlanetProfile_EOS.tab"
    assert table["active_perplex_components"][0] == {"oxide": "Na2O", "component": "NA2O"}
    assert table["database_file"].endswith("stx21ver.dat")
    assert table["solution_model_file"].endswith("stx21_solution_model.dat")
    assert table["p_t_range"]["pressure_bar"]["min"] == 1000.0
    assert table["excluded_phases"] == ["qtz"]
    assert table["werami_input_sequence"] == list(run_perplex.DEFAULT_WERAMI_INPUT_SEQUENCE)
    assert (output_dir / f"{PROJECT}_planetprofile_native.tab").exists()


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
    assert (output_dir / f"{PROJECT}_planetprofile_native.tab").exists()
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


def test_full_pipeline_allows_explicit_composition_file_without_inline_oxides(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_full_pipeline(config_path, skip_compositions=False)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "No inline compositions to generate" in result.stdout
    assert (output_dir / f"{PROJECT}_planetprofile.tab").exists()


def test_full_pipeline_generates_configured_inline_model(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, output_dir = make_inline_config(tmp_path, perplex_dir)

    result = run_full_pipeline(config_path, skip_compositions=False)

    assert result.returncode == 0, result.stderr + result.stdout
    composition = tmp_path / "compositions" / f"{PROJECT}.json"
    assert composition.exists()
    data = json.loads(composition.read_text())
    assert data["scientific_status"] == "surface_proxy_smoke_test"
    assert data["omitted_oxides_from_default_build"][0]["oxide"] == "TiO2"
    assert (output_dir / f"{PROJECT}_planetprofile_native.tab").exists()
    build_log = (output_dir / "build.log").read_text()
    assert "0.60060060 9.20920921 14.91491491 45.44544545 11.81181181 14.11411411" in build_log


def test_full_pipeline_exports_planetprofile_tables(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, _ = make_config(
        tmp_path,
        perplex_dir,
        planetprofile_filename="Pipeline_Exported_EOS.tab",
    )
    export_dir = tmp_path / "exported"

    result = run_full_pipeline_export(config_path, export_dir)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Exporting PlanetProfile tables" in result.stdout
    assert (export_dir / "Pipeline_Exported_EOS.tab").exists()
    manifest = json.loads((export_dir / "planetprofile_export_manifest.json").read_text())
    assert manifest["tables"][0]["export_warning"].startswith("This table is mechanically exportable")


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
