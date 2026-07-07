from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def slash_path(path: Path) -> str:
    return path.as_posix()


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
    datafiles_dir = perplex_dir / "datafiles"
    datafiles_dir.mkdir()
    (datafiles_dir / "stx21ver.dat").write_text(
        "begin_components\n"
        "NA2O 61.9790\n"
        "MGO 40.3040\n"
        "AL2O3 101.9610\n"
        "SIO2 60.0840\n"
        "CAO 56.0770\n"
        "FEO 71.8440\n"
        "O2 31.9990\n"
        "end_components\n"
    )
    (datafiles_dir / "stx21_solution_model.dat").write_text("O\nOpx\nCpx\n")
    (datafiles_dir / "hp633ver.dat").write_text(
        "begin_components\n"
        "Na2O 61.9790\n"
        "MgO 40.3040\n"
        "Al2O3 101.9610\n"
        "SiO2 60.0840\n"
        "K2O 94.1960\n"
        "CaO 56.0770\n"
        "TiO2 79.8660\n"
        "Cr2O3 151.9900\n"
        "MnO 70.9370\n"
        "FeO 71.8440\n"
        "NiO 74.6930\n"
        "end_components\n"
    )
    (datafiles_dir / "solution_model.dat").write_text(
        "O(HP)\nOpx(HP)\nCpx(HP)\nGt(HP)\nSp(HP)\nPl(I1,HP)\nIlm(WPH)\n"
        "Gt(H)\nFper(H)\nMpv(H)\nCpv(H)\nCFer(H)\nAki(H)\nO(JH)\nWad(H)\nRing(H)\n"
        "Cpx(JH)\nOpx(JH)\nHpx(H)\nNAl(H)\nCor(H)\nAtg(PN)\nAmph(DHP)\nChum\n"
        "St(HP)\nmelt(HP)\nCpx(HGP)\nFsp(C1)\nO(HGP)\nOpx(HGP)\nSp(HGP)\n"
        "Gt(HGP)\nCrd(HGP)\nBi(HGP)\nMica(W)\nEp(HP11)\ncAmph(G)\nChl(W)\n"
    )
    (datafiles_dir / "dew17hp622ver_elements.dat").write_text(
        "begin_components\n"
        "Na 22.9898\n"
        "Mg 24.3045\n"
        "Al 26.9812\n"
        "Si 28.0850\n"
        "Ca 40.0775\n"
        "Ti 47.8670\n"
        "Mn 54.9380\n"
        "Fe 55.8445\n"
        "Ni 58.6934\n"
        "O2 31.9990\n"
        "H2 2.0155\n"
        "C 12.0110\n"
        "S2 64.1300\n"
        "N2 28.0130\n"
        "end_components\n"
    )
    (datafiles_dir / "dew13hp622ver_elements.dat").write_text(
        "begin_components\n"
        "Mg 24.3045\n"
        "Si 28.0850\n"
        "Fe 55.8445\n"
        "O2 31.9990\n"
        "H2 2.0155\n"
        "C 12.0110\n"
        "S2 64.1300\n"
        "end_components\n"
    )
    (datafiles_dir / "hpha02ver.dat").write_text(
        "begin_components\n"
        "NA2O 61.9790\n"
        "MGO 40.3040\n"
        "AL2O3 101.9610\n"
        "SIO2 60.0840\n"
        "K2O 94.1960\n"
        "CAO 56.0770\n"
        "TIO2 79.8660\n"
        "CR2O3 151.9900\n"
        "MNO 70.9370\n"
        "FEO 71.8440\n"
        "NIO 74.6930\n"
        "H2O 18.0150\n"
        "end_components\n"
    )

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
expected_sequences = [
    ["2", "38", "1", "2", "13", "14", "3", "4", "10", "11", "0", "n", "1", "0"],
    ["2", "38", "1", "n", "2", "13", "14", "3", "4", "10", "11", "0", "n", "1", "0"],
]
if lines[1:] not in expected_sequences:
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


def make_component_config(
    tmp_path: Path,
    perplex_dir: Path,
    *,
    project: str = "ci_component_test",
    database: str = "dew17_hhph",
    components: dict[str, float] | None = None,
    planetprofile_first_axis: str = "T",
) -> tuple[Path, Path]:
    output_dir = tmp_path / "outputs" / project
    if components is None:
        components = {
            "H2": 2.07,
            "C": 3.53,
            "Mg": 9.94,
            "Al": 0.89,
            "Si": 10.90,
            "S2": 5.54,
            "Ca": 0.95,
            "Ti": 0.00,
            "Mn": 0.00,
            "Fe": 18.65,
            "Ni": 0.00,
            "O2": 47.54,
        }
    config = {
        "perplex_dir": str(perplex_dir),
        "database": database,
        "models": [
            {
                "project": project,
                "description": f"{project} component test model",
                "database": database,
                "output_dir": str(output_dir),
                "planetprofile_filename": f"{project}.tab",
                "planetprofile_first_axis": planetprofile_first_axis,
                "scientific_status": "test_candidate",
                "model_scope": "icy_world_component_model",
                "planetprofile_readiness": "not_assessed_for_planetprofile_science",
                "composition_interpretation": "Component model used by the test suite.",
                "component_label": "Perple_X component",
                "components_wt_percent": components,
            }
        ],
    }
    config_path = tmp_path / f"{project}_models.json"
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
    # Extended oxide list - stx21 only supports 6 oxides, rest are source-only
    assert data["default_perplex_build"]["source_only_oxides"] == ["TiO2", "Cr2O3", "MnO", "NiO", "K2O", "P2O5", "H2O"]
    assert data["default_perplex_build"]["bulk_values_order"] == ["NA2O", "MGO", "AL2O3", "SIO2", "CAO", "FEO"]
    omitted = data["omitted_oxides_from_default_build"]
    assert omitted[0]["oxide"] == "TiO2"
    assert math.isclose(omitted[0]["normalized_wt_percent"], 3.90390390, rel_tol=0, abs_tol=1e-8)
    bulk_values = (tmp_path / f"{NEAR_PROJECT}_bulk_values.txt").read_text().strip()
    assert bulk_values == "0.60060060 9.20920921 14.91491491 45.44544545 11.81181181 14.11411411"


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

    assert slash_path(tmp_path / "fake_perplex") in rendered.replace("\\", "/")
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


def test_icy_databases_use_fluid_prompt_werami_sequence() -> None:
    for database in ("dew17_hhph", "hpha02_hydrous", "dew13_hydrous", "dew17_comet"):
        assert run_perplex.default_werami_sequence_for_database(database) == run_perplex.HP633_WERAMI_INPUT_SEQUENCE


def test_hp633_default_werami_sequence_answers_fluid_prompt_and_requests_density(tmp_path: Path) -> None:
    model = run_perplex.ModelConfig(
        project=PROJECT,
        composition_file=tmp_path / "composition.json",
        build_input_file=tmp_path / "build.in",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        database="hp633",
        werami_input_sequence=run_perplex.default_werami_sequence_for_database("hp633"),
    )

    assert run_perplex.werami_input_text(model) == (
        f"{PROJECT}\n2\n38\n1\nn\n2\n13\n14\n3\n4\n10\n11\n0\nn\n1\n0\n"
    )


def test_parse_perplex_database_components_from_stx_style_header() -> None:
    text = (
        "title | comment begin_components | < 6 chars, molar weight "
        "NA2O 61.9790 MGO 40.3040 AL2O3 101.9610 SIO2 60.0840 "
        "CAO 56.0770 FEO 71.8440 O2 31.9990 end_components | tail"
    )

    components = run_perplex.parse_perplex_components(text)

    assert components == ["NA2O", "MGO", "AL2O3", "SIO2", "CAO", "FEO", "O2"]


def test_default_component_status_marks_ti_k_p_as_not_declared(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)

    rows = run_perplex.default_component_status(perplex_dir)
    by_oxide = {row["oxide"]: row for row in rows}

    assert by_oxide["SiO2"]["declared_in_default_database"] is True
    assert by_oxide["SiO2"]["passed_by_default_build"] is True
    assert by_oxide["TiO2"]["declared_in_default_database"] is False
    assert by_oxide["K2O"]["passed_by_default_build"] is False
    assert by_oxide["P2O5"]["declared_in_default_database"] is False


def test_hp633_component_status_models_ti_and_k_but_not_p(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)

    rows = run_perplex.default_component_status(perplex_dir, database="hp633")
    by_oxide = {row["oxide"]: row for row in rows}

    assert by_oxide["TiO2"]["declared_in_database"] is True
    assert by_oxide["TiO2"]["passed_by_build"] is True
    assert by_oxide["K2O"]["declared_in_database"] is True
    assert by_oxide["K2O"]["passed_by_build"] is True
    assert by_oxide["P2O5"]["declared_in_database"] is False
    assert by_oxide["P2O5"]["passed_by_build"] is False


def test_hp633_composition_metadata_and_bulk_order(tmp_path: Path) -> None:
    near = [model for model in make_compositions.lunar_models() if model.project == NEAR_PROJECT][0]

    make_compositions.write_composition(near, outdir=tmp_path, database="hp633")

    data = json.loads((tmp_path / f"{NEAR_PROJECT}.json").read_text())
    build = data["perplex_build"]
    assert build["database_name"] == "hp633"
    assert build["thermodynamic_database"] == "hp633ver.dat"
    assert build["solution_model_file"] == "solution_model.dat"
    # hp633 now includes all rock-forming oxides (only P2O5 is source-only)
    assert build["source_only_oxides"] == ["P2O5"]
    # Order matches OXIDE_ORDER: SiO2, TiO2, Al2O3, Cr2O3, FeO, MnO, NiO, MgO, CaO, Na2O, K2O, H2O
    assert build["bulk_values_order"] == ["SiO2", "TiO2", "Al2O3", "Cr2O3", "FeO", "MnO", "NiO", "MgO", "CaO", "Na2O", "K2O", "H2O"]
    assert data["omitted_oxides_from_build"] == []

    bulk_values = (tmp_path / f"{NEAR_PROJECT}_bulk_values.txt").read_text().strip()
    # Order: SiO2 TiO2 Al2O3 Cr2O3 FeO MnO NiO MgO CaO Na2O K2O H2O (trace elements=0)
    assert bulk_values == "45.44544545 3.90390390 14.91491491 0.00000000 14.11411411 0.00000000 0.00000000 9.20920921 11.81181181 0.60060060 0.00000000 0.00000000"


def test_component_composition_generation_writes_perplex_components(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, _ = make_component_config(tmp_path, perplex_dir)

    result = make_compositions.main(["--config", str(config_path)])

    assert result is None
    composition_path = tmp_path / "compositions" / "ci_component_test.json"
    values_path = tmp_path / "compositions" / "ci_component_test_bulk_values.txt"
    data = json.loads(composition_path.read_text())
    assert data["composition_basis"] == "perplex_components"
    assert data["component_order"] == ["H2", "C", "Mg", "Al", "Si", "S2", "Ca", "Ti", "Mn", "Fe", "Ni", "O2"]
    assert data["perplex_build"]["thermodynamic_database"] == "dew17hp622ver_elements.dat"
    assert data["perplex_build"]["bulk_values_order"] == ["H2", "C", "Mg", "Al", "Si", "S2", "Ca", "Ti", "Mn", "Fe", "Ni", "O2"]
    bulk_values = [float(value) for value in values_path.read_text().split()]
    assert len(bulk_values) == 12  # H2, C, Mg, Al, Si, S2, Ca, Ti, Mn, Fe, Ni, O2
    assert math.isclose(sum(bulk_values), 100.0, rel_tol=0, abs_tol=1e-6)
    assert math.isclose(bulk_values[0], data["composition_normalized"]["H2"], rel_tol=0, abs_tol=1e-8)


def test_component_pipeline_runs_build_with_default_icy_template(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, output_dir = make_component_config(tmp_path, perplex_dir)

    result = run_full_pipeline(config_path, skip_compositions=False)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Running BUILD for ci_component_test" in result.stdout
    assert "BUILD skipped" not in result.stdout + result.stderr
    build_log = (output_dir / "build.log").read_text()
    assert "dew17hp622ver_elements.dat" in build_log
    assert "H2\nC\nMg\nAl\nSi\nS2\nCa\nTi\nMn\nFe\nNi\nO2" in build_log
    assert "${PERPLEX_BULK_VALUES}" not in build_log
    assert (output_dir / "work" / "ci_component_test.dat").exists()
    assert (output_dir / "ci_component_test_planetprofile_native.tab").exists()


def test_hpha02_component_pipeline_can_write_pressure_first_native_table(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, output_dir = make_component_config(
        tmp_path,
        perplex_dir,
        project="hydrous_component_test",
        database="hpha02_hydrous",
        planetprofile_first_axis="P",
        components={
            "SIO2": 34.00,
            "TIO2": 0.00,
            "AL2O3": 3.22,
            "FEO": 26.83,
            "MGO": 24.58,
            "CAO": 2.62,
            "NA2O": 0.49,
            "K2O": 0.00,
            "H2O": 0.92,
        },
    )

    result = run_full_pipeline(config_path, skip_compositions=False)

    assert result.returncode == 0, result.stderr + result.stdout
    lines = (output_dir / "hydrous_component_test_planetprofile_native.tab").read_text().splitlines()
    assert lines[3].strip() == "P(bar)"
    assert lines[7].strip() == "T(K)"


def test_hpha02_default_template_uses_simple_component_list() -> None:
    template = run_perplex.default_build_template_for_database("hpha02_hydrous")
    text = template.read_text()
    (p_min, p_max), (t_min, t_max) = run_perplex.extract_pt_range_from_template(template)

    assert template.name == "icy_hpha02_hydrous_simple_template.build.in"
    assert "\nSIO2\nAL2O3\nFEO\nMGO\nCAO\nNA2O\nH2O\n" in text
    assert "\nTIO2\n" not in text
    assert "\nCR2O3\n" not in text
    assert (p_min, p_max) == (1.0, 7000.0)
    assert (t_min, t_max) == (250.0, 320.0)


def test_model_level_build_template_file_is_honored(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    template = tmp_path / "custom_hpha02.build.in"
    template.write_text("${PROJECT}\n${PERPLEX_BULK_VALUES}\n")
    config = {
        "perplex_dir": str(perplex_dir),
        "models": [
            {
                "project": "custom_template_test",
                "database": "hpha02_hydrous",
                "composition_file": str(tmp_path / "composition.json"),
                "build_template_file": str(template),
                "output_dir": str(tmp_path / "outputs" / "custom_template_test"),
            }
        ],
    }
    config_path = tmp_path / "models.json"
    config_path.write_text(json.dumps(config) + "\n")

    loaded = run_perplex.load_config(config_path)

    assert loaded.models[0].build_input_file == template


def test_hpha02_component_generation_uses_uppercase_component_aliases(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, _ = make_component_config(
        tmp_path,
        perplex_dir,
        project="hpha02_uppercase_components",
        database="hpha02_hydrous",
        components={
            "SIO2": 34.00,
            "AL2O3": 3.22,
            "FEO": 26.83,
            "MGO": 24.58,
            "CAO": 2.62,
            "NA2O": 0.49,
            "H2O": 0.92,
        },
    )

    make_compositions.main(["--config", str(config_path)])

    composition_path = tmp_path / "compositions" / "hpha02_uppercase_components.json"
    values_path = tmp_path / "compositions" / "hpha02_uppercase_components_bulk_values.txt"
    data = json.loads(composition_path.read_text())
    bulk_values = [float(value) for value in values_path.read_text().split()]

    assert data["component_order"][:7] == ["SIO2", "AL2O3", "FEO", "MGO", "CAO", "NA2O", "H2O"]
    assert data["perplex_build"]["bulk_values_order"] == ["SIO2", "AL2O3", "FEO", "MGO", "CAO", "NA2O", "H2O"]
    assert math.isclose(bulk_values[0], data["composition_normalized"]["SIO2"], rel_tol=0, abs_tol=1e-8)
    assert math.isclose(bulk_values[1], data["composition_normalized"]["AL2O3"], rel_tol=0, abs_tol=1e-8)


def test_hp633_config_uses_matching_default_template(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config = {
        "perplex_dir": str(perplex_dir),
        "database": "hp633",
        "build_template_file": str(PIPELINE_DIR / "build_inputs" / "lunar_stx21_template.build.in"),
        "models": [
            {
                "project": PROJECT,
                "composition_file": str(tmp_path / "composition.json"),
                "output_dir": str(tmp_path / "outputs" / PROJECT),
            }
        ],
    }
    config_path = tmp_path / "models.json"
    config_path.write_text(json.dumps(config) + "\n")

    loaded = run_perplex.load_config(config_path)

    assert loaded.database == "hp633"
    assert loaded.models[0].database == "hp633"
    assert loaded.models[0].build_input_file == PIPELINE_DIR / "build_inputs" / "lunar_hp633_template.build.in"
    assert loaded.models[0].werami_input_sequence == run_perplex.default_werami_sequence_for_database("hp633")


def test_render_hp633_build_input_uses_hp_bulk_values(tmp_path: Path) -> None:
    composition_file = tmp_path / "composition.json"
    composition_file.write_text(
        json.dumps(
            {
                "composition_normalized": {
                    "SiO2": 45.0,
                    "TiO2": 4.0,
                    "Al2O3": 15.0,
                    "Cr2O3": 0.0,
                    "FeO": 14.0,
                    "MnO": 0.0,
                    "NiO": 0.0,
                    "MgO": 9.0,
                    "CaO": 12.0,
                    "Na2O": 0.5,
                    "K2O": 0.5,
                    "P2O5": 0.0,
                    "H2O": 0.0,
                }
            }
        )
        + "\n"
    )
    build_input_file = tmp_path / "hp.build.in"
    build_input_file.write_text("${PERPLEX_BULK_VALUES}\n")
    model = run_perplex.ModelConfig(
        project=PROJECT,
        composition_file=composition_file,
        build_input_file=build_input_file,
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        database="hp633",
    )

    rendered = run_perplex.render_build_input(tmp_path / "fake_perplex", model)

    # hp633 now uses OXIDE_ORDER: SiO2, TiO2, Al2O3, Cr2O3, FeO, MnO, NiO, MgO, CaO, Na2O, K2O, H2O
    assert rendered.strip() == "45.00000000 4.00000000 15.00000000 0.00000000 14.00000000 0.00000000 0.00000000 9.00000000 12.00000000 0.50000000 0.50000000 0.00000000"


def test_default_build_templates_answer_chemical_potential_prompt_before_components() -> None:
    stx_template = (PIPELINE_DIR / "build_inputs" / "lunar_stx21_template.build.in").read_text()
    hp_template = (PIPELINE_DIR / "build_inputs" / "lunar_hp633_template.build.in").read_text()

    assert "\nn\nn\nn\nNA2O\nMGO\nAL2O3\n" in stx_template
    # hp633 now uses OXIDE_ORDER: SiO2, TiO2, Al2O3, FeO, MgO, CaO, Na2O, K2O, H2O
    assert "\nn\nn\nn\nSiO2\nTiO2\nAl2O3\n" in hp_template


def test_hp633_default_template_excludes_silica_phases_with_incomplete_seismic_properties() -> None:
    hp_template = (PIPELINE_DIR / "build_inputs" / "lunar_hp633_template.build.in").read_text()

    assert "\nn\ny\nn\nq\ncrst\ntrd\n\ny\n" in hp_template


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


def test_phase_diagram_property_points_support_velocity_columns(tmp_path: Path) -> None:
    from planetary_eos_lab.gui import phase_diagram

    source = tmp_path / "source.tab"
    source.write_text(VALID_TAB)

    t_points, p_points, values, config = phase_diagram.property_points_from_tab(
        source,
        "P-wave velocity",
    )

    assert config["canonical"] == "vp_kms"
    assert t_points == [1200.0, 1200.0, 1300.0, 1300.0]
    assert p_points == [0.1, 0.2, 0.1, 0.2]
    assert values == [8.0, 8.05, 8.06, 8.1]


def test_phase_diagram_simplified_assemblages_group_minor_phase_changes() -> None:
    from planetary_eos_lab.core.phase_parser import AssemblageGrid, assemblage_boundary_segments
    from planetary_eos_lab.gui import phase_diagram

    assemblage_grid = AssemblageGrid(
        ids=[[1, 2, 3], [4, 5, None]],
        labels={
            1: ("Cpx(HP)", "Gt(HP)", "coe", "ru"),
            2: ("Cpx(HP)", "Gt(HP)", "q"),
            3: ("Cpx(HP)", "Gt(HP)", "crst"),
            4: ("Opx(HP)", "Cpx(HP)", "ru"),
            5: ("ru",),
        },
    )

    group_labels, raw_to_group_id = phase_diagram.build_simplified_assemblage_labels(assemblage_grid)
    simplified_ids = phase_diagram.remap_assemblage_ids(assemblage_grid.ids, raw_to_group_id)

    assert simplified_ids[0][0] == simplified_ids[0][1] == simplified_ids[0][2]
    assert group_labels[simplified_ids[0][0]] == ("Cpx(HP)", "Gt(HP)", "SiO2")
    assert group_labels[simplified_ids[1][0]] == ("Opx(HP)", "Cpx(HP)")
    assert group_labels[simplified_ids[1][1]] == ("ru",)
    assert phase_diagram.simplified_phase_tuple(("Cpx(HP)", "qL", "anL")) == ("Cpx(HP)", "Melt(L)")
    assert phase_diagram.major_framework_phase_tuple(("Cpx(HP)", "Gt(HP)", "coe", "ru")) == ("Cpx(HP)", "Gt(HP)")
    assert phase_diagram.major_framework_phase_tuple(("qL", "anL")) == ()

    framework_labels, framework_raw_to_group_id = phase_diagram.build_grouped_assemblage_labels(
        assemblage_grid,
        phase_diagram.MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION,
    )
    framework_ids = phase_diagram.remap_assemblage_ids(assemblage_grid.ids, framework_raw_to_group_id)

    assert framework_ids[0][0] == framework_ids[0][1] == framework_ids[0][2]
    assert framework_labels[framework_ids[0][0]] == ("Cpx(HP)", "Gt(HP)")

    hover_grid = phase_diagram.assemblage_hover_grid(
        framework_ids,
        framework_labels,
        hover_label="Major framework",
    )
    assert "Major framework" in hover_grid[0][0]
    assert "Full Perple_X assemblage" not in hover_grid[0][0]
    assert phase_diagram.assemblage_field_label(("Cpx(HP)", "Gt(HP)")) == "Cpx + Gt"
    caption_text = phase_diagram.assemblage_caption_text(
        assemblage_grid,
        phase_diagram.MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION,
    )
    assert "The '+' sign means" in caption_text
    assert "Opx = orthopyroxene" in caption_text
    assert "Cpx = clinopyroxene" in caption_text
    assert "Gt = garnet" in caption_text

    detailed_caption_text = phase_diagram.assemblage_caption_text(
        assemblage_grid,
        phase_diagram.DETAILED_ASSEMBLAGE_OPTION,
    )
    assert "coe = coesite" in detailed_caption_text
    assert "q = quartz" in detailed_caption_text
    assert "ru = rutile" in detailed_caption_text

    detailed_segments = assemblage_boundary_segments(
        temperatures_k=[800.0, 900.0, 1000.0],
        pressures=[0.1, 0.2],
        assemblage_ids=assemblage_grid.ids,
    )
    simplified_segments = assemblage_boundary_segments(
        temperatures_k=[800.0, 900.0, 1000.0],
        pressures=[0.1, 0.2],
        assemblage_ids=simplified_ids,
    )

    assert simplified_segments.count < detailed_segments.count

    polylines = phase_diagram.connected_boundary_polylines(
        temperatures_k=[800.0, 900.0, 1000.0],
        pressures=[0.1, 0.2],
        assemblage_ids=framework_ids,
    )
    boundary_x, boundary_y, boundary_count = phase_diagram.boundary_polyline_coordinates(polylines)

    assert boundary_count > 0
    assert boundary_x[-1] is None
    assert boundary_y[-1] is None


def test_parse_vertex_assemblage_preview_from_plt_and_blk(tmp_path: Path) -> None:
    from planetary_eos_lab.core.phase_parser import (
        assemblage_boundary_segments,
        parse_assemblage_grid,
    )

    plt_path = tmp_path / "model.plt"
    blk_path = tmp_path / "model.blk"
    plt_path.write_text(
        "\n".join(
            [
                "2 3 1",
                "2 1",
                "2 2",
                "2",
                "2 0 2",
                "1 2",
                "1 0 1",
                "-4",
                "",
                "4 compound counter",
                "1 fo",
                "2 fa",
                "3 coe",
                "4 q",
                "",
                "2 solution model counter",
                "1 8 4 Opx(HP)",
                "2 2 2 O(HP)",
            ]
        )
    )
    blk_path.write_text(
        "\n".join(
            [
                "1 1 1",
                "0.1 0.2",
                "1 2 1",
                "0.1 0.2",
                "1 3 2",
                "0.1 0.2",
                "2 1 1",
                "0.1 0.2",
                "2 2 2",
                "0.1 0.2",
                "2 3 2",
                "0.1 0.2",
            ]
        )
    )

    assemblage_grid = parse_assemblage_grid(plt_path, blk_path)

    assert assemblage_grid is not None
    assert assemblage_grid.ids == [[1, 1, 2], [1, 2, 2]]
    assert assemblage_grid.labels[1] == ("Opx(HP)", "O(HP)")
    assert assemblage_grid.labels[2] == ("q",)

    segments = assemblage_boundary_segments(
        temperatures_k=[800.0, 900.0, 1000.0],
        pressures=[0.1, 0.2],
        assemblage_ids=assemblage_grid.ids,
    )

    assert segments.count == 3
    assert 950.0 in segments.x
    assert any(math.isclose(value, 0.15) for value in segments.y if value is not None)


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
    assert slash_path(perplex_dir / "datafiles" / "example.dat") in build_log.replace("\\", "/")
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


def test_missing_build_input_fails_before_vertex(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config_path, _ = make_config(tmp_path, perplex_dir, build_input=False)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "Missing BUILD input file" in result.stderr


def test_missing_executable_fails_clearly(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path, omit="vertex")
    config_path, _ = make_config(tmp_path, perplex_dir, build_input=True)

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


def test_warning_ver177_log_is_reported_without_failing_finite_tables(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path, werami_log="warning ver177")
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode == 0
    report = (output_dir / "validation_report.txt").read_text()
    assert "STATUS: PASS" in report
    assert "Warnings:" in report
    assert "warning ver177" in report


def test_bad_number_sentinel_in_tab_fails_validation(tmp_path: Path) -> None:
    bad_tab = VALID_TAB.replace("4100000", "0.100000E+100")
    perplex_dir = make_fake_perplex(tmp_path, tab_text=bad_tab)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "bad-number" in (output_dir / "validation_report.txt").read_text()


def test_partial_nan_required_column_fails_validation(tmp_path: Path) -> None:
    partial_nan_tab = VALID_TAB.replace("8.05", "NaN", 1)
    perplex_dir = make_fake_perplex(tmp_path, tab_text=partial_nan_tab)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    report = (output_dir / "validation_report.txt").read_text()
    assert "Non-finite values in VP_kms: 1 of 4" in report


def test_zero_only_alpha_column_fails_validation(tmp_path: Path) -> None:
    zero_alpha_tab = VALID_TAB.replace("3.0E-5", "0.0").replace("3.1E-5", "0.0")
    perplex_dir = make_fake_perplex(tmp_path, tab_text=zero_alpha_tab)
    config_path, output_dir = make_config(tmp_path, perplex_dir)

    result = run_pipeline(config_path)

    assert result.returncode != 0
    assert "Zero-only alpha column" in (output_dir / "validation_report.txt").read_text()


def test_component_composition_missing_required_component_shows_helpful_error(tmp_path: Path) -> None:
    """Test that missing required components produce helpful error with database suggestions."""
    # Create a component composition missing O2 (required by dew17_hhph)
    incomplete_model = make_compositions.ComponentComposition(
        project="incomplete_ci",
        description="CI missing O2 for testing error message",
        raw_wt_percent={
            "H2": 2.0,
            "C": 3.5,
            "Mg": 10.0,
            "Al": 1.0,
            "Si": 11.0,
            "S2": 5.5,
            "Ca": 1.0,
            "Fe": 19.0,
            # Missing O2!
        },
        component_order=["H2", "C", "Mg", "Al", "Si", "S2", "Ca", "Fe"],
        database="dew17_hhph",
    )

    try:
        make_compositions.write_component_composition(incomplete_model, tmp_path / "compositions")
        assert False, "Should have raised ValueError for missing O2"
    except ValueError as e:
        error_msg = str(e)
        # Check that error message is helpful
        assert "missing BUILD component(s): Ti, Mn, Ni, O2" in error_msg
        assert "Your database 'dew17_hhph' requires" in error_msg
        assert "Your composition provides:" in error_msg
        assert "Available databases:" in error_msg
        assert "docs/icy_worlds_guide.md" in error_msg


def test_database_template_mismatch_shows_helpful_error(tmp_path: Path) -> None:
    """Test that database-template mismatches produce helpful error."""
    perplex_dir = make_fake_perplex(tmp_path)

    # Create model with dew17_hhph database but lunar_stx21 template
    model = run_perplex.ModelConfig(
        project="mismatch_test",
        composition_file=tmp_path / "compositions" / "test.json",
        build_input_file=PIPELINE_DIR / "build_inputs" / "lunar_stx21_template.build.in",
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        database="dew17_hhph",  # Wrong database for stx21 template!
    )

    try:
        run_perplex.validate_thermodynamic_setup(perplex_dir, model)
        assert False, "Should have raised PipelineError for template mismatch"
    except run_perplex.PipelineError as e:
        error_msg = str(e)
        # Check helpful error message
        assert "BUILD template mismatch" in error_msg
        assert "lunar_stx21_template.build.in" in error_msg
        assert "designed for 'stx21'" in error_msg
        assert "Model database: dew17_hhph" in error_msg
        assert "Solutions:" in error_msg
        assert "docs/icy_worlds_guide.md" in error_msg


def test_component_composition_plot_labels_correctly(tmp_path: Path) -> None:
    """Test that component compositions are labeled correctly in plots."""
    # Create two component compositions
    perplex_dir = make_fake_perplex(tmp_path)

    ci_model = make_compositions.ComponentComposition(
        project="ci_test",
        description="CI test",
        raw_wt_percent={"H2": 2.0, "C": 3.5, "Mg": 10.0, "Al": 1.0, "Si": 11.0, "S2": 5.5, "Ca": 1.0, "Ti": 0.0, "Mn": 0.0, "Fe": 19.0, "Ni": 0.0, "O2": 47.0},
        component_order=["H2", "C", "Mg", "Al", "Si", "S2", "Ca", "Ti", "Mn", "Fe", "Ni", "O2"],
        database="dew17_hhph",
    )

    cm_model = make_compositions.ComponentComposition(
        project="cm_test",
        description="CM test",
        raw_wt_percent={"H2": 1.4, "C": 2.3, "Mg": 11.8, "Al": 1.2, "Si": 13.0, "S2": 2.8, "Ca": 1.3, "Ti": 0.0, "Mn": 0.0, "Fe": 22.0, "Ni": 0.0, "O2": 44.0},
        component_order=["H2", "C", "Mg", "Al", "Si", "S2", "Ca", "Ti", "Mn", "Fe", "Ni", "O2"],
        database="dew17_hhph",
    )

    comp_dir = tmp_path / "compositions"
    make_compositions.write_component_composition(ci_model, comp_dir)
    make_compositions.write_component_composition(cm_model, comp_dir)

    models = [
        plot_comparisons.PlotModel(
            project="ci_test",
            label="CI test",
            composition_file=comp_dir / "ci_test.json",
            tab_file=tmp_path / "outputs" / "ci_test" / "ci_test_planetprofile.tab",
        ),
        plot_comparisons.PlotModel(
            project="cm_test",
            label="CM test",
            composition_file=comp_dir / "cm_test.json",
            tab_file=tmp_path / "outputs" / "cm_test" / "cm_test_planetprofile.tab",
        ),
    ]

    svg = plot_comparisons.composition_plot_svg(models)

    # Check that plot is labeled as "component" not "oxide"
    assert "Normalized component composition" in svg
    assert "nonzero components" in svg
    # Check that component names appear
    assert "H2" in svg or "Mg" in svg or "Fe" in svg


def test_pt_range_extraction_from_template() -> None:
    """Test that PT ranges can be extracted from BUILD templates."""
    # Test with real icy world template
    template_path = PIPELINE_DIR / "build_inputs" / "icy_dew17_hhph_template.build.in"
    if template_path.exists():
        pt_range = run_perplex.extract_pt_range_from_template(template_path)
        assert pt_range is not None, "Should extract PT range from icy template"
        (p_min, p_max), (t_min, t_max) = pt_range
        # dew17_hhph uses 1-140000 bar, 250-2000 K (reduced to avoid NaN at high T)
        assert p_min == 1.0
        assert p_max == 140000.0
        assert t_min == 250.0
        assert t_max == 2000.0

    # Test with lunar template
    lunar_template = PIPELINE_DIR / "build_inputs" / "lunar_stx21_template.build.in"
    if lunar_template.exists():
        pt_range = run_perplex.extract_pt_range_from_template(lunar_template)
        assert pt_range is not None
        (p_min, p_max), (t_min, t_max) = pt_range
        # stx21 uses 1000-50000 bar, 800-2200 K
        assert 800 <= t_min <= 1000
        assert 2000 <= t_max <= 2500
