"""Table analysis: quality checks, T(r)-profile sampling and table comparison.

Units follow the Perple_X tables: P in bar, T in K.
"""
from planetary_eos_lab.analysis.compare import compare_tables, relative_diff_stats, resolution_convergence
from planetary_eos_lab.analysis.profiles import phase_fractions_along, profile_along
from planetary_eos_lab.analysis.quality import Table, domain_check, load_table, table_quality, validity_mask

__all__ = [
    "Table",
    "compare_tables",
    "domain_check",
    "load_table",
    "phase_fractions_along",
    "profile_along",
    "relative_diff_stats",
    "resolution_convergence",
    "table_quality",
    "validity_mask",
]
