from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_perplex
from planetary_eos_lab.core.config import DATABASES
from planetary_eos_lab.core.database_utils import get_database_components, list_available_databases
from planetary_eos_lab.core.exceptions import ConfigurationError


@pytest.fixture
def clean_registry():
    yield
    for name in [n for n in DATABASES if n.startswith("mydb")]:
        DATABASES.pop(name)
        run_perplex.DEFAULT_BUILD_TEMPLATES.pop(name, None)
        run_perplex.DEFAULT_WERAMI_INPUT_SEQUENCES.pop(name, None)


def write_config(tmp_path: Path, custom: list[dict]) -> Path:
    (tmp_path / "configs").mkdir()
    (tmp_path / "build_inputs").mkdir()
    (tmp_path / "build_inputs" / "mydb.build.in").write_text("${PERPLEX_DIR}/datafiles/mydbver.dat\n${PERPLEX_BULK_VALUES}\n")
    (tmp_path / "compositions").mkdir()
    (tmp_path / "compositions" / "rock.json").write_text(
        json.dumps({"composition_normalized": {"SiO2": 50.0, "MgO": 40.0, "FeO": 10.0}}) + "\n"
    )
    config = {
        "perplex_dir": str(tmp_path / "perplex"),
        "custom_databases": custom,
        "models": [{"project": "rock", "database": "mydb", "composition_file": "compositions/rock.json"}],
    }
    path = tmp_path / "configs" / "models.json"
    path.write_text(json.dumps(config))
    return path


MYDB = {
    "name": "mydb",
    "database_file": "mydbver.dat",
    "solution_model_file": "solution_model.dat",
    "components": [["MgO", "MGO"], ["SiO2", "SIO2"], ["FeO", "FEO"]],
    "build_template": "build_inputs/mydb.build.in",
    "werami_input_sequence": ["2", "38", "1", "0"],
}


def test_database_declared_in_config_is_usable_everywhere(tmp_path: Path, clean_registry) -> None:
    config = run_perplex.load_config(write_config(tmp_path, [MYDB]))

    assert "mydb" in list_available_databases()
    assert get_database_components("mydb") == (("MgO", "MGO"), ("SiO2", "SIO2"), ("FeO", "FEO"))
    model = config.models[0]
    assert model.database == "mydb"
    assert model.build_input_file == tmp_path / "build_inputs" / "mydb.build.in"
    assert model.werami_input_sequence == ("2", "38", "1", "0")
    rendered = run_perplex.render_build_input(tmp_path / "perplex", model)
    assert "mydbver.dat" in rendered
    assert "40.00000000 50.00000000 10.00000000" in rendered


def test_loading_the_same_config_twice_is_safe(tmp_path: Path, clean_registry) -> None:
    path = write_config(tmp_path, [MYDB])
    run_perplex.load_config(path)
    run_perplex.load_config(path)
    assert list_available_databases().count("mydb") == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"name": "stx21"}, "built-in"),
        ({"build_template": "build_inputs/missing.build.in"}, "not found"),
        ({"components": []}, "missing: components"),
        ({"components": [["SiO2"]]}, "pairs"),
    ],
)
def test_invalid_custom_database_is_rejected(tmp_path: Path, clean_registry, change: dict, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        run_perplex.load_config(write_config(tmp_path, [{**MYDB, **change}]))
