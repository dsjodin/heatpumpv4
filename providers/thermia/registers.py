"""
Thermia Diplomat Register Definitions
Based on Husdata H66 documentation (C60.pdf)
"""

THERMIA_REGISTERS = {
    # Temperatures
    "0001": {
        "name": "radiator_return",
        "unit": "°C",
        "type": "temperature",
        "description": "Radiator return temperature (from radiators)"
    },
    "0002": {
        "name": "radiator_forward",
        "unit": "°C",
        "type": "temperature",
        "description": "Radiator forward temperature (to radiators)"
    },
    "0005": {
        "name": "brine_in_evaporator",
        "unit": "°C",
        "type": "temperature",
        "description": "Brine in/Evaporator temp (from ground for LW, evaporator for AW/EW)"
    },
    "0006": {
        "name": "brine_out_condenser",
        "unit": "°C",
        "type": "temperature",
        "description": "Brine out/Condenser temp (to ground for LW, condenser for AW/EW)"
    },
    "0007": {
        "name": "outdoor_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Outdoor temperature sensor"
    },
    "0008": {
        "name": "indoor_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Indoor temperature (cable connected sensor if installed)"
    },
    "0009": {
        "name": "hot_water_top",
        "unit": "°C",
        "type": "temperature",
        "description": "Hot water tank top sensor"
    },
    "0012": {
        "name": "pressure_tube_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Temperature after compressor before expansion valve"
    },
    "0013": {
        "name": "cooling_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Cooling circuit temperature (if installed)"
    },
    "0107": {
        "name": "heating_setpoint",
        "unit": "°C",
        "type": "temperature",
        "description": "Target temperature for heating"
    },

    # Pump Speeds (Percentage)
    "3109": {
        "name": "circulation_pump_speed",
        "unit": "%",
        "type": "percentage",
        "description": "Variable speed for circulation pump"
    },
    "3110": {
        "name": "brine_pump_speed",
        "unit": "%",
        "type": "percentage",
        "description": "Variable speed for ground source brine pump (LW only)"
    },

    # Pump Statuses (0=off, 1=on)
    "1A01": {
        "name": "compressor_status",
        "unit": "",
        "type": "status",
        "description": "Compressor on/off status"
    },
    "1A04": {
        "name": "brine_pump_status",
        "unit": "",
        "type": "status",
        "description": "Ground source brine pump status (LW only)"
    },
    "1A06": {
        "name": "radiator_pump_status",
        "unit": "",
        "type": "status",
        "description": "Radiator circulation pump status"
    },
    "1A07": {
        "name": "switch_valve_status",
        "unit": "",
        "type": "status",
        "description": "Switch valve position (0=radiator heating, 1=hot water heating)"
    },

    # Additional Heat
    "3104": {
        "name": "additional_heat_percent",
        "unit": "%",
        "type": "percentage",
        "description": "Additional electrical heater percentage (typically 9kW max)"
    },

    # Alarm
    "1A20": {
        "name": "alarm_status",
        "unit": "",
        "type": "alarm",
        "description": "Pump alarm status (0=OK, 1=Alarming)"
    },
    "2A91": {
        "name": "alarm_code",
        "unit": "",
        "type": "alarm",
        "description": "Active alarm code (e.g., 10=HP, 40=Motor protector)"
    },

    # Settings
    "2201": {
        "name": "operating_mode",
        "unit": "",
        "type": "setting",
        "description": "Operational mode (0=All off, 1=Auto, 2=Normal, 3=Add heat only, 4=Hot water only)"
    },
    "0203": {
        "name": "room_temp_setpoint",
        "unit": "°C",
        "type": "temperature",
        "description": "Room temperature setpoint (if indoor sensor installed)"
    },
    "2204": {
        "name": "room_sensor_influence",
        "unit": "°C",
        "type": "setting",
        "description": "How much room temp should influence heating"
    },
    "0205": {
        "name": "heat_curve_L",
        "unit": "°C",
        "type": "setting",
        "description": "Heat curve setting (CurveL base point)"
    },
    "0206": {
        "name": "heat_curve_R",
        "unit": "°C",
        "type": "setting",
        "description": "Heat curve MAX setting (CurveR)"
    },
    "0208": {
        "name": "hot_water_stop_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Hot water highest temperature setpoint"
    },
    "0211": {
        "name": "heating_stop_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Heating stop temperature setpoint"
    },
    "0212": {
        "name": "hot_water_start_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Hot water lowest temperature setpoint"
    },
    "0214": {
        "name": "cooling_setpoint",
        "unit": "°C",
        "type": "temperature",
        "description": "Cooling temperature level (if installed)"
    },
    "0217": {
        "name": "outdoor_temp_offset",
        "unit": "°C",
        "type": "temperature",
        "description": "Outdoor temperature offset adjustment"
    },
    "0233": {
        "name": "external_control",
        "unit": "°C",
        "type": "setting",
        "description": "Temperature reduction when EVU input has 10kOhm"
    },
    "8105": {
        "name": "degree_minutes",
        "unit": "",
        "type": "setting",
        "description": "Regulation delay variable (integral)"
    },

    # Runtime Counters
    "6C60": {
        "name": "compressor_runtime",
        "unit": "hours",
        "type": "runtime",
        "description": "Compressor total runtime hours"
    },
    "6C63": {
        "name": "aux_heater_3kw_runtime",
        "unit": "hours",
        "type": "runtime",
        "description": "3kW electrical heater total runtime"
    },
    "6C64": {
        "name": "hot_water_runtime",
        "unit": "hours",
        "type": "runtime",
        "description": "Total time producing hot water"
    },
    "6C66": {
        "name": "aux_heater_6kw_runtime",
        "unit": "hours",
        "type": "runtime",
        "description": "6kW electrical heater total runtime"
    },

    # Power and Energy (Common H60/H66 registers)
    "CFAA": {
        "name": "power_consumption",
        "unit": "W",
        "type": "power",
        "description": "Real-time power consumption in Watts"
    },
    "5FAB": {
        "name": "accumulated_energy",
        "unit": "kWh",
        "type": "energy",
        "description": "Total accumulated energy consumption"
    }
}
