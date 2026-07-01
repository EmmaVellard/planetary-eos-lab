from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config_io import REPO_ROOT


@dataclass(frozen=True)
class PipelineCommand:
    label: str
    command: list[str]
    cwd: Path = REPO_ROOT

    @property
    def display(self) -> str:
        return " ".join(self.command)


@dataclass(frozen=True)
class CommandResult:
    command: PipelineCommand
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def generate_compositions_command(config_path: str | Path, project: str | None = None) -> PipelineCommand:
    command = [sys.executable, str(REPO_ROOT / "make_compositions.py"), "--config", str(config_path)]
    if project:
        command.extend(["--project", project])
    return PipelineCommand(label="Generate compositions", command=command)


def full_pipeline_command(
    config_path: str | Path,
    *,
    project: str | None = None,
    export_planetprofile: bool = False,
    export_dir: str | Path | None = None,
) -> PipelineCommand:
    command = [sys.executable, str(REPO_ROOT / "run_full_pipeline.py"), "--config", str(config_path)]
    if project:
        command.extend(["--project", project])
    if export_planetprofile:
        command.append("--export-planetprofile")
        if export_dir:
            command.extend(["--planetprofile-export-dir", str(export_dir)])
    return PipelineCommand(label="Run full pipeline", command=command)


def export_planetprofile_command(
    config_path: str | Path,
    *,
    project: str | None = None,
    export_dir: str | Path | None = None,
) -> PipelineCommand:
    command = [sys.executable, str(REPO_ROOT / "export_planetprofile.py"), "--config", str(config_path)]
    if project:
        command.extend(["--project", project])
    if export_dir:
        command.extend(["--planetprofile-export-dir", str(export_dir)])
    return PipelineCommand(label="Export PlanetProfile tables", command=command)


def run_command_capture(pipeline_command: PipelineCommand) -> CommandResult:
    result = subprocess.run(
        pipeline_command.command,
        cwd=str(pipeline_command.cwd),
        text=True,
        capture_output=True,
    )
    return CommandResult(
        command=pipeline_command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )

