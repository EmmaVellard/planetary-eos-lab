"""Database selection widget and integration for Streamlit GUI."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from planetary_eos_lab.core.config_io import save_config_json
from planetary_eos_lab.core.database_utils import (
    describe_database,
    get_active_oxides,
    get_source_only_oxides,
    list_available_databases,
)


DEFAULT_BUILD_TEMPLATES = {
    "stx21": "build_inputs/lunar_stx21_template.build.in",
    "hp633": "build_inputs/lunar_hp633_template.build.in",
    "dew17_hhph": "build_inputs/icy_dew17_hhph_template.build.in",
    "hpha02_hydrous": "build_inputs/icy_hpha02_hydrous_simple_template.build.in",
    "dew13_hydrous": "build_inputs/icy_dew13_hydrous_template.build.in",
    "dew17_comet": "build_inputs/icy_dew17_comet_template.build.in",
}


def show_database_selector(config: dict[str, Any], config_path: Path) -> str:
    """Render database selector and return selected database name.

    Args:
        config: Configuration dictionary
        config_path: Path to config file

    Returns:
        Selected database name (e.g., "stx21", "hp633")
    """
    current_db = config.get("database", "stx21")
    databases = list_available_databases()

    # Database selector
    selected = st.selectbox(
        "Thermodynamic Database",
        options=databases,
        index=databases.index(current_db) if current_db in databases else 0,
        key="database_selector",
        help="Choose which thermodynamic database to use for Perple_X calculations",
    )

    # Show database capabilities in expander
    with st.expander(f"📋 Database details: {selected}", expanded=False):
        st.code(describe_database(selected), language="text")

        active = sorted(get_active_oxides(selected))
        st.caption(f"**Modeled components/oxides ({len(active)})**: {', '.join(active)}")

        source_only = get_source_only_oxides(selected)
        if source_only:
            st.caption(f"**Source-only oxides**: {', '.join(source_only)}")
            st.info(
                "Source-only oxides are tracked in composition records but not "
                "passed to the BUILD file for this database."
            )

    # Switch database if changed
    if selected != current_db:
        st.warning(
            f"`{current_db}` is still the active thermodynamic setup. "
            f"Apply the switch before editing or running models with `{selected}`."
        )
        if st.button(f"💾 Switch to {selected} database", type="primary"):
            config["database"] = selected
            if selected in DEFAULT_BUILD_TEMPLATES:
                config["build_template_file"] = DEFAULT_BUILD_TEMPLATES[selected]
            save_config_json(config_path, config)
            st.success(f"✅ Database changed to {selected}. The new database will be used for all future calculations.")
            st.info("Existing models in your config remain unchanged. Their compositions may need adjustment if switching databases.")
            st.rerun()
        return current_db

    return selected


def get_current_database(config: dict[str, Any]) -> str:
    """Get current database from config with fallback to default.

    Args:
        config: Configuration dictionary

    Returns:
        Database name
    """
    return config.get("database", "stx21")


def database_selector_help_text() -> str:
    """Return help text explaining database selection.

    Returns:
        Help text string
    """
    return """
**Choosing a Database:**

- **stx21** (default): Standard for silicate mantle compositions
  - Modeled oxides: Na2O, MgO, Al2O3, SiO2, CaO, FeO (6 components)
  - Best for typical mantle mineralogy

- **hp633**: Holland & Powell 2011 setup
  - Modeled oxides: Na2O, MgO, Al2O3, SiO2, K2O, CaO, TiO2, FeO
  - P2O5 is still source-only unless you provide a P-bearing database/template
  - Default BUILD excludes `q`, `crst`, and `trd` to avoid incomplete seismic properties
  - Use when TiO2 or K2O need to be passed to BUILD

- **dew17_hhph**, **dew13_hydrous**, **dew17_comet**: element/component setups for volatile-bearing icy-world candidates
  - Use Perple_X component names such as H2, O2, S2, N2, C, Mg, Si, Fe

- **hpha02_hydrous**: hydrous oxide/component setup
  - Uses component names such as SIO2, AL2O3, FEO, MGO, CAO, NA2O, H2O

The database choice affects which oxides or components are included in Perple_X BUILD calculations.
"""
