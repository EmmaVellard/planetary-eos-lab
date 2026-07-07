from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import run_perplex


DEFAULT_EXPORT_DIR = run_perplex.BASE_DIR / "outputs" / "planetprofile_export"


class ExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportedTable:
    project: str
    model: run_perplex.ModelConfig
    source: Path
    destination: Path


def native_table_path(model: run_perplex.ModelConfig) -> Path:
    return model.output_dir / f"{model.project}_planetprofile_native.tab"


def export_filename(model: run_perplex.ModelConfig) -> str:
    return model.planetprofile_filename or f"{model.project}_planetprofile_native.tab"


def select_models(
    config: run_perplex.PipelineConfig,
    project: str | None = None,
) -> list[run_perplex.ModelConfig]:
    selected = [model for model in config.models if project is None or model.project == project]
    if project and not selected:
        raise ExportError(f"Project not found in config: {project}")
    return selected


def export_tables(
    config: run_perplex.PipelineConfig,
    models: list[run_perplex.ModelConfig],
    export_dir: Path,
) -> list[ExportedTable]:
    export_dir.mkdir(parents=True, exist_ok=True)
    exported: list[ExportedTable] = []

    for model in models:
        source = native_table_path(model)
        if not source.exists():
            raise ExportError(
                f"Missing native PlanetProfile table for {model.project}: {source}. "
                "Run run_full_pipeline.py first."
            )

        destination = export_dir / export_filename(model)
        shutil.copy2(source, destination)
        exported.append(ExportedTable(project=model.project, model=model, source=source, destination=destination))

    write_manifest(export_dir, exported, config)
    return exported


def read_composition_metadata(model: run_perplex.ModelConfig) -> dict:
    if not model.composition_file.exists():
        return {}
    try:
        data = json.loads(model.composition_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def metadata_value(model: run_perplex.ModelConfig, composition: dict, key: str, default: str) -> str:
    value = getattr(model, key, None) or composition.get(key) or default
    return str(value)


def omitted_oxide_manifest_records(model: run_perplex.ModelConfig, composition: dict) -> list[dict]:
    records = composition.get("omitted_oxides_from_build") or composition.get("omitted_oxides_from_default_build")
    if isinstance(records, list):
        return [record for record in records if isinstance(record, dict)]
    try:
        return run_perplex.omitted_oxide_records(model.composition_file, database=model.database)
    except (FileNotFoundError, run_perplex.PipelineError, json.JSONDecodeError):
        return []


def table_manifest_record(table: ExportedTable, config: run_perplex.PipelineConfig) -> dict:
    model = table.model
    composition = read_composition_metadata(model)
    build_provenance = run_perplex.build_template_provenance(config.perplex_dir, model)
    return {
        "project": table.project,
        "exported_filename": table.destination.name,
        "filename_for_planetprofile": table.destination.name,
        "source_native_table": str(table.source),
        "export_destination": str(table.destination),
        "composition_file": str(model.composition_file),
        "planetprofile_first_axis": model.planetprofile_first_axis,
        "scientific_status": metadata_value(
            model,
            composition,
            "scientific_status",
            "unknown_scientific_status",
        ),
        "model_scope": metadata_value(model, composition, "model_scope", "unknown_model_scope"),
        "planetprofile_readiness": metadata_value(
            model,
            composition,
            "planetprofile_readiness",
            "not_assessed_for_planetprofile_science",
        ),
        "composition_interpretation": metadata_value(
            model,
            composition,
            "composition_interpretation",
            "No composition interpretation was provided.",
        ),
        "source_note": str(composition.get("source_note", "")),
        "database_name": model.database,
        "active_perplex_components": run_perplex.active_component_records(model.database),
        "omitted_oxides": omitted_oxide_manifest_records(model, composition),
        "build_template_used": str(model.build_input_file),
        "perplex_dir": str(config.perplex_dir),
        "database_file": build_provenance["database_file"],
        "solution_model_file": build_provenance["solution_model_file"],
        "p_t_range": build_provenance["p_t_range"],
        "excluded_phases": build_provenance["excluded_phases"],
        "solution_models": build_provenance["solution_models"],
        "werami_input_sequence": list(model.werami_input_sequence),
        "werami_input_description": run_perplex.WERAMI_INPUT_DESCRIPTION,
        "export_warning": (
            "This table is mechanically exportable for PlanetProfile, but export success "
            "does not imply scientific readiness or a defensible lunar mantle EOS."
        ),
    }


def write_manifest(
    export_dir: Path,
    exported: list[ExportedTable],
    config: run_perplex.PipelineConfig,
) -> Path:
    manifest = {
        "schema_version": 2,
        "description": "PlanetProfile-format Perple_X EOS tables exported by Planetary EOS Lab.",
        "export_warning": (
            "Export success means the files are mechanically available to PlanetProfile. "
            "Export success does not imply scientific readiness: the compositions, "
            "thermodynamic data, solution models, phase exclusions, and P-T grid still "
            "require review before scientific use."
        ),
        "tables": [
            table_manifest_record(table, config)
            for table in exported
        ],
    }
    manifest_path = export_dir / "planetprofile_export_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export generated native Perple_X tables for use in PlanetProfile."
    )
    parser.add_argument("--config", default=str(run_perplex.DEFAULT_CONFIG), help="Path to configs/models.json.")
    parser.add_argument("--project", help="Export only one project from the config.")
    parser.add_argument(
        "--database",
        choices=sorted(run_perplex.DATABASES),
        help="Thermodynamic database profile to use instead of the config value.",
    )
    parser.add_argument(
        "--perplex-dir",
        help="Path to a Perple_X installation, overriding configs/models.json.",
    )
    parser.add_argument(
        "--planetprofile-export-dir",
        default=str(DEFAULT_EXPORT_DIR),
        help="Directory where PlanetProfile-format .tab files will be copied.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = run_perplex.resolve_path(args.config, run_perplex.BASE_DIR)

    try:
        config = run_perplex.load_config(
            config_path,
            database_override=args.database,
            perplex_dir_override=args.perplex_dir,
        )
        base_dir = run_perplex.config_base_dir(config_path)
        export_dir = run_perplex.resolve_path(args.planetprofile_export_dir, base_dir)
        exported = export_tables(config, select_models(config, args.project), export_dir)
    except (FileNotFoundError, PermissionError, ValueError, ExportError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for table in exported:
        print(f"Exported {table.project}: {table.destination}")
    print(f"Wrote {export_dir / 'planetprofile_export_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
