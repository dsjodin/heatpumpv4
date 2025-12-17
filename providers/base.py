"""
Base Provider Class for Heat Pump Brands
Abstract base class that all brand-specific providers must implement.

To add a new brand:
1. Create a new directory: providers/<brand>/
2. Create provider.py with a class named <Brand>Provider (e.g., BoschProvider)
3. The class must inherit from HeatPumpProvider and implement all abstract methods
4. Create registers.py with register definitions
5. Create alarms.py with alarm code definitions
6. The factory will auto-discover your provider - no code changes needed elsewhere!
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class HeatPumpProvider(ABC):
    """
    Abstract base class for heat pump brand providers.

    All brand-specific providers must inherit from this class and implement
    the abstract methods. Optional methods have default implementations that
    can be overridden if the brand supports those features.
    """

    def __init__(self):
        """Initialize provider and cache commonly used data"""
        self._brand_name = self.get_brand_name()
        self._registers = None  # Lazy loaded
        self._alarm_codes = None  # Lazy loaded

    @property
    def brand_name(self) -> str:
        """Brand name property (cached)"""
        return self._brand_name

    @property
    def registers(self) -> Dict[str, Any]:
        """Register definitions (lazy loaded and cached)"""
        if self._registers is None:
            self._registers = self.get_registers()
        return self._registers

    @property
    def alarm_codes(self) -> Dict[int, str]:
        """Alarm codes (lazy loaded and cached)"""
        if self._alarm_codes is None:
            self._alarm_codes = self.get_alarm_codes()
        return self._alarm_codes

    # =========================================================================
    # REQUIRED ABSTRACT METHODS - Must be implemented by all providers
    # =========================================================================

    @abstractmethod
    def get_brand_name(self) -> str:
        """
        Return the internal brand identifier (lowercase).
        Used for configuration and factory lookup.

        Returns:
            Brand name (e.g., 'thermia', 'ivt', 'nibe', 'bosch')
        """
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        """
        Return the human-readable brand name for UI display.

        Returns:
            Display name (e.g., 'Thermia Diplomat', 'IVT Greenline', 'NIBE Fighter')
        """
        pass

    @abstractmethod
    def get_registers(self) -> Dict[str, Any]:
        """
        Return register definitions for this brand.

        Each register should have at minimum:
        - name: Internal metric name (e.g., 'radiator_return')
        - unit: Unit of measurement (e.g., '°C', '%', '')
        - type: Category (e.g., 'temperature', 'status', 'alarm', 'runtime')
        - description: Human-readable description

        Returns:
            Dictionary of register definitions:
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
        Return alarm code definitions for this brand.

        Returns:
            Dictionary mapping alarm codes to descriptions:
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
        Return the register ID that contains the alarm code.

        Returns:
            Register ID (e.g., '2A91' for Thermia, 'BA91' for IVT, '2A20' for NIBE)
        """
        pass

    @abstractmethod
    def get_dashboard_title(self) -> str:
        """
        Return the dashboard page title.

        Returns:
            Dashboard title (e.g., 'Thermia Heat Pump Monitor')
        """
        pass

    @abstractmethod
    def get_runtime_register_ids(self) -> Dict[str, str]:
        """
        Return runtime counter register IDs.

        Returns:
            Dictionary mapping runtime types to register IDs.

            Example for Thermia (combined counters):
            {
                'compressor_total': '6C60',
                'aux_3kw': '6C63',
                'hot_water': '6C64',
                'aux_6kw': '6C66'
            }

            Example for IVT (split by heating/hotwater):
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
        Return auxiliary heater configuration.

        Returns:
            Dictionary describing auxiliary heater setup.

            Example for percentage-based (Thermia):
            {
                'type': 'percentage',
                'register': '3104',
                'max_power_kw': 9,
                'description': 'Auxiliary electrical heater'
            }

            Example for step-based (IVT):
            {
                'type': 'steps',
                'percentage_register': '3104',
                'step1_register': '1A02',
                'step1_power_kw': 3,
                'step2_register': '1A03',
                'step2_power_kw': 6,
                'max_power_kw': 9,
                'description': 'Auxiliary heater with 2 steps'
            }
        """
        pass

    # =========================================================================
    # OPTIONAL METHODS - Default implementations, override if brand supports
    # =========================================================================

    def get_brand_specific_features(self) -> Dict[str, Any]:
        """
        Return brand-specific features for dashboard customization.

        Override this to expose features unique to your brand.

        Returns:
            Dictionary of features with their configuration:
            {
                'feature_name': {
                    'enabled': True/False,
                    'register': 'XXXX',  # or 'registers': {...}
                    'description': 'Feature description',
                    ...additional config...
                },
                ...
            }
        """
        return {}

    def has_pump_speed_control(self) -> bool:
        """Does this brand support variable speed pump control?"""
        return False

    def get_pump_speed_registers(self) -> Dict[str, str]:
        """
        Return pump speed control registers if supported.

        Returns:
            Dictionary mapping pump type to register ID:
            {'circulation_pump': '3109', 'brine_pump': '3110'}
        """
        return {}

    def has_operating_mode(self) -> bool:
        """Does this brand have an operating mode register?"""
        return False

    def get_operating_mode_register(self) -> Optional[str]:
        """Return operating mode register ID if supported."""
        return None

    def get_operating_modes(self) -> Dict[int, str]:
        """
        Return operating mode descriptions.

        Returns:
            Dictionary mapping mode values to descriptions:
            {0: "Off", 1: "Auto", 2: "Manual", ...}
        """
        return {}

    def has_cooling(self) -> bool:
        """Does this brand support cooling mode?"""
        return False

    def has_internal_heat_carrier_sensors(self) -> bool:
        """Does this brand have internal heat carrier temperature sensors?"""
        return False

    def get_internal_heat_carrier_registers(self) -> Dict[str, str]:
        """Return internal heat carrier sensor registers if supported."""
        return {}

    def has_dual_hot_water_sensors(self) -> bool:
        """Does this brand support dual hot water sensors?"""
        return False

    def get_hot_water_registers(self) -> Dict[str, str]:
        """Return hot water sensor registers."""
        return {'hot_water_top': '0009'}

    def has_hot_gas_sensor(self) -> bool:
        """Does this brand have a hot gas/compressor temperature sensor?"""
        return False

    def get_hot_gas_register(self) -> Optional[str]:
        """Return hot gas sensor register ID if supported."""
        return None

    def has_holiday_mode(self) -> bool:
        """Does this brand support holiday mode?"""
        return False

    def get_holiday_mode_register(self) -> Optional[str]:
        """Return holiday mode register ID if supported."""
        return None

    def has_summer_mode(self) -> bool:
        """Does this brand support summer mode?"""
        return False

    def get_summer_mode_register(self) -> Optional[str]:
        """Return summer mode temperature register if supported."""
        return None

    def has_extra_hot_water_mode(self) -> bool:
        """Does this brand support extra hot water boost mode?"""
        return False

    def get_extra_hot_water_register(self) -> Optional[str]:
        """Return extra hot water timer register if supported."""
        return None

    def has_alarm_reset(self) -> bool:
        """Does this brand support alarm reset via register?"""
        return False

    def get_alarm_reset_register(self) -> Optional[str]:
        """Return alarm reset register ID if supported."""
        return None

    def supports_write(self) -> bool:
        """Does this provider support writing to registers?"""
        return False

    def get_writable_registers(self) -> List[str]:
        """Return list of register IDs that support write operations."""
        return []

    # =========================================================================
    # UTILITY METHODS - Common functionality for all providers
    # =========================================================================

    def get_common_sensors(self) -> Dict[str, List[str]]:
        """
        Return common sensor register IDs available across most brands.

        Returns:
            Dictionary grouping common sensor register IDs by category.
        """
        return {
            'temperatures': ['0001', '0002', '0005', '0006', '0007', '0008', '0009'],
            'status': ['1A01', '1A04', '1A06', '1A07', '1A20'],
            'setpoints': ['0107', '0203']
        }

    def has_register(self, register_id: str) -> bool:
        """
        Check if this provider supports a specific register.

        Args:
            register_id: Register ID to check

        Returns:
            True if register is supported
        """
        return register_id.upper() in self.registers

    def get_register_info(self, register_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific register.

        Args:
            register_id: Register ID

        Returns:
            Register info dictionary or None if not found
        """
        return self.registers.get(register_id.upper())

    def get_registers_by_type(self, register_type: str) -> Dict[str, Any]:
        """
        Get all registers of a specific type.

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

    def get_brand_specific_registers(self) -> List[str]:
        """
        Return list of brand-specific register IDs not in common sensors.

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

    def get_alarm_description(self, code: int) -> str:
        """
        Get alarm description from code.

        Args:
            code: Alarm code

        Returns:
            Alarm description string
        """
        return self.alarm_codes.get(code, f"Unknown alarm: {code}")

    def validate_register_value(self, register_id: str, value: float) -> bool:
        """
        Validate if a register value is within expected range.
        Override in subclass for brand-specific validation.

        Args:
            register_id: Register identifier
            value: Value to validate

        Returns:
            True if value is valid
        """
        reg_info = self.get_register_info(register_id)
        if not reg_info:
            return True  # Unknown register, accept any value

        reg_type = reg_info.get('type', '')

        # Basic validation by type
        if reg_type == 'temperature':
            return -50 <= value <= 100
        elif reg_type == 'status':
            return value in [0, 1]
        elif reg_type == 'percentage':
            return 0 <= value <= 100

        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(brand='{self.brand_name}')>"
