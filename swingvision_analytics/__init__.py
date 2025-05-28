"""
SwingVision Analytics Module
Tennis match analysis and visualization tools
"""

from . import dashboard
from . import performance_evolution
from . import shot_analysis  # New
from . import match_analysis  # New
from . import tactical_analysis  # New
from . import raw_data
from . import match_details
from . import upload_files
from . import data_processing

__all__ = [
    "dashboard",
    "performance_evolution",
    "shot_analysis",  # New
    "match_analysis",  # New
    "tactical_analysis",  # New
    "raw_data",
    "match_details",
    "upload_files",
    "data_processing",
]
