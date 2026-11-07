#!/usr/bin/env python3
"""
Heat Pump Dashboard - Flask + WebSocket Version
Modern architecture with ECharts and Socket.IO
Supports: Thermia, IVT, NIBE
"""

import os
import sys
import copy
import time
import logging
import yaml
import math
import pandas as pd
import numpy as np
from datetime import datetime

# Version info - increment when making changes
VERSION = '1.2.0'
BUILD_TIME = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import eventlet

# Add parent directory to path for provider imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers import get_provider
from data_query import HeatPumpDataQuery, load_config, CONFIG_PATH
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

# Same-origin only unless CORS_ORIGINS is set (comma separated)
cors_origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()] or None

# Initialize Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins=cors_origins,
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25
)

# Load provider from config
def load_provider():
    """Load heat pump provider from config"""
    try:
        brand = load_config().get('brand') or os.getenv('HEATPUMP_BRAND', 'thermia')
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

DEFAULT_TIME_RANGES = ['1h', '6h', '24h', '7d', '30d', '90d']


def validate_time_range(value):
    """Only allow configured time ranges (value is interpolated into Flux)"""
    allowed = load_config().get('dashboard', {}).get('time_ranges') or DEFAULT_TIME_RANGES
    if value not in allowed:
        raise ValueError(f'Ogiltigt tidsintervall: {value!r}')
    return value


# ==================== HTTP Routes ====================

@app.route('/')
def index():
    """Serve main dashboard page"""
    return render_template('dashboard.html',
                         brand=provider.get_brand_name(),
                         brand_name=provider.get_display_name(),
                         dashboard_title=provider.get_dashboard_title(),
                         schema=provider.get_schema_layout())

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
        'colors': THERMIA_COLORS,
        'version': VERSION,
        'build_time': BUILD_TIME
    })


# ==================== Settings API ====================

def set_bucket_retention(days):
    """Set InfluxDB bucket retention policy"""
    try:
        buckets_api = data_query.client.buckets_api()
        bucket = buckets_api.find_bucket_by_name(data_query.bucket)
        if bucket:
            retention_seconds = days * 86400 if days > 0 else 0
            bucket.retention_rules = [BucketRetentionRules(type="expire", every_seconds=retention_seconds)]
            buckets_api.update_bucket(bucket=bucket)
            logger.info(f"✅ Bucket retention set to {days} days ({retention_seconds}s)")
            return True
    except Exception as e:
        logger.error(f"❌ Failed to set retention: {e}")
    return False


def apply_retention_from_config():
    """Apply retention policy from config at startup"""
    try:
        days = load_config().get('retention', {}).get('days', 90)
        if days > 0:
            set_bucket_retention(days)
            logger.info(f"✅ Applied retention policy: {days} days")
    except Exception as e:
        logger.warning(f"⚠️ Could not apply retention policy: {e}")


# Apply retention on startup
apply_retention_from_config()


@app.route('/api/settings')
def get_settings():
    """Get all editable settings + system info"""
    config = load_config()

    # Get InfluxDB health
    try:
        is_ready = data_query.client.ping()
        if is_ready:
            influx_status = {'status': 'pass'}
        else:
            influx_status = {'status': 'fail'}
        # Try to get version from health endpoint
        try:
            health = data_query.client.health()
            influx_status['version'] = str(health.version) if health.version else 'unknown'
        except Exception:
            influx_status['version'] = 'unknown'
    except Exception as e:
        logger.error(f"InfluxDB health check failed: {e}")
        influx_status = {'status': 'unavailable', 'version': 'unknown'}

    # Get bucket retention
    try:
        buckets_api = data_query.client.buckets_api()
        bucket = buckets_api.find_bucket_by_name(data_query.bucket)
        if bucket and bucket.retention_rules:
            retention_seconds = bucket.retention_rules[0].every_seconds
            current_retention_days = retention_seconds // 86400 if retention_seconds > 0 else 0
        else:
            current_retention_days = 0
    except Exception as e:
        logger.error(f"Failed to read bucket retention: {e}")
        current_retention_days = 0

    return jsonify({
        'brand': config.get('brand', 'thermia'),
        'cop_flow_factor': config.get('cop', {}).get('flow_factor', 2.7),
        'hw_min_cycle_minutes': config.get('hot_water', {}).get('min_cycle_minutes', 2),
        'collection_interval': config.get('collection', {}).get('interval_seconds', 30),
        'dashboard_refresh_interval': config.get('dashboard', {}).get('refresh_interval', 30),
        'electricity_price': config.get('electricity_price', 2.0),
        'retention_days': config.get('retention', {}).get('days', 90),
        'current_retention_days': current_retention_days,
        'system': {
            'influxdb': influx_status,
            'dashboard_version': VERSION,
            'build_time': BUILD_TIME,
        }
    })


@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save settings to config.yaml and apply retention"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Ogiltig JSON'}), 400

    config = copy.deepcopy(load_config())
    needs_restart = []
    errors = []

    def number(key, cast, lo, hi, label):
        try:
            val = cast(data[key])
        except (TypeError, ValueError):
            errors.append(f'{label}: måste vara ett tal')
            return None
        if not lo <= val <= hi:
            errors.append(f'{label}: måste vara mellan {lo} och {hi}')
            return None
        return val

    if 'brand' in data:
        if data['brand'] not in ('thermia', 'ivt', 'nibe'):
            errors.append(f"Märke: okänt värde {data['brand']!r}")
        else:
            if data['brand'] != config.get('brand'):
                needs_restart += ['collector', 'dashboard']
            config['brand'] = data['brand']

    if 'cop_flow_factor' in data:
        val = number('cop_flow_factor', float, 1.0, 5.0, 'Flödesfaktor')
        if val is not None:
            config.setdefault('cop', {})['flow_factor'] = round(val, 2)

    if 'hw_min_cycle_minutes' in data:
        val = number('hw_min_cycle_minutes', int, 0, 60, 'Min cykeltid')
        if val is not None:
            config.setdefault('hot_water', {})['min_cycle_minutes'] = val

    if 'collection_interval' in data:
        val = number('collection_interval', int, 5, 300, 'Insamlingsintervall')
        if val is not None:
            if val != config.get('collection', {}).get('interval_seconds') and 'collector' not in needs_restart:
                needs_restart.append('collector')
            config.setdefault('collection', {})['interval_seconds'] = val

    if 'dashboard_refresh_interval' in data:
        val = number('dashboard_refresh_interval', int, 5, 300, 'Uppdateringsintervall')
        if val is not None:
            config.setdefault('dashboard', {})['refresh_interval'] = val

    if 'electricity_price' in data:
        val = number('electricity_price', float, 0, 100, 'Elpris')
        if val is not None:
            config['electricity_price'] = round(val, 2)

    if 'retention_days' in data:
        val = number('retention_days', int, 0, 365, 'Lagring')
        if val is not None:
            if val != 0 and val < 7:
                errors.append('Lagring: 0 (obegränsat) eller 7-365 dagar')
            else:
                config.setdefault('retention', {})['days'] = val

    if errors:
        return jsonify({'success': False, 'message': '; '.join(errors), 'errors': errors}), 400

    # Write config
    try:
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Kunde inte spara: {e}'}), 500

    # Apply retention policy
    if 'retention_days' in data:
        retention_days = config.get('retention', {}).get('days', 90)
        set_bucket_retention(retention_days)

    return jsonify({
        'success': True,
        'needs_restart': needs_restart,
        'message': 'Inställningar sparade'
    })


# Allowed container names for restart (safety whitelist)
RESTARTABLE_CONTAINERS = {
    'collector': 'heatpump-collector',
    'dashboard': 'heatpump-dashboard-websocket',
}


@app.route('/api/restart-service', methods=['POST'])
def restart_service():
    """Restart a Docker container by service name"""
    data = request.json or {}
    service = data.get('service', '')

    if service not in RESTARTABLE_CONTAINERS:
        return jsonify({
            'success': False,
            'message': f'Okänd tjänst: {service}'
        }), 400

    container_name = RESTARTABLE_CONTAINERS[service]

    try:
        import docker
        docker_client = docker.from_env()
        container = docker_client.containers.get(container_name)
        container.restart(timeout=10)
        logger.info(f"✅ Restarted container: {container_name}")
        return jsonify({
            'success': True,
            'message': f'{service} har startats om'
        })
    except ImportError:
        logger.error("❌ docker library not installed")
        return jsonify({
            'success': False,
            'message': 'Docker-biblioteket är inte installerat'
        }), 500
    except Exception as e:
        logger.error(f"❌ Failed to restart {container_name}: {e}")
        return jsonify({
            'success': False,
            'message': f'Kunde inte starta om: {e}'
        }), 500


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


def fetch_all_data_batch(time_range):
    """Fetch all dashboard data: batch, viz-wide, hot water, runtime, min/max and latest queries."""
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
    # Using InfluxDB-side pivot for better performance (no pandas pivot needed)
    logger.info(f"  📊 Fetching visualization metrics with InfluxDB-side pivot...")
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

    # Use InfluxDB-side pivot - returns wide format directly
    # Since HTTP API delivers all sensors with synchronized timestamps,
    # no pandas pivot or ffill needed
    viz_df_pivot = data_query.query_metrics_wide(viz_metrics, time_range, aggregation_window=viz_aggregation)
    viz_query_elapsed = time.time() - viz_query_start
    logger.info(f"    ⏱️  Visualization query (with pivot) took {viz_query_elapsed:.2f}s ({viz_aggregation} aggregation, {len(viz_df_pivot)} rows)")

    # Pre-calculate COP from pivoted data (aligned timestamps guaranteed)
    logger.info(f"  📊 Pre-calculating COP from pivoted data...")
    cop_cache_start = time.time()
    cached_cop_df = data_query.calculate_cop_from_pivot(viz_df_pivot)
    cop_cache_elapsed = time.time() - cop_cache_start
    logger.info(f"    ⏱️  COP calculation took {cop_cache_elapsed:.2f}s")

    # Hot water cycles need fine-grained data (coarse buckets hide short cycles).
    # Short ranges are widened to 7d so cycles/day is meaningful.
    hw_cache_start = time.time()
    hw_range = '7d' if time_range in ('1h', '6h', '24h') else time_range
    hw_window = '1m' if hw_range == '7d' else '5m'
    hw_df = data_query.query_metrics(['switch_valve_status', 'power_consumption'], hw_range, aggregation_window=hw_window)
    cached_hot_water_stats = data_query.analyze_hot_water_cycles_from_df(hw_df, hw_range)
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

    price_per_kwh = load_config().get('electricity_price', 2.0)

    data = {
        'cop': get_cop_data_from_pivot(cached_cop_df),
        'temperature': get_temperature_data_from_pivot(viz_df_pivot),
        'runtime': get_runtime_data_cached(cached_runtime_stats),
        'sankey': get_sankey_data_cached(cached_cop_df, cached_runtime_stats),
        'performance': get_performance_data_from_pivot(viz_df_pivot),
        'power': get_power_data_from_df(df),
        'valve': get_valve_data_from_df(df),
        'status': get_status_data_fully_cached(cached_cop_df, cached_min_max, cached_latest_values, cached_alarm_status),
        'events': get_event_log_cached(cached_events),
        'kpi': get_kpi_data_cached(time_range, cached_runtime_stats, cached_hot_water_stats, price_per_kwh),
    }

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
# Note: COP calculation is now consolidated in DataQuery.calculate_cop_from_pivot()

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

        # Check if data needs re-pivoting (InfluxDB union+pivot doesn't always work correctly)
        # Each metric may end up on separate rows instead of being aligned
        temp_cols = ['radiator_forward', 'radiator_return', 'brine_in_evaporator', 'brine_out_condenser']
        available_cols = [c for c in temp_cols if c in df_pivot.columns]
        if available_cols:
            avg_fill_rate = sum(df_pivot[c].notna().sum() for c in available_cols) / (len(df_pivot) * len(available_cols))
            if avg_fill_rate < 0.5:  # Less than 50% fill rate suggests unpivoted data
                logger.info(f"get_temperature_data_from_pivot: Data not properly pivoted (fill rate: {avg_fill_rate:.1%}), re-pivoting...")
                # Re-pivot using pandas groupby to align metrics by timestamp
                numeric_cols = df_pivot.select_dtypes(include=[np.number]).columns.tolist()
                agg_dict = {col: 'mean' for col in numeric_cols if col in df_pivot.columns}
                # Use 'last' for status columns
                for status_col in ['compressor_status', 'brine_pump_status', 'radiator_pump_status', 'switch_valve_status']:
                    if status_col in agg_dict:
                        agg_dict[status_col] = 'last'
                if agg_dict:
                    df_pivot = df_pivot.groupby('_time').agg(agg_dict).reset_index()
                    logger.info(f"  Re-pivoted to {len(df_pivot)} rows")

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
        # Check for actual data, not just column existence
        has_heat_carrier = ('heat_carrier_forward' in df_pivot.columns and
                           'heat_carrier_return' in df_pivot.columns and
                           df_pivot['heat_carrier_forward'].notna().any() and
                           df_pivot['heat_carrier_return'].notna().any())
        has_radiator = ('radiator_forward' in df_pivot.columns and
                       'radiator_return' in df_pivot.columns and
                       df_pivot['radiator_forward'].notna().any() and
                       df_pivot['radiator_return'].notna().any())

        if has_heat_carrier:
            # IVT uses heat_carrier
            df_pivot['radiator_delta'] = df_pivot['heat_carrier_forward'] - df_pivot['heat_carrier_return']
            result['radiator_delta'] = df_pivot['radiator_delta'].replace({float('nan'): None}).tolist()
        elif has_radiator:
            # Thermia uses radiator
            df_pivot['radiator_delta'] = df_pivot['radiator_forward'] - df_pivot['radiator_return']
            result['radiator_delta'] = df_pivot['radiator_delta'].replace({float('nan'): None}).tolist()

        # Calculate delta for brine/köldbärare side
        has_brine = ('brine_in_evaporator' in df_pivot.columns and
                    'brine_out_condenser' in df_pivot.columns and
                    df_pivot['brine_in_evaporator'].notna().any() and
                    df_pivot['brine_out_condenser'].notna().any())
        if has_brine:
            df_pivot['brine_delta'] = df_pivot['brine_in_evaporator'] - df_pivot['brine_out_condenser']
            result['brine_delta'] = df_pivot['brine_delta'].replace({float('nan'): None}).tolist()

        return result
    except Exception as e:
        logger.error(f"Error getting temperature data from pivot: {e}")
        return {'timestamps': []}


def _to_chart_data(df, time_col: str, value_col: str) -> list:
    """
    Convert DataFrame columns to chart data format [[timestamp, value], ...]

    OPTIMIZED: Uses vectorized operations instead of iterrows() for 100x speedup
    """
    if time_col not in df.columns or value_col not in df.columns:
        return []

    # Vectorized timestamp conversion
    if pd.api.types.is_datetime64_any_dtype(df[time_col]):
        times = df[time_col].dt.strftime('%Y-%m-%dT%H:%M:%S.%f').str[:-3] + 'Z'
    else:
        times = df[time_col].astype(str)

    # Vectorized value extraction with NaN→None
    values = df[value_col].where(df[value_col].notna(), None)

    # Convert to list of [time, value] pairs
    return list(map(list, zip(times.tolist(), values.tolist())))


def _get_value_with_minmax(metric_name: str, current_metrics: dict, min_max: dict) -> dict:
    """
    Helper to get current value with min/max/avg statistics.

    Extracted to standalone function to avoid 3x code duplication.
    """
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


def get_performance_data_from_pivot(df_pivot):
    """Extract performance data from pre-pivoted dataframe (guaranteed aligned timestamps)

    OPTIMIZED: Uses vectorized operations instead of iterrows()
    """
    try:
        if df_pivot.empty:
            return {
                'brine_delta': [],
                'radiator_delta': [],
                'compressor_status': [],
                'timestamps': []
            }

        # Check if data needs re-pivoting (InfluxDB union+pivot doesn't always work correctly)
        temp_cols = ['radiator_forward', 'radiator_return', 'brine_in_evaporator', 'brine_out_condenser']
        available_cols = [c for c in temp_cols if c in df_pivot.columns]
        if available_cols:
            avg_fill_rate = sum(df_pivot[c].notna().sum() for c in available_cols) / (len(df_pivot) * len(available_cols))
            if avg_fill_rate < 0.5:  # Less than 50% fill rate suggests unpivoted data
                # Re-pivot using pandas groupby to align metrics by timestamp
                numeric_cols = df_pivot.select_dtypes(include=[np.number]).columns.tolist()
                agg_dict = {col: 'mean' for col in numeric_cols if col in df_pivot.columns}
                for status_col in ['compressor_status', 'brine_pump_status', 'radiator_pump_status', 'switch_valve_status']:
                    if status_col in agg_dict:
                        agg_dict[status_col] = 'last'
                if agg_dict:
                    df_pivot = df_pivot.groupby('_time').agg(agg_dict).reset_index()

        # Get consistent timestamps
        timestamps = df_pivot['_time'].astype(str).tolist()

        # Calculate deltas using vectorized operations
        # Check for actual data, not just column existence
        brine_delta = []
        radiator_delta = []
        compressor_status = []

        has_brine = ('brine_in_evaporator' in df_pivot.columns and
                    'brine_out_condenser' in df_pivot.columns and
                    df_pivot['brine_in_evaporator'].notna().any() and
                    df_pivot['brine_out_condenser'].notna().any())
        if has_brine:
            df_pivot['brine_delta_calc'] = df_pivot['brine_in_evaporator'] - df_pivot['brine_out_condenser']
            brine_delta = _to_chart_data(df_pivot, '_time', 'brine_delta_calc')

        # Check for radiator (Thermia) or heat_carrier (IVT) data
        has_heat_carrier = ('heat_carrier_forward' in df_pivot.columns and
                           'heat_carrier_return' in df_pivot.columns and
                           df_pivot['heat_carrier_forward'].notna().any() and
                           df_pivot['heat_carrier_return'].notna().any())
        has_radiator = ('radiator_forward' in df_pivot.columns and
                       'radiator_return' in df_pivot.columns and
                       df_pivot['radiator_forward'].notna().any() and
                       df_pivot['radiator_return'].notna().any())

        if has_heat_carrier:
            df_pivot['radiator_delta_calc'] = df_pivot['heat_carrier_forward'] - df_pivot['heat_carrier_return']
            radiator_delta = _to_chart_data(df_pivot, '_time', 'radiator_delta_calc')
        elif has_radiator:
            df_pivot['radiator_delta_calc'] = df_pivot['radiator_forward'] - df_pivot['radiator_return']
            radiator_delta = _to_chart_data(df_pivot, '_time', 'radiator_delta_calc')

        if 'compressor_status' in df_pivot.columns:
            compressor_status = _to_chart_data(df_pivot, '_time', 'compressor_status')

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


def get_power_data_from_df(df):
    """Extract power data from pre-fetched dataframe

    OPTIMIZED: Uses vectorized operations instead of iterrows()
    """
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
            result['power_consumption'] = _to_chart_data(power, '_time', '_value')
            result['timestamps'] = power['_time'].astype(str).tolist()

        # Get compressor status
        comp = df[df['name'] == 'compressor_status']
        if not comp.empty:
            result['compressor_status'] = _to_chart_data(comp, '_time', '_value')

        # Get heater percentage
        heater = df[df['name'] == 'additional_heat_percent']
        if not heater.empty:
            result['additional_heat_percent'] = _to_chart_data(heater, '_time', '_value')

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
    """Extract valve data from pre-fetched dataframe

    OPTIMIZED: Uses vectorized operations instead of iterrows()
    """
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

        # Get valve status
        valve = df[df['name'] == 'switch_valve_status']
        if not valve.empty:
            result['valve_status'] = _to_chart_data(valve, '_time', '_value')
            result['timestamps'] = valve['_time'].astype(str).tolist()

        # Get compressor status
        comp = df[df['name'] == 'compressor_status']
        if not comp.empty:
            result['compressor_status'] = _to_chart_data(comp, '_time', '_value')

        # Get hot water temp
        hw_temp = df[df['name'] == 'hot_water_top']
        if not hw_temp.empty:
            result['hot_water_temp'] = _to_chart_data(hw_temp, '_time', '_value')

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
    try:
        time_range = validate_time_range(request.args.get('range', '24h'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        logger.info(f"📥 Loading initial data for range: {time_range}")
        data = fetch_all_data_batch(time_range)

        logger.info(f"✅ Initial data loaded successfully")
        # Clean NaN values before JSON serialization
        data = clean_nan_values(data)
        return jsonify(data)

    except Exception as e:
        logger.error(f"❌ Error loading initial data: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== Data Extraction Functions ====================


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


def get_sankey_data_cached(cached_cop_df, cached_runtime_stats):
    """Build Sankey diagram data using pre-calculated COP and runtime stats (avoids redundant InfluxDB queries)"""
    try:
        # Calculate energy flows (same logic as Plotly version)
        cop_values = cached_cop_df['estimated_cop'].dropna() if 'estimated_cop' in cached_cop_df.columns else pd.Series(dtype=float)
        if cop_values.empty:
            return {'nodes': [], 'links': [], 'cop': None, 'free_energy_percent': 0, 'has_data': False}
        avg_cop = float(cop_values.mean())
        has_data = True

        # Calculate energy flows (normalized to 100 units electric power)
        electric_power = 100
        ground_energy = electric_power * max(avg_cop - 1, 0)
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

        # Use wrapper to bind closure variables to standalone helper
        def get_value(metric_name):
            return _get_value_with_minmax(metric_name, current_metrics, min_max)

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
                'outdoor_temp': get_value('outdoor_temp'),
                'indoor_temp': get_value('indoor_temp'),
                'hot_water': get_value('hot_water_top'),
                'brine_in': get_value('brine_in_evaporator'),
                'brine_out': get_value('brine_out_condenser'),
                # IVT uses heat_carrier_forward/return, Thermia uses radiator_forward/return
                'radiator_forward': get_value('heat_carrier_forward') if get_value('heat_carrier_forward').get('current') is not None else get_value('radiator_forward'),
                'radiator_return': get_value('heat_carrier_return') if get_value('heat_carrier_return').get('current') is not None else get_value('radiator_return'),
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
            'latest': {name: m.get('value') for name, m in current_metrics.items()},
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
                'compressor_starts': cached_runtime_stats.get('compressor_starts', 0),
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
            'runtime': {'compressor_hours': 0, 'compressor_percent': 0, 'compressor_starts': 0, 'aux_heater_hours': 0, 'aux_heater_percent': 0, 'total_hours': 0},
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
    try:
        time_range = validate_time_range((data or {}).get('range', '24h'))
    except ValueError as e:
        emit('error', {'message': str(e)})
        return

    logger.info(f"🔄 Client {client_id} changed time range to: {time_range}")

    # Update client's time range
    if client_id in connected_clients:
        connected_clients[client_id]['time_range'] = time_range

    # Send updated data immediately to this client using parallel fetching
    try:
        update_data = fetch_all_data_batch(time_range)
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
    try:
        time_range = validate_time_range((data or {}).get('range', '24h'))
    except ValueError as e:
        emit('error', {'message': str(e)})
        return

    logger.info(f"🔄 Client {client_id} requested manual update")

    try:
        update_data = fetch_all_data_batch(time_range)
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
            eventlet.sleep(load_config().get('dashboard', {}).get('refresh_interval', 30))

            if not connected_clients:
                continue

            logger.info(f"📊 Pushing individualized updates to {len(connected_clients)} clients...")

            # Send individualized updates to each client based on their time_range preference
            for client_id, client_info in list(connected_clients.items()):
                try:
                    time_range = client_info.get('time_range', '24h')

                    logger.debug(f"Sending update to {client_id} with range: {time_range}")

                    # Use parallel fetching for much faster updates
                    update_data = fetch_all_data_batch(time_range)
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
    logger.info(f"📦 Version: {VERSION} (built {BUILD_TIME})")
    logger.info("=" * 60)
    logger.info("📊 WebSocket Dashboard with ECharts")
    logger.info(f"🏢 Provider: {provider.get_brand_name()}")
    logger.info("🔌 WebSocket support: Socket.IO")
    logger.info("📈 Charts: ECharts 5.4+")
    logger.info("🌐 Dashboard will be available at http://localhost:8050")
    logger.info("=" * 60)

    socketio.run(
        app,
        host='0.0.0.0',
        port=8050,
        debug=os.getenv('FLASK_DEBUG') == '1',
        use_reloader=False  # Disable reloader to prevent duplicate background tasks
    )
