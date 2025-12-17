#!/usr/bin/env python3
"""
Heat Pump Dashboard - Flask + WebSocket Version
Modern architecture with ECharts and Socket.IO
Supports: Thermia, IVT, NIBE
"""

import os
import sys
import logging
import yaml
import math
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import eventlet

# Add parent directory to path for provider imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers import get_provider
from data_query import HeatPumpDataQuery
from config_colors import THERMIA_COLORS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'heatpump-dashboard-secret-key')
CORS(app)

# Initialize Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25
)

# Load provider from config
def load_provider():
    """Load heat pump provider from config"""
    config_path = '/app/config.yaml'
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            brand = config.get('brand', 'thermia')
        else:
            brand = os.getenv('HEATPUMP_BRAND', 'thermia')

        provider = get_provider(brand)
        logger.info(f"✅ Loaded provider: {provider.get_display_name()}")
        return provider
    except Exception as e:
        logger.error(f"Failed to load provider: {e}, defaulting to Thermia")
        from providers.thermia.provider import ThermiaProvider
        return ThermiaProvider()


# Initialize global objects
provider = load_provider()
data_query = HeatPumpDataQuery()

# Store connected clients and their time ranges
connected_clients = {}


# ==================== HTTP Routes ====================

@app.route('/')
def index():
    """Serve main dashboard page"""
    return render_template('dashboard.html',
                         brand=provider.get_brand_name(),
                         brand_name=provider.get_display_name(),
                         dashboard_title=provider.get_dashboard_title())

def clean_nan_values(obj):
    """
    Recursively replace NaN, Infinity, and non-serializable types for JSON serialization.
    JSON doesn't support NaN/Infinity, pandas Timestamps, or numpy types.
    """
    import pandas as pd
    import numpy as np
    from datetime import datetime as dt

    try:
        if isinstance(obj, dict):
            return {key: clean_nan_values(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [clean_nan_values(item) for item in obj]
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat() if pd.notna(obj) else None
        elif isinstance(obj, dt):
            return obj.isoformat()
        elif isinstance(obj, (np.bool_,)):  # numpy boolean
            return bool(obj)
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif obj is pd.NaT:  # Explicit check for NaT
            return None
        else:
            # Try pd.isna() but catch errors for incompatible types
            try:
                if pd.isna(obj):
                    return None
            except (ValueError, TypeError):
                pass
            return obj
    except Exception as e:
        logger.warning(f"clean_nan_values error for {type(obj)}: {e}")
        return str(obj) if obj is not None else None


@app.route('/test')
def test():
    """Serve test dashboard page"""
    return render_template('index.html',
                         brand_name=provider.get_display_name(),
                         dashboard_title=provider.get_dashboard_title())


@app.route('/mobile')
def mobile():
    """Serve mobile-optimized dashboard page"""
    return render_template('mobile.html',
                         brand_name=provider.get_display_name(),
                         dashboard_title=provider.get_dashboard_title())


@app.route('/api/config')
def get_config():
    """Get dashboard configuration"""
    return jsonify({
        'brand': provider.get_brand_name(),
        'display_name': provider.get_display_name(),
        'colors': THERMIA_COLORS
    })


@app.route('/api/debug/all-metrics')
def get_all_metrics_debug():
    """
    DEBUG ENDPOINT: Get all current metrics from InfluxDB
    Returns all available metrics with their latest values for troubleshooting
    """
    try:
        logger.info("🔧 Debug: Fetching all metrics")

        # Query to get ALL unique metric names from the last hour
        query = f'''
            from(bucket: "{data_query.bucket}")
                |> range(start: -1h)
                |> filter(fn: (r) => r._measurement == "heatpump")
                |> keep(columns: ["name", "_value", "_time"])
                |> last()
        '''

        logger.info(f"🔧 Debug query: {query}")
        df = data_query.query_api.query_data_frame(query)

        # Handle case where result is a list of DataFrames
        if isinstance(df, list):
            if len(df) == 0:
                logger.warning("⚠️ No data returned from query")
                return jsonify({
                    'total_metrics': 0,
                    'metrics': [],
                    'timestamp': datetime.now().isoformat(),
                    'brand': provider.get_brand_name(),
                    'message': 'No data found in last hour'
                })
            df = pd.concat(df, ignore_index=True)

        logger.info(f"🔧 Debug: DataFrame shape: {df.shape}, columns: {list(df.columns) if not df.empty else 'empty'}")

        # Values are already converted by the collector before storing to DB
        metrics = []

        if not df.empty:
            # Group by metric name
            for metric_name in df['name'].unique():
                metric_data = df[df['name'] == metric_name].iloc[0]

                value = metric_data['_value']
                timestamp = metric_data['_time']

                # Convert numpy types to native Python types for JSON serialization
                if hasattr(value, 'item'):
                    # numpy int64/float64 -> Python int/float
                    display_value = value.item()
                else:
                    display_value = value

                # Format value based on type
                if isinstance(display_value, float):
                    formatted_value = f"{display_value:.1f}"
                else:
                    formatted_value = f"{display_value}"

                metrics.append({
                    'name': metric_name,
                    'value': display_value,
                    'formatted_value': formatted_value,
                    'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    'type': type(display_value).__name__
                })

        # Sort by metric name
        metrics.sort(key=lambda x: x['name'])

        result = {
            'total_metrics': len(metrics),
            'metrics': metrics,
            'timestamp': datetime.now().isoformat(),
            'brand': provider.get_brand_name()
        }

        logger.info(f"✅ Debug: Found {len(metrics)} metrics")
        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ Error in debug endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e), 'metrics': [], 'traceback': str(e)}), 500


def fetch_all_data_parallel(time_range):
    """
    Fetch all dashboard data in parallel using eventlet green threads.

    This reduces load time from ~20s (sequential) to ~2-3s (parallel)
    by running all InfluxDB queries simultaneously.

    OPTIMIZATION: Uses batch fetching for all time ranges to reduce round-trips.
    """
    import time
    start_time = time.time()

    # Use optimized batch fetch for ALL time ranges (much faster)
    logger.info(f"🚀 Using optimized batch fetch for {time_range}")
    return fetch_all_data_batch(time_range)


def fetch_all_data_batch(time_range):
    """
    OPTIMIZED: Fetch all metrics in ONE InfluxDB query, then split.

    This reduces 30d load time from 8s to ~2s by minimizing InfluxDB round-trips.
    Instead of 10 separate queries, we do 1 big query with all metrics.
    """
    import time
    start_time = time.time()

    # List ALL metrics we need (including alarm/status for events)
    all_metrics = [
        'outdoor_temp', 'indoor_temp', 'radiator_forward', 'radiator_return',
        'heat_carrier_forward', 'heat_carrier_return',  # IVT alternative for radiator temps
        'hot_water_top', 'brine_in_evaporator', 'brine_out_condenser',
        'compressor_status', 'power_consumption', 'additional_heat_percent',
        'switch_valve_status', 'brine_pump_status', 'radiator_pump_status',
        'alarm_status', 'alarm_code'  # Added for alarm/event detection
    ]

    # ONE query to get everything
    logger.info(f"📊 Batch fetching {len(all_metrics)} metrics for {time_range}")
    query_start = time.time()
    df = data_query.query_metrics(all_metrics, time_range)
    query_elapsed = time.time() - query_start
    logger.info(f"  ⏱️  InfluxDB query took {query_elapsed:.2f}s")

    # Process the data in parallel (much faster than separate queries)
    process_start = time.time()

    # OPTIMIZATION: Calculate runtime once and reuse (used by runtime, sankey, and kpi)
    logger.info(f"  📊 Pre-calculating runtime stats (used by 3 tasks)...")
    runtime_cache_start = time.time()
    cached_runtime_stats = data_query.calculate_runtime_stats(time_range)
    runtime_cache_elapsed = time.time() - runtime_cache_start
    logger.info(f"    ⏱️  Runtime calculation took {runtime_cache_elapsed:.2f}s")

    # OPTIMIZATION: Query visualization metrics with fine aggregation for aligned charts
    # Temperature, COP, and Performance charts need same data points for alignment
    logger.info(f"  📊 Fetching visualization metrics with fine aggregation...")
    viz_query_start = time.time()
    viz_metrics = [
        'outdoor_temp', 'indoor_temp', 'radiator_forward', 'radiator_return',
        'heat_carrier_forward', 'heat_carrier_return',  # IVT alternative for radiator temps
        'hot_water_top', 'brine_in_evaporator', 'brine_out_condenser',
        'compressor_status', 'power_consumption',
        'pressure_tube_temp', 'hot_gas_compressor',  # Hetgas: Thermia uses pressure_tube_temp, IVT uses hot_gas_compressor
        'degree_minutes'  # Integral for Thermia
    ]
    viz_aggregation = data_query._get_cop_aggregation_window(time_range)
    viz_df_raw = data_query.query_metrics(viz_metrics, time_range, aggregation_window=viz_aggregation)
    viz_query_elapsed = time.time() - viz_query_start
    logger.info(f"    ⏱️  Visualization query took {viz_query_elapsed:.2f}s ({viz_aggregation} aggregation)")

    # CRITICAL: Pivot once to create unified timestamp index for all charts
    logger.info(f"  📊 Creating unified timestamp index for chart alignment...")
    pivot_start = time.time()
    viz_df_pivot = viz_df_raw.pivot_table(
        index='_time',
        columns='name',
        values='_value',
        aggfunc='mean'
    ).reset_index()
    pivot_elapsed = time.time() - pivot_start
    logger.info(f"    ⏱️  Pivot completed in {pivot_elapsed:.2f}s ({len(viz_df_pivot)} timestamps)")

    # Fill small gaps (1-3 missing points) using forward fill
    # This handles sensors reporting at slightly different times
    # Only fills small gaps (limit=3) to avoid propagating stale data
    logger.info(f"  📊 Filling small gaps in sensor data...")
    fill_start = time.time()
    viz_df_pivot = viz_df_pivot.ffill(limit=3)
    fill_elapsed = time.time() - fill_start
    logger.info(f"    ⏱️  Gap filling completed in {fill_elapsed:.2f}s")

    # Pre-calculate COP from pivoted data (aligned timestamps guaranteed)
    logger.info(f"  📊 Pre-calculating COP from pivoted data...")
    cop_cache_start = time.time()
    cached_cop_df = calculate_cop_from_pivot(viz_df_pivot)
    cop_cache_elapsed = time.time() - cop_cache_start
    logger.info(f"    ⏱️  COP calculation took {cop_cache_elapsed:.2f}s")

    # OPTIMIZATION: Calculate hot water stats from batch data (eliminates 2.5s InfluxDB query)
    logger.info(f"  📊 Pre-calculating hot water stats from batch data (used by kpi task)...")
    hw_cache_start = time.time()
    # Use same time range as batch query for consistency (batch data already fetched)
    cached_hot_water_stats = data_query.analyze_hot_water_cycles_from_df(df, time_range)
    hw_cache_elapsed = time.time() - hw_cache_start
    logger.info(f"    ⏱️  Hot water analysis took {hw_cache_elapsed:.2f}s")

    # FIX: Get min/max/avg directly from DB using min()/max()/mean() on RAW data
    # The batch data uses aggregateWindow(fn: mean) which corrupts min/max values
    # For Thermia H66, even min/max should end in .0 (e.g., 33.0, not 31.9)
    logger.info(f"  📊 Fetching min/max/avg directly from DB (avoids mean aggregation bug)...")
    minmax_cache_start = time.time()
    cached_min_max = data_query.get_min_max_values(time_range)  # Uses |> min(), |> max(), |> mean() on raw data
    minmax_cache_elapsed = time.time() - minmax_cache_start
    logger.info(f"    ⏱️  Min/max query took {minmax_cache_elapsed:.2f}s")

    # FIX: Get latest values directly from DB using last() - NOT from aggregated batch data
    # The batch data uses aggregateWindow(fn: mean) which causes averaged values
    # For Thermia H66, temperatures must always end in .0 (e.g., 33.0, not 31.9)
    logger.info(f"  📊 Fetching latest values directly from DB (avoids mean aggregation bug)...")
    latest_cache_start = time.time()
    cached_latest_values = data_query.get_latest_values()  # Uses |> last() - actual raw values
    latest_cache_elapsed = time.time() - latest_cache_start
    logger.info(f"    ⏱️  Latest values query took {latest_cache_elapsed:.2f}s")

    # OPTIMIZATION: Get alarm status from batch data (eliminates 1-2 DB queries)
    logger.info(f"  📊 Pre-calculating alarm status from batch data (used by status task)...")
    alarm_cache_start = time.time()
    cached_alarm_status = data_query.get_alarm_status_from_df(df)
    alarm_cache_elapsed = time.time() - alarm_cache_start
    logger.info(f"    ⏱️  Alarm status calculation took {alarm_cache_elapsed:.2f}s")

    # OPTIMIZATION: Get event log from batch data (eliminates 6 separate DB queries ~2s)
    logger.info(f"  📊 Pre-calculating event log from batch data (used by events task)...")
    events_cache_start = time.time()
    cached_events = data_query.get_event_log_from_df(df, limit=20)
    events_cache_elapsed = time.time() - events_cache_start
    logger.info(f"    ⏱️  Event log calculation took {events_cache_elapsed:.2f}s")

    pool = eventlet.GreenPool(size=10)

    tasks = {
        'cop': lambda: get_cop_data_from_pivot(cached_cop_df),  # Uses interval COP data
        'temperature': lambda: get_temperature_data_from_pivot(viz_df_pivot),  # Uses pivoted viz data (aligned)
        'runtime': lambda: get_runtime_data_cached(cached_runtime_stats),
        'sankey': lambda: get_sankey_data_cached(cached_cop_df, cached_runtime_stats),  # Uses COP for average
        'performance': lambda: get_performance_data_from_pivot(viz_df_pivot),  # Uses pivoted viz data (aligned)
        'power': lambda: get_power_data_from_df(df),  # Uses batch data (OK for simple power chart)
        'valve': lambda: get_valve_data_from_df(df),  # Uses batch data (OK for valve status)
        'status': lambda: get_status_data_fully_cached(cached_cop_df, cached_min_max, cached_latest_values, cached_alarm_status),
        'events': lambda: get_event_log_cached(cached_events),  # Uses pre-calculated events
        'kpi': lambda: get_kpi_data_cached(time_range, cached_runtime_stats, cached_hot_water_stats),
    }

    results = {}
    for key, task in tasks.items():
        results[key] = pool.spawn(task)

    # Collect results with timing
    data = {}
    for key, green_thread in results.items():
        task_start = time.time()
        data[key] = green_thread.wait()
        task_elapsed = time.time() - task_start
        if task_elapsed > 0.5:  # Log slow tasks
            logger.info(f"    ⏱️  Task '{key}' took {task_elapsed:.2f}s")

    process_elapsed = time.time() - process_start
    logger.info(f"  ⏱️  Data processing took {process_elapsed:.2f}s")

    data['config'] = {
        'brand': provider.get_brand_name(),
        'display_name': provider.get_display_name(),
        'colors': THERMIA_COLORS
    }

    elapsed = time.time() - start_time
    logger.info(f"⚡⚡ BATCH fetch completed in {elapsed:.2f}s (range: {time_range})")

    return data


# Helper functions to extract data from pre-pivoted dataframe

def calculate_cop_from_pivot(df_pivot, interval_minutes=15):
    """Calculate Interval COP from pre-pivoted dataframe (guaranteed aligned timestamps)

    IMPROVED: Uses interval-based aggregation for more accurate COP:
    - Groups data into fixed intervals (default 15 minutes)
    - COP = Σ heat_output / Σ electrical_input per interval
    - This matches industry standards and manufacturer testing methods

    Returns a NEW dataframe with interval-aggregated COP values.
    """
    try:
        if df_pivot.empty:
            logger.warning("calculate_cop_from_pivot: Empty input dataframe")
            return pd.DataFrame()

        logger.debug(f"calculate_cop_from_pivot: Input shape {df_pivot.shape}, columns: {list(df_pivot.columns)}")

        # Get flow_factor from data_query (configured in config.yaml)
        flow_factor = data_query.cop_flow_factor

        # Make a copy to avoid modifying original
        df = df_pivot.copy()

        # Ensure _time is datetime
        if '_time' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['_time']):
            df['_time'] = pd.to_datetime(df['_time'])

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
            df.loc[valid_mask, 'radiator_delta'] * flow_factor *
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


def get_cop_data_from_pivot(df_cop):
    """Extract COP data from pre-calculated interval COP dataframe"""
    try:
        if df_cop.empty or 'estimated_cop' not in df_cop.columns:
            return {'timestamps': [], 'values': [], 'seasonal_values': [], 'avg': 0}

        # Convert timestamps and COP values
        timestamps = df_cop['_time'].astype(str).tolist()
        values = df_cop['estimated_cop'].replace({float('nan'): None}).tolist()

        # Include seasonal COP if available
        seasonal_values = []
        if 'seasonal_cop' in df_cop.columns:
            seasonal_values = df_cop['seasonal_cop'].replace({float('nan'): None}).tolist()

        # Calculate average only from non-NaN values
        avg_cop = float(df_cop['estimated_cop'].mean()) if not df_cop['estimated_cop'].isna().all() else 0

        return {
            'timestamps': timestamps,
            'values': values,
            'seasonal_values': seasonal_values,
            'avg': avg_cop
        }
    except Exception as e:
        logger.error(f"Error getting COP data from pivot: {e}")
        return {'timestamps': [], 'values': [], 'seasonal_values': [], 'avg': 0}


def get_temperature_data_from_pivot(df_pivot):
    """Extract temperature data from pre-pivoted dataframe (guaranteed aligned timestamps)"""
    try:
        if df_pivot.empty:
            return {'timestamps': []}

        # Get consistent timestamps from pivoted dataframe
        timestamps = df_pivot['_time'].astype(str).tolist()

        # Extract each metric with same timestamp index
        metrics = [
            'outdoor_temp', 'indoor_temp', 'radiator_forward',
            'radiator_return', 'heat_carrier_forward', 'heat_carrier_return',  # IVT alternative
            'hot_water_top', 'brine_in_evaporator', 'brine_out_condenser',
            'pressure_tube_temp', 'hot_gas_compressor',  # Hetgas: Thermia or IVT
            'degree_minutes'  # Integral for Thermia
        ]

        result = {'timestamps': timestamps}
        for metric in metrics:
            if metric in df_pivot.columns:
                # Replace NaN with None for JSON null values
                result[metric] = df_pivot[metric].replace({float('nan'): None}).tolist()

        # Calculate delta for radiator side (Thermia: radiator, IVT: heat_carrier)
        if 'heat_carrier_forward' in df_pivot.columns and 'heat_carrier_return' in df_pivot.columns:
            # IVT uses heat_carrier
            df_pivot['radiator_delta'] = df_pivot['heat_carrier_forward'] - df_pivot['heat_carrier_return']
            result['radiator_delta'] = df_pivot['radiator_delta'].replace({float('nan'): None}).tolist()
        elif 'radiator_forward' in df_pivot.columns and 'radiator_return' in df_pivot.columns:
            # Thermia uses radiator
            df_pivot['radiator_delta'] = df_pivot['radiator_forward'] - df_pivot['radiator_return']
            result['radiator_delta'] = df_pivot['radiator_delta'].replace({float('nan'): None}).tolist()

        # Calculate delta for brine/köldbärare side
        if 'brine_in_evaporator' in df_pivot.columns and 'brine_out_condenser' in df_pivot.columns:
            df_pivot['brine_delta'] = df_pivot['brine_in_evaporator'] - df_pivot['brine_out_condenser']
            result['brine_delta'] = df_pivot['brine_delta'].replace({float('nan'): None}).tolist()

        return result
    except Exception as e:
        logger.error(f"Error getting temperature data from pivot: {e}")
        return {'timestamps': []}


def get_performance_data_from_pivot(df_pivot):
    """Extract performance data from pre-pivoted dataframe (guaranteed aligned timestamps)"""
    import pandas as pd
    try:
        if df_pivot.empty:
            return {
                'brine_delta': [],
                'radiator_delta': [],
                'compressor_status': [],
                'timestamps': []
            }

        # Get consistent timestamps
        timestamps = df_pivot['_time'].astype(str).tolist()

        # Calculate deltas using pivoted data (aligned timestamps guaranteed)
        brine_delta = []
        radiator_delta = []
        compressor_status = []

        if 'brine_in_evaporator' in df_pivot.columns and 'brine_out_condenser' in df_pivot.columns:
            df_pivot['brine_delta_calc'] = df_pivot['brine_in_evaporator'] - df_pivot['brine_out_condenser']
            brine_delta = [
                [row['_time'].isoformat(), float(row['brine_delta_calc']) if not pd.isna(row['brine_delta_calc']) else None]
                for _, row in df_pivot.iterrows()
            ]

        if 'radiator_forward' in df_pivot.columns and 'radiator_return' in df_pivot.columns:
            df_pivot['radiator_delta_calc'] = df_pivot['radiator_forward'] - df_pivot['radiator_return']
            radiator_delta = [
                [row['_time'].isoformat(), float(row['radiator_delta_calc']) if not pd.isna(row['radiator_delta_calc']) else None]
                for _, row in df_pivot.iterrows()
            ]

        if 'compressor_status' in df_pivot.columns:
            compressor_status = [
                [row['_time'].isoformat(), float(row['compressor_status']) if not pd.isna(row['compressor_status']) else None]
                for _, row in df_pivot.iterrows()
            ]

        return {
            'brine_delta': brine_delta,
            'radiator_delta': radiator_delta,
            'compressor_status': compressor_status,
            'timestamps': timestamps
        }
    except Exception as e:
        logger.error(f"Error getting performance data from pivot: {e}")
        return {
            'brine_delta': [],
            'radiator_delta': [],
            'compressor_status': [],
            'timestamps': []
        }


# DEPRECATED: Old helper functions (kept for compatibility)

def get_cop_data_cached(cached_cop_df):
    """Extract COP data from pre-calculated COP dataframe (avoids redundant InfluxDB query)"""
    try:
        if cached_cop_df.empty or 'estimated_cop' not in cached_cop_df.columns:
            return {'timestamps': [], 'values': [], 'avg': 0}

        # DON'T drop NaN values - keep timestamps aligned with other charts
        # Convert NaN to None (becomes null in JSON) for gaps when compressor is off
        timestamps = cached_cop_df['_time'].astype(str).tolist()
        values = cached_cop_df['estimated_cop'].replace({float('nan'): None}).tolist()

        # Calculate average only from non-NaN values
        avg_cop = float(cached_cop_df['estimated_cop'].mean()) if not cached_cop_df['estimated_cop'].isna().all() else 0

        return {
            'timestamps': timestamps,
            'values': values,
            'avg': avg_cop
        }
    except Exception as e:
        logger.error(f"Error getting cached COP data: {e}")
        return {'timestamps': [], 'values': [], 'avg': 0}


def get_temperature_data_from_df(df):
    """Extract temperature data from pre-fetched dataframe with aligned timestamps"""
    try:
        if df.empty:
            return {'timestamps': []}

        # Pivot dataframe to ensure consistent timestamp index across all metrics
        df_pivot = df.pivot_table(
            index='_time',
            columns='name',
            values='_value',
            aggfunc='mean'
        ).reset_index()

        # Get consistent timestamps from pivoted dataframe
        timestamps = df_pivot['_time'].astype(str).tolist()

        # Extract each metric with same timestamp index
        metrics = [
            'outdoor_temp', 'indoor_temp', 'radiator_forward',
            'radiator_return', 'hot_water_top',
            'brine_in_evaporator', 'brine_out_condenser'
        ]

        result = {'timestamps': timestamps}
        for metric in metrics:
            if metric in df_pivot.columns:
                # Replace NaN with None for JSON null values
                result[metric] = df_pivot[metric].replace({float('nan'): None}).tolist()

        return result
    except Exception as e:
        logger.error(f"Error getting temperature data from df: {e}")
        return {'timestamps': []}


def get_performance_data_from_df(df):
    """Extract performance data from pre-fetched dataframe with aligned timestamps"""
    import pandas as pd
    try:
        if df.empty:
            return {
                'brine_delta': [],
                'radiator_delta': [],
                'compressor_status': [],
                'timestamps': []
            }

        # Pivot dataframe to ensure consistent timestamp index
        df_pivot = df.pivot_table(
            index='_time',
            columns='name',
            values='_value',
            aggfunc='mean'
        ).reset_index()

        # Get consistent timestamps
        timestamps = df_pivot['_time'].astype(str).tolist()

        # Calculate deltas using pivoted data (aligned timestamps)
        brine_delta = []
        radiator_delta = []
        compressor_status = []

        if 'brine_in_evaporator' in df_pivot.columns and 'brine_out_condenser' in df_pivot.columns:
            df_pivot['brine_delta_calc'] = df_pivot['brine_in_evaporator'] - df_pivot['brine_out_condenser']
            brine_delta = [
                [row['_time'].isoformat(), float(row['brine_delta_calc']) if not pd.isna(row['brine_delta_calc']) else None]
                for _, row in df_pivot.iterrows()
            ]

        if 'radiator_forward' in df_pivot.columns and 'radiator_return' in df_pivot.columns:
            df_pivot['radiator_delta_calc'] = df_pivot['radiator_forward'] - df_pivot['radiator_return']
            radiator_delta = [
                [row['_time'].isoformat(), float(row['radiator_delta_calc']) if not pd.isna(row['radiator_delta_calc']) else None]
                for _, row in df_pivot.iterrows()
            ]

        if 'compressor_status' in df_pivot.columns:
            compressor_status = [
                [row['_time'].isoformat(), float(row['compressor_status']) if not pd.isna(row['compressor_status']) else None]
                for _, row in df_pivot.iterrows()
            ]

        return {
            'brine_delta': brine_delta,
            'radiator_delta': radiator_delta,
            'compressor_status': compressor_status,
            'timestamps': timestamps
        }
    except Exception as e:
        logger.error(f"Error getting performance data from df: {e}")
        return {
            'brine_delta': [],
            'radiator_delta': [],
            'compressor_status': [],
            'timestamps': []
        }


def get_power_data_from_df(df):
    """Extract power data from pre-fetched dataframe"""
    try:
        result = {
            'power_consumption': [],
            'compressor_status': [],
            'additional_heat_percent': [],
            'timestamps': []
        }

        if df.empty:
            return result

        # Get power consumption
        power = df[df['name'] == 'power_consumption']
        if not power.empty:
            result['power_consumption'] = [
                [row['_time'].isoformat(), float(row['_value'])]
                for _, row in power.iterrows()
            ]
            result['timestamps'] = power['_time'].astype(str).tolist()

        # Get compressor status
        comp = df[df['name'] == 'compressor_status']
        if not comp.empty:
            result['compressor_status'] = [
                [row['_time'].isoformat(), float(row['_value'])]
                for _, row in comp.iterrows()
            ]

        # Get heater percentage
        heater = df[df['name'] == 'additional_heat_percent']
        if not heater.empty:
            result['additional_heat_percent'] = [
                [row['_time'].isoformat(), float(row['_value'])]
                for _, row in heater.iterrows()
            ]

        return result
    except Exception as e:
        logger.error(f"Error getting power data from df: {e}")
        return {
            'power_consumption': [],
            'compressor_status': [],
            'additional_heat_percent': [],
            'timestamps': []
        }


def get_valve_data_from_df(df):
    """Extract valve data from pre-fetched dataframe"""
    try:
        result = {
            'valve_status': [],
            'compressor_status': [],
            'hot_water_temp': [],
            'timestamps': []
        }

        if df.empty:
            logger.warning("get_valve_data_from_df: DataFrame is empty")
            return result

        # Debug: show available metrics
        available_metrics = df['name'].unique().tolist() if 'name' in df.columns else []
        logger.info(f"get_valve_data_from_df: Available metrics: {available_metrics}")

        # Get valve status
        valve = df[df['name'] == 'switch_valve_status']
        logger.info(f"get_valve_data_from_df: switch_valve_status rows: {len(valve)}")
        if not valve.empty:
            result['valve_status'] = [
                [row['_time'].isoformat(), float(row['_value'])]
                for _, row in valve.iterrows()
            ]
            result['timestamps'] = valve['_time'].astype(str).tolist()

        # Get compressor status
        comp = df[df['name'] == 'compressor_status']
        if not comp.empty:
            result['compressor_status'] = [
                [row['_time'].isoformat(), float(row['_value'])]
                for _, row in comp.iterrows()
            ]

        # Get hot water temp
        hw_temp = df[df['name'] == 'hot_water_top']
        if not hw_temp.empty:
            result['hot_water_temp'] = [
                [row['_time'].isoformat(), float(row['_value'])]
                for _, row in hw_temp.iterrows()
            ]

        return result
    except Exception as e:
        logger.error(f"Error getting valve data from df: {e}")
        return {
            'valve_status': [],
            'compressor_status': [],
            'hot_water_temp': [],
            'timestamps': []
        }


@app.route('/api/initial-data')
def get_initial_data():
    """Load all graph data for initial page load - PARALLELIZED"""
    time_range = request.args.get('range', '24h')

    try:
        logger.info(f"📥 Loading initial data for range: {time_range}")

        # Use parallel fetching for much faster load times
        data = fetch_all_data_parallel(time_range)

        logger.info(f"✅ Initial data loaded successfully")
        # Clean NaN values before JSON serialization
        data = clean_nan_values(data)
        return jsonify(data)

    except Exception as e:
        logger.error(f"❌ Error loading initial data: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== Data Extraction Functions ====================

def get_cop_data(time_range):
    """Extract COP data from data_query"""
    try:
        cop_df = data_query.calculate_cop(time_range)

        if cop_df.empty or 'estimated_cop' not in cop_df.columns:
            return {'timestamps': [], 'values': [], 'avg': 0}

        # Filter out null/NaN values to avoid gaps in chart
        cop_df = cop_df.dropna(subset=['estimated_cop'])

        if cop_df.empty:
            return {'timestamps': [], 'values': [], 'avg': 0}

        return {
            'timestamps': cop_df['_time'].astype(str).tolist(),
            'values': cop_df['estimated_cop'].tolist(),
            'avg': float(cop_df['estimated_cop'].mean())
        }
    except Exception as e:
        logger.error(f"Error getting COP data: {e}")
        return {'timestamps': [], 'values': [], 'avg': 0}


def get_temperature_data(time_range):
    """Extract temperature data from data_query"""
    try:
        metrics = [
            'outdoor_temp', 'indoor_temp', 'radiator_forward',
            'radiator_return', 'hot_water_top',
            'brine_in_evaporator', 'brine_out_condenser'
        ]

        df = data_query.query_metrics(metrics, time_range)

        result = {'timestamps': []}

        if not df.empty:
            # Get common timestamps from first metric
            first_metric = df[df['name'] == metrics[0]]
            if not first_metric.empty:
                result['timestamps'] = first_metric['_time'].astype(str).tolist()

            # Extract data for each metric
            for metric in metrics:
                metric_df = df[df['name'] == metric]
                if not metric_df.empty:
                    result[metric] = metric_df['_value'].tolist()

        return result
    except Exception as e:
        logger.error(f"Error getting temperature data: {e}")
        return {'timestamps': []}


def get_runtime_data(time_range):
    """Extract runtime statistics"""
    try:
        runtime_stats = data_query.calculate_runtime_stats(time_range)
        return {
            'compressor_percent': runtime_stats.get('compressor_runtime_percent', 0),
            'aux_heater_percent': runtime_stats.get('aux_heater_runtime_percent', 0),
            'inactive_percent': 100 - runtime_stats.get('compressor_runtime_percent', 0) -
                              runtime_stats.get('aux_heater_runtime_percent', 0)
        }
    except Exception as e:
        logger.error(f"Error getting runtime data: {e}")
        return {'compressor_percent': 0, 'aux_heater_percent': 0, 'inactive_percent': 100}


def get_runtime_data_cached(cached_runtime_stats):
    """Extract runtime statistics from pre-calculated cache (avoids redundant InfluxDB query)"""
    try:
        return {
            'compressor_percent': cached_runtime_stats.get('compressor_runtime_percent', 0),
            'aux_heater_percent': cached_runtime_stats.get('aux_heater_runtime_percent', 0),
            'inactive_percent': 100 - cached_runtime_stats.get('compressor_runtime_percent', 0) -
                              cached_runtime_stats.get('aux_heater_runtime_percent', 0)
        }
    except Exception as e:
        logger.error(f"Error getting cached runtime data: {e}")
        return {'compressor_percent': 0, 'aux_heater_percent': 0, 'inactive_percent': 100}


def get_sankey_data(time_range):
    """Build Sankey diagram data"""
    try:
        cop_df = data_query.calculate_cop(time_range)
        runtime_stats = data_query.calculate_runtime_stats(time_range)

        # Calculate energy flows (same logic as Plotly version)
        if cop_df.empty or 'estimated_cop' not in cop_df.columns:
            avg_cop = 3.0
            has_data = False
        else:
            avg_cop = float(cop_df['estimated_cop'].mean())
            has_data = True

        # Ensure reasonable COP value
        if avg_cop < 1.5 or avg_cop > 5.0:
            avg_cop = 3.5

        # Calculate energy flows (normalized to 100 units electric power)
        electric_power = 100
        ground_energy = electric_power * (avg_cop - 1)
        aux_heater_percent = runtime_stats.get('aux_heater_runtime_percent', 0)
        aux_heater_power = (aux_heater_percent / 100) * 50 if aux_heater_percent > 0 else 0
        total_heat = electric_power + ground_energy + aux_heater_power
        free_energy_percent = (ground_energy / total_heat * 100) if total_heat > 0 else 0

        # Build nodes and links
        nodes = [
            {'name': '🌍 Markenergi'},
            {'name': '⚡ Elkraft'},
            {'name': '🔄 Värmepump'},
            {'name': '🏠 Värme till Hus'}
        ]

        links = [
            {'source': '🌍 Markenergi', 'target': '🔄 Värmepump', 'value': ground_energy},
            {'source': '⚡ Elkraft', 'target': '🔄 Värmepump', 'value': electric_power},
            {'source': '🔄 Värmepump', 'target': '🏠 Värme till Hus', 'value': total_heat - aux_heater_power}
        ]

        if aux_heater_power > 5:
            nodes.append({'name': '🔥 Tillsattsvärme'})
            links.append({'source': '🔥 Tillsattsvärme', 'target': '🏠 Värme till Hus', 'value': aux_heater_power})

        return {
            'nodes': nodes,
            'links': links,
            'cop': avg_cop,
            'free_energy_percent': free_energy_percent,
            'has_data': has_data
        }
    except Exception as e:
        logger.error(f"Error getting Sankey data: {e}")
        return {
            'nodes': [],
            'links': [],
            'cop': 0,
            'free_energy_percent': 0,
            'has_data': False
        }


def get_sankey_data_cached(cached_cop_df, cached_runtime_stats):
    """Build Sankey diagram data using pre-calculated COP and runtime stats (avoids redundant InfluxDB queries)"""
    try:
        # Calculate energy flows (same logic as Plotly version)
        if cached_cop_df.empty or 'estimated_cop' not in cached_cop_df.columns:
            avg_cop = 3.0
            has_data = False
        else:
            avg_cop = float(cached_cop_df['estimated_cop'].mean())
            has_data = True

        # Ensure reasonable COP value
        if avg_cop < 1.5 or avg_cop > 5.0:
            avg_cop = 3.5

        # Calculate energy flows (normalized to 100 units electric power)
        electric_power = 100
        ground_energy = electric_power * (avg_cop - 1)
        aux_heater_percent = cached_runtime_stats.get('aux_heater_runtime_percent', 0)
        aux_heater_power = (aux_heater_percent / 100) * 50 if aux_heater_percent > 0 else 0
        total_heat = electric_power + ground_energy + aux_heater_power
        free_energy_percent = (ground_energy / total_heat * 100) if total_heat > 0 else 0

        # Build nodes and links
        nodes = [
            {'name': '🌍 Markenergi'},
            {'name': '⚡ Elkraft'},
            {'name': '🔄 Värmepump'},
            {'name': '🏠 Värme till Hus'}
        ]

        links = [
            {'source': '🌍 Markenergi', 'target': '🔄 Värmepump', 'value': ground_energy},
            {'source': '⚡ Elkraft', 'target': '🔄 Värmepump', 'value': electric_power},
            {'source': '🔄 Värmepump', 'target': '🏠 Värme till Hus', 'value': total_heat - aux_heater_power}
        ]

        if aux_heater_power > 5:
            nodes.append({'name': '🔥 Tillsattsvärme'})
            links.append({'source': '🔥 Tillsattsvärme', 'target': '🏠 Värme till Hus', 'value': aux_heater_power})

        return {
            'nodes': nodes,
            'links': links,
            'cop': avg_cop,
            'free_energy_percent': free_energy_percent,
            'has_data': has_data
        }
    except Exception as e:
        logger.error(f"Error getting cached Sankey data: {e}")
        return {
            'nodes': [],
            'links': [],
            'cop': 0,
            'free_energy_percent': 0,
            'has_data': False
        }


def get_performance_data(time_range):
    """Extract performance graph data (delta temperatures + compressor status)"""
    try:
        metrics = [
            'brine_in_evaporator',
            'brine_out_condenser',
            'radiator_forward',
            'radiator_return',
            'compressor_status'
        ]

        df = data_query.query_metrics(metrics, time_range)

        result = {
            'brine_delta': [],
            'radiator_delta': [],
            'compressor_status': [],
            'timestamps': []
        }

        if not df.empty:
            # Calculate brine delta (ΔT)
            brine_in = df[df['name'] == 'brine_in_evaporator']
            brine_out = df[df['name'] == 'brine_out_condenser']

            if not brine_in.empty and not brine_out.empty:
                import pandas as pd
                brine_delta = pd.merge(
                    brine_in[['_time', '_value']],
                    brine_out[['_time', '_value']],
                    on='_time',
                    suffixes=('_in', '_out')
                )
                brine_delta['delta'] = brine_delta['_value_in'] - brine_delta['_value_out']

                result['brine_delta'] = [
                    [row['_time'].isoformat(), float(row['delta'])]
                    for _, row in brine_delta.iterrows()
                ]

            # Calculate radiator delta (ΔT)
            rad_forward = df[df['name'] == 'radiator_forward']
            rad_return = df[df['name'] == 'radiator_return']

            if not rad_forward.empty and not rad_return.empty:
                import pandas as pd
                rad_delta = pd.merge(
                    rad_forward[['_time', '_value']],
                    rad_return[['_time', '_value']],
                    on='_time',
                    suffixes=('_fwd', '_ret')
                )
                rad_delta['delta'] = rad_delta['_value_fwd'] - rad_delta['_value_ret']

                result['radiator_delta'] = [
                    [row['_time'].isoformat(), float(row['delta'])]
                    for _, row in rad_delta.iterrows()
                ]

            # Get compressor status
            comp = df[df['name'] == 'compressor_status']
            if not comp.empty:
                result['compressor_status'] = [
                    [row['_time'].isoformat(), float(row['_value'])]
                    for _, row in comp.iterrows()
                ]
                result['timestamps'] = comp['_time'].astype(str).tolist()

        return result
    except Exception as e:
        logger.error(f"Error getting performance data: {e}")
        return {
            'brine_delta': [],
            'radiator_delta': [],
            'compressor_status': [],
            'timestamps': []
        }


def get_power_data(time_range):
    """Extract power graph data (power consumption + system status)"""
    try:
        metrics = [
            'power_consumption',
            'compressor_status',
            'additional_heat_percent'
        ]

        df = data_query.query_metrics(metrics, time_range)

        result = {
            'power_consumption': [],
            'compressor_status': [],
            'additional_heat_percent': [],
            'timestamps': []
        }

        if not df.empty:
            # Get power consumption
            power = df[df['name'] == 'power_consumption']
            if not power.empty:
                result['power_consumption'] = [
                    [row['_time'].isoformat(), float(row['_value'])]
                    for _, row in power.iterrows()
                ]
                result['timestamps'] = power['_time'].astype(str).tolist()

            # Get compressor status
            comp = df[df['name'] == 'compressor_status']
            if not comp.empty:
                result['compressor_status'] = [
                    [row['_time'].isoformat(), float(row['_value'])]
                    for _, row in comp.iterrows()
                ]

            # Get auxiliary heater percentage
            heater = df[df['name'] == 'additional_heat_percent']
            if not heater.empty:
                result['additional_heat_percent'] = [
                    [row['_time'].isoformat(), float(row['_value'])]
                    for _, row in heater.iterrows()
                ]

        return result
    except Exception as e:
        logger.error(f"Error getting power data: {e}")
        return {
            'power_consumption': [],
            'compressor_status': [],
            'additional_heat_percent': [],
            'timestamps': []
        }


def get_valve_data(time_range):
    """Extract valve status graph data (valve + compressor + hot water temp)"""
    try:
        metrics = [
            'switch_valve_status',
            'compressor_status',
            'hot_water_top'
        ]

        df = data_query.query_metrics(metrics, time_range)

        result = {
            'valve_status': [],
            'compressor_status': [],
            'hot_water_temp': [],
            'timestamps': []
        }

        if not df.empty:
            # Get valve status
            valve = df[df['name'] == 'switch_valve_status']
            if not valve.empty:
                result['valve_status'] = [
                    [row['_time'].isoformat(), float(row['_value'])]
                    for _, row in valve.iterrows()
                ]
                result['timestamps'] = valve['_time'].astype(str).tolist()

            # Get compressor status
            comp = df[df['name'] == 'compressor_status']
            if not comp.empty:
                result['compressor_status'] = [
                    [row['_time'].isoformat(), float(row['_value'])]
                    for _, row in comp.iterrows()
                ]

            # Get hot water temperature
            hw_temp = df[df['name'] == 'hot_water_top']
            if not hw_temp.empty:
                result['hot_water_temp'] = [
                    [row['_time'].isoformat(), float(row['_value'])]
                    for _, row in hw_temp.iterrows()
                ]

        return result
    except Exception as e:
        logger.error(f"Error getting valve data: {e}")
        return {
            'valve_status': [],
            'compressor_status': [],
            'hot_water_temp': [],
            'timestamps': []
        }


def get_status_data(time_range='24h'):
    """Get current system status including alarm, compressor, current metrics, and min/max values"""
    try:
        # Get alarm status
        alarm = data_query.get_alarm_status()

        # Get current metrics for status display
        current_metrics = data_query.get_latest_values()

        # Get min/max values for the time range
        min_max = data_query.get_min_max_values(time_range)

        # Calculate COP - use Period COP (Σheat/Σelec) for consistency
        current_cop = None
        try:
            cop_df = data_query.calculate_cop(time_range)
            if not cop_df.empty:
                # Prefer seasonal_cop (total COP = Σheat/Σelec)
                if 'seasonal_cop' in cop_df.columns:
                    seasonal_values = cop_df['seasonal_cop'].dropna()
                    if len(seasonal_values) > 0:
                        current_cop = round(seasonal_values.iloc[-1], 2)
                elif 'estimated_cop' in cop_df.columns:
                    cop_values = cop_df['estimated_cop'].dropna()
                    if len(cop_values) > 0:
                        current_cop = round(cop_values.mean(), 2)
        except Exception as e:
            logger.debug(f"Could not calculate COP: {e}")
            pass

        def get_value_with_minmax(metric_name):
            """Helper to get current value with min/max/avg"""
            current = current_metrics.get(metric_name)
            # current_metrics returns {'value': ..., 'unit': ..., 'time': ...}
            if isinstance(current, dict):
                current_val = round(current.get('value'), 1) if current.get('value') is not None else None
            else:
                current_val = round(current, 1) if current is not None else None

            mm = min_max.get(metric_name, {})
            min_val = round(mm.get('min'), 1) if mm.get('min') is not None else None
            max_val = round(mm.get('max'), 1) if mm.get('max') is not None else None
            avg_val = round(mm.get('avg'), 1) if mm.get('avg') is not None else None

            return {
                'current': current_val,
                'min': min_val,
                'max': max_val,
                'avg': avg_val
            }

        status = {
            'alarm': {
                'is_active': alarm.get('is_alarm', False),
                'code': alarm.get('alarm_code'),
                'description': alarm.get('alarm_description'),
                'time': alarm['alarm_time'].isoformat() if alarm.get('alarm_time') else None
            },
            'current': {
                'outdoor_temp': get_value_with_minmax('outdoor_temp'),
                'indoor_temp': get_value_with_minmax('indoor_temp'),
                'hot_water': get_value_with_minmax('hot_water_top'),
                'brine_in': get_value_with_minmax('brine_in_evaporator'),
                'brine_out': get_value_with_minmax('brine_out_condenser'),
                # IVT uses heat_carrier_forward/return, Thermia uses radiator_forward/return
                'radiator_forward': get_value_with_minmax('heat_carrier_forward') if get_value_with_minmax('heat_carrier_forward').get('current') is not None else get_value_with_minmax('radiator_forward'),
                'radiator_return': get_value_with_minmax('heat_carrier_return') if get_value_with_minmax('heat_carrier_return').get('current') is not None else get_value_with_minmax('radiator_return'),
                'power': round(current_metrics.get('power_consumption', {}).get('value', 0), 0) if current_metrics.get('power_consumption', {}).get('value') is not None else None,
                'compressor_running': bool(current_metrics.get('compressor_status', {}).get('value', 0)),
                'brine_pump_running': bool(current_metrics.get('brine_pump_status', {}).get('value', 0)),
                'radiator_pump_running': bool(current_metrics.get('radiator_pump_status', {}).get('value', 0)),
                'vvb_pump_running': bool(current_metrics.get('pump_heat_circuit', {}).get('value', 0)),  # IVT only
                'switch_valve_status': int(current_metrics.get('switch_valve_status', {}).get('value', 0)) if current_metrics.get('switch_valve_status', {}).get('value') is not None else 0,
                'aux_heater': current_metrics.get('additional_heat_percent', {}).get('value', 0) > 0 if current_metrics.get('additional_heat_percent', {}).get('value') is not None else False,
                'current_cop': current_cop
            },
            'timestamp': datetime.now().isoformat()
        }

        return status
    except Exception as e:
        logger.error(f"Error getting status data: {e}")
        return {
            'alarm': {'is_active': False, 'code': None, 'description': None, 'time': None},
            'current': {},
            'timestamp': datetime.now().isoformat()
        }


def get_status_data_cached(time_range='24h', cached_cop_df=None, cached_min_max=None):
    """Get current system status using cached COP and min/max data (avoids 3s+ duplicate calculations)"""
    try:
        # Get alarm status
        alarm = data_query.get_alarm_status()

        # Get current metrics for status display
        current_metrics = data_query.get_latest_values()

        # Use cached min/max values if provided (avoids 3 separate DB queries)
        min_max = cached_min_max if cached_min_max is not None else data_query.get_min_max_values(time_range)

        # Use cached COP data - use Period COP (Σheat/Σelec) for consistency
        current_cop = None
        if cached_cop_df is not None and not cached_cop_df.empty:
            if 'seasonal_cop' in cached_cop_df.columns:
                seasonal_values = cached_cop_df['seasonal_cop'].dropna()
                if len(seasonal_values) > 0:
                    current_cop = round(seasonal_values.iloc[-1], 2)
            elif 'estimated_cop' in cached_cop_df.columns:
                cop_values = cached_cop_df['estimated_cop'].dropna()
                if len(cop_values) > 0:
                    current_cop = round(cop_values.mean(), 2)

        def get_value_with_minmax(metric_name):
            """Helper to get current value with min/max/avg"""
            current = current_metrics.get(metric_name)
            if isinstance(current, dict):
                current_val = round(current.get('value'), 1) if current.get('value') is not None else None
            else:
                current_val = round(current, 1) if current is not None else None

            mm = min_max.get(metric_name, {})
            min_val = round(mm.get('min'), 1) if mm.get('min') is not None else None
            max_val = round(mm.get('max'), 1) if mm.get('max') is not None else None
            avg_val = round(mm.get('avg'), 1) if mm.get('avg') is not None else None

            return {
                'current': current_val,
                'min': min_val,
                'max': max_val,
                'avg': avg_val
            }

        status = {
            'alarm': {
                'is_active': alarm.get('is_alarm', False),
                'code': alarm.get('alarm_code'),
                'description': alarm.get('alarm_description'),
                'time': alarm['alarm_time'].isoformat() if alarm.get('alarm_time') else None
            },
            'current': {
                'outdoor_temp': get_value_with_minmax('outdoor_temp'),
                'indoor_temp': get_value_with_minmax('indoor_temp'),
                'hot_water': get_value_with_minmax('hot_water_top'),
                'brine_in': get_value_with_minmax('brine_in_evaporator'),
                'brine_out': get_value_with_minmax('brine_out_condenser'),
                # IVT uses heat_carrier_forward/return, Thermia uses radiator_forward/return
                'radiator_forward': get_value_with_minmax('heat_carrier_forward') if get_value_with_minmax('heat_carrier_forward').get('current') is not None else get_value_with_minmax('radiator_forward'),
                'radiator_return': get_value_with_minmax('heat_carrier_return') if get_value_with_minmax('heat_carrier_return').get('current') is not None else get_value_with_minmax('radiator_return'),
                'power': round(current_metrics.get('power_consumption', {}).get('value', 0), 0) if current_metrics.get('power_consumption', {}).get('value') is not None else None,
                'compressor_running': bool(current_metrics.get('compressor_status', {}).get('value', 0)),
                'brine_pump_running': bool(current_metrics.get('brine_pump_status', {}).get('value', 0)),
                'radiator_pump_running': bool(current_metrics.get('radiator_pump_status', {}).get('value', 0)),
                'vvb_pump_running': bool(current_metrics.get('pump_heat_circuit', {}).get('value', 0)),  # IVT only
                'switch_valve_status': int(current_metrics.get('switch_valve_status', {}).get('value', 0)) if current_metrics.get('switch_valve_status', {}).get('value') is not None else 0,
                'aux_heater': current_metrics.get('additional_heat_percent', {}).get('value', 0) > 0 if current_metrics.get('additional_heat_percent', {}).get('value') is not None else False,
                'current_cop': current_cop
            },
            'timestamp': datetime.now().isoformat()
        }

        return status
    except Exception as e:
        logger.error(f"Error getting cached status data: {e}")
        return {
            'alarm': {'is_active': False, 'code': None, 'description': None, 'time': None},
            'current': {},
            'timestamp': datetime.now().isoformat()
        }


def get_event_log(limit=20):
    """Get recent event log entries"""
    try:
        events = data_query.get_event_log(limit=limit)

        event_list = []
        for event in events:
            event_list.append({
                'time': event.get('time', '').isoformat() if hasattr(event.get('time', ''), 'isoformat') else str(event.get('time', '')),
                'type': event.get('type', 'unknown'),
                'description': event.get('event', 'No description'),  # 'event' key contains the description
                'value': event.get('value'),
                'icon': event.get('icon', '')
            })

        return event_list
    except Exception as e:
        logger.error(f"Error getting event log: {e}")
        return []


def get_event_log_cached(cached_events):
    """Get recent event log entries from pre-calculated cache (avoids 6 DB queries)"""
    try:
        event_list = []
        for event in cached_events:
            event_list.append({
                'time': event.get('time', '').isoformat() if hasattr(event.get('time', ''), 'isoformat') else str(event.get('time', '')),
                'type': event.get('type', 'unknown'),
                'description': event.get('event', 'No description'),
                'value': event.get('value'),
                'icon': event.get('icon', '')
            })

        return event_list
    except Exception as e:
        logger.error(f"Error getting cached event log: {e}")
        return []


def get_status_data_fully_cached(cached_cop_df, cached_min_max, cached_latest_values, cached_alarm_status):
    """Get current system status using ALL cached data (no DB queries needed)"""
    try:
        # Use cached alarm status
        alarm = cached_alarm_status

        # Use cached latest values
        current_metrics = cached_latest_values

        # Use cached min/max values
        min_max = cached_min_max

        # Use cached COP data - use Period COP (Σheat/Σelec) for consistency
        current_cop = None
        if cached_cop_df is not None and not cached_cop_df.empty:
            # Prefer seasonal_cop (total COP = Σheat/Σelec) for accurate period average
            if 'seasonal_cop' in cached_cop_df.columns:
                seasonal_values = cached_cop_df['seasonal_cop'].dropna()
                if len(seasonal_values) > 0:
                    current_cop = round(seasonal_values.iloc[-1], 2)  # Last value = total period COP
            # Fallback to mean of interval COPs
            elif 'estimated_cop' in cached_cop_df.columns:
                cop_values = cached_cop_df['estimated_cop'].dropna()
                if len(cop_values) > 0:
                    current_cop = round(cop_values.mean(), 2)

        def get_value_with_minmax(metric_name):
            """Helper to get current value with min/max/avg"""
            current = current_metrics.get(metric_name)
            if isinstance(current, dict):
                current_val = round(current.get('value'), 1) if current.get('value') is not None else None
            else:
                current_val = round(current, 1) if current is not None else None

            mm = min_max.get(metric_name, {})
            min_val = round(mm.get('min'), 1) if mm.get('min') is not None else None
            max_val = round(mm.get('max'), 1) if mm.get('max') is not None else None
            avg_val = round(mm.get('avg'), 1) if mm.get('avg') is not None else None

            return {
                'current': current_val,
                'min': min_val,
                'max': max_val,
                'avg': avg_val
            }

        # Get Hetgas temperature - Thermia uses pressure_tube_temp, IVT uses hot_gas_compressor
        hotgas_temp = None
        if current_metrics.get('pressure_tube_temp', {}).get('value') is not None:
            hotgas_temp = round(current_metrics.get('pressure_tube_temp', {}).get('value'), 1)
        elif current_metrics.get('hot_gas_compressor', {}).get('value') is not None:
            hotgas_temp = round(current_metrics.get('hot_gas_compressor', {}).get('value'), 1)

        # Get Integral (degree_minutes) value
        degree_minutes = None
        if current_metrics.get('degree_minutes', {}).get('value') is not None:
            degree_minutes = round(current_metrics.get('degree_minutes', {}).get('value'), 0)

        status = {
            'alarm': {
                'is_active': alarm.get('is_alarm', False),
                'code': alarm.get('alarm_code'),
                'description': alarm.get('alarm_description'),
                'time': alarm['alarm_time'].isoformat() if alarm.get('alarm_time') else None
            },
            'current': {
                'outdoor_temp': get_value_with_minmax('outdoor_temp'),
                'indoor_temp': get_value_with_minmax('indoor_temp'),
                'hot_water': get_value_with_minmax('hot_water_top'),
                'brine_in': get_value_with_minmax('brine_in_evaporator'),
                'brine_out': get_value_with_minmax('brine_out_condenser'),
                # IVT uses heat_carrier_forward/return, Thermia uses radiator_forward/return
                'radiator_forward': get_value_with_minmax('heat_carrier_forward') if get_value_with_minmax('heat_carrier_forward').get('current') is not None else get_value_with_minmax('radiator_forward'),
                'radiator_return': get_value_with_minmax('heat_carrier_return') if get_value_with_minmax('heat_carrier_return').get('current') is not None else get_value_with_minmax('radiator_return'),
                'power': round(current_metrics.get('power_consumption', {}).get('value', 0), 0) if current_metrics.get('power_consumption', {}).get('value') is not None else None,
                'compressor_running': bool(current_metrics.get('compressor_status', {}).get('value', 0)),
                'brine_pump_running': bool(current_metrics.get('brine_pump_status', {}).get('value', 0)),
                'radiator_pump_running': bool(current_metrics.get('radiator_pump_status', {}).get('value', 0)),
                'vvb_pump_running': bool(current_metrics.get('pump_heat_circuit', {}).get('value', 0)),  # IVT only
                'switch_valve_status': int(current_metrics.get('switch_valve_status', {}).get('value', 0)) if current_metrics.get('switch_valve_status', {}).get('value') is not None else 0,
                'aux_heater': current_metrics.get('additional_heat_percent', {}).get('value', 0) > 0 if current_metrics.get('additional_heat_percent', {}).get('value') is not None else False,
                'current_cop': current_cop,
                'hotgas_temp': hotgas_temp,  # Hetgas temperature (pressure_tube_temp or hot_gas_temp)
                'degree_minutes': degree_minutes  # Integral value
            },
            'timestamp': datetime.now().isoformat()
        }

        return status
    except Exception as e:
        logger.error(f"Error getting fully cached status data: {e}")
        return {
            'alarm': {'is_active': False, 'code': None, 'description': None, 'time': None},
            'current': {},
            'timestamp': datetime.now().isoformat()
        }


def get_kpi_data(time_range='24h', price_per_kwh=2.0):
    """Get extended KPI metrics (energy, runtime, hot water)"""
    try:
        # Calculate energy costs
        energy_costs = data_query.calculate_energy_costs(time_range, price_per_kwh)

        # Calculate runtime statistics
        runtime_stats = data_query.calculate_runtime_stats(time_range)

        # Analyze hot water cycles (use longer period for meaningful stats)
        hw_time_range = '7d' if time_range in ['1h', '6h', '24h'] else time_range
        hot_water_stats = data_query.analyze_hot_water_cycles(hw_time_range)

        kpi = {
            'energy': {
                'total_kwh': energy_costs.get('total_kwh', 0),
                'total_cost': energy_costs.get('total_cost', 0),
                'avg_power': energy_costs.get('avg_power', 0),
                'peak_power': energy_costs.get('peak_power', 0)
            },
            'runtime': {
                'compressor_hours': runtime_stats.get('compressor_runtime_hours', 0),
                'compressor_percent': runtime_stats.get('compressor_runtime_percent', 0),
                'aux_heater_hours': runtime_stats.get('aux_heater_runtime_hours', 0),
                'aux_heater_percent': runtime_stats.get('aux_heater_runtime_percent', 0),
                'total_hours': runtime_stats.get('total_hours', 0)
            },
            'hot_water': {
                'total_cycles': hot_water_stats.get('total_cycles', 0),
                'cycles_per_day': hot_water_stats.get('cycles_per_day', 0),
                'avg_duration_minutes': hot_water_stats.get('avg_cycle_duration_minutes', 0),
                'avg_energy_kwh': hot_water_stats.get('avg_energy_per_cycle_kwh', 0)
            }
        }

        return kpi
    except Exception as e:
        logger.error(f"Error getting KPI data: {e}")
        return {
            'energy': {'total_kwh': 0, 'total_cost': 0, 'avg_power': 0, 'peak_power': 0},
            'runtime': {'compressor_hours': 0, 'compressor_percent': 0, 'aux_heater_hours': 0, 'aux_heater_percent': 0, 'total_hours': 0},
            'hot_water': {'total_cycles': 0, 'cycles_per_day': 0, 'avg_duration_minutes': 0, 'avg_energy_kwh': 0}
        }


def get_kpi_data_cached(time_range, cached_runtime_stats, cached_hot_water_stats, price_per_kwh=2.0):
    """Get extended KPI metrics using pre-calculated runtime and hot water stats (avoids redundant InfluxDB queries)"""
    try:
        # Calculate energy costs
        energy_costs = data_query.calculate_energy_costs(time_range, price_per_kwh)

        kpi = {
            'energy': {
                'total_kwh': energy_costs.get('total_kwh', 0),
                'total_cost': energy_costs.get('total_cost', 0),
                'avg_power': energy_costs.get('avg_power', 0),
                'peak_power': energy_costs.get('peak_power', 0)
            },
            'runtime': {
                'compressor_hours': cached_runtime_stats.get('compressor_runtime_hours', 0),
                'compressor_percent': cached_runtime_stats.get('compressor_runtime_percent', 0),
                'aux_heater_hours': cached_runtime_stats.get('aux_heater_runtime_hours', 0),
                'aux_heater_percent': cached_runtime_stats.get('aux_heater_runtime_percent', 0),
                'total_hours': cached_runtime_stats.get('total_hours', 0)
            },
            'hot_water': {
                'total_cycles': cached_hot_water_stats.get('total_cycles', 0),
                'cycles_per_day': cached_hot_water_stats.get('cycles_per_day', 0),
                'avg_duration_minutes': cached_hot_water_stats.get('avg_cycle_duration_minutes', 0),
                'avg_energy_kwh': cached_hot_water_stats.get('avg_energy_per_cycle_kwh', 0)
            }
        }

        return kpi
    except Exception as e:
        logger.error(f"Error getting cached KPI data: {e}")
        return {
            'energy': {'total_kwh': 0, 'total_cost': 0, 'avg_power': 0, 'peak_power': 0},
            'runtime': {'compressor_hours': 0, 'compressor_percent': 0, 'aux_heater_hours': 0, 'aux_heater_percent': 0, 'total_hours': 0},
            'hot_water': {'total_cycles': 0, 'cycles_per_day': 0, 'avg_duration_minutes': 0, 'avg_energy_kwh': 0}
        }


# ==================== WebSocket Handlers ====================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    client_id = request.sid
    connected_clients[client_id] = {'time_range': '24h', 'connected_at': datetime.now()}
    logger.info(f"✅ Client connected: {client_id} (Total: {len(connected_clients)})")

    # Send welcome message
    emit('connection_status', {'status': 'connected', 'message': 'WebSocket ansluten'})

    # Start background task if not already running
    if not hasattr(socketio, 'background_task_started'):
        socketio.background_task_started = True
        logger.info("🚀 Starting background update task...")
        socketio.start_background_task(background_updates)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    client_id = request.sid
    if client_id in connected_clients:
        del connected_clients[client_id]
    logger.info(f"❌ Client disconnected: {client_id} (Total: {len(connected_clients)})")


@socketio.on('ping')
def handle_ping():
    """Handle ping from client"""
    emit('pong', {'timestamp': datetime.now().isoformat()})


@socketio.on('change_time_range')
def handle_time_range_change(data):
    """Handle time range change from client - PARALLELIZED"""
    client_id = request.sid
    time_range = data.get('range', '24h')

    logger.info(f"🔄 Client {client_id} changed time range to: {time_range}")

    # Update client's time range
    if client_id in connected_clients:
        connected_clients[client_id]['time_range'] = time_range

    # Send updated data immediately to this client using parallel fetching
    try:
        update_data = fetch_all_data_parallel(time_range)
        update_data['timestamp'] = datetime.now().isoformat()

        update_data = clean_nan_values(update_data)
        emit('graph_update', update_data)
        logger.info(f"✅ Sent updated data to client {client_id}")

    except Exception as e:
        logger.error(f"❌ Error sending update to client {client_id}: {e}")
        emit('error', {'message': str(e)})


@socketio.on('request_update')
def handle_manual_update(data):
    """Handle manual update request from client - PARALLELIZED"""
    client_id = request.sid
    time_range = data.get('range', '24h')

    logger.info(f"🔄 Client {client_id} requested manual update")

    try:
        update_data = fetch_all_data_parallel(time_range)
        update_data['timestamp'] = datetime.now().isoformat()

        update_data = clean_nan_values(update_data)
        emit('graph_update', update_data)

    except Exception as e:
        logger.error(f"❌ Error in manual update: {e}")
        emit('error', {'message': str(e)})


# ==================== Background Tasks ====================

def background_updates():
    """Background task to push updates every 30 seconds to each client individually - PARALLELIZED"""
    logger.info("🔄 Background update task started")

    while True:
        try:
            # Wait 30 seconds (matches Dash interval)
            eventlet.sleep(30)

            if not connected_clients:
                continue

            logger.info(f"📊 Pushing individualized updates to {len(connected_clients)} clients...")

            # Send individualized updates to each client based on their time_range preference
            for client_id, client_info in list(connected_clients.items()):
                try:
                    time_range = client_info.get('time_range', '24h')

                    logger.debug(f"Sending update to {client_id} with range: {time_range}")

                    # Use parallel fetching for much faster updates
                    update_data = fetch_all_data_parallel(time_range)
                    update_data['timestamp'] = datetime.now().isoformat()
                    update_data['time_range'] = time_range  # Include time range in response

                    # Clean NaN values and send to specific client
                    update_data = clean_nan_values(update_data)
                    socketio.emit('graph_update', update_data, room=client_id)

                except Exception as client_error:
                    logger.error(f"❌ Error sending update to client {client_id}: {client_error}")
                    continue

            logger.info(f"✅ Updates pushed at {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"❌ Error in background update: {e}")
            eventlet.sleep(5)  # Wait a bit before retrying


# ==================== Main ====================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info(f"🔥 Starting {provider.get_display_name()} Dashboard")
    logger.info("=" * 60)
    logger.info("📊 WebSocket Dashboard with ECharts")
    logger.info(f"🏢 Provider: {provider.get_brand_name()}")
    logger.info("🔌 WebSocket support: Socket.IO")
    logger.info("📈 Charts: ECharts 5.4+")
    logger.info("⏱️  Auto-update: Every 30 seconds")
    logger.info("🌐 Dashboard will be available at http://localhost:8050")
    logger.info("=" * 60)

    socketio.run(
        app,
        host='0.0.0.0',
        port=8050,
        debug=True,
        use_reloader=False  # Disable reloader to prevent duplicate background tasks
    )
