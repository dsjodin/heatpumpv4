"""
Heat Pump Dashboard - Chart Color Palette
Common color definitions for all heat pump brands.
Used by dashboard for consistent chart styling across Thermia, IVT, NIBE, etc.
"""

# ==================== CHART COLOR PALETTE ====================
# Shared color palette for all brands - semantically consistent
# Colors chosen for maximum contrast and accessibility

CHART_COLORS = {
    # Temperatures - semantically meaningful colors
    'outdoor_temp': '#40464a',      # Dark gray - outdoor
    'indoor_temp': '#4caf50',       # Green - indoor comfort
    'hot_water_top': '#174c7a',     # Deep blue - hot water
    'warm_water_top': '#174c7a',    # Alias for NIBE naming
    'warm_water_mid': '#2196f3',    # Light blue - mid tank

    # Radiator pair - HIGH CONTRAST (Red vs Green)
    'radiator_forward': '#dc143c',  # Crimson - HOTTEST (forward)
    'radiator_return': '#287040',   # Forest green - COOLER (return)
    'heat_carrier_forward': '#dc143c',  # Alias for NIBE
    'heat_carrier_return': '#287040',   # Alias for NIBE

    # Brine pair - CLEAR CONTRAST
    'brine_in_evaporator': '#e6a930',   # Gold/Amber - IN from ground
    'brine_out_condenser': '#1565c0',   # Deep blue - OUT to ground

    # Compressor and system
    'compressor': '#4caf50',        # Green - normal operation
    'hot_gas_temp': '#ff5722',      # Deep orange - hot gas
    'aux_heater': '#ffc107',        # Amber - additional heat
    'power': '#9b59b6',             # Purple - power

    # Delta/differences
    'delta_brine': '#26c6da',       # Cyan - brine delta
    'delta_radiator': '#ff5722',    # Deep orange - radiator delta

    # COP
    'cop': '#4caf50',               # Green - good COP
    'cop_avg': '#ff9800',           # Orange - average
}

# Legacy alias for backwards compatibility
THERMIA_COLORS = CHART_COLORS

# Line widths for charts
LINE_WIDTH_NORMAL = 2.5     # Standard lines
LINE_WIDTH_THICK = 3.0      # Important lines
LINE_WIDTH_THIN = 2.0       # Secondary lines
