"""
Heat Pump Provider Factory
Auto-discovers and provides brand-specific implementations for different heat pump manufacturers.

To add a new brand:
1. Create a new directory: providers/<brand>/
2. Create provider.py with a class named <Brand>Provider (e.g., BoschProvider)
   - The class must inherit from HeatPumpProvider
   - Implement all abstract methods
3. Create registers.py with register definitions
4. Create alarms.py with alarm code definitions
5. Done! The factory will auto-discover your provider.

No changes to this file are required when adding new brands.
"""

import importlib
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Type

from .base import HeatPumpProvider

logger = logging.getLogger(__name__)

# Cache for discovered providers
_provider_cache: Dict[str, Type[HeatPumpProvider]] = {}
_discovery_done: bool = False


def _discover_providers() -> Dict[str, Type[HeatPumpProvider]]:
    """
    Auto-discover all available providers by scanning the providers directory.

    Looks for directories containing a provider.py file with a class
    that inherits from HeatPumpProvider.

    Returns:
        Dictionary mapping brand names to provider classes
    """
    global _provider_cache, _discovery_done

    if _discovery_done:
        return _provider_cache

    providers_dir = Path(__file__).parent

    for item in providers_dir.iterdir():
        # Skip non-directories and special directories
        if not item.is_dir() or item.name.startswith('_'):
            continue

        # Check for provider.py in the directory
        provider_file = item / 'provider.py'
        if not provider_file.exists():
            continue

        brand_name = item.name.lower()

        try:
            # Import the provider module
            module = importlib.import_module(f'providers.{brand_name}.provider')

            # Find the provider class (look for class ending with 'Provider')
            provider_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, HeatPumpProvider) and
                    attr is not HeatPumpProvider and
                    attr_name.endswith('Provider')):
                    provider_class = attr
                    break

            if provider_class:
                _provider_cache[brand_name] = provider_class
                logger.debug(f"Discovered provider: {brand_name} -> {provider_class.__name__}")
            else:
                logger.warning(f"No provider class found in providers/{brand_name}/provider.py")

        except Exception as e:
            logger.warning(f"Failed to load provider '{brand_name}': {e}")

    _discovery_done = True
    logger.info(f"Provider discovery complete. Found: {list(_provider_cache.keys())}")
    return _provider_cache


def get_provider(brand: str) -> HeatPumpProvider:
    """
    Factory function to get the appropriate provider for a brand.

    Uses auto-discovery to find available providers - no hardcoding required.

    Args:
        brand: Brand name (e.g., 'thermia', 'ivt', 'nibe')

    Returns:
        Provider instance for the specified brand

    Raises:
        ValueError: If brand is not supported

    Example:
        >>> provider = get_provider('thermia')
        >>> print(provider.get_display_name())
        'Thermia Diplomat'
    """
    brand = brand.lower().strip()
    providers = _discover_providers()

    if brand not in providers:
        supported = ', '.join(sorted(providers.keys()))
        raise ValueError(
            f"Unsupported brand: '{brand}'. "
            f"Supported brands: {supported}"
        )

    provider_class = providers[brand]
    return provider_class()


def get_supported_brands() -> List[str]:
    """
    Get list of supported brands (auto-discovered).

    Returns:
        Sorted list of supported brand names
    """
    providers = _discover_providers()
    return sorted(providers.keys())


def is_brand_supported(brand: str) -> bool:
    """
    Check if a brand is supported.

    Args:
        brand: Brand name to check

    Returns:
        True if brand is supported
    """
    providers = _discover_providers()
    return brand.lower().strip() in providers


def get_provider_class(brand: str) -> Optional[Type[HeatPumpProvider]]:
    """
    Get the provider class (not instance) for a brand.

    Useful for inspection or custom instantiation.

    Args:
        brand: Brand name

    Returns:
        Provider class or None if not found
    """
    providers = _discover_providers()
    return providers.get(brand.lower().strip())


def reload_providers() -> None:
    """
    Force re-discovery of providers.

    Useful after dynamically adding new provider packages.
    """
    global _provider_cache, _discovery_done
    _provider_cache = {}
    _discovery_done = False
    _discover_providers()


__all__ = [
    'HeatPumpProvider',
    'get_provider',
    'get_supported_brands',
    'is_brand_supported',
    'get_provider_class',
    'reload_providers',
]
