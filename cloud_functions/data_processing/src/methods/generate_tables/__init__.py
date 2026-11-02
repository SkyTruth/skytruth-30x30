from src.methods.generate_tables.fishing_protection import (
    generate_fishing_protection_table,
    get_iho_fishing_protection_region_stats,
)
from src.methods.generate_tables.habitat_protection import generate_habitat_protection_table
from src.methods.generate_tables.marine_protection_level import (
    generate_marine_protection_level_stats_table,
)
from src.methods.generate_tables.protected_areas_diff import generate_protected_areas_diff_table
from src.methods.generate_tables.protection_coverage_table import (
    generate_protection_coverage_stats_table,
)

__all__ = [
    # Protected areas diff
    "generate_protected_areas_diff_table",
    # Habitat protection
    "generate_habitat_protection_table",
    # Protection coverage
    "generate_protection_coverage_stats_table",
    # Marine protection level
    "generate_marine_protection_level_stats_table",
    # Fishing protection
    "generate_fishing_protection_table",
    "get_iho_fishing_protection_region_stats",
]
