"""
Base Provider Class for Heat Pump Brands
Abstract base class that all brand-specific providers must implement
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class HeatPumpProvider(ABC):
    """Abstract base class for heat pump brand providers"""

    def __init__(self):
        """Initialize provider"""
        self.brand_name = self.get_brand_name()
        self.registers = self.get_registers()
        self.alarm_codes = self.get_alarm_codes()

    @abstractmethod
    def get_brand_name(self) -> str:
        """
        Return the brand name

        Returns:
            Brand name (e.g., 'thermia', 'ivt')
        """
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        """
        Return the display name for the brand

        Returns:
            Display name (e.g., 'Thermia Diplomat', 'IVT Greenline')
        """
        pass

    @abstractmethod
    def get_registers(self) -> Dict[str, Any]:
        """
        Return register definitions for this brand

        Returns:
            Dictionary of register definitions with format:
            {
                "0001": {
                    "name": "radiator_return",
                    "unit": "°C",
                    "type": "temperature",
                    "description": "Radiator return temperature"
                },
                ...
            }
        """
        pass

    @abstractmethod
    def get_alarm_codes(self) -> Dict[int, str]:
        """
        Return alarm code definitions for this brand

        Returns:
            Dictionary mapping alarm codes to descriptions
            {
                0: "No alarm",
                10: "HP - High pressure",
                ...
            }
        """
        pass

    @abstractmethod
    def get_alarm_register_id(self) -> str:
        """
        Return the register ID for alarm codes

        Returns:
            Register ID (e.g., '2A91' for Thermia, 'BA91' for IVT)
        """
        pass

    @abstractmethod
    def get_dashboard_title(self) -> str:
        """
        Return the dashboard title

        Returns:
            Dashboard title (e.g., 'Thermia Heat Pump Monitor')
        """
        pass

    def get_common_sensors(self) -> Dict[str, List[str]]:
        """
        Return common sensors available across all brands

        Returns:
            Dictionary grouping common sensor register IDs
        """
        return {
            'temperatures': ['0001', '0002', '0005', '0006', '0007', '0008', '0009'],
            'status': ['1A01', '1A04', '1A06', '1A07', '1A20'],
            'setpoints': ['0107', '0203']
        }

    def has_register(self, register_id: str) -> bool:
        """
        Check if this provider supports a specific register

        Args:
            register_id: Register ID to check

        Returns:
            True if register is supported
        """
        return register_id.upper() in self.registers

    def get_register_info(self, register_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific register

        Args:
            register_id: Register ID

        Returns:
            Register info dictionary or None if not found
        """
        return self.registers.get(register_id.upper())

    def get_registers_by_type(self, register_type: str) -> Dict[str, Any]:
        """
        Get all registers of a specific type

        Args:
            register_type: Type of registers (e.g., 'temperature', 'status')

        Returns:
            Dictionary of registers matching the type
        """
        return {
            reg_id: reg_info
            for reg_id, reg_info in self.registers.items()
            if reg_info.get('type') == register_type
        }

    @abstractmethod
    def get_runtime_register_ids(self) -> Dict[str, str]:
        """
        Return runtime counter register IDs

        Returns:
            Dictionary mapping runtime types to register IDs
            Example for Thermia:
            {
                'compressor_total': '6C60',
                'aux_3kw': '6C63',
                'hot_water': '6C64',
                'aux_6kw': '6C66'
            }

            Example for IVT:
            {
                'compressor_heating': '6C55',
                'compressor_hotwater': '6C56',
                'aux_heating': '6C58',
                'aux_hotwater': '6C59'
            }
        """
        pass

    @abstractmethod
    def get_auxiliary_heat_config(self) -> Dict[str, Any]:
        """
        Return auxiliary heater configuration

        Returns:
            Dictionary describing auxiliary heater setup
            Example for Thermia:
            {
                'type': 'percentage',
                'register': '3104',
                'max_power_kw': 9
            }

            Example for IVT:
            {
                'type': 'steps',
                'percentage_register': '3104',
                'step1_register': '1A02',
                'step1_power_kw': 3,
                'step2_register': '1A03',
                'step2_power_kw': 6
            }
        """
        pass

    def get_brand_specific_registers(self) -> List[str]:
        """
        Return list of brand-specific register IDs not in common sensors

        Returns:
            List of register IDs
        """
        common = set()
        for sensor_list in self.get_common_sensors().values():
            common.update(sensor_list)

        return [
            reg_id for reg_id in self.registers.keys()
            if reg_id not in common
        ]
