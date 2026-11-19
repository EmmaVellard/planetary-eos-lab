from __future__ import annotations

import pytest

from planetary_eos_lab.core.config_io import remove_custom_database, upsert_custom_database
from planetary_eos_lab.gui.streamlit_app import parse_component_pairs, split_names, template_with_file_placeholders


def test_component_lines_become_pairs() -> None:
    assert parse_component_pairs("SiO2, SIO2\nFeO, Fe\nFeO; O\n\nMgO\n") == [
        ["SiO2", "SIO2"], ["FeO", "Fe"], ["FeO", "O"], ["MgO", "MgO"]]
    with pytest.raises(ValueError, match="Too many"):
        parse_component_pairs("SiO2, SIO2, extra")
    assert split_names("O(HP), Opx(HP),\nGt(HP)") == ["O(HP)", "Opx(HP)", "Gt(HP)"]


def test_custom_database_entries_are_replaced_by_name_and_removed() -> None:
    config = {"models": [], "custom_databases": [{"name": "a", "x": 1}, {"name": "b"}]}
    updated = upsert_custom_database(config, {"name": "a", "x": 2})
    assert updated["custom_databases"] == [{"name": "b"}, {"name": "a", "x": 2}]
    assert config["custom_databases"][0] == {"name": "a", "x": 1}  # input untouched
    assert "custom_databases" not in remove_custom_database(remove_custom_database(updated, "a"), "b")


def test_copied_template_uses_the_form_data_files() -> None:
    text = "${PROJECT}\n${PERPLEX_DIR}/datafiles/hp633ver.dat\n...\ny\n${PERPLEX_DIR}/datafiles/solution_model.dat\nO(HP)\n"
    assert template_with_file_placeholders(text) == (
        "${PROJECT}\n${THERMODYNAMIC_DATABASE_FILE}\n...\ny\n${SOLUTION_MODEL_FILE}\nO(HP)\n")
