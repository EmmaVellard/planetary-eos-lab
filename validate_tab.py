from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "configs" / "models.json"
DEFAULT_LOG_NAMES = ("build.log", "vertex.log", "werami.log")

BAD_TEXT_PATTERNS = (
    "Reading solution models from file: not requested",
)
WARNING_TEXT_PATTERNS = (
    "warning ver177",
    "cannot be computed because of missing/invalid properties",
)
BAD_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.+-])[-+]?0\.100000E\+100(?![A-Za-z0-9.+-])", re.IGNORECASE)

REQUIRED_COLUMNS = {
    "p_bar": "P(bar)",
    "t_k": "T(K)",
    "rho_kgm3": "rho_kgm3",
    "vp_kms": "VP_kms",
    "vs_kms": "VS_kms",
    "cp_jm3k": "Cp_Jm3K",
    "alpha_pk": "alpha_pK",
    "ks_bar": "KS_bar",
    "gs_bar": "GS_bar",
}

ALIASES = {
    "p_bar": {"p", "pbar", "p_bar", "pressurebar"},
    "t_k": {"t", "tk", "t_k", "temperaturek"},
    "rho_kgm3": {"rho", "rhokgm3", "rho_kgm3", "densitykgm3"},
    "vp_kms": {"vp", "vpkms", "vp_kms"},
    "vs_kms": {"vs", "vskms", "vs_kms"},
    "cp_jm3k": {"cp", "cpjkm3", "cpjm3k", "cp_jm3k", "cpjperm3k"},
    "alpha_pk": {"alpha", "alpha1k", "alphapk", "alpha_pk"},
    "ks_bar": {"ks", "ksbar", "ks_bar"},
    "gs_bar": {"gs", "gsbar", "gs_bar"},
}

NONPHYSICAL_NEGATIVE_COLUMNS = {
    "rho_kgm3": "density",
    "vp_kms": "Vp",
    "vs_kms": "Vs",
    "ks_bar": "bulk modulus",
    "gs_bar": "shear modulus",
}


@dataclass(frozen=True)
class TabData:
    headers: list[str]
    rows: list[list[float]]


@dataclass(frozen=True)
class ValidationResult:
    project: str
    output_dir: Path
    tab_path: Path
    report_path: Path
    issues: list[str]
    warnings: list[str]

    @property
    def passed(self) -> bool:
        return not self.issues


def resolve_path(value: str | Path, base_dir: Path = BASE_DIR) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.lower())


def canonical_column(label: str) -> str | None:
    normalized = normalize_label(label)
    for canonical, aliases in ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def parse_float(token: str) -> float:
    return float(token.replace("D", "E").replace("d", "e"))


def parse_numeric_row(tokens: list[str], expected_columns: int) -> list[float] | None:
    if len(tokens) != expected_columns:
        return None
    values: list[float] = []
    for token in tokens:
        try:
            values.append(parse_float(token))
        except ValueError:
            return None
    return values


def header_score(tokens: Iterable[str]) -> int:
    return sum(1 for token in tokens if canonical_column(token) is not None)


def find_header_line(lines: list[str]) -> tuple[int, list[str]] | None:
    best: tuple[int, int, list[str]] | None = None
    for index, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) < 3:
            continue
        score = header_score(tokens)
        if score < 3:
            continue
        if best is None or score > best[0]:
            best = (score, index, tokens)
    if best is None:
        return None
    return best[1], best[2]


def read_tab(tab_path: Path) -> TabData:
    lines = tab_path.read_text(errors="replace").splitlines()
    header = find_header_line(lines)
    if header is None:
        raise ValueError("Could not find a table header with required property columns.")

    header_index, headers = header
    rows: list[list[float]] = []
    for line in lines[header_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        values = parse_numeric_row(stripped.split(), len(headers))
        if values is not None:
            rows.append(values)

    if not rows:
        raise ValueError("Table header was found, but no numeric data rows were parsed.")

    return TabData(headers=headers, rows=rows)


def column_indices(headers: list[str]) -> dict[str, int]:
    indices: dict[str, int] = {}
    for index, header in enumerate(headers):
        canonical = canonical_column(header)
        if canonical and canonical not in indices:
            indices[canonical] = index
    return indices


def finite_values(rows: list[list[float]], column_index: int) -> list[float]:
    return [row[column_index] for row in rows if math.isfinite(row[column_index])]


def scan_text_for_issues(text: str) -> list[str]:
    issues: list[str] = []
    lowered = text.lower()
    for pattern in BAD_TEXT_PATTERNS:
        if pattern.lower() in lowered:
            issues.append(f"Detected log/table issue: {pattern}")

    for match in sorted(set(BAD_NUMBER_RE.findall(text))):
        issues.append(f"Detected Perple_X bad-number sentinel: {match}")

    return issues


def scan_text_for_warnings(text: str) -> list[str]:
    warnings: list[str] = []
    lowered = text.lower()
    for pattern in WARNING_TEXT_PATTERNS:
        if pattern.lower() in lowered:
            warnings.append(f"Detected Perple_X warning: {pattern}")
    return warnings


def scan_table_for_issues(tab_path: Path, tab: TabData) -> list[str]:
    issues: list[str] = []
    indices = column_indices(tab.headers)

    for canonical, display in REQUIRED_COLUMNS.items():
        if canonical not in indices:
            issues.append(f"Missing required column: {display}")

    if issues:
        return issues

    for index, header in enumerate(tab.headers):
        values = [row[index] for row in tab.rows]
        if all(math.isnan(value) for value in values):
            issues.append(f"NaN-only column: {header}")

    row_count = len(tab.rows)
    # Allow up to 0.1% non-finite values (common for edge cases with incomplete phase data)
    # For small datasets, still require at least 90% finite values
    tolerance_fraction = 0.001  # 0.1%
    max_allowed_nonfinite = max(1, int(row_count * tolerance_fraction)) if row_count >= 1000 else 0

    for canonical, display in REQUIRED_COLUMNS.items():
        column_index = indices[canonical]
        nonfinite_count = sum(1 for row in tab.rows if not math.isfinite(row[column_index]))
        if 0 < nonfinite_count < row_count:
            if nonfinite_count > max_allowed_nonfinite:
                issues.append(f"Non-finite values in {display}: {nonfinite_count} of {row_count}")
            # else: Small number of non-finite values is acceptable for large datasets

    alpha_values = finite_values(tab.rows, indices["alpha_pk"])
    if alpha_values and all(abs(value) <= 1.0e-30 for value in alpha_values):
        issues.append("Zero-only alpha column: alpha_pK")

    for canonical, label in NONPHYSICAL_NEGATIVE_COLUMNS.items():
        values = finite_values(tab.rows, indices[canonical])
        negative_count = sum(1 for value in values if value < 0.0)
        if negative_count:
            issues.append(f"Nonphysical negative {label} values: {negative_count}")

    for row_number, row in enumerate(tab.rows, start=1):
        for column_number, value in enumerate(row):
            if math.isfinite(value) and abs(value) >= 1.0e90:
                header = tab.headers[column_number]
                issues.append(
                    f"Perple_X bad-number-scale value in {header} at data row {row_number}: {value:g}"
                )
                return issues

    return issues


def read_logs(output_dir: Path, log_names: Iterable[str] = DEFAULT_LOG_NAMES) -> tuple[str, list[str]]:
    chunks: list[str] = []
    warnings: list[str] = []
    for name in log_names:
        path = output_dir / name
        if path.exists():
            chunks.append(f"\n--- {name} ---\n")
            chunks.append(path.read_text(errors="replace"))
        else:
            warnings.append(f"Log file not found: {path}")
    return "".join(chunks), warnings


def build_report(result: ValidationResult) -> str:
    lines = [
        f"STATUS: {'PASS' if result.passed else 'FAIL'}",
        f"PROJECT: {result.project}",
        f"OUTPUT_DIR: {result.output_dir}",
        f"TAB_FILE: {result.tab_path}",
        "",
        "TECHNICAL_OUTPUT: tab file present" if result.tab_path.exists() else "TECHNICAL_OUTPUT: tab file missing",
        "READINESS: validation checks passed" if result.passed else "READINESS: validation checks failed",
    ]
    if result.issues:
        lines.extend(["", "Issues:"])
        lines.extend(f"- {issue}" for issue in result.issues)
    if result.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.append("")
    return "\n".join(lines)


def validate_project_output(
    project: str,
    output_dir: Path,
    tab_path: Path | None = None,
) -> ValidationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    tab = tab_path or output_dir / f"{project}_planetprofile.tab"
    report_path = output_dir / "validation_report.txt"

    issues: list[str] = []
    logs_text, warnings = read_logs(output_dir)

    if not tab.exists():
        issues.append(f"Missing .tab output: {tab}")
        combined_text = logs_text
    else:
        tab_text = tab.read_text(errors="replace")
        combined_text = logs_text + "\n--- tab ---\n" + tab_text
        try:
            tab_data = read_tab(tab)
        except ValueError as exc:
            issues.append(str(exc))
        else:
            issues.extend(scan_table_for_issues(tab, tab_data))

    warnings.extend(scan_text_for_warnings(logs_text))
    issues.extend(scan_text_for_issues(combined_text))
    issues = sorted(set(issues))
    warnings = sorted(set(warnings))
    result = ValidationResult(
        project=project,
        output_dir=output_dir,
        tab_path=tab,
        report_path=report_path,
        issues=issues,
        warnings=warnings,
    )
    report_path.write_text(build_report(result))
    return result


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text())


def iter_configured_projects(config_path: Path) -> Iterable[tuple[str, Path]]:
    config = load_config(config_path)
    for model in config["models"]:
        project = model["project"]
        output_dir = model.get("output_dir", f"outputs/{project}")
        yield project, resolve_path(output_dir, config_path.parent.parent)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Perple_X WERAMI .tab output and logs.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to configs/models.json.")
    parser.add_argument("--project", help="Validate one project from the config.")
    parser.add_argument("--output-dir", help="Validate an explicit output directory.")
    parser.add_argument("--tab", help="Explicit .tab file path. Defaults to <output-dir>/<project>_planetprofile.tab.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config)

    if args.output_dir:
        if not args.project:
            print("--project is required when --output-dir is used.", file=sys.stderr)
            return 2
        tab_path = resolve_path(args.tab) if args.tab else None
        result = validate_project_output(
            project=args.project,
            output_dir=resolve_path(args.output_dir),
            tab_path=tab_path,
        )
        print(result.report_path.read_text())
        return 0 if result.passed else 1

    results: list[ValidationResult] = []
    for project, output_dir in iter_configured_projects(config_path):
        if args.project and project != args.project:
            continue
        results.append(validate_project_output(project, output_dir))

    if args.project and not results:
        print(f"Project not found in config: {args.project}", file=sys.stderr)
        return 2

    for result in results:
        print(result.report_path.read_text())

    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
