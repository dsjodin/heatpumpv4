#!/usr/bin/env python3
"""
Heat Pump Data Collector - API Only
Polls H60/H66 Gateway API for all sensor data and stores in InfluxDB

Features:
- Perfect timestamp synchronization (all sensors get identical timestamp)
- No chart gaps (single API call fetches all data)
- Raw integer values stored in InfluxDB
- Simple, reliable polling architecture

Usage:
    export H66_IP="192.168.1.100"
    export COLLECTION_INTERVAL="30"  # seconds
    python3 collector.py
"""

import os
import sys
import time
import logging
import requests
import yaml
from datetime import datetime
from typing import Dict, Any, Optional

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Add parent directory to path for provider imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers import get_provider

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_brand_from_config() -> str:
    """Load brand from config.yaml, falling back to environment variable"""
    config_path = '/app/config.yaml'
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            brand = config.get('brand', 'thermia')
            logger.info(f"Loaded brand '{brand}' from config.yaml")
            return brand
    except Exception as e:
        logger.warning(f"Could not read config.yaml: {e}")

    # Fallback to environment variable
    brand = os.getenv('HEATPUMP_BRAND', 'thermia')
    logger.info(f"Using brand '{brand}' from environment variable")
    return brand


class HeatPumpAPICollector:
    """API-based collector for heat pump data with perfect synchronization"""

    def __init__(self, h66_ip: str = None, interval: int = 30):
        """
        Initialize the API collector

        Args:
            h66_ip: IP address of H66 gateway (or from H66_IP env var)
            interval: Polling interval in seconds (default: 30)
        """
        self.h66_ip = h66_ip or os.getenv('H66_IP')
        if not self.h66_ip:
            raise ValueError("H66_IP must be provided or set in environment")

        self.api_url = f"http://{self.h66_ip}/api/alldata"
        self.interval = interval
        self.influx_client = None
        self.write_api = None

        # Get brand-specific provider (reads from config.yaml first, then env var)
        brand = load_brand_from_config()
        try:
            self.provider = get_provider(brand)
            logger.info(f"Loaded provider for brand: {self.provider.get_display_name()}")
        except ValueError as e:
            logger.error(f"Failed to load provider: {e}")
            raise

        # Get register mappings
        self.registers = self.provider.get_registers()

        # Setup InfluxDB
        self._setup_influxdb()

    def _setup_influxdb(self):
        """Setup InfluxDB client and write API"""
        try:
            url = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
            token = os.getenv('INFLUXDB_TOKEN')
            org = os.getenv('INFLUXDB_ORG', 'thermia')
            self.bucket = os.getenv('INFLUXDB_BUCKET', 'heatpump')

            if not token:
                raise ValueError("INFLUXDB_TOKEN environment variable must be set")

            self.influx_client = InfluxDBClient(url=url, token=token, org=org)
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

            # Test connection
            health = self.influx_client.health()
            logger.info(f"InfluxDB connection established: {health.status}")

        except Exception as e:
            logger.error(f"Failed to setup InfluxDB: {e}")
            raise

    def fetch_all_data(self) -> Dict[str, int]:
        """
        Fetch all sensor data from H66 API

        Returns:
            Dictionary mapping register IDs to raw integer values

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            logger.debug(f"Fetching data from {self.api_url}")
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Received {len(data)} register values from API")

            # Store raw values as integers (no division by 10)
            # Dashboard will handle conversion when displaying
            processed_data = {}
            for register_id, raw_value in data.items():
                register_id_upper = register_id.upper()

                # Check if we know this register
                if register_id_upper not in self.registers:
                    logger.debug(f"Unknown register: {register_id_upper}")
                    continue

                # Store all values as integers (raw from API)
                processed_data[register_id_upper] = int(raw_value)

            return processed_data

        except requests.RequestException as e:
            logger.error(f"Failed to fetch data from API: {e}")
            raise

    def _convert_value(self, raw_value: int, register_info: Dict[str, Any]) -> float:
        """
        Convert raw register value to actual value based on type.

        Most temperature values from heat pumps are stored as integers
        multiplied by 10 (e.g., 305 = 30.5°C). This method converts them
        to actual values before storing in InfluxDB.

        Args:
            raw_value: Raw integer value from API
            register_info: Register definition with type info

        Returns:
            Converted float value
        """
        reg_type = register_info.get('type', '')
        reg_name = register_info.get('name', '')

        # Values that should NOT be divided (already in correct units)
        no_division_types = ['status', 'alarm', 'runtime', 'power', 'energy']
        no_division_names = [
            'compressor_status', 'brine_pump_status', 'radiator_pump_status',
            'pump_cold_circuit', 'pump_heat_circuit', 'pump_radiator',
            'switch_valve_status', 'switch_valve_1', 'alarm_status', 'alarm_code',
            'add_heat_step_1', 'add_heat_step_2',
            'power_consumption', 'accumulated_energy',  # Already in W/kWh
            'compressor_runtime_heating', 'compressor_runtime_hotwater',
            'aux_runtime_heating', 'aux_runtime_hotwater'
        ]

        # Check if this value should NOT be divided
        if reg_type in no_division_types or reg_name in no_division_names:
            return float(raw_value)

        # Temperature, percentage, and most other values: divide by 10
        return raw_value / 10.0

    def store_data(self, data: Dict[str, int], timestamp: datetime):
        """
        Store all sensor data in InfluxDB with the same timestamp

        Args:
            data: Dictionary mapping register IDs to raw integer values
            timestamp: Single timestamp for ALL values (perfect sync!)
        """
        try:
            points = []

            for register_id, value in data.items():
                register_info = self.registers[register_id]

                # Convert raw value to actual value
                converted_value = self._convert_value(value, register_info)

                # Create InfluxDB point with converted value
                point = Point("heatpump") \
                    .tag("register_id", register_id) \
                    .tag("name", register_info['name']) \
                    .tag("type", register_info['type']) \
                    .field("value", converted_value) \
                    .time(timestamp)

                # Add unit as tag if present
                if register_info.get('unit'):
                    point = point.tag("unit", register_info['unit'])

                points.append(point)

            # Write all points at once
            self.write_api.write(bucket=self.bucket, record=points)
            logger.info(f"Stored {len(points)} metrics with timestamp {timestamp.isoformat()}")

        except Exception as e:
            logger.error(f"Error storing data to InfluxDB: {e}")
            raise

    def collect_once(self):
        """
        Perform one collection cycle: fetch from API and store to InfluxDB

        This is the core operation - all sensors get the SAME timestamp!
        """
        try:
            # Single timestamp for ALL values - perfect synchronization!
            timestamp = datetime.utcnow()

            # Fetch all data from API in one request
            data = self.fetch_all_data()

            if not data:
                logger.warning("No data received from API")
                return

            # Store all data with the same timestamp
            self.store_data(data, timestamp)

            logger.debug(f"Collection cycle complete: {len(data)} sensors synchronized")

        except Exception as e:
            logger.error(f"Collection cycle failed: {e}")

    def run(self):
        """
        Main run loop - polls API at specified interval

        This replaces the MQTT-based collector with perfect timestamp sync
        """
        logger.info(f"Starting Heat Pump API Collector for {self.provider.get_display_name()}")
        logger.info(f"H66 Gateway: {self.h66_ip}")
        logger.info(f"Polling interval: {self.interval} seconds")
        logger.info(f"Monitoring {len(self.registers)} registers")
        logger.info("All sensors will be synchronized to identical timestamps!")

        # Initial collection
        logger.info("Performing initial data collection...")
        self.collect_once()

        # Main loop
        try:
            while True:
                time.sleep(self.interval)
                self.collect_once()

        except KeyboardInterrupt:
            logger.info("Collector stopped by user")
        except Exception as e:
            logger.error(f"Collector crashed: {e}")
            raise
        finally:
            if self.influx_client:
                self.influx_client.close()
            logger.info("InfluxDB connection closed")


def main():
    """Entry point for API collector"""
    # Get configuration from environment
    h66_ip = os.getenv('H66_IP')
    interval = int(os.getenv('COLLECTION_INTERVAL', '30'))

    if not h66_ip:
        logger.error("H66_IP environment variable must be set")
        logger.error("Example: export H66_IP=192.168.1.100")
        sys.exit(1)

    # Create and run collector
    collector = HeatPumpAPICollector(h66_ip=h66_ip, interval=interval)
    collector.run()


if __name__ == '__main__':
    main()
