from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config_io import config_base_dir, resolve_path


@dataclass(frozen=True)
class OutputPaths:
    output_dir: Path
    work_dir: Path
    raw_werami_table: Path
    planetprofile_table: Path
    native_planetprofile_table: Path
    validation_report: Path
    oxide_omissions: Path
    build_log: Path
    vertex_log: Path
    werami_log: Path


def model_output_paths(model: dict[str, Any], config_path: str | Path) -> OutputPaths:
    base_dir = config_base_dir(config_path)
    project = str(model["project"])
    output_dir = resolve_path(model.get("output_dir", f"outputs/{project}"), base_dir)
    work_dir = resolve_path(model["work_dir"], base_dir) if "work_dir" in model else output_dir / "work"
    return OutputPaths(
        output_dir=output_dir,
        work_dir=work_dir,
        raw_werami_table=output_dir / f"{project}_raw_werami.tab",
        planetprofile_table=output_dir / f"{project}_planetprofile.tab",
        native_planetprofile_table=output_dir / f"{project}_planetprofile_native.tab",
        validation_report=output_dir / "validation_report.txt",
        oxide_omissions=output_dir / "oxide_omissions.txt",
        build_log=output_dir / "build.log",
        vertex_log=output_dir / "vertex.log",
        werami_log=output_dir / "werami.log",
    )


def comparison_plot_paths(config_path: str | Path) -> dict[str, Path]:
    base_dir = config_base_dir(config_path)
    output_dir = base_dir / "outputs" / "comparisons"
    return {
        "composition_oxides": output_dir / "composition_oxides.svg",
        "planetprofile_properties": output_dir / "planetprofile_properties.svg",
    }


def export_manifest_path(config_path: str | Path, export_dir: str | Path | None = None) -> Path:
    base_dir = config_base_dir(config_path)
    directory = resolve_path(export_dir, base_dir) if export_dir else base_dir / "outputs" / "planetprofile_export"
    return directory / "planetprofile_export_manifest.json"


def read_text_if_exists(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.read_text(encoding="utf-8", errors="replace")


def validation_status(report_text: str | None) -> str:
    if not report_text:
        return "missing"
    if "STATUS: PASS" in report_text:
        return "pass"
    if "STATUS: FAIL" in report_text:
        return "fail"
    return "unknown"


def read_export_manifest(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    return json.loads(file_path.read_text(encoding="utf-8"))


def export_manifest_table_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    tables = manifest.get("tables", [])
    if not isinstance(tables, list):
        return rows
    for table in tables:
        if not isinstance(table, dict):
            continue
        omitted = table.get("omitted_oxides", [])
        omitted_names = []
        if isinstance(omitted, list):
            omitted_names = [
                str(item.get("oxide"))
                for item in omitted
                if isinstance(item, dict) and item.get("oxide")
            ]
        rows.append(
            {
                "project": str(table.get("project", "")),
                "exported filename": str(table.get("exported_filename", "")),
                "scientific status": str(table.get("scientific_status", "")),
                "PlanetProfile readiness": str(table.get("planetprofile_readiness", "")),
                "omitted oxides": ", ".join(omitted_names) if omitted_names else "none",
                "database": Path(str(table.get("database_file", ""))).name,
                "excluded phases": ", ".join(str(item) for item in table.get("excluded_phases", [])),
            }
        )
    return rows
