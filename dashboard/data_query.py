"""
Heat Pump Data Query & Calculations - Multi-Brand Support
Handles all InfluxDB queries and advanced calculations
Supports: Thermia, IVT, NIBE (auto-discovered providers)

FEATURES:
1. Brand-aware alarm codes (from provider)
2. Brand-aware status field detection (from provider)
3. InfluxDB-side pivot for wide format (no pandas pivot needed)
4. Varmvattenberäkning med verklig effekt under cykler
5. Flexibel aggregering baserat på tidsperiod
6. Bättre tidshantering i alla beräkningar
"""

import os
import sys
import time
import logging
import yaml
import warnings
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction

# Suppress InfluxDB pivot warnings (we handle pivoting ourselves)
warnings.simplefilter("ignore", MissingPivotFunction)

# Add parent directory to path for provider imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers import get_provider

logger = logging.getLogger(__name__)


class HeatPumpDataQuery:
    """Query data from InfluxDB with advanced calculations"""

    def __init__(self, config_path: str = '/app/config.yaml'):
        """Initialize InfluxDB client and load provider"""
        self.url = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
        self.token = os.getenv('INFLUXDB_TOKEN')
        self.org = os.getenv('INFLUXDB_ORG', 'thermia')
        self.bucket = os.getenv('INFLUXDB_BUCKET', 'heatpump')
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.query_api = self.client.query_api()

        # Load provider and settings based on config
        self.provider, self.cop_flow_factor, self.hw_min_cycle_minutes = self._load_provider_and_settings(config_path)
        self.alarm_codes = self.provider.get_alarm_codes()
        self.alarm_register_id = self.provider.get_alarm_register_id()
        logger.info(f"Data query initialized for {self.provider.get_display_name()}, COP flow factor: {self.cop_flow_factor}, HW min cycle: {self.hw_min_cycle_minutes} min")

    def _load_provider_and_settings(self, config_path: str):
        """Load provider and settings from config"""
        cop_flow_factor = 2.7  # Default: ~0.65 L/s flow rate
        hw_min_cycle_minutes = 2  # Default: 2 minutes minimum

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                brand = config.get('brand', 'thermia')

                # Load COP settings
                cop_config = config.get('cop', {})
                cop_flow_factor = cop_config.get('flow_factor', 2.7)

                # Load hot water settings
                hw_config = config.get('hot_water', {})
                hw_min_cycle_minutes = hw_config.get('min_cycle_minutes', 2)
            else:
                brand = os.getenv('HEATPUMP_BRAND', 'thermia')

            return get_provider(brand), cop_flow_factor, hw_min_cycle_minutes
        except Exception as e:
            logger.warning(f"Failed to load provider from config: {e}, defaulting to Thermia")
            from providers.thermia.provider import ThermiaProvider
            return ThermiaProvider(), cop_flow_factor, hw_min_cycle_minutes
    
    def _get_aggregation_window(self, time_range: str) -> str:
        """
        NYTT: Dynamisk aggregering baserat på tidsperiod

        Returnerar lämpligt aggregeringsfönster för att balansera prestanda och noggrannhet.
        Mer aggressiv nedsampling för längre perioder för bättre prestanda.
        """
        # Extrahera numeriskt värde och enhet från time_range (t.ex. "24h", "7d")
        if time_range.endswith('h'):
            hours = int(time_range[:-1])
            if hours <= 1:
                return "1m"   # 1 timme = 1 minut aggregering (~60 datapunkter)
            elif hours <= 6:
                return "3m"   # 6 timmar = 3 minuter (~120 datapunkter)
            elif hours <= 24:
                return "5m"   # 24 timmar = 5 minuter (~288 datapunkter)
            else:
                return "15m"  # >24 timmar = 15 minuter
        elif time_range.endswith('d'):
            days = int(time_range[:-1])
            if days <= 1:
                return "5m"   # 1 dag = 5 minuter (~288 datapunkter)
            elif days <= 7:
                return "30m"  # 7 dagar = 30 minuter (~336 datapunkter) - IMPROVED
            elif days <= 30:
                return "2h"   # 30 dagar = 2 timmar (~360 datapunkter) - IMPROVED
            else:
                return "6h"   # >30 dagar = 6 timmar
        else:
            return "5m"  # Default
    
    def query_metrics(self, metric_names: List[str], time_range: str = '24h',
                     aggregation_window: Optional[str] = None) -> pd.DataFrame:
        """
        Query metrics from InfluxDB

        FÖRBÄTTRING: Nu med konfigurerbar aggregering

        Args:
            metric_names: Lista över metrics att hämta
            time_range: Tidsperiod (t.ex. '24h', '7d')
            aggregation_window: Specifikt aggregeringsfönster (None = automatisk)
        """
        try:
            # Get status fields from provider (brand-aware)
            # Status fields should use 'last' aggregation, not 'mean'
            # (averaging 0/1 values gives meaningless fractional results)
            status_fields = set(self.provider.get_status_field_names())

            # Split metrics into status and non-status
            status_metrics = [m for m in metric_names if m in status_fields]
            value_metrics = [m for m in metric_names if m not in status_fields]

            # Använd angiven aggregering eller beräkna automatiskt
            if aggregation_window is None:
                aggregation_window = self._get_aggregation_window(time_range)

            results = []

            # Query value metrics with mean aggregation
            if value_metrics:
                name_filter = ' or '.join([f'r.name == "{name}"' for name in value_metrics])
                query = f'''
                    from(bucket: "{self.bucket}")
                        |> range(start: -{time_range})
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => {name_filter})
                        |> aggregateWindow(every: {aggregation_window}, fn: mean, createEmpty: false)
                        |> yield(name: "mean")
                '''
                result = self.query_api.query_data_frame(query)
                if isinstance(result, list):
                    result = pd.concat(result, ignore_index=True)
                if not result.empty:
                    results.append(result)

            # Query status metrics with last aggregation (preserves 0/1 values)
            if status_metrics:
                name_filter = ' or '.join([f'r.name == "{name}"' for name in status_metrics])
                query = f'''
                    from(bucket: "{self.bucket}")
                        |> range(start: -{time_range})
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => {name_filter})
                        |> aggregateWindow(every: {aggregation_window}, fn: last, createEmpty: false)
                        |> yield(name: "last")
                '''
                result = self.query_api.query_data_frame(query)
                if isinstance(result, list):
                    result = pd.concat(result, ignore_index=True)
                if not result.empty:
                    results.append(result)

            logger.debug(f"Querying metrics with {aggregation_window} aggregation for {time_range}")

            if results:
                return pd.concat(results, ignore_index=True)
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error querying metrics: {e}")
            return pd.DataFrame()

    def query_metrics_wide(self, metric_names: List[str], time_range: str = '24h',
                           aggregation_window: Optional[str] = None) -> pd.DataFrame:
        """
        Query metrics from InfluxDB and return in WIDE format using DB-side pivot.

        Since all data is collected with identical timestamps (HTTP API approach),
        InfluxDB can pivot directly - no pandas pivot needed.

        Returns DataFrame with columns: _time, metric1, metric2, metric3, ...

        Args:
            metric_names: List of metrics to fetch
            time_range: Time period (e.g., '24h', '7d')
            aggregation_window: Aggregation window (None = automatic)

        Returns:
            DataFrame in wide format with _time as index column
        """
        try:
            start_time = time.time()

            # Get status fields from provider (brand-aware)
            status_fields = set(self.provider.get_status_field_names())

            # Determine aggregation window
            if aggregation_window is None:
                aggregation_window = self._get_aggregation_window(time_range)

            # Separate aggregation functions for status vs value fields
            # Status fields use 'last', value fields use 'mean'
            status_metrics = [m for m in metric_names if m in status_fields]
            value_metrics = [m for m in metric_names if m not in status_fields]

            # Build query based on which metric types we have
            # This avoids empty table issues when only one type is requested
            if value_metrics and status_metrics:
                # Both types - use union
                value_filter = ' or '.join([f'r.name == "{m}"' for m in value_metrics])
                status_filter = ' or '.join([f'r.name == "{m}"' for m in status_metrics])

                query = f'''
                    value_data = from(bucket: "{self.bucket}")
                        |> range(start: -{time_range})
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => {value_filter})
                        |> aggregateWindow(every: {aggregation_window}, fn: mean, createEmpty: false)

                    status_data = from(bucket: "{self.bucket}")
                        |> range(start: -{time_range})
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => {status_filter})
                        |> aggregateWindow(every: {aggregation_window}, fn: last, createEmpty: false)

                    union(tables: [value_data, status_data])
                        |> pivot(rowKey: ["_time"], columnKey: ["name"], valueColumn: "_value")
                        |> sort(columns: ["_time"])
                '''
            elif value_metrics:
                # Only value metrics
                value_filter = ' or '.join([f'r.name == "{m}"' for m in value_metrics])

                query = f'''
                    from(bucket: "{self.bucket}")
                        |> range(start: -{time_range})
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => {value_filter})
                        |> aggregateWindow(every: {aggregation_window}, fn: mean, createEmpty: false)
                        |> pivot(rowKey: ["_time"], columnKey: ["name"], valueColumn: "_value")
                        |> sort(columns: ["_time"])
                '''
            elif status_metrics:
                # Only status metrics
                status_filter = ' or '.join([f'r.name == "{m}"' for m in status_metrics])

                query = f'''
                    from(bucket: "{self.bucket}")
                        |> range(start: -{time_range})
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => {status_filter})
                        |> aggregateWindow(every: {aggregation_window}, fn: last, createEmpty: false)
                        |> pivot(rowKey: ["_time"], columnKey: ["name"], valueColumn: "_value")
                        |> sort(columns: ["_time"])
                '''
            else:
                # No metrics requested
                logger.warning("query_metrics_wide: No metrics requested")
                return pd.DataFrame()

            result = self.query_api.query_data_frame(query)

            if isinstance(result, list):
                result = pd.concat(result, ignore_index=True)

            elapsed = time.time() - start_time

            if not result.empty:
                # Clean up columns - remove InfluxDB metadata columns we don't need
                cols_to_drop = ['result', 'table', '_start', '_stop', '_measurement']
                result = result.drop(columns=[c for c in cols_to_drop if c in result.columns], errors='ignore')

                logger.info(f"query_metrics_wide: {len(result)} rows, {len(result.columns)} columns in {elapsed:.2f}s")
            else:
                logger.warning(f"query_metrics_wide: No data returned for {time_range}")

            return result

        except Exception as e:
            logger.error(f"Error in query_metrics_wide: {e}")
            return pd.DataFrame()

    def get_latest_values(self) -> Dict[str, Any]:
        """Get latest values for all metrics

        OPTIMIZED: Uses vectorized set_index instead of iterrows()
        """
        try:
            query = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: -1h)
                    |> filter(fn: (r) => r._measurement == "heatpump")
                    |> group(columns: ["name"])
                    |> last()
            '''

            result = self.query_api.query_data_frame(query)

            if isinstance(result, list):
                result = pd.concat(result, ignore_index=True)

            # Values are already converted by the collector before storing to DB
            latest = {}
            if not result.empty:
                # Vectorized: convert to dict directly without iterrows()
                result = result.set_index('name')
                for metric_name in result.index:
                    row = result.loc[metric_name]
                    latest[metric_name] = {
                        'value': row['_value'],
                        'unit': row.get('unit', '') if hasattr(row, 'get') else '',
                        'time': row['_time']
                    }

            return latest

        except Exception as e:
            logger.error(f"Error getting latest values: {e}")
            return {}
    
    def get_min_max_values(self, time_range: str = '24h') -> Dict[str, Dict[str, float]]:
        """Get MIN, MAX and MEAN values for all metrics over the specified time range

        OPTIMIZED: Uses vectorized dict conversion instead of iterrows()
        """
        try:
            query_min = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: -{time_range})
                    |> filter(fn: (r) => r._measurement == "heatpump")
                    |> group(columns: ["name"])
                    |> min()
            '''

            query_max = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: -{time_range})
                    |> filter(fn: (r) => r._measurement == "heatpump")
                    |> group(columns: ["name"])
                    |> max()
            '''

            query_mean = f'''
                from(bucket: "{self.bucket}")
                    |> range(start: -{time_range})
                    |> filter(fn: (r) => r._measurement == "heatpump")
                    |> group(columns: ["name"])
                    |> mean()
            '''

            result_min = self.query_api.query_data_frame(query_min)
            result_max = self.query_api.query_data_frame(query_max)
            result_mean = self.query_api.query_data_frame(query_mean)

            if isinstance(result_min, list):
                result_min = pd.concat(result_min, ignore_index=True)
            if isinstance(result_max, list):
                result_max = pd.concat(result_max, ignore_index=True)
            if isinstance(result_mean, list):
                result_mean = pd.concat(result_mean, ignore_index=True)

            # Vectorized: convert to dicts using set_index
            min_dict = result_min.set_index('name')['_value'].to_dict() if not result_min.empty else {}
            max_dict = result_max.set_index('name')['_value'].to_dict() if not result_max.empty else {}
            avg_dict = result_mean.set_index('name')['_value'].to_dict() if not result_mean.empty else {}

            # Combine into single dict
            all_metrics = set(min_dict.keys()) | set(max_dict.keys()) | set(avg_dict.keys())
            min_max = {}
            for metric_name in all_metrics:
                min_max[metric_name] = {}
                if metric_name in min_dict:
                    min_max[metric_name]['min'] = min_dict[metric_name]
                if metric_name in max_dict:
                    min_max[metric_name]['max'] = max_dict[metric_name]
                if metric_name in avg_dict:
                    min_max[metric_name]['avg'] = avg_dict[metric_name]

            return min_max

        except Exception as e:
            logger.error(f"Error getting min/max values: {e}")
            return {}

    def calculate_min_max_from_df(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """
        Calculate MIN, MAX and MEAN values from pre-fetched DataFrame

        OPTIMIZED: Avoids 3 separate InfluxDB queries by using batch data
        This saves ~2-3s of load time when min/max values are needed
        """
        try:
            if df.empty:
                return {}

            min_max = {}

            # Group by metric name and calculate statistics
            for metric_name in df['name'].unique():
                metric_df = df[df['name'] == metric_name]
                values = metric_df['_value'].dropna()

                if len(values) > 0:
                    min_max[metric_name] = {
                        'min': float(values.min()),
                        'max': float(values.max()),
                        'avg': float(values.mean())
                    }

            return min_max

        except Exception as e:
            logger.error(f"Error calculating min/max from dataframe: {e}")
            return {}

    def get_latest_values_from_df(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get latest values for all metrics from pre-fetched DataFrame

        OPTIMIZED: Avoids separate InfluxDB query by using batch data
        Takes the most recent row for each metric
        """
        try:
            if df.empty:
                return {}

            latest = {}

            # Get the last row for each metric (data is already sorted by time in query)
            for metric_name in df['name'].unique():
                metric_df = df[df['name'] == metric_name].sort_values('_time')
                if not metric_df.empty:
                    last_row = metric_df.iloc[-1]
                    latest[metric_name] = {
                        'value': last_row['_value'],
                        'unit': last_row.get('unit', ''),
                        'time': last_row['_time']
                    }

            return latest

        except Exception as e:
            logger.error(f"Error getting latest values from dataframe: {e}")
            return {}

    def get_alarm_status_from_df(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get current alarm status from pre-fetched DataFrame

        OPTIMIZED: Avoids separate InfluxDB query by using batch data
        """
        try:
            # Get latest alarm values from batch data
            alarm_status = 0
            alarm_code = 0

            if 'name' in df.columns:
                alarm_status_df = df[df['name'] == 'alarm_status']
                if not alarm_status_df.empty:
                    alarm_status = alarm_status_df.sort_values('_time').iloc[-1]['_value']

                alarm_code_df = df[df['name'] == 'alarm_code']
                if not alarm_code_df.empty:
                    alarm_code = int(alarm_code_df.sort_values('_time').iloc[-1]['_value'])

            is_alarm = alarm_status > 0 or alarm_code > 0

            # Use brand-specific alarm codes
            alarm_description = self.alarm_codes.get(alarm_code, f"Okänd larmkod: {alarm_code}")

            # Get alarm time if active (from the last alarm_code > 0)
            alarm_time = None
            if is_alarm and 'name' in df.columns:
                alarm_code_df = df[df['name'] == 'alarm_code']
                alarm_active = alarm_code_df[alarm_code_df['_value'] > 0]
                if not alarm_active.empty:
                    alarm_time = alarm_active.sort_values('_time').iloc[-1]['_time']

            return {
                'is_alarm': is_alarm,
                'alarm_code': alarm_code,
                'alarm_description': alarm_description if is_alarm else 'Inget larm',
                'alarm_time': alarm_time,
                'alarm_status_raw': alarm_status
            }

        except Exception as e:
            logger.error(f"Error getting alarm status from dataframe: {e}")
            return {
                'is_alarm': False,
                'alarm_code': 0,
                'alarm_description': 'Inget larm',
                'alarm_time': None,
                'alarm_status_raw': 0
            }

    def get_event_log_from_df(self, df: pd.DataFrame, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent events (state changes) from pre-fetched DataFrame

        OPTIMIZED: Uses vectorized operations instead of iterrows() for 100x speedup
        """
        try:
            if df.empty:
                return []

            events = []

            # Binary status metrics (0/1 transitions)
            binary_metrics = {
                'compressor_status': ('Kompressor PÅ', 'Kompressor AV', '🔄', '⏸️', 'info', 'info'),
                'brine_pump_status': ('Köldbärarpump PÅ', 'Köldbärarpump AV', '💧', '💧', 'info', 'info'),
                'radiator_pump_status': ('Radiatorpump PÅ', 'Radiatorpump AV', '📡', '📡', 'info', 'info'),
                'switch_valve_status': ('Varmvattencykel START', 'Varmvattencykel STOPP', '🚿', '🚿', 'info', 'info'),
                'alarm_status': ('Larm aktiverat', 'Larm återställt', '⚠️', '✅', 'danger', 'success'),
            }

            # Process binary metrics with vectorized operations
            for metric_name, (on_msg, off_msg, icon_on, icon_off, type_on, type_off) in binary_metrics.items():
                metric_df = df[df['name'] == metric_name].copy()
                if metric_df.empty:
                    continue

                metric_df = metric_df.sort_values('_time')
                metric_df['prev_value'] = metric_df['_value'].shift(1)

                # Vectorized: find rising edges (0→1)
                rising = (metric_df['_value'] > 0) & (metric_df['prev_value'] == 0) & metric_df['prev_value'].notna()
                for ts in metric_df.loc[rising, '_time']:
                    events.append({'time': ts, 'event': on_msg, 'type': type_on, 'icon': icon_on})

                # Vectorized: find falling edges (1→0)
                falling = (metric_df['_value'] == 0) & (metric_df['prev_value'] > 0) & metric_df['prev_value'].notna()
                for ts in metric_df.loc[falling, '_time']:
                    events.append({'time': ts, 'event': off_msg, 'type': type_off, 'icon': icon_off})

            # Additional heat percent - special handling for percentage changes
            aux_df = df[df['name'] == 'additional_heat_percent'].copy()
            if not aux_df.empty:
                aux_df = aux_df.sort_values('_time')
                aux_df['prev_value'] = aux_df['_value'].shift(1)

                # Rising: 0→>0
                rising = (aux_df['_value'] > 0) & (aux_df['prev_value'] == 0) & aux_df['prev_value'].notna()
                for ts, val in zip(aux_df.loc[rising, '_time'], aux_df.loc[rising, '_value']):
                    events.append({'time': ts, 'event': f'Tillsattsvärme PÅ ({int(val)}%)', 'type': 'warning', 'icon': '🔥'})

                # Falling: >0→0
                falling = (aux_df['_value'] == 0) & (aux_df['prev_value'] > 0) & aux_df['prev_value'].notna()
                for ts in aux_df.loc[falling, '_time']:
                    events.append({'time': ts, 'event': 'Tillsattsvärme AV', 'type': 'info', 'icon': '🔥'})

                # Significant change: both >0 and |delta| > 10
                significant = (aux_df['_value'] > 0) & (aux_df['prev_value'] > 0) & \
                              (abs(aux_df['_value'] - aux_df['prev_value']) > 10) & aux_df['prev_value'].notna()
                for ts, val in zip(aux_df.loc[significant, '_time'], aux_df.loc[significant, '_value']):
                    events.append({'time': ts, 'event': f'Tillsattsvärme ändrad till {int(val)}%', 'type': 'warning', 'icon': '🔥'})

            # Alarm code - special handling for alarm descriptions
            alarm_df = df[df['name'] == 'alarm_code'].copy()
            if not alarm_df.empty:
                alarm_df = alarm_df.sort_values('_time')
                alarm_df['prev_value'] = alarm_df['_value'].shift(1)

                # Rising: alarm triggered
                rising = (alarm_df['_value'] > 0) & (alarm_df['prev_value'] == 0) & alarm_df['prev_value'].notna()
                for ts, code in zip(alarm_df.loc[rising, '_time'], alarm_df.loc[rising, '_value']):
                    alarm_desc = self.alarm_codes.get(int(code), f"Kod {int(code)}")
                    events.append({'time': ts, 'event': f'LARM - {alarm_desc}', 'type': 'danger', 'icon': '⚠️'})

                # Falling: alarm cleared
                falling = (alarm_df['_value'] == 0) & (alarm_df['prev_value'] > 0) & alarm_df['prev_value'].notna()
                for ts in alarm_df.loc[falling, '_time']:
                    events.append({'time': ts, 'event': 'Larm återställt', 'type': 'success', 'icon': '✅'})

            # Sort by time (newest first) and limit
            events = sorted(events, key=lambda x: x['time'], reverse=True)[:limit]

            return events

        except Exception as e:
            logger.error(f"Error getting event log from dataframe: {e}")
            return []

    def calculate_cop_from_pivot(self, df_pivot: pd.DataFrame, interval_minutes: int = 15) -> pd.DataFrame:
        """
        Calculate Interval COP from pre-pivoted dataframe (guaranteed aligned timestamps)

        IMPROVED: Uses interval-based aggregation for more accurate COP:
        - Groups data into fixed intervals (default 15 minutes)
        - COP = Σ heat_output / Σ electrical_input per interval
        - This matches industry standards and manufacturer testing methods

        Args:
            df_pivot: DataFrame with metrics as columns (already pivoted)
            interval_minutes: Aggregation interval (default 15 min)

        Returns:
            DataFrame with interval COP and cumulative COP
        """
        try:
            if df_pivot.empty:
                logger.warning("calculate_cop_from_pivot: Empty input dataframe")
                return pd.DataFrame()

            logger.debug(f"calculate_cop_from_pivot: Input shape {df_pivot.shape}, columns: {list(df_pivot.columns)}")

            # Make a copy to avoid modifying original
            df = df_pivot.copy()

            # Ensure _time is datetime
            if '_time' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['_time']):
                df['_time'] = pd.to_datetime(df['_time'])

            # Check if data needs re-pivoting (InfluxDB union+pivot doesn't work correctly)
            # If most values are NaN per column, data isn't properly aligned
            cop_cols = ['radiator_forward', 'radiator_return', 'power_consumption', 'compressor_status']
            available_cols = [c for c in cop_cols if c in df.columns]
            if available_cols:
                avg_fill_rate = sum(df[c].notna().sum() for c in available_cols) / (len(df) * len(available_cols))
                if avg_fill_rate < 0.5:  # Less than 50% fill rate suggests unpivoted data
                    logger.info(f"calculate_cop_from_pivot: Data not properly pivoted (fill rate: {avg_fill_rate:.1%}), re-pivoting...")
                    # Group by time and aggregate - this aligns all metrics to same timestamp
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    agg_dict = {col: 'mean' for col in numeric_cols if col in df.columns}
                    # Status columns should use 'last' not 'mean'
                    for status_col in ['compressor_status', 'brine_pump_status', 'radiator_pump_status', 'switch_valve_status']:
                        if status_col in agg_dict:
                            agg_dict[status_col] = 'last'
                    if agg_dict:
                        df = df.groupby('_time').agg(agg_dict).reset_index()
                        logger.info(f"calculate_cop_from_pivot: Re-pivoted to {len(df)} rows")

            # Calculate temperature deltas
            # Prefer heat_carrier if available and valid (IVT uses these, radiator sensors may be faulty)
            forward_col = None
            return_col = None

            if 'heat_carrier_forward' in df.columns and 'heat_carrier_return' in df.columns:
                hc_forward_mean = df['heat_carrier_forward'].mean()
                if hc_forward_mean > 0:  # Valid heat carrier data (not -48°C)
                    forward_col = 'heat_carrier_forward'
                    return_col = 'heat_carrier_return'
                    logger.debug(f"calculate_cop_from_pivot: Using heat_carrier temps (mean forward: {hc_forward_mean:.1f}°C)")

            # Fall back to radiator if heat_carrier not valid
            if forward_col is None:
                if 'radiator_forward' in df.columns and 'radiator_return' in df.columns:
                    rad_forward_mean = df['radiator_forward'].mean()
                    if rad_forward_mean > 0:  # Valid radiator data
                        forward_col = 'radiator_forward'
                        return_col = 'radiator_return'
                        logger.debug(f"calculate_cop_from_pivot: Using radiator temps (mean forward: {rad_forward_mean:.1f}°C)")

            if forward_col is None or return_col is None:
                logger.warning("calculate_cop_from_pivot: No valid forward/return temperature data")
                return pd.DataFrame()

            # Create radiator_delta using the selected columns (keeping name for compatibility)
            # Convert to numeric if needed (handles mixed types from InfluxDB)
            df[forward_col] = pd.to_numeric(df[forward_col], errors='coerce')
            df[return_col] = pd.to_numeric(df[return_col], errors='coerce')

            df['radiator_delta'] = df[forward_col] - df[return_col]

            # Also copy the forward/return values with standard names for groupby later
            df['radiator_forward'] = df[forward_col]
            df['radiator_return'] = df[return_col]

            # Check what data we have
            has_power = 'power_consumption' in df.columns
            has_compressor = 'compressor_status' in df.columns

            if not has_power:
                logger.warning("No power consumption data available for COP calculation")
                return pd.DataFrame()

            # Sort by time and calculate time differences
            df = df.sort_values('_time').reset_index(drop=True)
            df['time_diff_hours'] = df['_time'].diff().dt.total_seconds() / 3600
            df['time_diff_hours'] = df['time_diff_hours'].fillna(0).clip(0, 1)  # Cap at 1 hour max

            # Valid mask: compressor running and valid data
            if has_compressor:
                compressor_on = df['compressor_status'].fillna(0) > 0
            else:
                compressor_on = True

            valid_mask = (
                compressor_on &
                (df['radiator_delta'].fillna(0) > 0.5) &
                (df['power_consumption'].fillna(0) > 100)
            )

            df['heat_kwh'] = 0.0
            df['elec_kwh'] = 0.0

            # Heat output in kWh = (delta_T × flow_factor) × time_hours
            df.loc[valid_mask, 'heat_kwh'] = (
                df.loc[valid_mask, 'radiator_delta'] * self.cop_flow_factor *
                df.loc[valid_mask, 'time_diff_hours']
            )

            # Electrical input in kWh = power_W / 1000 × time_hours
            df.loc[valid_mask, 'elec_kwh'] = (
                df.loc[valid_mask, 'power_consumption'] / 1000.0 *
                df.loc[valid_mask, 'time_diff_hours']
            )

            # Create interval groups (e.g., 15-minute intervals)
            # Use 'T' suffix for broader pandas compatibility
            df['interval'] = df['_time'].dt.floor(f'{interval_minutes}T')

            logger.debug(f"calculate_cop_from_pivot: Valid samples: {valid_mask.sum()}/{len(df)}, total heat: {df['heat_kwh'].sum():.2f} kWh, total elec: {df['elec_kwh'].sum():.2f} kWh")

            # Aggregate by interval: sum heat and electricity
            interval_df = df.groupby('interval').agg({
                'heat_kwh': 'sum',
                'elec_kwh': 'sum',
                'radiator_forward': 'mean',
                'radiator_return': 'mean',
                'power_consumption': 'mean'
            }).reset_index()

            # Calculate interval COP = Σ heat / Σ electricity
            interval_df['estimated_cop'] = None
            valid_intervals = interval_df['elec_kwh'] > 0.01  # At least some electricity used

            interval_df.loc[valid_intervals, 'estimated_cop'] = (
                interval_df.loc[valid_intervals, 'heat_kwh'] /
                interval_df.loc[valid_intervals, 'elec_kwh']
            )

            # Log COP for diagnostics
            if valid_intervals.any():
                raw_cop_mean = interval_df.loc[valid_intervals, 'estimated_cop'].mean()
                raw_cop_max = interval_df.loc[valid_intervals, 'estimated_cop'].max()
                logger.info(f"calculate_cop_from_pivot: COP - mean: {raw_cop_mean:.2f}, max: {raw_cop_max:.2f}")

            # No clamping - show real calculated values for proper flow_factor calibration

            # Calculate cumulative/seasonal COP
            interval_df['cumulative_heat'] = interval_df['heat_kwh'].cumsum()
            interval_df['cumulative_elec'] = interval_df['elec_kwh'].cumsum()
            interval_df['seasonal_cop'] = None

            cumulative_valid = interval_df['cumulative_elec'] > 0.1
            interval_df.loc[cumulative_valid, 'seasonal_cop'] = (
                interval_df.loc[cumulative_valid, 'cumulative_heat'] /
                interval_df.loc[cumulative_valid, 'cumulative_elec']
            )

            # Rename interval column to _time for compatibility
            interval_df = interval_df.rename(columns={'interval': '_time'})

            valid_cop_count = interval_df['estimated_cop'].notna().sum()
            logger.info(f"calculate_cop_from_pivot: Generated {len(interval_df)} intervals, {valid_cop_count} with valid COP")

            return interval_df
        except Exception as e:
            logger.error(f"Error calculating COP from pivot: {e}", exc_info=True)
            return pd.DataFrame()

    def calculate_cop_from_df(self, df: pd.DataFrame, interval_minutes: int = 15) -> pd.DataFrame:
        """
        Calculate Interval COP from unpivoted dataframe (pivots first, then calculates)

        Args:
            df: DataFrame with 'name' column containing metric names and '_value' column
            interval_minutes: Aggregation interval (default 15 min)

        Returns:
            DataFrame with interval COP and cumulative COP
        """
        try:
            if df.empty:
                return pd.DataFrame()

            # Filter to only COP-related metrics
            cop_metrics = [
                'radiator_forward',
                'radiator_return',
                'heat_carrier_forward',  # IVT alternative
                'heat_carrier_return',   # IVT alternative
                'brine_in_evaporator',
                'brine_out_condenser',
                'power_consumption',
                'compressor_status'
            ]

            df_filtered = df[df['name'].isin(cop_metrics)].copy()

            if df_filtered.empty:
                return pd.DataFrame()

            # Pivot to get each metric as a column
            df_pivot = df_filtered.pivot_table(
                index='_time',
                columns='name',
                values='_value',
                aggfunc='mean'
            ).reset_index()

            # Delegate to the pivoted version
            return self.calculate_cop_from_pivot(df_pivot, interval_minutes)

        except Exception as e:
            logger.error(f"Error calculating COP from dataframe: {e}")
            return pd.DataFrame()

    def calculate_cop(self, time_range: str = '24h') -> pd.DataFrame:
        """
        Calculate COP (Coefficient of Performance) over time

        Uses optimized aggregation for smooth COP visualization
        Finer granularity than batch query for better chart quality

        COP = Heat Output / Electrical Input
        Simplified calculation using temperature deltas
        """
        try:
            metrics = [
                'radiator_forward',
                'radiator_return',
                'heat_carrier_forward',  # IVT alternative
                'heat_carrier_return',   # IVT alternative
                'brine_in_evaporator',
                'brine_out_condenser',
                'power_consumption',
                'compressor_status'
            ]

            # Use finer aggregation for COP visualization (smoother charts)
            # 7d: 10m instead of 30m, 30d: 30m instead of 2h
            cop_aggregation = self._get_cop_aggregation_window(time_range)
            df = self.query_metrics(metrics, time_range, aggregation_window=cop_aggregation)

            # Use the optimized method
            return self.calculate_cop_from_df(df)

        except Exception as e:
            logger.error(f"Error calculating COP: {e}")
            return pd.DataFrame()

    def _get_cop_aggregation_window(self, time_range: str) -> str:
        """
        Get optimal aggregation window for COP calculation

        Uses finer granularity than batch queries for smoother visualization
        UPDATED: 10m for both 7d and 30d for consistent fine granularity
        """
        if time_range.endswith('h'):
            hours = int(time_range[:-1])
            if hours <= 1:
                return "1m"
            elif hours <= 6:
                return "2m"
            elif hours <= 24:
                return "5m"
            else:
                return "10m"
        elif time_range.endswith('d'):
            days = int(time_range[:-1])
            if days <= 1:
                return "5m"
            elif days <= 7:
                return "10m"  # 7d: 10m aggregation (~1000 points)
            elif days <= 30:
                return "10m"  # 30d: 10m aggregation (~4320 points) - FINER!
            else:
                return "1h"
        else:
            return "5m"
    
    def calculate_energy_costs(self, time_range: str = '24h', price_per_kwh: float = 2.0) -> Dict[str, Any]:
        """
        Calculate energy consumption and costs
        
        KORREKT: Använder verklig tid mellan datapunkter
        """
        try:
            df = self.query_metrics(['power_consumption'], time_range)
            
            if df.empty:
                return {
                    'total_kwh': 0,
                    'total_cost': 0,
                    'avg_power': 0,
                    'peak_power': 0
                }
            
            df = df.sort_values('_time')
            
            # Calculate time differences in hours - ANVÄNDER VERKLIG TID
            df['time_diff_hours'] = df['_time'].diff().dt.total_seconds() / 3600
            df['time_diff_hours'] = df['time_diff_hours'].fillna(0)
            
            # Energy = Power (W) * Time (h) / 1000 (to get kWh)
            df['energy_kwh'] = (df['_value'] * df['time_diff_hours']) / 1000
            
            total_kwh = df['energy_kwh'].sum()
            total_cost = total_kwh * price_per_kwh
            avg_power = df['_value'].mean()
            peak_power = df['_value'].max()
            
            return {
                'total_kwh': round(total_kwh, 2),
                'total_cost': round(total_cost, 2),
                'avg_power': round(avg_power, 0),
                'peak_power': round(peak_power, 0)
            }
            
        except Exception as e:
            logger.error(f"Error calculating energy costs: {e}")
            return {
                'total_kwh': 0,
                'total_cost': 0,
                'avg_power': 0,
                'peak_power': 0
            }
    
    def calculate_runtime_stats(self, time_range: str = '24h') -> Dict[str, Any]:
        """
        Calculate runtime statistics for compressor and auxiliary heater
        
        KORREKT: Använder verklig tid mellan datapunkter
        """
        try:
            metrics = ['compressor_status', 'additional_heat_percent']
            df = self.query_metrics(metrics, time_range)
            
            if df.empty:
                return {
                    'compressor_runtime_hours': 0,
                    'compressor_runtime_percent': 0,
                    'aux_heater_runtime_hours': 0,
                    'aux_heater_runtime_percent': 0,
                    'total_hours': 0
                }
            
            df = df.sort_values('_time')
            
            # Beräkna total tidsperiod
            total_seconds = (df['_time'].max() - df['_time'].min()).total_seconds()
            total_hours = total_seconds / 3600
            
            if total_hours == 0:
                return {
                    'compressor_runtime_hours': 0,
                    'compressor_runtime_percent': 0,
                    'aux_heater_runtime_hours': 0,
                    'aux_heater_runtime_percent': 0,
                    'total_hours': 0
                }
            
            # Kompressor runtime - ANVÄNDER VERKLIG TID
            comp_df = df[df['name'] == 'compressor_status'].copy()
            comp_runtime_seconds = 0
            
            if not comp_df.empty:
                comp_df = comp_df.sort_values('_time')
                
                # Beräkna tiden för varje datapunkt baserat på nästa datapunkt
                for i in range(len(comp_df) - 1):
                    if comp_df.iloc[i]['_value'] > 0:  # Om kompressor är PÅ
                        # Beräkna VERKLIG tid till nästa datapunkt
                        time_diff = (comp_df.iloc[i + 1]['_time'] - comp_df.iloc[i]['_time']).total_seconds()
                        comp_runtime_seconds += time_diff
                
                # För sista datapunkten, anta samma intervall som föregående
                if len(comp_df) > 1 and comp_df.iloc[-1]['_value'] > 0:
                    avg_interval = (comp_df.iloc[-1]['_time'] - comp_df.iloc[-2]['_time']).total_seconds()
                    comp_runtime_seconds += avg_interval
            
            comp_runtime_hours = comp_runtime_seconds / 3600
            comp_runtime_percent = (comp_runtime_hours / total_hours * 100) if total_hours > 0 else 0
            
            # Auxiliary heater runtime - ANVÄNDER VERKLIG TID
            aux_df = df[df['name'] == 'additional_heat_percent'].copy()
            aux_runtime_seconds = 0
            
            if not aux_df.empty:
                aux_df = aux_df.sort_values('_time')
                
                # Beräkna tiden för varje datapunkt baserat på nästa datapunkt
                for i in range(len(aux_df) - 1):
                    if aux_df.iloc[i]['_value'] > 0:  # Om tillsats är PÅ
                        # Beräkna VERKLIG tid till nästa datapunkt
                        time_diff = (aux_df.iloc[i + 1]['_time'] - aux_df.iloc[i]['_time']).total_seconds()
                        aux_runtime_seconds += time_diff
                
                # För sista datapunkten, anta samma intervall som föregående
                if len(aux_df) > 1 and aux_df.iloc[-1]['_value'] > 0:
                    avg_interval = (aux_df.iloc[-1]['_time'] - aux_df.iloc[-2]['_time']).total_seconds()
                    aux_runtime_seconds += avg_interval
            
            aux_runtime_hours = aux_runtime_seconds / 3600
            aux_runtime_percent = (aux_runtime_hours / total_hours * 100) if total_hours > 0 else 0
            
            logger.info(f"Runtime calculation for {time_range}:")
            logger.info(f"  Total period: {total_hours:.2f} hours")
            logger.info(f"  Compressor: {comp_runtime_hours:.2f}h ({comp_runtime_percent:.1f}%)")
            logger.info(f"  Aux heater: {aux_runtime_hours:.2f}h ({aux_runtime_percent:.1f}%)")
            
            return {
                'compressor_runtime_hours': round(comp_runtime_hours, 1),
                'compressor_runtime_percent': round(comp_runtime_percent, 1),
                'aux_heater_runtime_hours': round(aux_runtime_hours, 1),
                'aux_heater_runtime_percent': round(aux_runtime_percent, 1),
                'total_hours': round(total_hours, 1)
            }
            
        except Exception as e:
            logger.error(f"Error calculating runtime stats: {e}")
            return {
                'compressor_runtime_hours': 0,
                'compressor_runtime_percent': 0,
                'aux_heater_runtime_hours': 0,
                'aux_heater_runtime_percent': 0,
                'total_hours': 0
            }
    
    def analyze_hot_water_cycles_from_df(self, df: pd.DataFrame, time_range: str = '7d') -> Dict[str, Any]:
        """
        Analyze hot water heating cycles from pre-fetched dataframe

        OPTIMIZED: Uses existing dataframe to avoid redundant InfluxDB query
        Uses batch aggregation data which may be coarser but much faster
        """
        try:
            if df.empty:
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }

            # Filter to hot water-related metrics
            valve_df = df[df['name'] == 'switch_valve_status'].copy()
            power_df = df[df['name'] == 'power_consumption'].copy()

            if valve_df.empty:
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }

            valve_df = valve_df.sort_values('_time')
            power_df = power_df.sort_values('_time')

            # Detect cycles (transitions from 0 to 1)
            valve_df['prev_value'] = valve_df['_value'].shift(1)
            cycles_start = valve_df[(valve_df['_value'] == 1) & (valve_df['prev_value'] == 0)]

            num_cycles = len(cycles_start)

            logger.info(f"Hot water cycle detection from batch data for {time_range}:")
            logger.info(f"  Detected {num_cycles} valve transitions (0→1)")

            if num_cycles == 0:
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }

            # Calculate average cycle duration AND energy
            cycle_durations = []
            cycle_energies = []

            # MINIMUM DURATION FILTER - configurable in config.yaml
            min_cycle_minutes = self.hw_min_cycle_minutes

            filtered_count = 0

            for start_time in cycles_start['_time']:
                after_start = valve_df[valve_df['_time'] > start_time]
                end_times = after_start[after_start['_value'] == 0]

                if not end_times.empty:
                    end_time = end_times.iloc[0]['_time']
                    duration_seconds = (end_time - start_time).total_seconds()
                    duration_minutes = duration_seconds / 60

                    # FILTER: Skippa cykler kortare än minimum
                    if duration_minutes < min_cycle_minutes:
                        filtered_count += 1
                        continue

                    cycle_durations.append(duration_minutes)

                    # Calculate energy for this cycle
                    cycle_power = power_df[
                        (power_df['_time'] >= start_time) &
                        (power_df['_time'] <= end_time)
                    ].copy()

                    if not cycle_power.empty:
                        cycle_power = cycle_power.sort_values('_time')
                        cycle_power['time_diff_hours'] = cycle_power['_time'].diff().dt.total_seconds() / 3600
                        cycle_power['time_diff_hours'] = cycle_power['time_diff_hours'].fillna(0)

                        # Energy = Power (W) * Time (h) / 1000 = kWh
                        cycle_power['energy_kwh'] = (cycle_power['_value'] * cycle_power['time_diff_hours']) / 1000

                        total_cycle_energy = cycle_power['energy_kwh'].sum()
                        cycle_energies.append(total_cycle_energy)

            # Antal giltiga cykler (efter filtrering)
            num_valid_cycles = len(cycle_durations)

            logger.info(f"  Total: {num_valid_cycles} valid cycles, {filtered_count} filtered (<{min_cycle_minutes} min)")

            if num_valid_cycles == 0:
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }

            avg_duration = np.mean(cycle_durations) if cycle_durations else 0
            avg_energy_kwh = np.mean(cycle_energies) if cycle_energies else 0

            # Calculate cycles per day
            total_days = (valve_df['_time'].max() - valve_df['_time'].min()).total_seconds() / 86400
            cycles_per_day = num_valid_cycles / total_days if total_days > 0 else 0

            return {
                'total_cycles': num_valid_cycles,
                'avg_cycle_duration_minutes': round(avg_duration, 1),
                'avg_energy_per_cycle_kwh': round(avg_energy_kwh, 2),
                'cycles_per_day': round(cycles_per_day, 1)
            }

        except Exception as e:
            logger.error(f"Error analyzing hot water cycles from dataframe: {e}")
            return {
                'total_cycles': 0,
                'avg_cycle_duration_minutes': 0,
                'avg_energy_per_cycle_kwh': 0,
                'cycles_per_day': 0
            }

    def analyze_hot_water_cycles(self, time_range: str = '7d') -> Dict[str, Any]:
        """
        Analyze hot water heating cycles

        DEPRECATED: Use analyze_hot_water_cycles_from_df() with pre-fetched data for better performance
        KORRIGERAD: Använder nu korrekt effekt under varmvattencykler
        """
        try:
            metrics = ['switch_valve_status', 'hot_water_top', 'power_consumption']

            # Använd finare aggregering för varmvattenanalys
            df = self.query_metrics(metrics, time_range, aggregation_window='1m')
            
            if df.empty:
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }
            
            valve_df = df[df['name'] == 'switch_valve_status'].copy()
            power_df = df[df['name'] == 'power_consumption'].copy()
            
            if valve_df.empty:
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }
            
            valve_df = valve_df.sort_values('_time')
            power_df = power_df.sort_values('_time')
            
            # Detect cycles (transitions from 0 to 1)
            valve_df['prev_value'] = valve_df['_value'].shift(1)
            cycles_start = valve_df[(valve_df['_value'] == 1) & (valve_df['prev_value'] == 0)]
            
            num_cycles = len(cycles_start)
            
            logger.info(f"Hot water cycle detection for {time_range}:")
            logger.info(f"  Detected {num_cycles} valve transitions (0→1)")
            
            if num_cycles == 0:
                logger.info("  No valve transitions detected - växelventilen har inte slagit över till varmvatten")
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }
            
            # Calculate average cycle duration AND energy
            cycle_durations = []
            cycle_energies = []

            # MINIMUM DURATION FILTER - configurable in config.yaml
            min_cycle_minutes = self.hw_min_cycle_minutes

            filtered_count = 0

            for start_time in cycles_start['_time']:
                after_start = valve_df[valve_df['_time'] > start_time]
                end_times = after_start[after_start['_value'] == 0]

                if not end_times.empty:
                    end_time = end_times.iloc[0]['_time']
                    duration_seconds = (end_time - start_time).total_seconds()
                    duration_minutes = duration_seconds / 60

                    # FILTER: Skippa cykler kortare än minimum
                    if duration_minutes < min_cycle_minutes:
                        filtered_count += 1
                        logger.debug(f"  ❌ FILTRERAD kort cykel kl {start_time.strftime('%H:%M:%S')}: {duration_minutes:.1f} min (< {min_cycle_minutes} min)")
                        continue
                    
                    cycle_durations.append(duration_minutes)
                    
                    # KORRIGERING: Beräkna energi för DENNA specifika cykel
                    # Hämta effektdata under denna cykel
                    cycle_power = power_df[
                        (power_df['_time'] >= start_time) & 
                        (power_df['_time'] <= end_time)
                    ].copy()
                    
                    if not cycle_power.empty:
                        # Beräkna energi genom att integrera effekt över tid
                        cycle_power = cycle_power.sort_values('_time')
                        cycle_power['time_diff_hours'] = cycle_power['_time'].diff().dt.total_seconds() / 3600
                        cycle_power['time_diff_hours'] = cycle_power['time_diff_hours'].fillna(0)
                        
                        # Energy = Power (W) * Time (h) / 1000 = kWh
                        cycle_power['energy_kwh'] = (cycle_power['_value'] * cycle_power['time_diff_hours']) / 1000
                        
                        total_cycle_energy = cycle_power['energy_kwh'].sum()
                        cycle_energies.append(total_cycle_energy)

                        logger.debug(f"  ✅ GILTIG cykel kl {start_time.strftime('%H:%M:%S')}: {duration_minutes:.1f} min, {total_cycle_energy:.2f} kWh")
            
            # Antal giltiga cykler (efter filtrering)
            num_valid_cycles = len(cycle_durations)
            
            logger.info(f"  Totalt: {num_valid_cycles} giltiga cykler, {filtered_count} filtrerade (<{min_cycle_minutes} min)")

            if num_valid_cycles == 0:
                logger.warning(f"⚠️  Inga giltiga varmvattencykler hittades - alla {filtered_count} cykler var < {min_cycle_minutes} min!")
                logger.warning("   → Kontrollera växelventilsgrafen för att se vad som händer")
                return {
                    'total_cycles': 0,
                    'avg_cycle_duration_minutes': 0,
                    'avg_energy_per_cycle_kwh': 0,
                    'cycles_per_day': 0
                }
            
            avg_duration = np.mean(cycle_durations) if cycle_durations else 0
            avg_energy_kwh = np.mean(cycle_energies) if cycle_energies else 0
            
            # Calculate cycles per day - ANVÄNDER VERKLIG TID
            total_days = (valve_df['_time'].max() - valve_df['_time'].min()).total_seconds() / 86400
            cycles_per_day = num_valid_cycles / total_days if total_days > 0 else 0
            
            logger.info(f"Hot water analysis for {time_range}:")
            logger.info(f"  Total cycles: {num_valid_cycles} (filtered, min {min_cycle_minutes} min)")
            logger.info(f"  Avg duration: {avg_duration:.1f} min")
            logger.info(f"  Avg energy: {avg_energy_kwh:.2f} kWh")
            logger.info(f"  Cycles/day: {cycles_per_day:.1f}")
            
            return {
                'total_cycles': num_valid_cycles,
                'avg_cycle_duration_minutes': round(avg_duration, 1),
                'avg_energy_per_cycle_kwh': round(avg_energy_kwh, 2),
                'cycles_per_day': round(cycles_per_day, 1)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing hot water cycles: {e}")
            return {
                'total_cycles': 0,
                'avg_cycle_duration_minutes': 0,
                'avg_energy_per_cycle_kwh': 0,
                'cycles_per_day': 0
            }
    
    def get_alarm_status(self) -> Dict[str, Any]:
        """Get current alarm status with description (brand-aware)"""
        try:
            latest = self.get_latest_values()

            alarm_status = latest.get('alarm_status', {}).get('value', 0)
            alarm_code = int(latest.get('alarm_code', {}).get('value', 0))

            is_alarm = alarm_status > 0 or alarm_code > 0

            # Use brand-specific alarm codes
            alarm_description = self.alarm_codes.get(alarm_code, f"Okänd larmkod: {alarm_code}")
            
            # Hämta när larmet aktiverades
            if is_alarm:
                query = f'''
                    from(bucket: "{self.bucket}")
                        |> range(start: -7d)
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => r.name == "alarm_code")
                        |> filter(fn: (r) => r._value > 0)
                        |> last()
                '''
                
                result = self.query_api.query_data_frame(query)
                
                if isinstance(result, list):
                    result = pd.concat(result, ignore_index=True)
                
                if not result.empty:
                    alarm_time = result.iloc[0]['_time']
                else:
                    alarm_time = None
            else:
                alarm_time = None
            
            return {
                'is_alarm': is_alarm,
                'alarm_code': alarm_code,
                'alarm_description': alarm_description,
                'alarm_time': alarm_time,
                'alarm_status_raw': alarm_status
            }
            
        except Exception as e:
            logger.error(f"Error getting alarm status: {e}")
            return {
                'is_alarm': False,
                'alarm_code': 0,
                'alarm_description': 'Inget larm',
                'alarm_time': None,
                'alarm_status_raw': 0
            }
    
    def get_event_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent events (state changes) from the heat pump
        
        Events tracked:
        - Compressor ON/OFF
        - Brine pump ON/OFF
        - Radiator pump ON/OFF
        - Additional heater ON/OFF
        - Hot water cycle start/stop
        - Alarms
        """
        try:
            events = []
            
            # Hämta state changes för de senaste 24 timmarna
            metrics = [
                'compressor_status',
                'brine_pump_status',
                'radiator_pump_status',
                'switch_valve_status',
                'additional_heat_percent',
                'alarm_code',
                'alarm_status'
            ]
            
            logger.info(f"Fetching event log for {len(metrics)} metrics...")
            
            for metric in metrics:
                # Aggregera till 1-minuters intervall
                query = f'''
                    from(bucket: "{self.bucket}")
                        |> range(start: -24h)
                        |> filter(fn: (r) => r._measurement == "heatpump")
                        |> filter(fn: (r) => r.name == "{metric}")
                        |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
                        |> yield(name: "mean")
                '''
                
                logger.debug(f"Querying metric: {metric}")
                result = self.query_api.query_data_frame(query)
                
                if isinstance(result, list):
                    result = pd.concat(result, ignore_index=True)
                
                if result.empty:
                    logger.debug(f"No data for {metric}")
                    continue
                
                logger.info(f"Got {len(result)} rows for {metric}")
                
                result = result.sort_values('_time')
                
                # Detektera state changes
                result['prev_value'] = result['_value'].shift(1)
                
                # Räkna antal changes
                changes_detected = 0
                
                for idx, row in result.iterrows():
                    if pd.isna(row['prev_value']):
                        continue
                    
                    current = row['_value']
                    previous = row['prev_value']
                    timestamp = row['_time']
                    
                    # Kompressor
                    if metric == 'compressor_status':
                        if current > 0 and previous == 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Kompressor PÅ',
                                'type': 'info',
                                'icon': '🔄'
                            })
                            changes_detected += 1
                        elif current == 0 and previous > 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Kompressor AV',
                                'type': 'info',
                                'icon': '⏸️'
                            })
                            changes_detected += 1
                    
                    # Köldbärarpump
                    elif metric == 'brine_pump_status':
                        if current > 0 and previous == 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Köldbärarpump PÅ',
                                'type': 'info',
                                'icon': '💧'
                            })
                            changes_detected += 1
                        elif current == 0 and previous > 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Köldbärarpump AV',
                                'type': 'info',
                                'icon': '💧'
                            })
                            changes_detected += 1
                    
                    # Radiatorpump
                    elif metric == 'radiator_pump_status':
                        if current > 0 and previous == 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Radiatorpump PÅ',
                                'type': 'info',
                                'icon': '📡'
                            })
                            changes_detected += 1
                        elif current == 0 and previous > 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Radiatorpump AV',
                                'type': 'info',
                                'icon': '📡'
                            })
                            changes_detected += 1
                    
                    # Varmvattencykel
                    elif metric == 'switch_valve_status':
                        if current == 1 and previous == 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Varmvattencykel START',
                                'type': 'info',
                                'icon': '🚿'
                            })
                            changes_detected += 1
                        elif current == 0 and previous == 1:
                            events.append({
                                'time': timestamp,
                                'event': 'Varmvattencykel STOPP',
                                'type': 'info',
                                'icon': '🚿'
                            })
                            changes_detected += 1
                    
                    # Tillsattsvärme
                    elif metric == 'additional_heat_percent':
                        if current > 0 and previous == 0:
                            events.append({
                                'time': timestamp,
                                'event': f'Tillsattsvärme PÅ ({int(current)}%)',
                                'type': 'warning',
                                'icon': '🔥'
                            })
                            changes_detected += 1
                        elif current == 0 and previous > 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Tillsattsvärme AV',
                                'type': 'info',
                                'icon': '🔥'
                            })
                            changes_detected += 1
                        elif current > 0 and previous > 0 and abs(current - previous) > 10:
                            events.append({
                                'time': timestamp,
                                'event': f'Tillsattsvärme ändrad till {int(current)}%',
                                'type': 'warning',
                                'icon': '🔥'
                            })
                            changes_detected += 1
                    
                    # Larm (brand-aware)
                    elif metric == 'alarm_code':
                        if current > 0 and previous == 0:
                            alarm_desc = self.alarm_codes.get(int(current), f"Kod {int(current)}")
                            events.append({
                                'time': timestamp,
                                'event': f'LARM - {alarm_desc}',
                                'type': 'danger',
                                'icon': '⚠️'
                            })
                            changes_detected += 1
                        elif current == 0 and previous > 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Larm återställt',
                                'type': 'success',
                                'icon': '✅'
                            })
                            changes_detected += 1

                    # Larmstatus (IVT uses alarm_status to signal active alarms)
                    elif metric == 'alarm_status':
                        if current > 0 and previous == 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Larm aktiverat',
                                'type': 'danger',
                                'icon': '⚠️'
                            })
                            changes_detected += 1
                        elif current == 0 and previous > 0:
                            events.append({
                                'time': timestamp,
                                'event': 'Larm återställt',
                                'type': 'success',
                                'icon': '✅'
                            })
                            changes_detected += 1

                logger.info(f"Detected {changes_detected} changes for {metric}")
            
            logger.info(f"Total events before sorting: {len(events)}")
            
            # Sortera efter tid (senaste först)
            events = sorted(events, key=lambda x: x['time'], reverse=True)
            
            # Begränsa till antal
            events = events[:limit]
            
            logger.info(f"Returning {len(events)} events after limit")
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting event log: {e}")
            return []
