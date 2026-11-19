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


def test_per_model_perplex_options_are_loaded_and_written(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config = {
        "perplex_dir": str(perplex_dir),
        "perplex_options": {
            "sample_on_grid": "T",
            "x_nodes": [10, 50],
            "y_nodes": [20, 60],
        },
        "models": [
            {
                "project": PROJECT,
                "composition_file": str(tmp_path / "composition.json"),
                "output_dir": str(tmp_path / "outputs" / PROJECT),
                "perplex_options": {
                    "sample_on_grid": "F",
                    "x_nodes": [40, 300],
                    "y_nodes": [40, 300],
                },
            }
        ],
    }
    config_path = tmp_path / "models.json"
    config_path.write_text(json.dumps(config) + "\n")

    loaded = run_perplex.load_config(config_path)
    options = loaded.models[0].perplex_options

    assert options.sample_on_grid is False
    assert options.x_nodes == (40, 300)
    assert options.y_nodes == (40, 300)
    text = run_perplex.render_perplex_option_text(options)
    assert "sample_on_grid F" in text
    assert "x_nodes 40 300" in text
    assert "y_nodes 40 300" in text
    assert "grid_levels 1 4" in text


def test_top_level_perplex_options_apply_to_models(tmp_path: Path) -> None:
    perplex_dir = make_fake_perplex(tmp_path)
    config = {
        "perplex_dir": str(perplex_dir),
        "perplex_options": {
            "sample_on_grid": True,
            "x_nodes": "12 34",
            "y_nodes": "56 78",
        },
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
    options = loaded.models[0].perplex_options

    assert options.sample_on_grid is True
    assert options.x_nodes == (12, 34)
    assert options.y_nodes == (56, 78)
    text = run_perplex.render_perplex_option_text(options)
    assert "sample_on_grid T" in text
    assert "grid_levels 1 1" in text
    assert "x_nodes 12 34" in text
    assert "y_nodes 56 78" in text


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
    color_entries = phase_diagram.assemblage_color_key_entries(
        assemblage_grid,
        phase_diagram.MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION,
    )
    assert color_entries[0][1] == "clinopyroxene + garnet"
    color_key_html = phase_diagram.assemblage_color_key_html(color_entries)
    assert color_key_html.startswith("<div")
    assert "background-color:" in color_key_html
    assert "border-left:" in color_key_html
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

    # Lunar templates take their range from the database (or the model) through placeholders
    lunar_template = PIPELINE_DIR / "build_inputs" / "lunar_stx21_template.build.in"
    text = lunar_template.read_text()
    assert "${P_RANGE_BAR}" in text and "${T_RANGE_K}" in text


# ----------------------------------------------------------------------
# Tracked BSM scientific catalogue
#
# Source of truth for these tests is configs/lunar_bsm_models.json,
# which is a tracked, machine-independent catalogue of literature-
# verified Bulk Silicate Moon reference compositions.
#
# Warren (2005) Preferred BSM (core-excluded silicate inventory):
#   Warren, P. H. (2005). "New" lunar meteorites: Implications for
#   composition of the global lunar surface, lunar crust, and the bulk
#   Moon. Meteoritics & Planetary Science 40(3), 477-506.
#   DOI: 10.1111/j.1945-5100.2005.tb00395.x. Table 6 row "Same,
#   excluding 1.2 wt% core".
#
# Published CFMAS+Ti values (wt%):
#   SiO2 46.8, TiO2 0.18, Al2O3 3.87, FeO 9.24, MgO 36.0, CaO 3.06.
# Subset sum 99.15. Renormalization factor 100/99.15 = 1.0085728693898135.
# ----------------------------------------------------------------------

TRACKED_BSM_CATALOGUE = PIPELINE_DIR / "configs" / "lunar_bsm_models.json"

W05_PREFERRED_BSM_PROJECT = "moon_w05_preferred_bsm"
H15_PROJECT = "moon_h15_lowFe"
W05_ALT5_PROJECT = "moon_w05_alt5_feRich"
W05_ALT5_LEGACY_ID = "moon_w05_moderateFe"

# Warren Table 6 "Same, excluding 1.2 wt% core" published CFMAS+Ti oxides.
W05_PREFERRED_PUBLISHED_CFMAS_TI = {
    "SiO2": 46.8,
    "TiO2": 0.18,
    "Al2O3": 3.87,
    "FeO": 9.24,
    "MgO": 36.0,
    "CaO": 3.06,
}
W05_PREFERRED_PUBLISHED_MINORS_EXCLUDED = {
    "Cr2O3": 0.44,
    "MnO": 0.132,
    "Na2O": 0.051,
    "K2O": 0.005,
}
W05_PREFERRED_CFMAS_TI_SUBSET_SUM = 99.15
W05_PREFERRED_RENORM_FACTOR = 100.0 / W05_PREFERRED_CFMAS_TI_SUBSET_SUM


def _load_tracked_bsm_catalogue() -> list[dict]:
    """Load the tracked BSM scientific catalogue.

    This function reads only configs/lunar_bsm_models.json, which is a
    tracked file. A clean clone (without configs/models.json) can run
    every test that uses this helper.
    """
    with TRACKED_BSM_CATALOGUE.open() as handle:
        return json.load(handle)["models"]


def _entry_from_catalogue(project: str) -> dict:
    for entry in _load_tracked_bsm_catalogue():
        if entry["project"] == project:
            return entry
    raise KeyError(project)


def _lunar_composition_from_entry(entry: dict) -> "make_compositions.LunarComposition":
    return make_compositions.LunarComposition(
        project=entry["project"],
        description=entry["description"],
        raw_wt_percent=entry["oxides_wt_percent"],
        source_note=entry["source_note"],
        scientific_status=entry["scientific_status"],
        model_scope=entry["model_scope"],
        planetprofile_readiness=entry["planetprofile_readiness"],
        composition_interpretation=entry["composition_interpretation"],
        literature_proxy=entry["literature_proxy"],
        database=entry["database"],
        composition_class=entry.get("composition_class", ""),
        study_role=entry.get("study_role", ""),
    )


def test_tracked_bsm_catalogue_contains_expected_entries() -> None:
    """The tracked BSM scientific catalogue must exist, be readable
    without configs/models.json, and contain exactly the three audited
    BSM entries (Hauri 2015 + Warren Preferred + Warren Alt Model 5).
    moon_t82_highFe must NOT be present in the runnable scientific set."""
    assert TRACKED_BSM_CATALOGUE.exists(), (
        "Tracked BSM catalogue must be present as configs/lunar_bsm_models.json"
    )
    models = _load_tracked_bsm_catalogue()
    projects = [m["project"] for m in models]
    assert projects == [H15_PROJECT, W05_PREFERRED_BSM_PROJECT, W05_ALT5_PROJECT], (
        f"Unexpected tracked catalogue contents: {projects}"
    )
    # All three entries must be BSM.
    for entry in models:
        assert entry["scientific_status"] == "literature_based"
        assert entry["model_scope"] == "bulk_silicate_body"
    # Uniqueness.
    assert len(projects) == len(set(projects))
    # moon_t82_highFe is deliberately excluded.
    assert "moon_t82_highFe" not in projects


def test_moon_w05_preferred_bsm_entry_records_warren_core_excluded_values() -> None:
    """moon_w05_preferred_bsm in the tracked catalogue stores the
    CFMAS+Ti-renormalized 2-decimal composition derived from Warren 2005
    Table 6 'Same, excluding 1.2 wt% core', with the source_note preserving
    the original published values and the transformation."""

    entry = _entry_from_catalogue(W05_PREFERRED_BSM_PROJECT)

    assert entry["scientific_status"] == "literature_based"
    assert entry["model_scope"] == "bulk_silicate_body"
    assert entry["literature_proxy"] is True
    assert entry["database"] == "hp633"
    assert entry["planetprofile_readiness"] == "pending_eos_generation_and_validation"

    source_note = entry["source_note"]
    assert "Warren, P. H. (2005)" in source_note
    assert "10.1111/j.1945-5100.2005.tb00395.x" in source_note
    assert "Same, excluding 1.2 wt% core" in source_note
    # Machine-readable provenance now lives in source_transformation.
    t = entry["source_transformation"]
    assert t["publication"].startswith("Warren (2005)")
    assert t["doi"] == "10.1111/j.1945-5100.2005.tb00395.x"
    assert t["table"] == "Table 6"
    assert t["row_label"] == "Same, excluding 1.2 wt% core"
    assert t["source_oxides_wt_percent"]["SiO2"] == 46.8
    assert t["source_oxides_wt_percent"]["FeO"] == 9.24
    assert t["source_oxides_wt_percent"]["MgO"] == 36.0
    assert t["source_oxides_wt_percent"]["Cr2O3"] == 0.44
    assert t["published_mg_number_mol_percent"] == 87.4
    assert t["retained_subset_sum_source"] == 99.15
    assert abs(t["normalization_factor"] - 100.0 / 99.15) < 1e-8

    interp = entry["composition_interpretation"]
    assert W05_ALT5_PROJECT in interp
    assert "same" in interp.lower() and "Warren" in interp
    assert "NOT be presented as independent" in interp

    oxides = entry["oxides_wt_percent"]
    published_renormalized_two_dp = {
        oxide: round(value * W05_PREFERRED_RENORM_FACTOR, 2)
        for oxide, value in W05_PREFERRED_PUBLISHED_CFMAS_TI.items()
    }
    for oxide, expected in published_renormalized_two_dp.items():
        stored = oxides[oxide]
        assert stored == expected, (
            f"{oxide}: stored {stored}, expected {expected} "
            f"(= published {W05_PREFERRED_PUBLISHED_CFMAS_TI[oxide]} "
            f"x {W05_PREFERRED_RENORM_FACTOR:.16f} rounded to 2 dp)"
        )

    for oxide in W05_PREFERRED_PUBLISHED_MINORS_EXCLUDED:
        assert oxides[oxide] == 0.0
    for oxide in ("NiO", "H2O", "P2O5"):
        assert oxides[oxide] == 0.0

    # Warren-Preferred's 2-decimal CFMAS+Ti values happen to sum to exactly
    # 100.00 (46.8 * 1.008573 rounds to 47.20, and so on such that all
    # rounding directions balance). This is a stronger property than
    # required by the schema (see test_stored_oxides_sum_to_100_at_declared_precision
    # for the general bound).
    assert sum(oxides.values()) == 100.00


def test_moon_w05_preferred_bsm_normalization_reproduces_warren_full_precision() -> None:
    """Feeding the stored 2-decimal oxide vector into
    make_compositions.normalize_wt_percent recovers the full-precision
    CFMAS+Ti values Warren Table 6 * (100/99.15)."""

    entry = _entry_from_catalogue(W05_PREFERRED_BSM_PROJECT)
    normalized = make_compositions.normalize_wt_percent(entry["oxides_wt_percent"])

    for oxide, published in W05_PREFERRED_PUBLISHED_CFMAS_TI.items():
        expected_full_precision = published * W05_PREFERRED_RENORM_FACTOR
        max_rounding_error = 0.5 * 0.01  # half a step at 2 dp
        assert abs(normalized[oxide] - expected_full_precision) <= max_rounding_error

    for oxide in ("Cr2O3", "MnO", "Na2O", "K2O", "NiO", "H2O", "P2O5"):
        assert normalized[oxide] == 0.0

    assert math.isclose(sum(normalized.values()), 100.0, rel_tol=0, abs_tol=1e-9)


def test_bsm_write_composition_emits_bsm_metadata_not_surface_proxy(tmp_path: Path) -> None:
    """Running make_compositions.write_composition against each BSM entry
    in the tracked catalogue produces JSON and summary files that carry
    BSM classification metadata and do NOT carry the surface-proxy
    warning strings."""

    for entry in _load_tracked_bsm_catalogue():
        model = _lunar_composition_from_entry(entry)
        outdir = tmp_path / entry["project"]
        outdir.mkdir()
        make_compositions.write_composition(model, outdir=outdir, database="hp633")

        # JSON classification metadata
        data = json.loads((outdir / f"{entry['project']}.json").read_text())
        assert data["scientific_status"] == "literature_based"
        assert data["model_scope"] == "bulk_silicate_body"

        json_text = (outdir / f"{entry['project']}.json").read_text()
        summary_text = (outdir / f"{entry['project']}_summary.txt").read_text()

        # BSM outputs MUST NOT contain the surface-proxy warning strings.
        assert "SURFACE PROXY SMOKE TEST ONLY" not in json_text
        assert "SURFACE PROXY SMOKE TEST ONLY" not in summary_text
        assert "surface/terrane proxies" not in json_text
        assert "surface/terrane proxies" not in summary_text

        # BSM outputs MUST contain a BSM scope statement (either the primary
        # reference or the published-alternative variant, depending on
        # composition_class).
        has_reference_line = "BULK SILICATE MOON reference composition" in json_text
        has_alternative_line = "BULK SILICATE MOON published alternative" in json_text
        assert has_reference_line or has_alternative_line, (
            f"{entry['project']}: neither BSM reference nor BSM alternative line in JSON"
        )
        summary_has_bsm_line = (
            "BULK SILICATE MOON reference composition" in summary_text
            or "BULK SILICATE MOON published alternative" in summary_text
        )
        assert summary_has_bsm_line, (
            f"{entry['project']}: no BSM status line in summary"
        )
        # Contract for BSM notes: the anti-identification statement is present.
        assert "identify" in json_text.lower() and "present-day mantle" in json_text.lower()


def test_surface_proxy_write_composition_retains_surface_proxy_warnings(tmp_path: Path) -> None:
    """The hardcoded surface-proxy configurations must continue to emit
    the strong 'SURFACE PROXY SMOKE TEST ONLY' warning and the
    surface/terrane-proxy note in both the JSON and the summary."""

    for project, model in {
        m.project: m for m in make_compositions.lunar_models()
    }.items():
        outdir = tmp_path / project
        outdir.mkdir()
        make_compositions.write_composition(model, outdir=outdir)

        json_text = (outdir / f"{project}.json").read_text()
        summary_text = (outdir / f"{project}_summary.txt").read_text()

        assert "SURFACE PROXY SMOKE TEST ONLY" in json_text
        assert "SURFACE PROXY SMOKE TEST ONLY" in summary_text
        assert "surface/terrane proxies" in json_text

        # And they must NOT carry the BSM statement.
        assert "BULK SILICATE MOON reference composition" not in json_text
        assert "BULK SILICATE MOON reference composition" not in summary_text


def test_bsm_catalogue_preserves_warren_alt5_values() -> None:
    """Adding the Warren-Preferred BSM to the catalogue must not disturb
    the Warren Alt Model 5 within-framework sensitivity endmember."""

    entry = _entry_from_catalogue(W05_ALT5_PROJECT)
    assert entry["scientific_status"] == "literature_based"
    assert entry["model_scope"] == "bulk_silicate_body"
    # Warren Alt Model 5 CFMAS+Ti (verified in the study repo audit).
    assert entry["oxides_wt_percent"]["FeO"] == 10.53
    assert entry["oxides_wt_percent"]["MgO"] == 35.8
    assert entry["oxides_wt_percent"]["SiO2"] == 46.5
    # Its interpretation must mark it as a within-framework sensitivity.
    interp = entry["composition_interpretation"]
    assert "Alternative Model 5" in interp
    assert "not" in interp.lower() and "independent" in interp.lower()


def test_bsm_catalogue_moon_h15_hauri_values() -> None:
    """The Hauri 2015 BSM entry preserves its CFMAS+Ti composition."""
    entry = _entry_from_catalogue(H15_PROJECT)
    assert entry["scientific_status"] == "literature_based"
    assert entry["model_scope"] == "bulk_silicate_body"
    assert entry["oxides_wt_percent"]["SiO2"] == 45.43
    assert entry["oxides_wt_percent"]["FeO"] == 8.13
    assert entry["oxides_wt_percent"]["MgO"] == 38.16
    assert "Hauri" in entry["source_note"]
    assert "10.1016/j.epsl.2014.10.053" in entry["source_note"]


def test_tracked_bsm_catalogue_records_composition_class_and_study_role() -> None:
    """Each tracked BSM entry must carry a composition_class and a
    study_role that distinguishes primary references from within-framework
    alternatives."""

    role_map = {
        H15_PROJECT: ("published_bsm_reference", "primary_reference"),
        W05_PREFERRED_BSM_PROJECT: ("published_bsm_reference", "primary_reference"),
        W05_ALT5_PROJECT: ("published_bsm_alternative", "within_framework_sensitivity"),
    }
    for project, (expected_class, expected_role) in role_map.items():
        entry = _entry_from_catalogue(project)
        assert entry.get("composition_class") == expected_class, (
            f"{project}: composition_class {entry.get('composition_class')!r}, "
            f"expected {expected_class!r}"
        )
        assert entry.get("study_role") == expected_role, (
            f"{project}: study_role {entry.get('study_role')!r}, "
            f"expected {expected_role!r}"
        )

    # Two primary_reference entries; one within_framework_sensitivity entry.
    catalogue = _load_tracked_bsm_catalogue()
    primaries = [m for m in catalogue if m.get("study_role") == "primary_reference"]
    sensitivities = [m for m in catalogue if m.get("study_role") == "within_framework_sensitivity"]
    assert len(primaries) == 2
    assert len(sensitivities) == 1


def test_bsm_reference_output_differs_from_bsm_alternative_output(tmp_path: Path) -> None:
    """Generated status/notes for a published_bsm_reference entry must
    differ from those of a published_bsm_alternative entry: the alternative
    must be labelled a within-framework sensitivity and must NOT be
    described as a primary literature-level BSM reference."""

    # Primary reference: Hauri 2015.
    primary = _lunar_composition_from_entry(_entry_from_catalogue(H15_PROJECT))
    primary_out = tmp_path / "primary"
    primary_out.mkdir()
    make_compositions.write_composition(primary, outdir=primary_out, database="hp633")
    primary_json = (primary_out / f"{H15_PROJECT}.json").read_text()
    primary_summary = (primary_out / f"{H15_PROJECT}_summary.txt").read_text()

    # Alternative: Warren Alt Model 5.
    alt = _lunar_composition_from_entry(_entry_from_catalogue(W05_ALT5_PROJECT))
    alt_out = tmp_path / "alt"
    alt_out.mkdir()
    make_compositions.write_composition(alt, outdir=alt_out, database="hp633")
    alt_json = (alt_out / f"{W05_ALT5_PROJECT}.json").read_text()
    alt_summary = (alt_out / f"{W05_ALT5_PROJECT}_summary.txt").read_text()

    # Primary must carry the BSM_REFERENCE_STATUS.
    assert "BULK SILICATE MOON reference composition" in primary_json
    assert "BULK SILICATE MOON reference composition" in primary_summary
    # Primary must NOT be labelled a within-framework sensitivity.
    assert "within-framework sensitivity" not in primary_json.lower()
    assert "must NOT be presented as an independent" not in primary_json

    # Alternative must carry the BSM_ALTERNATIVE_STATUS.
    assert "BULK SILICATE MOON published alternative" in alt_json
    assert "BULK SILICATE MOON published alternative" in alt_summary
    assert "within-framework sensitivity" in alt_json.lower()
    assert "must NOT be presented as an independent" in alt_json
    # Alternative must NOT be described as a reference composition first-line.
    assert "BULK SILICATE MOON reference composition" not in alt_summary.splitlines()[2]

    # Both retain the "not automatically a homogeneous present-day mantle"
    # caveat.
    for txt in (primary_json, alt_json):
        assert "not automatically" in txt
        assert "homogeneous present-day" in txt or "homogeneous, present-day" in txt


def test_literature_proxy_is_documented_and_not_used_as_scope_flag() -> None:
    """literature_proxy is pure metadata (per audit): it is never
    interpreted as a surface-proxy scope flag by the pipeline. This test
    documents that contract by asserting that the pipeline module lists
    'literature_proxy' in the semantics docstring near the module top."""

    src = (PIPELINE_DIR / "make_compositions.py").read_text()
    # The semantics docstring must exist and warn against using this flag
    # as a scope indicator.
    assert "`literature_proxy` flag semantics" in src
    assert "Do not use this flag to distinguish surface-proxy" in src


# ----------------------------------------------------------------------
# Structured source_transformation schema + deterministic reproducibility
# ----------------------------------------------------------------------

_RETAINED_CFMAS_TI = ("SiO2", "TiO2", "Al2O3", "FeO", "MgO", "CaO")


def test_every_tracked_bsm_entry_follows_common_schema() -> None:
    """Every BSM entry in the tracked catalogue must carry the common
    structured schema (composition_class, study_role, source_transformation
    block with retained/excluded lists, source_oxides_wt_percent,
    normalization_factor, retained_subset_sum_source)."""
    required_top_fields = (
        "project", "description", "scientific_status", "composition_class",
        "study_role", "model_scope", "planetprofile_readiness",
        "composition_interpretation", "literature_proxy", "source_note",
        "source_transformation", "oxides_wt_percent", "database",
        "perplex_options",
    )
    required_transformation_fields = (
        "publication", "doi", "table", "row_label",
        "normalization_basis", "source_precision",
        "source_oxides_wt_percent", "retained_oxides", "excluded_oxides",
        "retained_subset_sum_source", "normalization_factor",
        "implementation_basis", "implementation_precision_decimals",
        "published_mg_number_mol_percent",
    )
    for entry in _load_tracked_bsm_catalogue():
        for field in required_top_fields:
            assert field in entry, (
                f"{entry.get('project')}: missing top-level field {field!r}"
            )
        t = entry["source_transformation"]
        for field in required_transformation_fields:
            assert field in t, (
                f"{entry['project']}: missing source_transformation.{field!r}"
            )
        # All entries use CFMAS+Ti with the same retained subset.
        assert tuple(t["retained_oxides"]) == _RETAINED_CFMAS_TI, (
            f"{entry['project']}: retained_oxides is not CFMAS+Ti"
        )
        assert t["implementation_basis"] == "CFMAS+Ti"


def test_stored_oxides_reproducible_from_source_transformation() -> None:
    """The stored oxides_wt_percent must equal
    round(source_oxides * normalization_factor, implementation_precision_decimals)
    for each retained oxide, and 0.0 for each other oxide in OXIDE_ORDER.
    """
    for entry in _load_tracked_bsm_catalogue():
        t = entry["source_transformation"]
        precision = int(t["implementation_precision_decimals"])
        factor = float(t["normalization_factor"])
        # Verify factor is the deterministic inverse of the source subset sum.
        expected_factor = 100.0 / float(t["retained_subset_sum_source"])
        assert abs(factor - expected_factor) < 1e-8, (
            f"{entry['project']}: normalization_factor {factor} != 100/subset_sum "
            f"({expected_factor})"
        )
        stored = entry["oxides_wt_percent"]
        source = t["source_oxides_wt_percent"]
        for oxide in t["retained_oxides"]:
            expected = round(source[oxide] * factor, precision)
            assert stored[oxide] == expected, (
                f"{entry['project']}: {oxide} stored {stored[oxide]}, "
                f"expected round({source[oxide]} * {factor}, {precision}) = "
                f"{expected}"
            )
        # Every oxide NOT in retained_oxides must be zero in the stored vector.
        from make_compositions import OXIDE_ORDER
        for oxide in OXIDE_ORDER:
            if oxide in t["retained_oxides"]:
                continue
            assert stored.get(oxide, 0.0) == 0.0, (
                f"{entry['project']}: non-retained oxide {oxide} is not zero "
                f"in stored vector"
            )


def test_stored_oxides_sum_to_100_within_deterministic_rounding_bound() -> None:
    """Storing N retained oxides at precision p introduces per-component
    rounding of at most 0.5 * 10^-p. The worst-case sum error is therefore
    N * 0.5 * 10^-p. This bound is a mathematical consequence of the
    documented rounding, not an invented scientific tolerance."""
    for entry in _load_tracked_bsm_catalogue():
        t = entry["source_transformation"]
        p = int(t["implementation_precision_decimals"])
        n_retained = len(t["retained_oxides"])
        bound = n_retained * 0.5 * (10 ** -p)  # e.g., 6 * 0.5 * 0.01 = 0.03
        total = sum(entry["oxides_wt_percent"].values())
        assert abs(total - 100.0) <= bound, (
            f"{entry['project']}: stored sum {total} deviates from 100 by more "
            f"than the deterministic rounding bound {bound} (N={n_retained}, "
            f"p={p})"
        )
        # After the pipeline's own renormalize_wt_percent, the sum must be
        # exactly 100 at full float precision. Verify this separately.
        renormalized = make_compositions.normalize_wt_percent(entry["oxides_wt_percent"])
        assert math.isclose(sum(renormalized.values()), 100.0, rel_tol=0, abs_tol=1e-9), (
            f"{entry['project']}: pipeline renormalization does not produce sum=100"
        )


def test_source_minor_oxides_are_preserved_in_provenance_even_when_excluded() -> None:
    """Even though excluded oxides are zeroed in oxides_wt_percent, they must
    remain visible in source_transformation.source_oxides_wt_percent."""
    for entry in _load_tracked_bsm_catalogue():
        t = entry["source_transformation"]
        for oxide in t["excluded_oxides"]:
            assert oxide in t["source_oxides_wt_percent"], (
                f"{entry['project']}: excluded oxide {oxide} missing from "
                "source_oxides_wt_percent"
            )
            assert t["source_oxides_wt_percent"][oxide] > 0.0 \
                or oxide == "P2O5"  # P2O5 may be trace or zero in Hauri
        # Retained and excluded must partition the source oxides.
        source_keys = set(t["source_oxides_wt_percent"].keys())
        retained = set(t["retained_oxides"])
        excluded = set(t["excluded_oxides"])
        assert retained.isdisjoint(excluded)
        assert source_keys == retained | excluded, (
            f"{entry['project']}: source_oxides {source_keys} do not equal "
            f"retained {retained} + excluded {excluded}"
        )


def test_mg_number_recomputed_matches_stored_and_published(tmp_path: Path) -> None:
    """Recomputed Mg# in the generated JSON must be consistent with the
    stored FeO/MgO values, and within reasonable proximity to the published
    Mg# (bounded by rounding of the retained CFMAS+Ti oxides and any
    Fe2O3/FeO reporting differences in the source)."""
    for entry in _load_tracked_bsm_catalogue():
        model = _lunar_composition_from_entry(entry)
        outdir = tmp_path / entry["project"]
        outdir.mkdir()
        make_compositions.write_composition(model, outdir=outdir, database="hp633")
        data = json.loads((outdir / f"{entry['project']}.json").read_text())
        recomputed = data["mg_number_recomputed_mol_percent"]
        # Independently recompute from the stored oxides.
        stored = data["composition_normalized"]
        mg_mol = stored["MgO"] / 40.30
        fe_mol = stored["FeO"] / 71.85
        expected = round(100.0 * mg_mol / (mg_mol + fe_mol), 2)
        assert recomputed == expected

        # Compare to published Mg#; allow up to 2 mol% offset, which is
        # dominated by the FeO 2-decimal rounding at these oxide levels and
        # by any Fe redox choices in the source publication. This is not an
        # invented tolerance: 0.01 wt% rounding in a 9-10 wt% FeO shifts
        # Mg# by ~0.05 mol%; larger allowance covers cases where the source
        # reports Mg# under a slightly different Fe convention.
        published = entry["source_transformation"]["published_mg_number_mol_percent"]
        assert abs(recomputed - float(published)) <= 2.0, (
            f"{entry['project']}: recomputed Mg# {recomputed} vs published "
            f"{published}"
        )


def test_all_bsms_use_identical_thermodynamic_settings() -> None:
    """All three approved BSMs must use the same hp633 solid-only settings
    so that differences in the resulting EOS tables can be attributed to
    input composition rather than to different numerical or thermodynamic
    settings."""
    databases = set()
    perplex_options = set()
    for entry in _load_tracked_bsm_catalogue():
        databases.add(entry["database"])
        po = entry["perplex_options"]
        # Serialize deterministically for set membership.
        perplex_options.add(json.dumps(po, sort_keys=True))
    assert databases == {"hp633"}
    assert len(perplex_options) == 1


def test_no_liquid_model_or_disallowed_composition_in_catalogue() -> None:
    """The catalogue must not silently include a liquid model, a rejected
    model (moon_t82_highFe), a surface proxy, or any composition outside
    the approved reference set."""
    approved = {"moon_h15_lowFe", "moon_w05_preferred_bsm", "moon_w05_alt5_feRich"}
    for entry in _load_tracked_bsm_catalogue():
        assert entry["project"] in approved, (
            f"Unexpected project in catalogue: {entry['project']}"
        )
        assert entry["scientific_status"] == "literature_based"
        assert entry["composition_class"] in (
            "published_bsm_reference", "published_bsm_alternative"
        )
        # No liquid model activated yet.
        assert "liquid_model" not in entry
        assert "melt_model" not in entry
        assert "liquid_solution_models" not in entry


def test_two_warren_models_share_same_paper_but_have_different_study_roles() -> None:
    """Contract: the two Warren entries share the same DOI and must NOT
    both be labelled `primary_reference`."""
    warren_entries = [
        e for e in _load_tracked_bsm_catalogue()
        if e["source_transformation"]["doi"] == "10.1111/j.1945-5100.2005.tb00395.x"
    ]
    assert len(warren_entries) == 2
    roles = sorted(e["study_role"] for e in warren_entries)
    assert roles == ["primary_reference", "within_framework_sensitivity"]


def test_render_stx24_build_input_splits_feo_into_fe_and_o(tmp_path: Path) -> None:
    """Ti-free Warren (2005) Preferred through the default stx24 template gives the
    bulk line recorded for moon_w05_preferred_stx24_unified in August 2026
    (lunar-bsm-interior-models compositions/bsm/war05_preferred/perplex_input.txt)."""
    composition_file = tmp_path / "composition.json"
    composition_file.write_text(
        json.dumps(
            {
                "composition_normalized": {
                    "SiO2": 47.285113,
                    "Al2O3": 3.907033,
                    "Cr2O3": 0.0,
                    "FeO": 9.336806,
                    "MgO": 36.375476,
                    "CaO": 3.095572,
                    "Na2O": 0.0,
                }
            }
        )
        + "\n"
    )
    model = run_perplex.ModelConfig(
        project=PROJECT,
        composition_file=composition_file,
        build_input_file=run_perplex.default_build_template_for_database("stx24"),
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        database="stx24",
    )

    rendered = run_perplex.render_build_input(tmp_path / "fake_perplex", model)

    assert "stx24ver.dat" in rendered and "stx24_solution_model.dat" in rendered
    assert "0.00000000 36.37547600 3.90703300 47.28511300 3.09557200 7.25749810 2.07930790 0.00000000" in rendered
    assert run_perplex.active_component_oxides("stx24") == {"Na2O", "MgO", "Al2O3", "SiO2", "CaO", "FeO", "Cr2O3"}
    perplex_dir = tmp_path / "perplex"
    (perplex_dir / "datafiles").mkdir(parents=True)
    (perplex_dir / "datafiles" / "stx24ver.dat").write_text(
        "begin_components\nNa2O 61.979\nMgO 40.304\nAl2O3 101.961\nSiO2 60.084\nCaO 56.077\n"
        "Fe 55.842\nO 15.999\nCr2O3 151.990\nend_components\n"
    )
    feo = {row["oxide"]: row for row in run_perplex.default_component_status(perplex_dir, "stx24")}["FeO"]
    assert feo["component"] == "Fe + O" and feo["declared_in_database"] and feo["passed_by_build"]
