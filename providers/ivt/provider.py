"""
IVT Provider Implementation
Provider for IVT Greenline heat pumps with Rego 600/637 controllers
"""

from typing import Dict, Any
from ..base import HeatPumpProvider
from .registers import IVT_REGISTERS
from .alarms import IVT_ALARM_CODES


class IVTProvider(HeatPumpProvider):
    """Provider implementation for IVT Greenline heat pumps"""

    def get_brand_name(self) -> str:
        """Return brand name"""
        return "ivt"

    def get_display_name(self) -> str:
        """Return display name"""
        return "IVT Greenline"

    def get_registers(self) -> Dict[str, Any]:
        """Return IVT register definitions"""
        return IVT_REGISTERS

    def get_alarm_codes(self) -> Dict[int, str]:
        """Return IVT alarm codes"""
        return IVT_ALARM_CODES

    def get_alarm_register_id(self) -> str:
        """Return alarm code register ID for IVT"""
        return "BA91"

    def get_dashboard_title(self) -> str:
        """Return dashboard title"""
        return "IVT Greenline Monitor"

    def get_runtime_register_ids(self) -> Dict[str, str]:
        """
        Return IVT runtime counter register IDs

        IVT splits runtime counters by heating and hot water production
        """
        return {
            'compressor_heating': '6C55',
            'compressor_hotwater': '6C56',
            'aux_heating': '6C58',
            'aux_hotwater': '6C59'
        }

    def get_auxiliary_heat_config(self) -> Dict[str, Any]:
        """
        Return IVT auxiliary heater configuration

        IVT uses both percentage (3104) and individual step control (1A02, 1A03)
        """
        return {
            'type': 'steps',
            'percentage_register': '3104',
            'step1_register': '1A02',
            'step1_power_kw': 3,
            'step2_register': '1A03',
            'step2_power_kw': 6,
            'max_power_kw': 9,
            'description': 'Auxiliary electrical heater with 2 steps (3kW + 6kW)'
        }

    def has_pump_speed_control(self) -> bool:
        """IVT does not have variable speed pump control"""
        return False

    def has_operating_mode(self) -> bool:
        """IVT does not have explicit operating mode register"""
        return False

    def has_cooling(self) -> bool:
        """IVT typically does not support cooling"""
        return False

    def has_internal_heat_carrier_sensors(self) -> bool:
        """IVT has internal heat carrier temperature sensors"""
        return True

    def get_internal_heat_carrier_registers(self) -> Dict[str, str]:
        """Return internal heat carrier sensor registers"""
        return {
            'heat_carrier_return': '0003',
            'heat_carrier_forward': '0004'
        }

    def has_dual_hot_water_sensors(self) -> bool:
        """IVT can have dual hot water sensors (internal + external tank)"""
        return True

    def get_hot_water_registers(self) -> Dict[str, str]:
        """Return hot water sensor registers"""
        return {
            'hot_water_top': '0009',  # Internal tank
            'warm_water_2_mid': '000A'   # External tank (if installed)
        }

    def has_hot_gas_sensor(self) -> bool:
        """IVT has hot gas sensor"""
        return True

    def get_hot_gas_register(self) -> str:
        """Return hot gas sensor register"""
        return '000B'

    def has_holiday_mode(self) -> bool:
        """IVT supports holiday mode"""
        return True

    def get_holiday_mode_register(self) -> str:
        """Return holiday mode register"""
        return '2210'

    def has_summer_mode(self) -> bool:
        """IVT supports summer mode"""
        return True

    def get_summer_mode_register(self) -> str:
        """Return summer mode temperature setting register"""
        return '020A'

    def has_extra_hot_water_mode(self) -> bool:
        """IVT supports extra hot water mode"""
        return True

    def get_extra_hot_water_register(self) -> str:
        """Return extra hot water timer register"""
        return '7209'

    def has_alarm_reset(self) -> bool:
        """IVT supports alarm reset via register"""
        return True

    def get_alarm_reset_register(self) -> str:
        """Return alarm reset register"""
        return '12F2'

    def get_brand_specific_features(self) -> Dict[str, Any]:
        """
        Return IVT-specific features for dashboard

        Returns features that are unique to IVT or should be
        displayed in a brand-specific way
        """
        return {
            'internal_heat_carrier': {
                'enabled': True,
                'registers': self.get_internal_heat_carrier_registers()
            },
            'dual_hot_water': {
                'enabled': True,
                'registers': self.get_hot_water_registers()
            },
            'hot_gas_sensor': {
                'enabled': True,
                'register': self.get_hot_gas_register()
            },
            'auxiliary_heat_steps': {
                'enabled': True,
                'step1_register': '1A02',
                'step2_register': '1A03',
                'percentage_register': '3104'
            },
            'runtime_split': {
                'enabled': True,
                'description': 'Runtime counters split by heating/hotwater',
                'registers': self.get_runtime_register_ids()
            },
            'holiday_mode': {
                'enabled': True,
                'register': self.get_holiday_mode_register()
            },
            'summer_mode': {
                'enabled': True,
                'register': self.get_summer_mode_register()
            },
            'extra_hot_water': {
                'enabled': True,
                'register': self.get_extra_hot_water_register()
            },
            'alarm_reset': {
                'enabled': True,
                'register': self.get_alarm_reset_register(),
                'description': 'Can reset alarms via register write'
            }
        }
