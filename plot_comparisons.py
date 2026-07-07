from __future__ import annotations

import argparse
import html
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import run_perplex
from validate_tab import column_indices, read_tab


BASE_DIR = Path(__file__).resolve().parent
COLORS = ("#1f6f8b", "#b85c38", "#4d7c3f", "#7a4d8f")
OXIDE_ORDER = ("SiO2", "TiO2", "Al2O3", "FeO", "MgO", "CaO", "Na2O", "K2O", "P2O5")

PROPERTY_PLOTS = (
    ("rho_kgm3", "Density", "kg/m3", 1.0),
    ("vp_kms", "P-wave speed", "km/s", 1.0),
    ("vs_kms", "S-wave speed", "km/s", 1.0),
    ("alpha_pk", "Thermal expansivity", "10^-5 / K", 1.0e5),
    ("ks_bar", "Bulk modulus", "GPa", 1.0e-4),
    ("gs_bar", "Shear modulus", "GPa", 1.0e-4),
)


@dataclass(frozen=True)
class PlotModel:
    project: str
    label: str
    composition_file: Path
    tab_file: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot composition and PlanetProfile table comparisons."
    )
    parser.add_argument("--config", default=str(run_perplex.DEFAULT_CONFIG), help="Path to configs/models.json.")
    parser.add_argument("--project", action="append", help="Only plot the selected project. Can be repeated.")
    parser.add_argument(
        "--output-dir",
        help="Directory for comparison SVGs. Defaults to outputs/comparisons next to the config.",
    )
    return parser.parse_args(argv)


def project_label(project: str) -> str:
    labels = {
        "moon_far_highlands_surface_proxy": "Far side / highlands surface proxy",
        "moon_near_maria_surface_proxy": "Near side / maria surface proxy",
    }
    return labels.get(project, project.replace("_", " "))


def selected_plot_models(config: run_perplex.PipelineConfig, projects: list[str] | None) -> list[PlotModel]:
    selected = []
    wanted = set(projects or [])
    for model in config.models:
        if wanted and model.project not in wanted:
            continue
        selected.append(
            PlotModel(
                project=model.project,
                label=project_label(model.project),
                composition_file=model.composition_file,
                tab_file=model.output_dir / f"{model.project}_planetprofile.tab",
            )
        )
    if wanted and len(selected) != len(wanted):
        found = {model.project for model in selected}
        missing = ", ".join(sorted(wanted - found))
        raise FileNotFoundError(f"Project(s) not found in config: {missing}")
    return selected


def load_normalized_composition(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text())
    composition = data.get("composition_normalized")
    if not isinstance(composition, dict):
        raise ValueError(f"Missing composition_normalized in {path}")

    normalized: dict[str, float] = {}
    for component, value in composition.items():
        try:
            normalized[str(component)] = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Composition value for {component} is not numeric in {path}")
    return normalized


def is_component_composition(path: Path) -> bool:
    """Check if composition file uses components instead of oxides."""
    data = json.loads(path.read_text())
    basis = data.get("composition_basis", "").lower()
    return "component" in basis or "element" in basis


def composition_keys(compositions: list[dict[str, float]], use_oxide_order: bool = True) -> list[str]:
    """Get ordered list of composition keys.

    Args:
        compositions: List of composition dictionaries
        use_oxide_order: If True, prioritize OXIDE_ORDER for ordering (for oxide compositions).
                        If False, use order from composition files (for component compositions).

    Returns:
        Ordered list of composition keys with nonzero values
    """
    configured_order = [component for composition in compositions for component in composition]
    nonzero = {
        component
        for composition in compositions
        for component, value in composition.items()
        if math.isfinite(value) and abs(value) > 1.0e-12
    }
    ordered: list[str] = []

    if use_oxide_order:
        # For oxide compositions, use OXIDE_ORDER for consistent ordering
        for component in OXIDE_ORDER:
            if component in nonzero:
                ordered.append(component)

    # Add any remaining components in order of appearance
    for component in configured_order:
        if component in nonzero and component not in ordered:
            ordered.append(component)
    return ordered


def finite(value: float) -> bool:
    return math.isfinite(value)


def pressure_profile(tab_file: Path, property_name: str, value_scale: float) -> list[tuple[float, float]]:
    tab = read_tab(tab_file)
    indices = column_indices(tab.headers)
    if "p_bar" not in indices or property_name not in indices:
        raise ValueError(f"Missing pressure or {property_name} column in {tab_file}")

    grouped: dict[float, list[float]] = defaultdict(list)
    p_index = indices["p_bar"]
    value_index = indices[property_name]
    for row in tab.rows:
        pressure = row[p_index]
        value = row[value_index]
        if finite(pressure) and finite(value):
            grouped[pressure].append(value * value_scale)

    return [
        (pressure_bar * 1.0e-4, statistics.fmean(values))
        for pressure_bar, values in sorted(grouped.items())
        if values
    ]


def svg_text(x: float, y: float, text: str, size: int = 13, anchor: str = "start", weight: str = "normal") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">'
        f"{html.escape(text)}</text>"
    )


def nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exponent = math.floor(math.log10(value))
    base = 10**exponent
    return math.ceil(value / base) * base


def axis_range(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        padding = abs(low) * 0.05 or 1.0
        return low - padding, high + padding
    padding = (high - low) * 0.08
    return low - padding, high + padding


def composition_plot_svg(models: list[PlotModel]) -> str:
    compositions = [load_normalized_composition(model.composition_file) for model in models]

    # Check if any models use component composition
    is_component = any(is_component_composition(model.composition_file) for model in models)
    use_oxide_order = not is_component

    keys = composition_keys(compositions, use_oxide_order=use_oxide_order)
    if not keys:
        raise ValueError("Selected composition files do not contain nonzero normalized composition values.")

    composition_type = "component" if is_component else "oxide"
    width, height = 1120, 600
    left, top, plot_width, plot_height = 82, 104, 938, 330
    bottom = top + plot_height
    max_value = nice_max(max(max(composition.get(key, 0.0) for key in keys) for composition in compositions))
    group_width = plot_width / len(keys)
    bar_width = min(30.0, group_width / (len(models) + 1.4))

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        svg_text(width / 2, 36, f"Normalized {composition_type} composition", 22, "middle", "bold"),
        svg_text(width / 2, 60, f"Only nonzero {composition_type}s present in the selected composition records are shown", 13, "middle"),
    ]

    for tick in range(6):
        value = max_value * tick / 5
        y = bottom - (value / max_value) * plot_height
        svg.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e6e6e6"/>')
        svg.append(svg_text(left - 10, y + 4, f"{value:.0f}", 12, "end"))

    svg.append(f'<line x1="{left}" y1="{bottom}" x2="{left + plot_width}" y2="{bottom}" stroke="#333"/>')
    svg.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#333"/>')
    svg.append(svg_text(left - 54, top + plot_height / 2, "wt%", 13, "middle"))

    for key_index, key in enumerate(keys):
        group_x = left + key_index * group_width
        center = group_x + group_width / 2
        svg.append(svg_text(center, bottom + 24, key, 12, "middle"))
        for model_index, composition in enumerate(compositions):
            value = composition.get(key, 0.0)
            bar_height = (value / max_value) * plot_height
            x = center - (len(models) * bar_width) / 2 + model_index * bar_width
            y = bottom - bar_height
            color = COLORS[model_index % len(COLORS)]
            svg.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width - 2:.1f}" height="{bar_height:.1f}" '
                f'fill="{color}"/>'
            )

    legend_x, legend_y = left, height - 92
    for index, model in enumerate(models):
        y = legend_y + index * 24
        color = COLORS[index % len(COLORS)]
        svg.append(f'<rect x="{legend_x}" y="{y - 13}" width="16" height="16" fill="{color}"/>')
        svg.append(svg_text(legend_x + 24, y, model.label, 13))

    svg.append(svg_text(width / 2, height - 18, "Generated by plot_comparisons.py", 11, "middle"))
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def write_composition_plot(models: list[PlotModel], output_path: Path) -> None:
    output_path.write_text(composition_plot_svg(models))


def line_points(series: list[tuple[float, float]], x_min: float, x_max: float, y_min: float, y_max: float, bounds: tuple[float, float, float, float]) -> str:
    x0, y0, width, height = bounds
    points: list[str] = []
    for x_value, y_value in series:
        x = x0 + (x_value - x_min) / (x_max - x_min) * width
        y = y0 + height - (y_value - y_min) / (y_max - y_min) * height
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def property_plot_svg(models: list[PlotModel]) -> str:
    width, height = 1240, 980
    panel_width, panel_height = 520, 215
    margin_x, margin_y = 85, 106
    gap_x, gap_y = 90, 58

    profiles: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for model in models:
        if not model.tab_file.exists():
            raise FileNotFoundError(f"Missing PlanetProfile table for plotting: {model.tab_file}")
        for property_name, _, _, scale in PROPERTY_PLOTS:
            profiles[(model.project, property_name)] = pressure_profile(model.tab_file, property_name, scale)

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        svg_text(width / 2, 34, "Property comparison", 22, "middle", "bold"),
        svg_text(width / 2, 56, "Each curve is the mean value at pressure over the sampled temperature grid", 13, "middle"),
    ]

    for plot_index, (property_name, title, unit, _) in enumerate(PROPERTY_PLOTS):
        row = plot_index // 2
        column = plot_index % 2
        x0 = margin_x + column * (panel_width + gap_x)
        y0 = margin_y + row * (panel_height + gap_y)
        bounds = (x0, y0, panel_width, panel_height)

        all_points = [
            point
            for model in models
            for point in profiles[(model.project, property_name)]
        ]
        x_values = [point[0] for point in all_points]
        y_values = [point[1] for point in all_points]
        x_min, x_max = axis_range(x_values)
        x_min = max(0.0, x_min)
        y_min, y_max = axis_range(y_values)

        svg.append(svg_text(x0 + panel_width / 2, y0 - 16, f"{title} ({unit})", 15, "middle", "bold"))
        svg.append(f'<rect x="{x0}" y="{y0}" width="{panel_width}" height="{panel_height}" fill="#fafafa" stroke="#d0d0d0"/>')

        for tick in range(5):
            x_value = x_min + (x_max - x_min) * tick / 4
            x = x0 + panel_width * tick / 4
            svg.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0 + panel_height}" stroke="#ececec"/>')
            svg.append(svg_text(x, y0 + panel_height + 18, f"{x_value:.1f}", 11, "middle"))

            y_value = y_min + (y_max - y_min) * tick / 4
            y = y0 + panel_height - panel_height * tick / 4
            svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + panel_width}" y2="{y:.1f}" stroke="#ececec"/>')
            svg.append(svg_text(x0 - 8, y + 4, f"{y_value:.2g}", 11, "end"))

        svg.append(svg_text(x0 + panel_width / 2, y0 + panel_height + 38, "Pressure (GPa)", 12, "middle"))
        for model_index, model in enumerate(models):
            series = profiles[(model.project, property_name)]
            if len(series) < 2:
                continue
            color = COLORS[model_index % len(COLORS)]
            points = line_points(series, x_min, x_max, y_min, y_max, bounds)
            svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.4"/>')

    legend_x, legend_y = margin_x, height - 44
    for index, model in enumerate(models):
        x = legend_x + index * 290
        color = COLORS[index % len(COLORS)]
        svg.append(f'<rect x="{x}" y="{legend_y - 13}" width="16" height="16" fill="{color}"/>')
        svg.append(svg_text(x + 24, legend_y, model.label, 13))

    svg.append(svg_text(width - 28, height - 18, "Generated by plot_comparisons.py", 11, "end"))
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def write_property_plot(models: list[PlotModel], output_path: Path) -> None:
    output_path.write_text(property_plot_svg(models))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = run_perplex.resolve_path(args.config, BASE_DIR)
    config = run_perplex.load_config(config_path)
    base_dir = run_perplex.config_base_dir(config_path)
    output_dir = (
        run_perplex.resolve_path(args.output_dir, base_dir)
        if args.output_dir
        else base_dir / "outputs" / "comparisons"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        models = selected_plot_models(config, args.project)
        if not models:
            raise FileNotFoundError("No models selected for plotting.")

        composition_plot = output_dir / "composition_oxides.svg"
        property_plot = output_dir / "planetprofile_properties.svg"
        write_composition_plot(models, composition_plot)
        write_property_plot(models, property_plot)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {composition_plot}")
    print(f"Wrote {property_plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
