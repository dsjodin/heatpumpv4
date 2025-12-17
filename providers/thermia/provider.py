"""
Thermia Provider Implementation
Provider for Thermia Diplomat heat pumps
"""

from typing import Dict, Any
from ..base import HeatPumpProvider
from .registers import THERMIA_REGISTERS
from .alarms import THERMIA_ALARM_CODES


class ThermiaProvider(HeatPumpProvider):
    """Provider implementation for Thermia Diplomat heat pumps"""

    def get_brand_name(self) -> str:
        """Return brand name"""
        return "thermia"

    def get_display_name(self) -> str:
        """Return display name"""
        return "Thermia Diplomat"

    def get_registers(self) -> Dict[str, Any]:
        """Return Thermia register definitions"""
        return THERMIA_REGISTERS

    def get_alarm_codes(self) -> Dict[int, str]:
        """Return Thermia alarm codes"""
        return THERMIA_ALARM_CODES

    def get_alarm_register_id(self) -> str:
        """Return alarm code register ID for Thermia"""
        return "2A91"

    def get_dashboard_title(self) -> str:
        """Return dashboard title"""
        return "Thermia Heat Pump Monitor"

    def get_runtime_register_ids(self) -> Dict[str, str]:
        """
        Return Thermia runtime counter register IDs

        Thermia has total runtime counters (not split by heating/hotwater)
        """
        return {
            'compressor_total': '6C60',
            'aux_3kw': '6C63',
            'hot_water': '6C64',
            'aux_6kw': '6C66'
        }

    def get_auxiliary_heat_config(self) -> Dict[str, Any]:
        """
        Return Thermia auxiliary heater configuration

        Thermia uses a percentage value (0-100%) for auxiliary heat
        """
        return {
            'type': 'percentage',
            'register': '3104',
            'max_power_kw': 9,
            'description': 'Auxiliary electrical heater (typically 9kW max)'
        }

    def has_pump_speed_control(self) -> bool:
        """Thermia has variable speed pump control"""
        return True

    def get_pump_speed_registers(self) -> Dict[str, str]:
        """Return pump speed control registers"""
        return {
            'circulation_pump': '3109',
            'brine_pump': '3110'
        }

    def has_operating_mode(self) -> bool:
        """Thermia has operating mode selection"""
        return True

    def get_operating_mode_register(self) -> str:
        """Return operating mode register"""
        return '2201'

    def get_operating_modes(self) -> Dict[int, str]:
        """Return operating mode descriptions"""
        return {
            0: "Alla av",
            1: "Auto",
            2: "Normal",
            3: "Endast tillsatsvärme",
            4: "Endast varmvatten"
        }

    def has_cooling(self) -> bool:
        """Thermia supports cooling (if installed)"""
        return True

    def get_brand_specific_features(self) -> Dict[str, Any]:
        """
        Return Thermia-specific features for dashboard

        Returns features that are unique to Thermia or should be
        displayed in a brand-specific way
        """
        return {
            'pump_speeds': {
                'enabled': True,
                'registers': self.get_pump_speed_registers()
            },
            'operating_mode': {
                'enabled': True,
                'register': self.get_operating_mode_register(),
                'modes': self.get_operating_modes()
            },
            'cooling': {
                'enabled': True,
                'temp_register': '0013',
                'setpoint_register': '0214'
            },
            'pressure_tube': {
                'enabled': True,
                'register': '0012'
            },
            'power_monitoring': {
                'enabled': True,
                'power_register': 'CFAA',
                'energy_register': '5FAB'
            }
        }
