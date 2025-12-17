"""
NIBE Heat Pump Provider
Implementation for NIBE Fighter/Supreme heat pumps (F/S-series)

Supports models: F1145, F1245, F1345, F1155, F1255, F1355, S-series
"""

from typing import Dict, Any, List
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from providers.base import HeatPumpProvider
from .registers import get_registers
from .alarms import get_alarm_codes


class NIBEProvider(HeatPumpProvider):
    """Provider for NIBE Fighter/Supreme heat pumps"""

    def get_brand_name(self) -> str:
        """Return brand identifier"""
        return "nibe"

    def get_display_name(self) -> str:
        """Return human-readable brand name"""
        return "NIBE Fighter/Supreme"

    def get_dashboard_title(self) -> str:
        """Return dashboard page title"""
        return "NIBE Värmepump Dashboard"

    def get_registers(self) -> Dict[str, Any]:
        """Return register definitions for NIBE"""
        return get_registers()

    def get_alarm_codes(self) -> Dict[int, str]:
        """Return alarm code definitions for NIBE"""
        return get_alarm_codes()

    def get_alarm_register(self) -> str:
        """Return the register ID for alarm codes"""
        return "2A20"

    def supports_write(self) -> bool:
        """NIBE supports write operations (future feature)"""
        return False  # Not implemented yet

    def get_writable_registers(self) -> List[str]:
        """Return list of registers that support write operations"""
        # Future: Allow changing setpoints, modes, etc.
        return []

    def get_primary_sensors(self) -> Dict[str, str]:
        """
        Return mapping of primary sensor roles to register names

        Returns:
            Dict mapping sensor role to register name
        """
        return {
            'outdoor': 'outdoor_temp',
            'indoor': 'indoor_temp',
            'radiator_forward': 'radiator_forward',
            'radiator_return': 'radiator_return',
            'brine_in': 'brine_in_evaporator',
            'brine_out': 'brine_out_condenser',
            'hot_water': 'warm_water_top',
            'compressor': 'hot_gas_temp',
        }

    def get_status_registers(self) -> Dict[str, str]:
        """
        Return mapping of status roles to register names

        Returns:
            Dict mapping status role to register name
        """
        return {
            'compressor': 'compressor_status',
            'brine_pump': 'brine_pump_status',
            'radiator_pump': 'radiator_pump_status',
            'additional_heat': 'additional_heat_status',
            'switch_valve': 'switch_valve_status',
            'hotwater_charging': 'hotwater_charging_status',
        }

    def get_performance_metrics(self) -> Dict[str, str]:
        """
        Return mapping of performance metric roles to register names

        Returns:
            Dict mapping metric role to register name
        """
        return {
            'compressor_runtime': 'compressor_runtime_total',
            'power_consumption': 'power_consumption',
            'energy_accumulated': 'energy_accumulated',
            'additional_heat_percent': 'additional_heat_percent',
        }

    def format_operating_mode(self, mode_value: int) -> str:
        """
        Format operating mode value to human-readable string

        Args:
            mode_value: Raw mode value from register

        Returns:
            Human-readable mode description
        """
        modes = {
            0: "Auto",
            1: "Uppvärmning",
            2: "Varmvatten",
            3: "Pool",
            4: "Transfer",
            5: "Anti Frys",
            6: "Stopp",
        }
        return modes.get(mode_value, f"Okänt läge ({mode_value})")

    def get_brand_specific_features(self) -> List[str]:
        """
        Return list of brand-specific features

        Returns:
            List of feature identifiers
        """
        return [
            'degree_minutes',        # Unique to NIBE
            'smart_home_mode',       # Smart grid functionality
            'inverter_compressor',   # Variable speed compressor
            'heat_curve_settings',   # Advanced curve control
            'dual_hotwater_sensors', # BT6 + BT7
            'runtime_split',         # Heating/hotwater split
        ]

    def get_sensor_description(self, sensor_name: str) -> str:
        """
        Get NIBE-specific sensor description with BT-numbering

        Args:
            sensor_name: Register name

        Returns:
            Description string with NIBE sensor codes
        """
        descriptions = {
            'outdoor_temp': 'Utomhustemperatur (BT1)',
            'radiator_forward': 'Framledning (BT2)',
            'radiator_return': 'Retur (BT3)',
            'warm_water_mid': 'VV Laddning (BT6)',
            'warm_water_top': 'VV Topp (BT7)',
            'brine_in_evaporator': 'Köldbärare In (BT10)',
            'brine_out_condenser': 'Köldbärare Ut (BT11)',
            'hot_gas_temp': 'Kompressor (BT12)',
            'external_supply_temp': 'Extern Framl. (BT25)',
            'indoor_temp': 'Rumstemperatur (BT50)',
        }
        return descriptions.get(sensor_name, sensor_name)

    def validate_register_value(self, register_id: str, value: float) -> bool:
        """
        Validate if a register value is within expected range

        Args:
            register_id: Register identifier
            value: Value to validate

        Returns:
            True if value is valid, False otherwise
        """
        # Temperature sensors: -40 to 80°C
        temp_registers = ['0001', '0002', '0005', '0006', '0007', '0008', '0009', '000A', '000B', '000D', '0010']
        if register_id in temp_registers:
            return -40 <= value <= 80

        # Status registers: 0 or 1
        status_registers = ['1A01', '1A02', '1A04', '1A06', '1A07', '1A08']
        if register_id in status_registers:
            return value in [0, 1]

        # Percentage: 0-100
        percent_registers = ['3104', '3109', '3110']
        if register_id in percent_registers:
            return 0 <= value <= 100

        # Frequency: 0-200 Hz
        if register_id == '310A':
            return 0 <= value <= 200

        # Default: accept any value
        return True

    def get_cop_calculation_method(self) -> str:
        """
        Return the COP calculation method for this brand

        Returns:
            'registers' if COP from registers, 'calculated' if needs calculation
        """
        return 'calculated'  # NIBE: calculate from heat meter / energy meter

    def calculate_cop(self, latest_values: Dict[str, Any]) -> float:
        """
        Calculate COP for NIBE heat pump

        Args:
            latest_values: Latest register values

        Returns:
            COP value or None if cannot be calculated
        """
        try:
            # NIBE uses heat meter and energy meter
            heat_comp = latest_values.get('heat_meter_compressor', {}).get('value', 0)
            energy_comp = latest_values.get('energy_accumulated', {}).get('value', 0)

            if energy_comp > 0:
                cop = heat_comp / energy_comp
                # Sanity check
                if 1.0 <= cop <= 8.0:
                    return cop

            return None
        except Exception:
            return None
