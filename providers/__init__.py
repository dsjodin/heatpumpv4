"""
Heat Pump Provider Factory
Provides brand-specific implementations for different heat pump manufacturers
"""

from typing import Optional
from .base import HeatPumpProvider


def get_provider(brand: str) -> HeatPumpProvider:
    """
    Factory function to get the appropriate provider for a brand

    Args:
        brand: Brand name ('thermia' or 'ivt')

    Returns:
        Provider instance for the specified brand

    Raises:
        ValueError: If brand is not supported
    """
    brand = brand.lower().strip()

    if brand == 'thermia':
        from .thermia.provider import ThermiaProvider
        return ThermiaProvider()
    elif brand == 'ivt':
        from .ivt.provider import IVTProvider
        return IVTProvider()
    elif brand == 'nibe':
        from .nibe.provider import NIBEProvider
        return NIBEProvider()
    else:
        raise ValueError(
            f"Unsupported brand: '{brand}'. "
            f"Supported brands: 'thermia', 'ivt', 'nibe'"
        )


def get_supported_brands():
    """
    Get list of supported brands

    Returns:
        List of supported brand names
    """
    return ['thermia', 'ivt', 'nibe']


__all__ = ['get_provider', 'get_supported_brands', 'HeatPumpProvider']
