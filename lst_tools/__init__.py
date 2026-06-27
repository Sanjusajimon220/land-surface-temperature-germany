"""lst-tools — turn real Landsat land-surface-temperature rasters into a
self-contained scrollytelling story of Germany's summer heat.

The open core behind "Germany is heating up" (satellite journalism).
Only the heat pipeline is included here; deformation/InSAR is a separate project.
"""
__version__ = "1.0.0"

from .germany import GERMANY, GERMANY_OUTLINE, CITIES
from .germany_states import STATES
from .surface import (surface_png_stops, HEAT_STOPS, ANOM_STOPS,
                      fill_small_gaps, interpolate_grid, grid_payload)
from .heat import grid_from_array
from .forecast import (lst_trend, lst_warming_rate, lst_project,
                       current_year_anomaly)
from .story import build_heat_story
