"""Parser for extracting phase information from Perple_X output."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class PhaseField:
    """Represents a phase stability field in P-T space."""

    pressure_bar: tuple[float, float]  # min, max
    temperature_k: tuple[float, float]  # min, max
    phases: tuple[str, ...]
    stable: bool = True


@dataclass(frozen=True)
class AssemblageGrid:
    """Assemblage IDs and labels parsed from VERTEX output."""

    ids: list[list[int | None]]
    labels: dict[int, tuple[str, ...]]

    @property
    def pressure_count(self) -> int:
        return len(self.ids)

    @property
    def temperature_count(self) -> int:
        return len(self.ids[0]) if self.ids else 0

    @property
    def assemblage_ids(self) -> set[int]:
        return {value for row in self.ids for value in row if value is not None}


@dataclass(frozen=True)
class BoundarySegments:
    """Line segments marking changes between neighboring assemblage IDs."""

    x: list[float | None]
    y: list[float | None]

    @property
    def count(self) -> int:
        return sum(1 for value in self.x if value is None)


GRID_HEADER_RE = re.compile(r"^\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*$")


def parse_vertex_log(vertex_log: Path) -> list[PhaseField]:
    """Extract phase stability information from VERTEX log.

    Note: VERTEX does not output structured phase data by default.
    This is a heuristic parser that does its best with available information.

    Args:
        vertex_log: Path to vertex.log file

    Returns:
        List of phase fields (may be empty if no phase info found)
    """
    phase_fields = []

    if not vertex_log.exists():
        return phase_fields

    try:
        text = vertex_log.read_text(errors="replace")

        # VERTEX logs contain minimal phase info
        # This is a placeholder for future enhancement
        # Real implementation would need VERTEX to be run with special options
        # or parse the .dat files that VERTEX generates

        # For now, return empty list and rely on tab-based inference
        return phase_fields

    except Exception:
        return phase_fields


def parse_ints(line: str) -> list[int]:
    return [int(token) for token in line.split()]


def find_counter_line(lines: list[str], label: str) -> tuple[int, int] | None:
    for index, line in enumerate(lines):
        if label in line:
            tokens = line.split()
            if not tokens:
                continue
            try:
                return index, int(tokens[0])
            except ValueError:
                continue
    return None


def parse_plt_header(plt_path: Path) -> tuple[int, int, int] | None:
    if not plt_path.exists():
        return None
    first_line = plt_path.read_text(errors="replace").splitlines()[0]
    values = parse_ints(first_line)
    if len(values) < 3:
        return None
    return values[0], values[1], values[2]


def skip_plt_grid(lines: list[str], nx: int, ny: int, step: int) -> int | None:
    """Return the line index immediately after the run-length encoded grid."""
    x_count = len(range(1, nx + 1, max(step, 1)))
    y_count = len(range(1, ny + 1, max(step, 1)))
    target = x_count * y_count
    decoded = 0

    for index, line in enumerate(lines[1:], start=1):
        values = parse_ints(line)
        if len(values) < 2:
            return None
        decoded += values[0] + 1
        if decoded == target:
            return index + 1
        if decoded > target:
            return None
    return None


def parse_counter_names(lines: list[str], label: str, fields_before_name: int) -> dict[int, str]:
    counter = find_counter_line(lines, label)
    if counter is None:
        return {}

    index, count = counter
    names: dict[int, str] = {}
    for line in lines[index + 1 : index + 1 + count]:
        parts = line.split()
        if len(parts) <= fields_before_name:
            continue
        try:
            item_id = int(parts[0])
        except ValueError:
            continue
        names[item_id] = " ".join(parts[fields_before_name:])
    return names


def parse_plt_assemblage_labels(plt_path: Path) -> dict[int, tuple[str, ...]]:
    """Parse VERTEX assemblage labels from a Perple_X .plt file.

    Positive IDs in the assemblage section refer to solution models. Negative IDs
    refer to compounds/endmembers. The file includes both lookup tables near the
    end, so this parser can produce human-readable preview labels.
    """
    if not plt_path.exists():
        return {}

    lines = plt_path.read_text(errors="replace").splitlines()
    if not lines:
        return {}

    header = parse_ints(lines[0])
    if len(header) < 3:
        return {}

    grid_end = skip_plt_grid(lines, header[0], header[1], header[2])
    if grid_end is None or grid_end >= len(lines):
        return {}

    try:
        assemblage_count = int(lines[grid_end].strip())
    except ValueError:
        return {}

    raw_labels: dict[int, tuple[int, ...]] = {}
    index = grid_end + 1
    for assemblage_id in range(1, assemblage_count + 1):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            break

        header_values = parse_ints(lines[index])
        index += 1
        if len(header_values) < 3:
            break

        phase_count = header_values[2]
        phase_ids: list[int] = []
        while index < len(lines) and len(phase_ids) < phase_count:
            phase_ids.extend(parse_ints(lines[index]))
            index += 1
        raw_labels[assemblage_id] = tuple(phase_ids[:phase_count])

    compound_names = parse_counter_names(lines, "compound counter", fields_before_name=1)
    solution_names = parse_counter_names(lines, "solution model counter", fields_before_name=3)

    labels: dict[int, tuple[str, ...]] = {}
    for assemblage_id, phase_ids in raw_labels.items():
        names: list[str] = []
        for phase_id in phase_ids:
            if phase_id > 0:
                names.append(solution_names.get(phase_id, f"solution_{phase_id}"))
            elif phase_id < 0:
                names.append(compound_names.get(abs(phase_id), f"compound_{abs(phase_id)}"))
        labels[assemblage_id] = tuple(names)
    return labels


def parse_blk_assemblage_ids(blk_path: Path, nx: int, ny: int) -> list[list[int | None]]:
    """Parse VERTEX .blk grid headers into [pressure][temperature] IDs."""
    if not blk_path.exists():
        return []

    grid: list[list[int | None]] = [[None for _ in range(ny)] for _ in range(nx)]
    found = 0
    for line in blk_path.read_text(errors="replace").splitlines():
        match = GRID_HEADER_RE.match(line)
        if not match:
            continue
        i_value, j_value, assemblage_id = (int(value) for value in match.groups())
        if 1 <= i_value <= nx and 1 <= j_value <= ny and assemblage_id > 0:
            if grid[i_value - 1][j_value - 1] is None:
                found += 1
            grid[i_value - 1][j_value - 1] = assemblage_id

    return grid if found else []


def parse_assemblage_grid(plt_path: Path, blk_path: Path) -> AssemblageGrid | None:
    """Parse the fast VERTEX assemblage preview from .plt and .blk files."""
    header = parse_plt_header(plt_path)
    if header is None:
        return None

    nx, ny, step = header
    if step != 1:
        return None

    ids = parse_blk_assemblage_ids(blk_path, nx, ny)
    if not ids:
        return None

    return AssemblageGrid(
        ids=ids,
        labels=parse_plt_assemblage_labels(plt_path),
    )


def coordinate_edges(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [values[0] - 0.5, values[0] + 0.5]

    edges = [values[0] - (values[1] - values[0]) / 2.0]
    for left, right in zip(values, values[1:]):
        edges.append((left + right) / 2.0)
    edges.append(values[-1] + (values[-1] - values[-2]) / 2.0)
    return edges


def assemblage_boundary_segments(
    temperatures_k: list[float],
    pressures: list[float],
    assemblage_ids: list[list[int | None]],
) -> BoundarySegments:
    """Build Plotly-ready boundary segments where neighboring IDs differ."""
    if not temperatures_k or not pressures or not assemblage_ids:
        return BoundarySegments([], [])

    row_count = min(len(pressures), len(assemblage_ids))
    column_count = min(len(temperatures_k), min(len(row) for row in assemblage_ids))
    if row_count == 0 or column_count == 0:
        return BoundarySegments([], [])

    t_edges = coordinate_edges(temperatures_k[:column_count])
    p_edges = coordinate_edges(pressures[:row_count])
    x_values: list[float | None] = []
    y_values: list[float | None] = []

    for row in range(row_count):
        for column in range(column_count - 1):
            left = assemblage_ids[row][column]
            right = assemblage_ids[row][column + 1]
            if left is not None and right is not None and left != right:
                x = t_edges[column + 1]
                x_values.extend([x, x, None])
                y_values.extend([p_edges[row], p_edges[row + 1], None])

    for row in range(row_count - 1):
        for column in range(column_count):
            lower = assemblage_ids[row][column]
            upper = assemblage_ids[row + 1][column]
            if lower is not None and upper is not None and lower != upper:
                y = p_edges[row + 1]
                x_values.extend([t_edges[column], t_edges[column + 1], None])
                y_values.extend([y, y, None])

    return BoundarySegments(x_values, y_values)


def infer_phase_boundaries_from_tab(tab_path: Path) -> list[PhaseField]:
    """Infer phase boundaries from property discontinuities in .tab file.

    This is an approximation - true phase info requires VERTEX output.
    We look for sharp changes in seismic velocities which often indicate
    phase transitions.

    Args:
        tab_path: Path to .tab file

    Returns:
        List of inferred phase fields
    """
    phase_fields = []

    if not tab_path.exists():
        return phase_fields

    try:
        from validate_tab import column_indices, read_tab

        tab = read_tab(tab_path)
        indices = column_indices(tab.headers)

        # Need P, T, and at least one velocity
        required = ["p_bar", "t_k", "vp_kms"]
        if not all(col in indices for col in required):
            return phase_fields

        # Group points by P-T grid
        # This is complex - placeholder for now
        # Would need to:
        # 1. Identify P-T grid structure
        # 2. Calculate property gradients
        # 3. Find discontinuities
        # 4. Group into phase fields

        return phase_fields

    except Exception:
        return phase_fields


def get_pt_grid_from_tab(tab_path: Path) -> tuple[list[float], list[float]]:
    """Extract P-T grid coordinates from .tab file.

    Args:
        tab_path: Path to .tab file

    Returns:
        Tuple of (pressures_bar, temperatures_k) lists
    """
    if not tab_path.exists():
        return [], []

    try:
        from validate_tab import column_indices, read_tab

        tab = read_tab(tab_path)
        indices = column_indices(tab.headers)

        if "p_bar" not in indices or "t_k" not in indices:
            return [], []

        p_index = indices["p_bar"]
        t_index = indices["t_k"]

        pressures = set()
        temperatures = set()

        for row in tab.rows:
            p = row[p_index]
            t = row[t_index]
            if abs(p) < 1e90 and abs(t) < 1e90:
                pressures.add(p)
                temperatures.add(t)

        return sorted(pressures), sorted(temperatures)

    except Exception:
        return [], []
