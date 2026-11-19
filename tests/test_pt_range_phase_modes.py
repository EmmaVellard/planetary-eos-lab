from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_perplex

ROOT = Path(__file__).resolve().parents[1]


def write_config(tmp_path: Path, model_extra: dict) -> Path:
    (tmp_path / "configs").mkdir()
    (tmp_path / "compositions").mkdir()
    (tmp_path / "compositions" / "rock.json").write_text(json.dumps({"composition_normalized": {
        "SiO2": 47.285113, "Al2O3": 3.907033, "Cr2O3": 0.0, "FeO": 9.336806,
        "MgO": 36.375476, "CaO": 3.095572, "Na2O": 0.0}}) + "\n")
    path = tmp_path / "configs" / "models.json"
    path.write_text(json.dumps({"perplex_dir": str(tmp_path / "perplex"), "models": [
        {"project": "rock", "database": "stx24", "composition_file": "compositions/rock.json", **model_extra}]}))
    return path


@pytest.mark.parametrize(
    ("database", "expected"),
    [("stx21", "1000 50000\n800 2200\n"), ("stx24", "1000 50000\n300 2200\n"),
     ("hp633", "1000 50000\n800 2200\n"), ("hp636", "1000 50000\n800 2200\n")],
)
def test_default_range_renders_as_the_old_literal_templates(tmp_path: Path, database: str, expected: str) -> None:
    from planetary_eos_lab.core.constants import OXIDE_ORDER

    composition = tmp_path / "rock.json"
    composition.write_text(json.dumps({"composition_normalized": {o: (50.0 if o in ("SiO2", "MgO") else 0.0) for o in OXIDE_ORDER}}))
    model = run_perplex.ModelConfig(
        project="rock", composition_file=composition,
        build_input_file=run_perplex.default_build_template_for_database(database),
        output_dir=tmp_path, work_dir=tmp_path, database=database,
    )
    rendered = run_perplex.render_build_input(tmp_path / "perplex", model)
    assert f"\n{expected}" in rendered
    assert "${" not in rendered


def test_model_pt_range_reaches_build_and_provenance(tmp_path: Path) -> None:
    low_t = {"pressure_bar": {"min": 1000, "max": 13000}, "temperature_k": {"min": 300, "max": 900}}
    config = run_perplex.load_config(write_config(tmp_path, {"pt_range": low_t, "phase_modes": True}))
    model = config.models[0]

    rendered = run_perplex.render_build_input(tmp_path / "perplex", model)
    assert "\n1000 13000\n300 900\n" in rendered
    assert model.phase_modes is True
    assert run_perplex.build_template_provenance(tmp_path / "perplex", model)["p_t_range"]["temperature_k"] == {"min": 300.0, "max": 900.0}


@pytest.mark.parametrize("bad", [{"pressure_bar": {"min": 1000}}, {"pressure_bar": {"min": 5, "max": 1}, "temperature_k": {"min": 1, "max": 2}}])
def test_invalid_pt_range_is_rejected(tmp_path: Path, bad: dict) -> None:
    with pytest.raises(ValueError, match="pt_range"):
        run_perplex.load_config(write_config(tmp_path, {"pt_range": bad}))


def test_phase_mode_pass_copies_the_new_werami_table(tmp_path: Path, monkeypatch) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir(); out.mkdir()
    (work / "rock_1.tab").write_text("properties")
    calls = []

    def fake_run_command(executable, stdin_text, cwd, log_path, label):
        calls.append(stdin_text)
        (cwd / "rock_2.tab").write_text("modes")

    monkeypatch.setattr(run_perplex, "run_command", fake_run_command)
    model = run_perplex.ModelConfig(project="rock", composition_file=tmp_path / "c.json",
                                    build_input_file=tmp_path / "b.in", output_dir=out, work_dir=work)
    destination = run_perplex.run_werami_phase_modes(tmp_path / "perplex", model)

    assert calls == ["rock\n2\n25\nn\nn\n1\n0\n"]
    assert destination == out / "rock_phase_modes.tab"
    assert destination.read_text() == "modes"
