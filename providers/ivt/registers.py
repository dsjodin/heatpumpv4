"""
IVT Greenline Register Definitions
Based on IVT Rego 600/637 Controllers (C00.pdf)
LW = Ground source Liquid/Water pump
AW pump = Air/Water pumps, EW pump = Exhaust Air pumps
"""

IVT_REGISTERS = {
    # Temperatures
    "0001": {
        "name": "radiator_return",
        "unit": "°C",
        "type": "temperature",
        "description": "Return water feed from radiators [if installed]"
    },
    "0002": {
        "name": "radiator_forward",
        "unit": "°C",
        "type": "temperature",
        "description": "Water feed out to radiators"
    },
    "0003": {
        "name": "heat_carrier_return",
        "unit": "°C",
        "type": "temperature",
        "description": "HP internal heat carrier return"
    },
    "0004": {
        "name": "heat_carrier_forward",
        "unit": "°C",
        "type": "temperature",
        "description": "HP internal heat supply forward"
    },
    "0005": {
        "name": "brine_in_evaporator",
        "unit": "°C",
        "type": "temperature",
        "description": "Supply in from ground source for LW pumps, Evaporator for AW pumps"
    },
    "0006": {
        "name": "brine_out_condenser",
        "unit": "°C",
        "type": "temperature",
        "description": "Supply out to ground source for LW pumps, Condenser for AW pumps"
    },
    "0007": {
        "name": "outdoor_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Outdoor sensor"
    },
    "0008": {
        "name": "indoor_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Temp of indoor sensor [if installed]"
    },
    "0009": {
        "name": "hot_water_top",
        "unit": "°C",
        "type": "temperature",
        "description": "Warm water tank temp GT3 (For internal Tank)"
    },
    "000A": {
        "name": "warm_water_2_mid",
        "unit": "°C",
        "type": "temperature",
        "description": "Warm water tank temp GT3X (For external tank if installed)"
    },
    "000B": {
        "name": "hot_gas_compressor",
        "unit": "°C",
        "type": "temperature",
        "description": "Hot gas from compressor before expansion valve"
    },

    # Additional Heat
    "3104": {
        "name": "additional_heat_percent",
        "unit": "%",
        "type": "percentage",
        "description": "Applied Additional Electrical heater to support compressor. Commonly 9kW max."
    },

    # Setpoints
    "0107": {
        "name": "heating_setpoint",
        "unit": "°C",
        "type": "temperature",
        "description": "Target temp for heating"
    },
    "0111": {
        "name": "warm_water_setpoint",
        "unit": "°C",
        "type": "temperature",
        "description": "Target temp for warm tap water"
    },
    "0203": {
        "name": "room_temp_setpoint",
        "unit": "°C",
        "type": "temperature",
        "description": "Set room temp if Indoor sensor [if installed]"
    },

    # Settings
    "2204": {
        "name": "room_sensor_influence",
        "unit": "°C",
        "type": "setting",
        "description": "Set how much room temp should influence heating (if Indoor sensor installed)"
    },
    "2205": {
        "name": "heat_curve_level",
        "unit": "",
        "type": "setting",
        "description": "Set heat curve level (Heat set 1, CurveL)"
    },
    "0207": {
        "name": "heat_curve_parallel",
        "unit": "",
        "type": "setting",
        "description": "Set heat curve parallel offset (Heat set 3 Parallel)"
    },
    "0208": {
        "name": "warm_water_stop_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Set stop temp for tap hot water (too high will trigger Pressostat alarm)"
    },
    "020B": {
        "name": "warm_water_difference",
        "unit": "°C",
        "type": "setting",
        "description": "Set tap water start threshold: WW Stop temp - Diff temp = WW start temp"
    },
    "7209": {
        "name": "extra_warm_water_time",
        "unit": "Minutes",
        "type": "setting",
        "description": "Set minutes for the Extra warm water feature to be activated"
    },
    "1215": {
        "name": "electric_heater_switch",
        "unit": "",
        "type": "setting",
        "description": "1=on, 0=off. Turn off Electrical heater (will take effect next time add heater is to start)"
    },
    "1233": {
        "name": "external_control",
        "unit": "",
        "type": "setting",
        "description": "Activate external control input 1 to block heat pump operations. 1=Activated, 0=Inactivated"
    },
    "020A": {
        "name": "summer_mode_temp",
        "unit": "°C",
        "type": "temperature",
        "description": "Set temp where HP should go into summer mode and only produce Hot Water"
    },
    "2210": {
        "name": "holiday_mode",
        "unit": "Hours",
        "type": "setting",
        "description": "Set 0-30 days for holiday mode to be activated"
    },
    "12F2": {
        "name": "alarm_reset",
        "unit": "",
        "type": "setting",
        "description": "Set to 0 to execute a cycle that turns off the pump for 10 seconds and then on again to reset alarm"
    },

    # Status
    "1A01": {
        "name": "compressor_status",
        "unit": "",
        "type": "status",
        "description": "0=Off, 1=On"
    },
    "1A02": {
        "name": "add_heat_step_1",
        "unit": "",
        "type": "status",
        "description": "0=Off, 1=On. Normally 3kW step"
    },
    "1A03": {
        "name": "add_heat_step_2",
        "unit": "",
        "type": "status",
        "description": "0=Off, 1=On. Normally 6kW step"
    },
    "1A04": {
        "name": "brine_pump_status",
        "unit": "",
        "type": "status",
        "description": "Ground source pump. 0=Off, 1=On (LW pumps only)"
    },
    "1A05": {
        "name": "pump_heat_circuit",
        "unit": "",
        "type": "status",
        "description": "Internal circulation pump. 0=Off, 1=On"
    },
    "1A06": {
        "name": "radiator_pump_status",
        "unit": "",
        "type": "status",
        "description": "Radiator pump. 0=Off, 1=On"
    },
    "1A07": {
        "name": "switch_valve_status",
        "unit": "",
        "type": "status",
        "description": "Switch valve position 0=Radiator heating, 1=Hot Water heating"
    },

    # Alarm
    "1A20": {
        "name": "alarm_status",
        "unit": "",
        "type": "alarm",
        "description": "Pump alarm. >0 = Alarming"
    },
    "BA91": {
        "name": "alarm_code",
        "unit": "",
        "type": "alarm",
        "description": "Number of the last triggered alarm, even if no active alarm now"
    },

    # Runtime Counters - IVT splits by heating/hotwater
    "6C55": {
        "name": "compressor_runtime_heating",
        "unit": "hours",
        "type": "runtime",
        "description": "Compressor runtime for heating"
    },
    "6C56": {
        "name": "compressor_runtime_hotwater",
        "unit": "hours",
        "type": "runtime",
        "description": "Compressor runtime for hot water production"
    },
    "6C58": {
        "name": "aux_runtime_heating",
        "unit": "hours",
        "type": "runtime",
        "description": "Electrical additional heater runtime for heating"
    },
    "6C59": {
        "name": "aux_runtime_hotwater",
        "unit": "hours",
        "type": "runtime",
        "description": "Electrical additional heater for hot water production"
    },

    # Power & Energy (Common H60/H66 registers)
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
    },

    # Custom Registers
    "025A": {
        "name": "heat_carrier_in_max",
        "unit": "°C",
        "type": "temperature",
        "description": "Heat carrier in Max (90)"
    },
    # Note: Register 0008 is indoor_temp, defined earlier in this file
    # "switch_on_rego" was incorrectly mapped here - removed duplicate
}
