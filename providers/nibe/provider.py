"""
NIBE Heat Pump Provider
Implementation for NIBE Fighter/Supreme heat pumps (F/S-series)

Supports models: F1145, F1245, F1345, F1155, F1255, F1355, S-series
"""

from typing import Dict, Any, List, Optional

from providers.base import HeatPumpProvider
from .registers import get_registers
from .alarms import get_alarm_codes


class NIBEProvider(HeatPumpProvider):
    """Provider for NIBE Fighter/Supreme heat pumps"""

    # =========================================================================
    # REQUIRED ABSTRACT METHODS
    # =========================================================================

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

    def get_alarm_register_id(self) -> str:
        """Return the register ID for alarm codes"""
        return "2A20"

    def get_runtime_register_ids(self) -> Dict[str, str]:
        """
        Return NIBE runtime counter register IDs.

        NIBE uses energy meters rather than traditional runtime counters.
        """
        return {
            'energy_total': '5C51',
            'energy_hotwater': '5C53',
            'energy_ventilation': '5C65',
        }

    def get_auxiliary_heat_config(self) -> Dict[str, Any]:
        """
        Return NIBE auxiliary heater configuration.

        NIBE uses percentage-based control with power monitoring.
        """
        return {
            'type': 'percentage',
            'register': '3104',
            'power_register': '9124',
            'max_setting_register': '9226',
            'max_power_kw': 9,
            'description': 'Tillsatsvärme med effektstyrning'
        }

    # =========================================================================
    # OPTIONAL METHODS - NIBE-specific features
    # =========================================================================

    def get_brand_specific_features(self) -> Dict[str, Any]:
        """
        Return NIBE-specific features for dashboard customization.

        Returns dictionary format consistent with other providers.
        """
        return {
            'degree_minutes': {
                'enabled': True,
                'register': '8255',
                'display_register': '8105',
                'description': 'Gradminuter för kompressorstyrning'
            },
            'smart_home_mode': {
                'enabled': True,
                'description': 'Smart Grid-funktionalitet'
            },
            'inverter_compressor': {
                'enabled': True,
                'speed_register': '9108',
                'description': 'Variabel kompressorhastighet'
            },
            'heat_curve_settings': {
                'enabled': True,
                'registers': {
                    'curve_1': '2205',
                    'offset_1': '2207',
                    'curve_2': '2222',
                    'offset_2': '2224'
                },
                'description': 'Avancerad värmekurvstyrning'
            },
            'dual_hotwater_sensors': {
                'enabled': True,
                'registers': {
                    'bt6_mid': '000A',
                    'bt7_top': '0009'
                },
                'description': 'BT6 och BT7 varmvattensensorer'
            },
            'energy_meters': {
                'enabled': True,
                'registers': self.get_runtime_register_ids(),
                'description': 'Energimätare per kategori'
            },
            'phase_current': {
                'enabled': True,
                'registers': {
                    'l1': '4101',
                    'l2': '4102',
                    'l3': '4103'
                },
                'description': 'Strömförbrukning per fas'
            }
        }

    def has_operating_mode(self) -> bool:
        """NIBE has operating mode register"""
        return True

    def get_operating_mode_register(self) -> Optional[str]:
        """Return operating mode register"""
        return '2201'

    def get_operating_modes(self) -> Dict[int, str]:
        """Return NIBE operating mode descriptions"""
        return {
            0: "Auto",
            1: "Manuell",
            2: "Endast tillsatsvärme"
        }

    def has_internal_heat_carrier_sensors(self) -> bool:
        """NIBE has internal heat carrier sensors"""
        return True

    def get_internal_heat_carrier_registers(self) -> Dict[str, str]:
        """Return internal heat carrier sensor registers"""
        return {
            'heat_carrier_return': '0003',
            'heat_carrier_forward': '0004'
        }

    def has_dual_hot_water_sensors(self) -> bool:
        """NIBE has dual hot water sensors (BT6 + BT7)"""
        return True

    def get_hot_water_registers(self) -> Dict[str, str]:
        """Return hot water sensor registers"""
        return {
            'warm_water_top': '0009',   # BT7
            'warm_water_mid': '000A'    # BT6
        }

    def has_hot_gas_sensor(self) -> bool:
        """NIBE has hot gas sensor"""
        return True

    def get_hot_gas_register(self) -> Optional[str]:
        """Return hot gas sensor register"""
        return '000B'

    def has_alarm_reset(self) -> bool:
        """NIBE supports alarm reset via register"""
        return True

    def get_alarm_reset_register(self) -> Optional[str]:
        """Return alarm reset register"""
        return '22F2'

    # =========================================================================
    # NIBE-SPECIFIC HELPER METHODS
    # =========================================================================

    def get_primary_sensors(self) -> Dict[str, str]:
        """
        Return mapping of primary sensor roles to register names.

        Returns:
            Dict mapping sensor role to register name
        """
        return {
            'outdoor': 'outdoor_temp',
            'indoor': 'indoor_temp',
            'radiator_forward': 'heat_carrier_forward',
            'radiator_return': 'radiator_return',
            'brine_in': 'brine_in_evaporator',
            'brine_out': 'brine_out_condenser',
            'hot_water': 'warm_water_top',
            'compressor': 'hot_gas_temp',
        }

    def get_status_registers(self) -> Dict[str, str]:
        """
        Return mapping of status roles to register names.

        Returns:
            Dict mapping status role to register name
        """
        return {
            'compressor': 'compressor_status',
            'brine_pump': 'brine_pump_status',
            'radiator_pump': 'radiator_pump_status',
            'switch_valve': 'switch_valve_status',
        }

    def get_sensor_description(self, sensor_name: str) -> str:
        """
        Get NIBE-specific sensor description with BT-numbering.

        Args:
            sensor_name: Register name

        Returns:
            Description string with NIBE sensor codes
        """
        descriptions = {
            'outdoor_temp': 'Utomhustemperatur (BT1)',
            'heat_carrier_forward': 'Framledning (BT2)',
            'heat_carrier_return': 'Retur (BT3)',
            'warm_water_mid': 'VV Laddning (BT6)',
            'warm_water_top': 'VV Topp (BT7)',
            'brine_in_evaporator': 'Köldbärare In (BT10)',
            'brine_out_condenser': 'Köldbärare Ut (BT11)',
            'hot_gas_temp': 'Kompressor (BT14)',
            'indoor_temp': 'Rumstemperatur (BT50)',
            'radiator_return': 'Radiator Retur (BT61)',
        }
        return descriptions.get(sensor_name, sensor_name)

    def format_operating_mode(self, mode_value: int) -> str:
        """
        Format operating mode value to human-readable string.

        Args:
            mode_value: Raw mode value from register

        Returns:
            Human-readable mode description
        """
        return self.get_operating_modes().get(mode_value, f"Okänt läge ({mode_value})")

    def validate_register_value(self, register_id: str, value: float) -> bool:
        """
        Validate if a register value is within expected range.

        NIBE-specific validation with tighter bounds.

        Args:
            register_id: Register identifier
            value: Value to validate

        Returns:
            True if value is valid
        """
        # Temperature sensors: -40 to 80°C
        temp_registers = ['0002', '0003', '0004', '0005', '0006', '0007', '0008', '0009', '000A', '000B', '000C']
        if register_id in temp_registers:
            return -40 <= value <= 80

        # Status registers: 0 or 1
        status_registers = ['1A01', '1A04', '1A05', '1A07', '1A0C']
        if register_id in status_registers:
            return value in [0, 1]

        # Percentage: 0-100
        percent_registers = ['3104', '9108']
        if register_id in percent_registers:
            return 0 <= value <= 100

        # Current (Amps): 0-100A
        current_registers = ['4101', '4102', '4103']
        if register_id in current_registers:
            return 0 <= value <= 100

        # Default: accept any value
        return True
