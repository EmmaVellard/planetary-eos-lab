from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from planetary_eos_lab.core import config_io, model_schema, pipeline_runner, validation_summary


def example_model() -> dict:
    return {
        "project": "moon_test_surface_proxy",
        "description": "Test surface proxy",
        "planetprofile_filename": "Moon_Test_PerpleX.tab",
        "scientific_status": "surface_proxy_smoke_test",
        "model_scope": "surface_terrane_proxy",
        "planetprofile_readiness": "mechanically_exportable_not_scientifically_final",
        "composition_interpretation": "Test surface proxy, not a final mantle EOS.",
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


def test_config_load_save_and_replace_model(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "models.json"
    config = {"perplex_dir": "/tmp/perplex", "models": [example_model()]}

    saved = config_io.save_config_json(config_path, config)
    loaded = config_io.load_config_json(saved)
    updated = config_io.update_perplex_dir(loaded, "/new/perplex")
    replacement = dict(example_model(), description="Updated")
    replaced = config_io.replace_model_entry(updated, "moon_test_surface_proxy", replacement)
    deleted = config_io.delete_model_entry(replaced, "moon_test_surface_proxy")

    assert saved == config_path
    assert loaded["perplex_dir"] == "/tmp/perplex"
    assert updated["perplex_dir"] == "/new/perplex"
    assert replaced["models"][0]["description"] == "Updated"
    assert deleted["models"] == []


def test_delete_model_entries_removes_multiple_projects() -> None:
    first = example_model()
    second = dict(example_model(), project="second_model")
    third = dict(example_model(), project="third_model")
    config = {"perplex_dir": "/tmp/perplex", "models": [first, second, third]}

    updated = config_io.delete_model_entries(config, ["moon_test_surface_proxy", "third_model"])

    assert [model["project"] for model in updated["models"]] == ["second_model"]
    assert [model["project"] for model in config["models"]] == [
        "moon_test_surface_proxy",
        "second_model",
        "third_model",
    ]


def test_model_validation_normalization_and_omitted_oxides() -> None:
    model = example_model()

    validation = model_schema.validate_model_entry(model)
    normalized = model_schema.normalized_model_composition(model)
    omitted = model_schema.omitted_oxides_for_model(model)
    guardrail = model_schema.scientific_guardrail_text(model)

    assert validation.ok
    assert math.isclose(normalized["SiO2"], 45.44544545, rel_tol=0, abs_tol=1e-8)
    assert omitted[0]["oxide"] == "TiO2"
    assert "Use as final Moon mantle EOS: no" in guardrail


def test_new_model_template_and_plot_rows() -> None:
    model = model_schema.new_model_template("custom_proxy")
    model["oxides_wt_percent"]["SiO2"] = 50.0
    model["oxides_wt_percent"]["MgO"] = 50.0

    validation = model_schema.validate_model_entry(model)
    rows = model_schema.composition_plot_rows(model)

    assert validation.ok
    assert model["project"] == "custom_proxy"
    assert model["planetprofile_readiness"] == "mechanically_exportable_not_scientifically_final"
    assert rows[0] == {
        "oxide": "SiO2",
        "raw_wt_percent": 50.0,
        "normalized_wt_percent": 50.0,
    }


def test_model_validation_catches_bad_fields() -> None:
    bad_model = {
        "project": "",
        "oxides_wt_percent": {
            "SiO2": "not numeric",
            "UnexpectedOxide": 1.0,
        },
    }

    validation = model_schema.validate_model_entry(bad_model)

    assert not validation.ok
    assert "Missing project name." in validation.errors
    assert any("Unknown oxide" in error for error in validation.errors)
    assert "Non-numeric value for SiO2." in validation.errors


def test_output_path_discovery_and_status(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "models.json"
    model = example_model()
    paths = validation_summary.model_output_paths(model, config_path)
    paths.validation_report.parent.mkdir(parents=True)
    paths.validation_report.write_text("STATUS: PASS\n", encoding="utf-8")

    plots = validation_summary.comparison_plot_paths(config_path)
    manifest = validation_summary.export_manifest_path(config_path)

    assert paths.output_dir == tmp_path / "outputs" / "moon_test_surface_proxy"
    assert paths.raw_werami_table.name == "moon_test_surface_proxy_raw_werami.tab"
    assert validation_summary.validation_status(validation_summary.read_text_if_exists(paths.validation_report)) == "pass"
    assert plots["composition_oxides"] == tmp_path / "outputs" / "comparisons" / "composition_oxides.svg"
    assert manifest == tmp_path / "outputs" / "planetprofile_export" / "planetprofile_export_manifest.json"


def test_pipeline_command_builders() -> None:
    config_path = "configs/models.json"

    generate = pipeline_runner.generate_compositions_command(config_path, "model_a")
    full = pipeline_runner.full_pipeline_command(
        config_path,
        project="model_a",
        export_planetprofile=True,
        export_dir="exports",
    )
    export = pipeline_runner.export_planetprofile_command(config_path, export_dir="exports")

    assert generate.command[:2] == [sys.executable, str(config_io.REPO_ROOT / "make_compositions.py")]
    assert "--project" in full.command
    assert "--export-planetprofile" in full.command
    assert "exports" in full.command
    assert str(config_io.REPO_ROOT / "export_planetprofile.py") in export.command


def test_read_export_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "planetprofile_export_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "tables": [
                    {
                        "project": "demo",
                        "exported_filename": "Demo.tab",
                        "scientific_status": "surface_proxy_smoke_test",
                        "planetprofile_readiness": "mechanically_exportable_not_scientifically_final",
                        "omitted_oxides": [{"oxide": "TiO2"}],
                        "database_file": "/tmp/perplex/datafiles/stx21ver.dat",
                        "excluded_phases": ["qtz"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    data = validation_summary.read_export_manifest(manifest)
    rows = validation_summary.export_manifest_table_rows(data or {})

    assert data is not None
    assert data["tables"][0]["project"] == "demo"
    assert rows[0]["exported filename"] == "Demo.tab"
    assert rows[0]["omitted oxides"] == "TiO2"
    assert rows[0]["database"] == "stx21ver.dat"
