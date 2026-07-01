"""Parser for extracting phase information from Perple_X output."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PhaseField:
    """Represents a phase stability field in P-T space."""

    pressure_bar: tuple[float, float]  # min, max
    temperature_k: tuple[float, float]  # min, max
    phases: tuple[str, ...]
    stable: bool = True


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
