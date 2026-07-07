"""Phase diagram visualization with Plotly."""
from __future__ import annotations

import colorsys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from planetary_eos_lab.core.phase_parser import (
    AssemblageGrid,
    coordinate_edges,
    get_pt_grid_from_tab,
    parse_assemblage_grid,
    parse_vertex_log,
)
from planetary_eos_lab.core.validation_summary import model_output_paths


PROPERTY_OPTIONS = {
    "Density": {
        "canonical": "rho_kgm3",
        "label": "Density",
        "unit": "kg/m3",
        "colorbar": "rho (kg/m3)",
        "colorscale": "Viridis",
    },
    "P-wave velocity": {
        "canonical": "vp_kms",
        "label": "P-wave velocity",
        "unit": "km/s",
        "colorbar": "Vp (km/s)",
        "colorscale": "Plasma",
    },
    "S-wave velocity": {
        "canonical": "vs_kms",
        "label": "S-wave velocity",
        "unit": "km/s",
        "colorbar": "Vs (km/s)",
        "colorscale": "Cividis",
    },
}
GRID_ONLY_OPTION = "Assemblage preview"
PHASE_MODEL_SELECTOR_KEY = "phase_diagram_project"
PHASE_PROPERTY_SELECTOR_KEY = "phase_diagram_property"
PHASE_PROPERTY_PROJECT_KEY = "phase_diagram_property_project"
DEFAULT_PHASE_PROPERTY = "Density"
MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION = "Major framework"
SIMPLIFIED_ASSEMBLAGE_OPTION = "Simplified major minerals"
DETAILED_ASSEMBLAGE_OPTION = "Full Perple_X detail"
ASSEMBLAGE_DETAIL_OPTIONS = [
    MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION,
    SIMPLIFIED_ASSEMBLAGE_OPTION,
]
PHASE_NAME_HINTS = {
    "SiO2": "silica phase group",
    "Melt(L)": "liquid/melt component group",
    "O": "olivine solution model",
    "O(HP)": "olivine solution model",
    "Opx": "orthopyroxene solution model",
    "Opx(HP)": "orthopyroxene solution model",
    "Cpx": "clinopyroxene solution model",
    "Cpx(HP)": "clinopyroxene solution model",
    "Gt": "garnet solution model",
    "Gt(HP)": "garnet solution model",
    "Sp": "spinel solution model",
    "Sp(HP)": "spinel solution model",
    "Pl": "plagioclase solution model",
    "Pl(I1,HP)": "plagioclase solution model",
    "Ilm": "ilmenite solution model",
    "Ilm(WPH)": "ilmenite solution model",
    "coe": "coesite",
    "coes": "coesite",
    "q": "quartz",
    "qtz": "quartz",
    "ru": "rutile",
    "crst": "cristobalite",
    "trd": "tridymite",
    "ky": "kyanite",
}
PHASE_ABBREVIATION_CAPTIONS = {
    "O": "olivine",
    "Opx": "orthopyroxene",
    "Cpx": "clinopyroxene",
    "Gt": "garnet",
    "Sp": "spinel",
    "Pl": "plagioclase",
    "Ilm": "ilmenite",
    "SiO2": "silica polymorph group",
    "Melt(L)": "melt/liquid group",
    "coe": "coesite",
    "coes": "coesite",
    "q": "quartz",
    "qtz": "quartz",
    "ru": "rutile",
    "crst": "cristobalite",
    "trd": "tridymite",
    "ky": "kyanite",
}
SILICA_POLYMORPHS = {"q", "qtz", "coe", "coes", "crst", "trd"}
MINOR_SIMPLIFIED_PHASES = {"ru"}
LIQUID_COMPONENT_SUFFIX = "L"
MAJOR_FRAMEWORK_PHASES = {
    "O",
    "O(HP)",
    "Opx",
    "Opx(HP)",
    "Cpx",
    "Cpx(HP)",
    "Gt",
    "Gt(HP)",
    "Sp",
    "Sp(HP)",
    "Pl",
    "Pl(I1,HP)",
    "Ilm",
    "Ilm(WPH)",
}
SIMPLIFIED_PHASE_ORDER = {
    "O": 10,
    "O(HP)": 10,
    "Opx": 20,
    "Opx(HP)": 20,
    "Cpx": 30,
    "Cpx(HP)": 30,
    "Gt": 40,
    "Gt(HP)": 40,
    "Sp": 50,
    "Sp(HP)": 50,
    "Pl": 60,
    "Pl(I1,HP)": 60,
    "Ilm": 70,
    "Ilm(WPH)": 70,
    "SiO2": 80,
    "Melt(L)": 90,
}


def assemblage_files(output_dir: Path, project: str) -> tuple[Path, Path]:
    work_dir = output_dir / "work"
    return work_dir / f"{project}.plt", work_dir / f"{project}.blk"


def property_points_from_tab(tab_path: Path, property_choice: str) -> tuple[list[float], list[float], list[float], dict[str, str]]:
    """Read P-T-property points from a PlanetProfile table."""
    from validate_tab import column_indices, read_tab

    property_config = PROPERTY_OPTIONS[property_choice]
    tab = read_tab(tab_path)
    indices = column_indices(tab.headers)
    p_index = indices["p_bar"]
    t_index = indices["t_k"]
    property_index = indices[property_config["canonical"]]

    t_points: list[float] = []
    p_points: list[float] = []
    property_values: list[float] = []
    for row in tab.rows:
        pressure = row[p_index]
        temperature = row[t_index]
        value = row[property_index]
        if abs(pressure) < 1e90 and abs(temperature) < 1e90 and abs(value) < 1e90:
            p_points.append(pressure * 1e-4)
            t_points.append(temperature)
            property_values.append(value)

    return t_points, p_points, property_values, property_config


def property_grid_from_tab(
    tab_path: Path,
    property_choice: str,
) -> tuple[list[float], list[float], list[list[float | None]], int, dict[str, str]]:
    """Read gridded P-T-property values from a PlanetProfile table."""
    from validate_tab import column_indices, read_tab

    property_config = PROPERTY_OPTIONS[property_choice]
    tab = read_tab(tab_path)
    indices = column_indices(tab.headers)
    p_index = indices["p_bar"]
    t_index = indices["t_k"]
    property_index = indices[property_config["canonical"]]

    values_by_point: dict[tuple[float, float], float] = {}
    for row in tab.rows:
        pressure = row[p_index]
        temperature = row[t_index]
        value = row[property_index]
        if abs(pressure) < 1e90 and abs(temperature) < 1e90 and abs(value) < 1e90:
            values_by_point[(temperature, pressure * 1e-4)] = value

    temperatures = sorted({temperature for temperature, _ in values_by_point})
    pressures = sorted({pressure for _, pressure in values_by_point})
    z_values = [
        [values_by_point.get((temperature, pressure)) for temperature in temperatures]
        for pressure in pressures
    ]

    return temperatures, pressures, z_values, len(values_by_point), property_config


def grid_points_from_tab(tab_path: Path) -> tuple[list[float], list[float]]:
    """Read P-T grid points from a PlanetProfile table."""
    from validate_tab import column_indices, read_tab

    tab = read_tab(tab_path)
    indices = column_indices(tab.headers)
    p_index = indices["p_bar"]
    t_index = indices["t_k"]

    t_points: list[float] = []
    p_points: list[float] = []
    for row in tab.rows:
        pressure = row[p_index]
        temperature = row[t_index]
        if abs(pressure) < 1e90 and abs(temperature) < 1e90:
            p_points.append(pressure * 1e-4)
            t_points.append(temperature)

    return t_points, p_points


def phase_display_name(phase: str) -> str:
    hint = PHASE_NAME_HINTS.get(phase)
    return f"{phase} ({hint})" if hint else phase


def assemblage_hover_text(assemblage_id: int, phases: tuple[str, ...], *, label: str = "Assemblage") -> str:
    if not phases:
        return f"{label} {assemblage_id}<br>phase labels unavailable"
    expanded_phases = " + ".join(phase_display_name(phase) for phase in phases)
    return f"{label} {assemblage_id}<br>{expanded_phases}"


def simplified_phase_tuple(phases: tuple[str, ...]) -> tuple[str, ...]:
    simplified: list[str] = []
    for phase in phases:
        if phase in SILICA_POLYMORPHS:
            simplified_phase = "SiO2"
        elif phase.endswith(LIQUID_COMPONENT_SUFFIX) and len(phase) > len(LIQUID_COMPONENT_SUFFIX):
            simplified_phase = "Melt(L)"
        elif phase in MINOR_SIMPLIFIED_PHASES:
            continue
        else:
            simplified_phase = phase

        if simplified_phase not in simplified:
            simplified.append(simplified_phase)

    if not simplified:
        simplified = list(phases)

    return tuple(sorted(simplified, key=lambda phase: (SIMPLIFIED_PHASE_ORDER.get(phase, 999), phase)))


def major_framework_phase_tuple(phases: tuple[str, ...]) -> tuple[str, ...]:
    simplified = simplified_phase_tuple(phases)
    framework = tuple(phase for phase in simplified if phase in MAJOR_FRAMEWORK_PHASES)
    return framework


def display_phase_tuple(phases: tuple[str, ...], assemblage_detail: str) -> tuple[str, ...]:
    if assemblage_detail == MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION:
        return major_framework_phase_tuple(phases)
    if assemblage_detail == SIMPLIFIED_ASSEMBLAGE_OPTION:
        return simplified_phase_tuple(phases)
    return phases


def build_grouped_assemblage_labels(
    assemblage_grid: AssemblageGrid,
    assemblage_detail: str,
) -> tuple[dict[int, tuple[str, ...]], dict[int, int]]:
    """Group raw Perple_X assemblage IDs into broader mineral assemblages."""
    label_to_group_id: dict[tuple[str, ...], int] = {}
    group_labels: dict[int, tuple[str, ...]] = {}
    raw_to_group_id: dict[int, int] = {}

    for raw_id in sorted(assemblage_grid.assemblage_ids):
        raw_label = assemblage_grid.labels.get(raw_id, ())
        display_label = display_phase_tuple(raw_label, assemblage_detail)
        if not display_label:
            continue
        group_id = label_to_group_id.get(display_label)
        if group_id is None:
            group_id = len(label_to_group_id) + 1
            label_to_group_id[display_label] = group_id
            group_labels[group_id] = display_label
        raw_to_group_id[raw_id] = group_id

    return group_labels, raw_to_group_id


def build_simplified_assemblage_labels(
    assemblage_grid: AssemblageGrid,
) -> tuple[dict[int, tuple[str, ...]], dict[int, int]]:
    return build_grouped_assemblage_labels(assemblage_grid, SIMPLIFIED_ASSEMBLAGE_OPTION)


def remap_assemblage_ids(
    original_ids: list[list[int | None]],
    raw_to_group_id: dict[int, int],
) -> list[list[int | None]]:
    return [
        [
            raw_to_group_id.get(assemblage_id) if assemblage_id is not None else None
            for assemblage_id in row
        ]
        for row in original_ids
    ]


def indexed_grid_from_ids(
    ids: list[list[int | None]],
) -> tuple[list[list[int | None]], dict[int, int]]:
    assemblage_ids = sorted({value for row in ids for value in row if value is not None})
    index_by_id = {assemblage_id: index for index, assemblage_id in enumerate(assemblage_ids)}
    indexed_grid = [
        [
            index_by_id.get(assemblage_id) if assemblage_id is not None else None
            for assemblage_id in row
        ]
        for row in ids
    ]
    return indexed_grid, index_by_id


def boundary_edges(
    temperatures_k: list[float],
    pressures: list[float],
    assemblage_ids: list[list[int | None]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Return boundary grid edges where neighboring assemblage IDs differ."""
    if not temperatures_k or not pressures or not assemblage_ids:
        return []

    row_count = min(len(pressures), len(assemblage_ids))
    column_count = min(len(temperatures_k), min(len(row) for row in assemblage_ids))
    if row_count == 0 or column_count == 0:
        return []

    t_edges = coordinate_edges(temperatures_k[:column_count])
    p_edges = coordinate_edges(pressures[:row_count])
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []

    for row in range(row_count):
        for column in range(column_count - 1):
            left = assemblage_ids[row][column]
            right = assemblage_ids[row][column + 1]
            if left is not None and right is not None and left != right:
                x = t_edges[column + 1]
                edges.append(((x, p_edges[row]), (x, p_edges[row + 1])))

    for row in range(row_count - 1):
        for column in range(column_count):
            lower = assemblage_ids[row][column]
            upper = assemblage_ids[row + 1][column]
            if lower is not None and upper is not None and lower != upper:
                y = p_edges[row + 1]
                edges.append(((t_edges[column], y), (t_edges[column + 1], y)))

    return edges


def normalized_edge(
    left: tuple[float, float],
    right: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    return (left, right) if left <= right else (right, left)


def connected_boundary_polylines(
    temperatures_k: list[float],
    pressures: list[float],
    assemblage_ids: list[list[int | None]],
) -> list[list[tuple[float, float]]]:
    """Trace individual grid-edge segments into longer boundary paths."""
    edges = boundary_edges(temperatures_k, pressures, assemblage_ids)
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for left, right in edges:
        adjacency.setdefault(left, []).append(right)
        adjacency.setdefault(right, []).append(left)

    visited: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    polylines: list[list[tuple[float, float]]] = []

    def trace_path(start: tuple[float, float], first: tuple[float, float]) -> list[tuple[float, float]]:
        path = [start, first]
        visited.add(normalized_edge(start, first))
        previous = start
        current = first

        while len(adjacency.get(current, [])) == 2:
            candidates = [point for point in adjacency[current] if point != previous]
            if not candidates:
                break
            next_point = candidates[0]
            edge = normalized_edge(current, next_point)
            if edge in visited:
                break
            visited.add(edge)
            path.append(next_point)
            previous, current = current, next_point

        return path

    endpoints = [point for point, neighbors in adjacency.items() if len(neighbors) != 2]
    for start in endpoints:
        for neighbor in adjacency[start]:
            edge = normalized_edge(start, neighbor)
            if edge not in visited:
                polylines.append(trace_path(start, neighbor))

    for start, neighbors in adjacency.items():
        for neighbor in neighbors:
            edge = normalized_edge(start, neighbor)
            if edge in visited:
                continue
            path = trace_path(start, neighbor)
            if len(path) > 1:
                polylines.append(path)

    return polylines


def chaikin_smooth_polyline(
    polyline: list[tuple[float, float]],
    *,
    iterations: int = 2,
) -> list[tuple[float, float]]:
    """Round grid-corner polylines for display without changing the source grid."""
    smoothed = polyline
    for _ in range(iterations):
        if len(smoothed) < 3:
            break
        next_points = [smoothed[0]]
        for left, right in zip(smoothed, smoothed[1:]):
            q_point = (0.75 * left[0] + 0.25 * right[0], 0.75 * left[1] + 0.25 * right[1])
            r_point = (0.25 * left[0] + 0.75 * right[0], 0.25 * left[1] + 0.75 * right[1])
            next_points.extend([q_point, r_point])
        next_points.append(smoothed[-1])
        smoothed = next_points
    return smoothed


def boundary_polyline_coordinates(polylines: list[list[tuple[float, float]]]) -> tuple[list[float | None], list[float | None], int]:
    x_values: list[float | None] = []
    y_values: list[float | None] = []
    count = 0
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        count += 1
        for x_value, y_value in chaikin_smooth_polyline(polyline):
            x_values.append(x_value)
            y_values.append(y_value)
        x_values.append(None)
        y_values.append(None)
    return x_values, y_values, count


def assemblage_field_label(phases: tuple[str, ...]) -> str:
    if not phases:
        return ""
    cleaned = [phase.replace("(HP)", "").replace("(WPH)", "").replace("(I1,HP)", "") for phase in phases]
    return " + ".join(cleaned)


def phase_abbreviation(phase: str) -> str:
    if phase.endswith(LIQUID_COMPONENT_SUFFIX) and len(phase) > len(LIQUID_COMPONENT_SUFFIX):
        return "Melt(L)"
    return phase.replace("(HP)", "").replace("(WPH)", "").replace("(I1,HP)", "")


def assemblage_caption_text(assemblage_grid: AssemblageGrid, assemblage_detail: str) -> str:
    if assemblage_detail != DETAILED_ASSEMBLAGE_OPTION:
        display_labels, _raw_to_group_id = build_grouped_assemblage_labels(assemblage_grid, assemblage_detail)
    else:
        display_labels = assemblage_grid.labels

    present_abbreviations: list[str] = []
    for phases in display_labels.values():
        for phase in phases:
            abbreviation = phase_abbreviation(phase)
            if abbreviation in PHASE_ABBREVIATION_CAPTIONS and abbreviation not in present_abbreviations:
                present_abbreviations.append(abbreviation)

    if not present_abbreviations:
        return ""

    abbreviation_text = "; ".join(
        f"{abbreviation} = {PHASE_ABBREVIATION_CAPTIONS[abbreviation]}"
        for abbreviation in sorted(
            present_abbreviations,
            key=lambda abbreviation: (SIMPLIFIED_PHASE_ORDER.get(abbreviation, 999), abbreviation),
        )
    )
    return (
        "The '+' sign means that the listed phases are stable together at that P-T condition. "
        f"Abbreviations shown in this diagram: {abbreviation_text}."
    )


def largest_component_label_points(
    display_ids: list[list[int | None]],
    display_labels: dict[int, tuple[str, ...]],
    temperatures_k: list[float],
    pressures_gpa: list[float],
    *,
    max_labels: int = 8,
) -> tuple[list[float], list[float], list[str]]:
    """Place labels at the centers of the largest connected fields."""
    if not display_ids or not temperatures_k or not pressures_gpa:
        return [], [], []

    row_count = min(len(pressures_gpa), len(display_ids))
    column_count = min(len(temperatures_k), min(len(row) for row in display_ids))
    visited: set[tuple[int, int]] = set()
    components: list[tuple[int, list[tuple[int, int]]]] = []

    for row in range(row_count):
        for column in range(column_count):
            assemblage_id = display_ids[row][column]
            if assemblage_id is None or (row, column) in visited:
                continue

            stack = [(row, column)]
            visited.add((row, column))
            cells: list[tuple[int, int]] = []
            while stack:
                current_row, current_column = stack.pop()
                cells.append((current_row, current_column))
                for next_row, next_column in (
                    (current_row - 1, current_column),
                    (current_row + 1, current_column),
                    (current_row, current_column - 1),
                    (current_row, current_column + 1),
                ):
                    if not (0 <= next_row < row_count and 0 <= next_column < column_count):
                        continue
                    if (next_row, next_column) in visited:
                        continue
                    if display_ids[next_row][next_column] != assemblage_id:
                        continue
                    visited.add((next_row, next_column))
                    stack.append((next_row, next_column))
            components.append((assemblage_id, cells))

    minimum_cells = max(30, int(row_count * column_count * 0.05))
    selected = sorted(components, key=lambda item: len(item[1]), reverse=True)[:max_labels]

    x_values: list[float] = []
    y_values: list[float] = []
    text_values: list[str] = []
    for assemblage_id, cells in selected:
        if len(cells) < minimum_cells:
            continue
        phases = display_labels.get(assemblage_id, ())
        label = assemblage_field_label(phases)
        if not label:
            continue
        sorted_rows = sorted(row for row, _ in cells)
        sorted_columns = sorted(column for _, column in cells)
        row_index = sorted_rows[len(sorted_rows) // 2]
        column_index = sorted_columns[len(sorted_columns) // 2]
        x_values.append(temperatures_k[column_index])
        y_values.append(pressures_gpa[row_index])
        text_values.append(label)

    return x_values, y_values, text_values


def hex_from_hls(hue: float, lightness: float, saturation: float) -> str:
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def assemblage_colorscale(color_count: int) -> list[tuple[float, str]]:
    """Build a discrete categorical colorscale for assemblage IDs."""
    if color_count <= 1:
        return [(0.0, "#7aa6c2"), (1.0, "#7aa6c2")]

    colors: list[str] = []
    for index in range(color_count):
        hue = (0.58 + index * 0.61803398875) % 1.0
        lightness = 0.66 if index % 2 == 0 else 0.78
        saturation = 0.45 if index % 3 else 0.58
        colors.append(hex_from_hls(hue, lightness, saturation))

    scale: list[tuple[float, str]] = []
    for index, color in enumerate(colors):
        left = index / color_count
        right = (index + 1) / color_count
        scale.append((left, color))
        scale.append((right, color))
    return scale


def assemblage_hover_grid(
    display_ids: list[list[int | None]],
    display_labels: dict[int, tuple[str, ...]],
    *,
    hover_label: str,
) -> list[list[str]]:
    hover_rows: list[list[str]] = []
    for row in display_ids:
        hover_row: list[str] = []
        for display_id in row:
            if display_id is None:
                hover_row.append("Assemblage: unavailable")
                continue
            phases = display_labels.get(display_id, ())
            hover_text = assemblage_hover_text(
                display_id,
                phases,
                label=hover_label,
            )
            hover_row.append(hover_text)
        hover_rows.append(hover_row)
    return hover_rows


def assemblage_hover_points(
    display_ids: list[list[int | None]],
    display_labels: dict[int, tuple[str, ...]],
    temperatures_k: list[float],
    pressures_gpa: list[float],
    *,
    hover_label: str,
) -> tuple[list[float], list[float], list[str]]:
    t_points: list[float] = []
    p_points: list[float] = []
    hover_text: list[str] = []
    for row_index, row in enumerate(display_ids[: len(pressures_gpa)]):
        for column_index, assemblage_id in enumerate(row[: len(temperatures_k)]):
            if assemblage_id is None:
                continue
            phases = display_labels.get(assemblage_id, ())
            t_points.append(temperatures_k[column_index])
            p_points.append(pressures_gpa[row_index])
            point_hover = assemblage_hover_text(
                assemblage_id,
                phases,
                label=hover_label,
            )
            hover_text.append(point_hover)
    return t_points, p_points, hover_text


def add_assemblage_preview_traces(
    fig: go.Figure,
    assemblage_grid: AssemblageGrid,
    temperatures_k: list[float],
    pressures_bar: list[float],
    *,
    show_heatmap: bool,
    assemblage_detail: str,
) -> tuple[int, int]:
    pressure_count = min(len(pressures_bar), assemblage_grid.pressure_count)
    temperature_count = min(len(temperatures_k), assemblage_grid.temperature_count)
    if pressure_count == 0 or temperature_count == 0:
        return 0, 0

    pressures_gpa = [pressure * 1e-4 for pressure in pressures_bar[:pressure_count]]
    temperatures = temperatures_k[:temperature_count]
    original_ids = [
        row[:temperature_count]
        for row in assemblage_grid.ids[:pressure_count]
    ]
    grouped = assemblage_detail != DETAILED_ASSEMBLAGE_OPTION
    if grouped:
        display_labels, raw_to_group_id = build_grouped_assemblage_labels(assemblage_grid, assemblage_detail)
        display_ids = remap_assemblage_ids(original_ids, raw_to_group_id)
    else:
        display_labels = assemblage_grid.labels
        display_ids = original_ids
    hover_label = {
        MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION: "Major framework",
        SIMPLIFIED_ASSEMBLAGE_OPTION: "Simplified assemblage",
        DETAILED_ASSEMBLAGE_OPTION: "Perple_X assemblage",
    }.get(assemblage_detail, "Assemblage")

    indexed_ids, index_by_id = indexed_grid_from_ids(display_ids)

    if show_heatmap:
        fig.add_trace(
            go.Heatmap(
                x=temperatures,
                y=pressures_gpa,
                z=indexed_ids,
                text=assemblage_hover_grid(
                    display_ids,
                    display_labels,
                    hover_label=hover_label,
                ),
                colorscale=assemblage_colorscale(len(index_by_id)),
                zmin=-0.5,
                zmax=max(len(index_by_id) - 0.5, 0.5),
                showscale=False,
                opacity=0.92,
                name="Assemblage fields",
                hovertemplate="<b>%{text}</b><br>T: %{x:.0f} K<br>P: %{y:.2f} GPa<extra></extra>",
            )
        )

    hover_x, hover_y, hover_text = assemblage_hover_points(
        display_ids,
        display_labels,
        temperatures,
        pressures_gpa,
        hover_label=hover_label,
    )
    if hover_x:
        fig.add_trace(
            go.Scatter(
                x=hover_x,
                y=hover_y,
                mode="markers",
                marker=dict(size=18, color="rgba(0,0,0,0.01)", line=dict(width=0)),
                name="Assemblage labels",
                text=hover_text,
                hovertemplate="<b>%{text}</b><br>T: %{x:.0f} K<br>P: %{y:.2f} GPa<extra></extra>",
                showlegend=False,
            )
        )

    polylines = connected_boundary_polylines(temperatures, pressures_gpa, display_ids)
    _boundary_x, _boundary_y, boundary_count = boundary_polyline_coordinates(polylines)

    label_x, label_y, label_text = largest_component_label_points(
        display_ids,
        display_labels,
        temperatures,
        pressures_gpa,
    )
    if label_x:
        fig.add_trace(
            go.Scatter(
                x=label_x,
                y=label_y,
                mode="text",
                text=label_text,
                textfont=dict(size=13, color="rgba(12,16,20,0.94)", family="Arial Black, Arial, sans-serif"),
                textposition="middle center",
                hoverinfo="skip",
                showlegend=False,
                name="Field labels",
            )
        )

    return len(index_by_id), boundary_count


def plot_phase_diagram_interactive(
    model: dict[str, Any],
    output_dir: Path,
    property_choice: str = "Density",
    assemblage_detail: str = MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION,
):
    """Create interactive P-T phase diagram with Plotly.

    Note: Phase diagrams require structured phase data from VERTEX.
    This implementation shows the P-T grid coverage and property contours
    as a fallback when phase info is unavailable.

    Args:
        model: Model configuration
        output_dir: Output directory path
    """
    project = model.get("project", "unknown")

    # Try to parse VERTEX log first
    vertex_log = output_dir / "vertex.log"
    phase_fields = []

    if vertex_log.exists():
        phase_fields = parse_vertex_log(vertex_log)

    # Fallback: show P-T coverage with property contours
    tab_path = output_dir / f"{project}_planetprofile.tab"

    if not tab_path.exists():
        st.warning("⚠️ No output file found. Run Perple_X first to generate phase diagram.")
        return

    # Get P-T grid
    pressures_bar, temperatures_k = get_pt_grid_from_tab(tab_path)

    if not pressures_bar or not temperatures_k:
        st.error("❌ Could not extract P-T grid from output file")
        return

    fig = go.Figure()
    plt_path, blk_path = assemblage_files(output_dir, project)
    assemblage_grid = parse_assemblage_grid(plt_path, blk_path)

    point_count = 0
    assemblage_count = 0
    boundary_count = 0
    try:
        if property_choice in PROPERTY_OPTIONS:
            temperatures, pressures, z_values, point_count, property_config = property_grid_from_tab(
                tab_path,
                property_choice,
            )
            if not point_count:
                st.warning(f"No finite values found for {property_choice}; showing P-T grid only.")
                t_points, p_points = grid_points_from_tab(tab_path)
                property_choice = GRID_ONLY_OPTION
            else:
                fig.add_trace(
                    go.Heatmap(
                        x=temperatures,
                        y=pressures,
                        z=z_values,
                        colorscale=property_config["colorscale"],
                        colorbar=dict(title=property_config["colorbar"]),
                        name=property_config["label"],
                        hovertemplate="<b>P-T cell</b><br>"
                        + "T: %{x:.0f} K<br>"
                        + "P: %{y:.2f} GPa<br>"
                        + f"{property_config['label']}: "
                        + f"%{{z:.3g}} {property_config['unit']}<extra></extra>",
                    )
                )
        else:
            t_points, p_points = grid_points_from_tab(tab_path)
            point_count = len(p_points)

        if property_choice == GRID_ONLY_OPTION:
            if assemblage_grid:
                assemblage_count, boundary_count = add_assemblage_preview_traces(
                    fig,
                    assemblage_grid,
                    temperatures_k,
                    pressures_bar,
                    show_heatmap=True,
                    assemblage_detail=assemblage_detail,
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=t_points,
                        y=p_points,
                        mode="markers",
                        marker=dict(size=6, color="blue", opacity=0.6),
                        name="P-T Grid",
                        hovertemplate="T: %{x:.0f} K<br>P: %{y:.2f} GPa<extra></extra>",
                    )
                )

        if assemblage_grid and property_choice != GRID_ONLY_OPTION:
            assemblage_count, boundary_count = add_assemblage_preview_traces(
                fig,
                assemblage_grid,
                temperatures_k,
                pressures_bar,
                show_heatmap=False,
                assemblage_detail=assemblage_detail,
            )

    except Exception as e:
        st.error(f"❌ Error reading output file: {e}")
        return

    plot_title = (
        f"{assemblage_detail} Boundary Preview: {project}"
        if property_choice == GRID_ONLY_OPTION
        else f"{property_choice} with {assemblage_detail} Boundaries: {project}"
    )
    fig.update_layout(
        title=plot_title,
        xaxis_title="Temperature (K)",
        yaxis_title="Pressure (GPa)",
        hovermode="closest",
        height=660,
        margin=dict(l=64, r=28, t=72, b=58),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
        ),
        hoverlabel=dict(bgcolor="white", bordercolor="rgba(20,24,28,0.18)", font_size=12),
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(20,24,28,0.08)",
        zeroline=False,
        ticks="outside",
        showline=True,
        mirror=True,
        linewidth=2,
        linecolor="rgba(12,16,20,0.95)",
    )
    fig.update_yaxes(
        autorange="reversed",
        showgrid=True,
        gridcolor="rgba(20,24,28,0.08)",
        zeroline=False,
        ticks="outside",
        showline=True,
        mirror=True,
        linewidth=2,
        linecolor="rgba(12,16,20,0.95)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary info
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("T range", f"{min(temperatures_k):.0f}–{max(temperatures_k):.0f} K")
    col2.metric("P range", f"{min(pressures_bar)*1e-4:.2f}–{max(pressures_bar)*1e-4:.2f} GPa")
    col3.metric("P-T cells", point_count)
    col4.metric("Fields shown", assemblage_count if assemblage_grid else "not found")
    col5.metric("Boundary paths", boundary_count if assemblage_grid else "not found")

    if assemblage_grid:
        if assemblage_detail == MAJOR_FRAMEWORK_ASSEMBLAGE_OPTION:
            st.caption(
                "Major framework boundaries group fields by the main solution-model phases "
                "(olivine, pyroxene, garnet, spinel, plagioclase, and ilmenite). "
                "Curved boundaries are a smoothed rendering of the VERTEX grid preview. "
                "Switch to a more detailed assemblage option to inspect silica, melt, or minor-phase changes."
            )
        elif assemblage_detail == SIMPLIFIED_ASSEMBLAGE_OPTION:
            st.caption(
                "Simplified boundaries group silica polymorphs as SiO2 and suppress rutile-only differences "
                "when other phases are present. Liquid component labels are grouped as Melt(L)."
            )
        else:
            st.caption(
                "Detailed assemblage boundaries are a fast preview parsed from VERTEX .plt/.blk files. "
                "Hover over a colored field to see the stable phase assemblage. "
                "Use PSSECT or full Perple_X plotting for publication-quality phase diagrams."
            )
        label_caption = assemblage_caption_text(assemblage_grid, assemblage_detail)
        if label_caption:
            st.caption(label_caption)
    else:
        st.caption(
            "No VERTEX .plt/.blk assemblage grid was found. This plot shows the P-T grid "
            "and property distribution from WERAMI output."
        )


def show_phase_diagram_panel(models: list[dict[str, Any]], selected_project: str | None, config_path: Path):
    """Render phase diagram panel in GUI.

    Args:
        models: List of all models
        selected_project: Currently selected project
        config_path: Path to config file
    """
    project_options = [str(model.get("project", "")) for model in models if model.get("project")]
    if not project_options:
        st.info("No saved models are available to plot.")
        return
    selected_project = selected_project if selected_project in project_options else None
    stored_project = st.session_state.get(PHASE_MODEL_SELECTOR_KEY)
    if stored_project not in project_options:
        st.session_state.pop(PHASE_MODEL_SELECTOR_KEY, None)
        if selected_project:
            st.session_state[PHASE_MODEL_SELECTOR_KEY] = selected_project

    selectbox_kwargs: dict[str, Any] = {
        "label": "Saved model to plot",
        "options": project_options,
        "placeholder": "Choose a saved model",
        "format_func": lambda project: f"{project}",
        "key": PHASE_MODEL_SELECTOR_KEY,
    }
    if PHASE_MODEL_SELECTOR_KEY not in st.session_state:
        selectbox_kwargs["index"] = None
    selected_project = st.selectbox(**selectbox_kwargs)
    if not selected_project or selected_project not in project_options:
        st.info("Select a saved model to display a phase/property plot.")
        return

    st.subheader(f"Phase Diagram: {selected_project}")

    selected_model = next((m for m in models if m["project"] == selected_project), None)

    if not selected_model:
        st.error("Model not found")
        return

    paths = model_output_paths(selected_model, config_path)
    output_dir = paths.output_dir

    if not output_dir.exists():
        st.warning("⚠️ Output directory not found. Run the pipeline first.")
        return

    # Options
    with st.expander("⚙️ Diagram options"):
        st.caption("**Property to visualize**")
        property_options = [*PROPERTY_OPTIONS.keys(), GRID_ONLY_OPTION]
        if (
            st.session_state.get(PHASE_PROPERTY_PROJECT_KEY) != selected_project
            or st.session_state.get(PHASE_PROPERTY_SELECTOR_KEY) not in property_options
        ):
            st.session_state[PHASE_PROPERTY_SELECTOR_KEY] = DEFAULT_PHASE_PROPERTY
            st.session_state[PHASE_PROPERTY_PROJECT_KEY] = selected_project
        prop_choice = st.radio(
            "Property",
            property_options,
            index=property_options.index(DEFAULT_PHASE_PROPERTY),
            key=PHASE_PROPERTY_SELECTOR_KEY,
            horizontal=True,
            label_visibility="collapsed",
        )
        assemblage_detail = st.radio(
            "Assemblage detail",
            ASSEMBLAGE_DETAIL_OPTIONS,
            horizontal=True,
            help=(
                "Major framework gives the cleanest interpretation. Simplified keeps broad silica and melt groups "
                "but still suppresses minor one-off phase changes."
            ),
        )

    plot_phase_diagram_interactive(
        selected_model,
        output_dir,
        property_choice=prop_choice,
        assemblage_detail=assemblage_detail,
    )
