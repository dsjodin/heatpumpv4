"""
Thermia Dashboard - Gemensam färgpalett och konstanter
Används av alla callback-moduler för konsistent styling
"""

# ==================== FÄRGPALETT - MAXIMAL KONTRAST ====================
# Gemensam färgpalett för konsistens över alla grafer
# UPPDATERAD: Radiatorparet har nu MYCKET mer kontrast
THERMIA_COLORS = {
    # Temperaturer - semantiskt meningsfulla färger
    'outdoor_temp': '#40464a',      # Ljusblå - utetemperatur
    'indoor_temp': '#4caf50',       # Grön - inomhus bekvämt
    'hot_water_top': '#174c7a',     # Orange - mycket varmt vatten
    
    # Radiator-paret - MAXIMAL KONTRAST (Röd vs Guld)
    'radiator_forward': '#dc143c',  # Crimson/Djup Röd - VARMAST (framledning)
    'radiator_return': '#287040',   # Guld/Gul - SVALARE (retur)
    
    # Köldbärare-paret - TYDLIG KONTRAST  
    'brine_in_evaporator': '#e6a930',   # Ljus Cyan/Turkos - IN från mark
    'brine_out_condenser': '#1565c0',   # Djup Blå - UT till mark (kallare)
    
    # Kompressor och system
    'compressor': '#4caf50',        # Grön - normal drift
    'aux_heater': '#ffc107',        # Amber/Gul - tillsattsvärme
    'power': '#9b59b6',             # Lila - effekt
    
    # Delta/differenser
    'delta_brine': '#26c6da',       # Cyan - KB delta
    'delta_radiator': '#ff5722',    # Djup orange - Radiator delta
    
    # COP
    'cop': '#4caf50',               # Grön - bra COP
    'cop_avg': '#ff9800',           # Orange - genomsnitt
}

# Linjebredder för grafer
LINE_WIDTH_NORMAL = 2.5     # Standard linjer
LINE_WIDTH_THICK = 3.0      # För viktiga linjer
LINE_WIDTH_THIN = 2.0       # För mindre viktiga linjer
