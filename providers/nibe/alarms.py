"""
NIBE Heat Pump Alarm Codes
Based on NIBE F/S-series alarm system

These codes are common across NIBE F1145, F1245, F1345, F1155, F1255, F1355
and S-series heat pumps. Verify with C40.pdf for your specific model.
"""

# NIBE Alarm Codes
# Register: 2A91 (or check C40.pdf for actual register)
ALARM_CODES = {
    0: "Inget larm",

    # Sensor alarms (1-29)
    1: "Sensor BT1 (utomhus) fel",
    2: "Sensor BT2 (framledning) fel",
    3: "Sensor BT3 (retur) fel",
    4: "Sensor BT6 (VV laddning) fel",
    5: "Sensor BT7 (VV topp) fel",
    6: "Sensor BT10 (köldbärare in) fel",
    7: "Sensor BT11 (köldbärare ut) fel",
    8: "Sensor BT12 (kompressor) fel",
    9: "Sensor BT14 (extern framledning) fel",
    10: "Sensor BT15 (extern retur) fel",
    11: "Sensor BT17 (sugg) fel",
    12: "Sensor BT25 (extern framledning 2) fel",
    13: "Sensor BT50 (rum) fel",
    14: "Sensor BP8 (tryck) fel",
    15: "Sensor EP14 (extern framledning) fel",

    # Compressor alarms (30-49)
    20: "Kompressor alarm",
    21: "Högtryckspressostat",
    22: "Lågtryckspressostat",
    23: "Kompressor motorskydd",
    24: "Kompressor för hög temperatur",
    25: "Kompressor frekvensomriktare",
    26: "Kompressor startar ej",
    27: "Kompressor maxfrekvens",

    # Flow and circulation alarms (50-69)
    30: "Brine flöde för lågt",
    31: "Radiatorflöde för lågt",
    32: "Köldbärarpump alarm",
    33: "Radiatorpump alarm",
    34: "Shuntventil alarm",
    35: "Flödesvakt köldbärare",
    36: "Flödesvakt radiator",

    # Hot water alarms (70-79)
    40: "VV temp för hög",
    41: "VV legionellaskydd misslyckades",
    42: "VV laddning timeout",

    # External heat alarms (80-89)
    50: "Tillsatsvärme fel",
    51: "Tillsatsvärme säkring utlöst",
    52: "Tillsatsvärme övertemp",
    53: "Tillsatsvärme steg 1 fel",
    54: "Tillsatsvärme steg 2 fel",

    # Communication alarms (90-99)
    60: "Kommunikationsfel intern",
    61: "Kommunikationsfel extern",
    62: "Kommunikationsfel sensor",
    63: "Kommunikationsfel display",
    64: "Kommunikationsfel frekvensomriktare",

    # System alarms (100-119)
    70: "Fasföljd fel",
    71: "Strömavbrott",
    72: "Låg spänning",
    73: "Hög spänning",
    74: "Jordfel",
    75: "Överhettning system",
    76: "Frysskydd köldbärare",
    77: "Frysskydd radiator",
    78: "Frysskydd varmvatten",

    # Configuration alarms (120-139)
    80: "Konfigurationsfel",
    81: "Installationsfel",
    82: "Inställningsfel",
    83: "COP-värde för lågt",

    # Smart grid / control alarms (140-149)
    90: "Smart Grid kommunikationsfel",
    91: "Smart Grid konflikt",
    92: "Extern styrning fel",

    # Service codes (200-255)
    200: "Service krävs",
    201: "Service filter",
    202: "Service kompressor",
    203: "Service värmesystem",

    # Generic error
    255: "Okänt larm - kontakta service",
}


def get_alarm_codes():
    """Return NIBE alarm code definitions"""
    return ALARM_CODES


def get_alarm_description(code: int) -> str:
    """
    Get alarm description from code

    Args:
        code: Alarm code (integer)

    Returns:
        Alarm description string
    """
    return ALARM_CODES.get(code, f"Okänt larm: {code}")


def is_active_alarm(code: int) -> bool:
    """
    Check if alarm code indicates an active alarm

    Args:
        code: Alarm code (integer)

    Returns:
        True if alarm is active, False otherwise
    """
    return code != 0


def get_alarm_severity(code: int) -> str:
    """
    Get alarm severity level

    Args:
        code: Alarm code (integer)

    Returns:
        Severity level: 'none', 'warning', 'error', 'critical'
    """
    if code == 0:
        return 'none'
    elif 1 <= code <= 15:
        return 'error'  # Sensor failures
    elif 20 <= code <= 29:
        return 'critical'  # Compressor issues
    elif 30 <= code <= 39:
        return 'critical'  # Flow issues
    elif 40 <= code <= 49:
        return 'warning'  # Hot water issues
    elif 50 <= code <= 59:
        return 'error'  # External heat
    elif 60 <= code <= 69:
        return 'error'  # Communication
    elif 70 <= code <= 89:
        return 'critical'  # System alarms
    elif 200 <= code <= 255:
        return 'warning'  # Service needed
    else:
        return 'warning'  # Unknown
