"""
NIBE Heat Pump Register Definitions
Based on NIBE EB100 Controller register specification (C40.pdf)

These registers are for NIBE F-series/S-series (Fighter, Supreme) heat pumps
when used with Husdata H66 gateway.

Document: NIBE EB100 Controller, Husdata.se H66, 2025-10-03
LW = Ground source Liquid/Water pump
AW pump = Air/Water pumps, EW pump = Exhaust Air pumps
"""

# NIBE Register Definitions for Husdata H66
# Verified from official NIBE EB100 Controller documentation

REGISTERS = {
    # ==================== Temperature Sensors ====================

    # Radiator circuit
    '0002': {
        'name': 'radiator_return',
        'description': 'Returtemperatur radiator (BT61)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Heat carrier (internal)
    '0003': {
        'name': 'heat_carrier_return',
        'description': 'Intern värmebärare retur (BT3)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '0004': {
        'name': 'heat_carrier_forward',
        'description': 'Intern värmebärare framledning (BT2)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Brine (ground source)
    '0005': {
        'name': 'brine_in_evaporator',
        'description': 'Köldbärare in från markkälla (BT10/BT16)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '0006': {
        'name': 'brine_out_condenser',
        'description': 'Köldbärare ut till markkälla (BT11/BT12)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Ambient
    '0007': {
        'name': 'outdoor_temp',
        'description': 'Utomhustemperatur (BT1)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '0008': {
        'name': 'indoor_temp',
        'description': 'Inomhustemperatur (BT50)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Hot water
    '0009': {
        'name': 'warm_water_top',
        'description': 'Varmvatten topp (BT7)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '000A': {
        'name': 'warm_water_mid',
        'description': 'Varmvatten mitt (BT6)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Compressor / Refrigerant
    '000B': {
        'name': 'hot_gas_temp',
        'description': 'Hetgas från kompressor (LW-BT14, EW-BT18)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '000C': {
        'name': 'suction_gas_temp',
        'description': 'Suggas efter expansionsventil (BT17)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Flow sensors
    '000D': {
        'name': 'liquid_flow',
        'description': 'Vätskeflöde',
        'unit': 'l/min',
        'scale': 0.1,
        'signed': False
    },

    # Air pumps only
    '000F': {
        'name': 'air_intake_temp',
        'description': 'Luftintag för EW pumpar',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '0010': {
        'name': 'air_outlet_temp',
        'description': 'Luftutlopp för EW pumpar',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Pool
    '0011': {
        'name': 'pool_temp',
        'description': 'Pooltemperatur om installerad',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Heat circuit 2 (if installed)
    '0020': {
        'name': 'radiator_forward_2',
        'description': 'Framledning värmekrets 2 (EP21-BT2)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '0021': {
        'name': 'indoor_temp_2',
        'description': 'Inomhustemperatur krets 2 (EP21-BT50)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '0022': {
        'name': 'heat_carrier_return_2',
        'description': 'Intern värmebärare retur krets 2 (EP-21 BT3)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # ==================== Setpoints & Settings ====================

    # Room temperature control
    '0203': {
        'name': 'room_temp_setpoint_set',
        'description': 'Ställ in rumstemperatur (M1.1.1)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True,
        'type': 'setpoint'
    },

    '0106': {
        'name': 'room_temp_setpoint',
        'description': 'Aktuellt rumstemperatur börvärde',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    '0107': {
        'name': 'heating_setpoint',
        'description': 'Måltemperatur för uppvärmning',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Heat curve circuit 1
    '2205': {
        'name': 'heating_curve',
        'description': 'Värmekurva för krets 1 (M1.9.11)',
        'unit': '',
        'scale': 0.1,
        'signed': True,
        'type': 'setpoint'
    },

    '2207': {
        'name': 'heating_curve_offset',
        'description': 'Värmekurva parallellförskjutning krets 1 (M1.9.11)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True,
        'type': 'setpoint'
    },

    # Heat curve circuit 2
    '2222': {
        'name': 'heating_curve_2',
        'description': 'Värmekurva för krets 2 (M1.9.11)',
        'unit': '',
        'scale': 0.1,
        'signed': True,
        'type': 'setpoint'
    },

    '2224': {
        'name': 'heating_curve_offset_2',
        'description': 'Värmekurva parallellförskjutning krets 2 (M1.9.11)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True,
        'type': 'setpoint'
    },

    # Room sensor influence
    '2204': {
        'name': 'room_sensor_influence',
        'description': 'Rumssensorpåverkan (M19.4)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'setpoint'
    },

    '0220': {
        'name': 'room_temp_setpoint_2',
        'description': 'Rumstemperatur börvärde krets 2 (M1.11)',
        'unit': '°C',
        'scale': 0.1,
        'signed': True,
        'type': 'setpoint'
    },

    # Degree minutes
    '8255': {
        'name': 'degree_minutes_compressor',
        'description': 'Gradminuter kompressor (M3.1)',
        'unit': 'DM',
        'scale': 1,
        'signed': True
    },

    '8105': {
        'name': 'degree_minutes_integral',
        'description': 'Gradminuter integral display (M3.1)',
        'unit': 'DM',
        'scale': 1,
        'signed': True
    },

    # Operating modes
    '2201': {
        'name': 'operating_mode',
        'description': 'Driftläge 1 (0=Auto, 1=Manual, 2=Only Additional heater) (M4.2)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'mode'
    },

    '2213': {
        'name': 'warm_water_program',
        'description': 'Varmvattenprogram (0=Eco, 1=Normal, 2=Luxury, 4=Smart) (M2.2)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'mode'
    },

    '2218': {
        'name': 'pool_mode',
        'description': 'Poolläge (0=off, 1=On) (M2.1)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'mode'
    },

    # Additional heat
    '9226': {
        'name': 'max_additional_heat',
        'description': 'Max tillsatsvärme effekt (M5.1.12)',
        'unit': 'kW',
        'scale': 1,
        'signed': False,
        'type': 'setpoint'
    },

    # Room controller
    '02F1': {
        'name': 'room_controller_emulation',
        'description': 'Om rumsstyrning emulering är aktiverad',
        'unit': '°C',
        'scale': 0.1,
        'signed': True
    },

    # Alarm reset
    '22F2': {
        'name': 'reset_alarm',
        'description': 'Ställ till 1 för att återställa aktivt larm',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'command'
    },

    # ==================== Status Registers ====================

    # Component status
    '1A01': {
        'name': 'compressor_status',
        'description': 'Kompressor status (0=Off, 1=On)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'status'
    },

    '1A04': {
        'name': 'brine_pump_status',
        'description': 'Köldbärarpump status (Ground source pump, LW pumps only)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'status'
    },

    '1A05': {
        'name': 'radiator_pump_status',
        'description': 'Intern cirkulationspump status (0=Off, 1=On)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'status'
    },

    '1A07': {
        'name': 'switch_valve_status',
        'description': 'Shuntventil 1 position (0=Radiator heating, 1=Hot Water heating)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'status'
    },

    '1A0C': {
        'name': 'heating_cable_status',
        'description': 'Värmekabel för ute sensor (AW pumps only) (0=off, 1=on)',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'status'
    },

    # ==================== Performance & Power ====================

    # Compressor speed (variable speed)
    '9108': {
        'name': 'compressor_speed',
        'description': 'Kompressor hastighet variabel kompressor',
        'unit': '%',
        'scale': 1,
        'signed': False
    },

    # Additional heat
    '3104': {
        'name': 'additional_heat_percent',
        'description': 'Tillsatsvärme procentuell användning',
        'unit': '%',
        'scale': 1,
        'signed': False
    },

    '9124': {
        'name': 'additional_heat_power',
        'description': 'Aktuell tillsatsvärme effekt',
        'unit': 'kW',
        'scale': 1,
        'signed': False
    },

    # Current draw (per phase)
    '4101': {
        'name': 'load_l1',
        'description': 'Fas 1 strömförbrukning (heat pump eller hela huset)',
        'unit': 'A',
        'scale': 0.1,
        'signed': False
    },

    '4102': {
        'name': 'load_l2',
        'description': 'Fas 2 strömförbrukning (heat pump eller hela huset)',
        'unit': 'A',
        'scale': 0.1,
        'signed': False
    },

    '4103': {
        'name': 'load_l3',
        'description': 'Fas 3 strömförbrukning (heat pump eller hela huset)',
        'unit': 'A',
        'scale': 0.1,
        'signed': False
    },

    # ==================== Energy Meters ====================

    # Total supplied energy
    '5C51': {
        'name': 'energy_total',
        'description': 'Total tillförd energi',
        'unit': 'kWh',
        'scale': 0.1,
        'signed': False
    },

    '5C53': {
        'name': 'energy_hotwater',
        'description': 'Total tillförd energi för varmvatten',
        'unit': 'kWh',
        'scale': 0.1,
        'signed': False
    },

    '5C65': {
        'name': 'energy_ventilation',
        'description': 'Total tillförd energi för ventilation',
        'unit': 'kWh',
        'scale': 0.1,
        'signed': False
    },

    # ==================== Alarm & Info ====================

    # Alarm code
    '2A20': {
        'name': 'alarm_code',
        'description': 'Larmkod om aktivt larm',
        'unit': '',
        'scale': 1,
        'signed': False,
        'type': 'alarm'
    },
}


def get_registers():
    """Return NIBE register definitions"""
    return REGISTERS
