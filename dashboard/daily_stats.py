"""
Daily statistics kept in a long-term bucket (no retention), so history survives the raw
data retention. One point per local day in measurement "daily"; a day is recomputed until
it has been written after its end (final=true).
"""

import time
import logging
from datetime import datetime, timedelta, timezone

import eventlet
import numpy as np
import pandas as pd
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from pricing import local_tz, price_config

logger = logging.getLogger(__name__)

UPDATE_SECONDS = 900
TODAY_MAX_AGE = 60

RUNTIME_METRICS = ['compressor_status', 'additional_heat_percent', 'switch_valve_status', 'power_consumption']
WIDE_METRICS = [
    'outdoor_temp', 'indoor_temp', 'radiator_forward', 'radiator_return',
    'heat_carrier_forward', 'heat_carrier_return', 'hot_water_top',
    'brine_in_evaporator', 'brine_out_condenser', 'compressor_status', 'power_consumption',
]
SUM_FIELDS = ['energy_kwh', 'cost_kr', 'heat_kwh', 'cop_elec_kwh', 'compressor_hours',
              'compressor_starts', 'aux_hours', 'hw_cycles', 'hw_kwh']
MEAN_FIELDS = ['outdoor_mean', 'indoor_mean', 'brine_in_mean', 'brine_out_mean', 'hot_water_mean']
MIN_FIELDS = ['outdoor_min', 'brine_in_min']
MAX_FIELDS = ['outdoor_max']


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _temp(df, col, fn):
    if col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors='coerce')
    s = s[(s > -40) & (s < 100)]
    return None if s.empty else round(float(getattr(s, fn)()), 2)


def _num(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else v


class DailyStats:
    def __init__(self, data_query, prices, bucket):
        self.dq = data_query
        self.prices = prices
        self.bucket = bucket
        self.write_api = data_query.client.write_api(write_options=SYNCHRONOUS)
        self._today = (0, None)
        self._today_lock = eventlet.semaphore.Semaphore()
        self._rows = (0, None)
        self._force = False

    def invalidate(self):
        """Recompute all days still in the raw data on the next update (e.g. after a price change)"""
        self._force = True
        self._today = (0, None)

    def ensure_bucket(self):
        try:
            api = self.dq.client.buckets_api()
            if not api.find_bucket_by_name(self.bucket):
                api.create_bucket(bucket_name=self.bucket, retention_rules=[], org=self.dq.org)
                logger.info(f"Created long-term bucket {self.bucket}")
        except Exception as e:
            logger.error(f"Could not create long-term bucket {self.bucket}: {e}")

    def compute_day(self, day):
        """Statistics for one local day (so far, if it is today), or None without data"""
        tz = local_tz()
        start = datetime.combine(day, datetime.min.time(), tz)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz)
        now = datetime.now(tz)
        stop = min(end, now)
        s, e = _iso(start), _iso(stop)

        df = self.dq.query_metrics(RUNTIME_METRICS, aggregation_window='1m', start=s, stop=e)
        wide = self.dq.query_metrics_wide(WIDE_METRICS, aggregation_window='5m', start=s, stop=e)
        row = {'final': now >= end}
        if df.empty and wide.empty:
            return dict(row, coverage_pct=0.0)

        cfg = price_config()
        runtime = self.dq.calculate_runtime_stats(df=df)
        energy = self.dq.calculate_energy_costs(price_per_kwh=cfg['fixed'], df=df,
                                                prices=self.prices.price_series(start, stop))
        hw = self.dq.analyze_hot_water_cycles_from_df(df, '1d')
        cop_df = self.dq.calculate_cop_from_pivot(wide)
        heat = float(cop_df['heat_kwh'].sum()) if not cop_df.empty else 0.0
        cop_elec = float(cop_df['elec_kwh'].sum()) if not cop_df.empty else 0.0

        minutes = max((stop - start).total_seconds() / 60, 1)
        samples = int(wide['outdoor_temp'].notna().sum()) if 'outdoor_temp' in wide.columns else 0
        brine_in = 'brine_in_evaporator'

        row.update({
            'energy_kwh': energy['total_kwh'],
            'cost_kr': energy['total_cost'],
            'heat_kwh': round(heat, 2),
            'cop_elec_kwh': round(cop_elec, 2),
            'cop': round(heat / cop_elec, 2) if cop_elec > 0.1 else None,
            'compressor_hours': runtime['compressor_runtime_hours'],
            'compressor_starts': runtime['compressor_starts'],
            'aux_hours': runtime['aux_heater_runtime_hours'],
            'hw_cycles': hw['total_cycles'],
            'hw_kwh': round(hw['total_cycles'] * hw['avg_energy_per_cycle_kwh'], 2),
            'outdoor_mean': _temp(wide, 'outdoor_temp', 'mean'),
            'outdoor_min': _temp(wide, 'outdoor_temp', 'min'),
            'outdoor_max': _temp(wide, 'outdoor_temp', 'max'),
            'indoor_mean': _temp(wide, 'indoor_temp', 'mean'),
            'brine_in_mean': _temp(wide, brine_in, 'mean'),
            'brine_in_min': _temp(wide, brine_in, 'min'),
            'brine_out_mean': _temp(wide, 'brine_out_condenser', 'mean'),
            'hot_water_mean': _temp(wide, 'hot_water_top', 'mean'),
            'coverage_pct': round(min(samples * 5 / minutes * 100, 100), 1),
        })
        return row

    def write_day(self, day, row):
        point = Point('daily').time(datetime.combine(day, datetime.min.time(), local_tz()))
        for k, v in row.items():
            if v is None:
                continue
            point = point.field(k, bool(v) if k == 'final' else float(v))
        self.write_api.write(bucket=self.bucket, record=point)
        self._rows = (0, None)

    def read_all(self):
        """All stored days as a DataFrame with a local 'date' column, sorted by date"""
        hit_time, rows = self._rows
        if rows is not None and time.time() - hit_time < TODAY_MAX_AGE:
            return rows
        query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: 2000-01-01T00:00:00Z)
                |> filter(fn: (r) => r._measurement == "daily")
                |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        try:
            df = self.dq.query_api.query_data_frame(query)
            if isinstance(df, list):
                df = pd.concat(df, ignore_index=True) if df else pd.DataFrame()
        except Exception as e:
            logger.error(f"Could not read daily stats: {e}")
            return pd.DataFrame()
        if not df.empty:
            df['date'] = pd.to_datetime(df['_time'], utc=True).dt.tz_convert(local_tz()).dt.date
            df = df.sort_values('date').drop_duplicates('date', keep='last').reset_index(drop=True)
        self._rows = (time.time(), df)
        return df

    def first_raw_day(self):
        query = f'''
            from(bucket: "{self.dq.bucket}")
                |> range(start: 0)
                |> filter(fn: (r) => r._measurement == "heatpump" and r.name == "outdoor_temp")
                |> first()
        '''
        try:
            df = self.dq.query_api.query_data_frame(query)
            if isinstance(df, list):
                df = pd.concat(df, ignore_index=True) if df else pd.DataFrame()
            if df.empty:
                return None
            return pd.to_datetime(df['_time'], utc=True).min().tz_convert(local_tz()).date()
        except Exception as e:
            logger.error(f"Could not find first raw day: {e}")
            return None

    def update(self):
        """Compute and store every day since the first raw sample that is not final yet"""
        first = self.first_raw_day()
        if first is None:
            return
        stored = self.read_all()
        done = set(stored.loc[stored['final'] == True, 'date']) if 'final' in stored.columns else set()  # noqa: E712
        if self._force:
            done, self._force = set(), False
        today = datetime.now(local_tz()).date()
        day = first
        while day <= today:
            if day not in done:
                row = self.compute_day(day)
                self.write_day(day, row)
                if day == today:
                    self._today = (time.time(), row)
                logger.info(f"Daily stats {day}: {row.get('energy_kwh')} kWh, coverage {row.get('coverage_pct')}%")
            eventlet.sleep(0)
            day += timedelta(days=1)

    def run(self):
        self.ensure_bucket()
        while True:
            try:
                self.update()
            except Exception as e:
                logger.error(f"Daily stats update failed: {e}")
            eventlet.sleep(UPDATE_SECONDS)

    def today(self):
        """Today's statistics so far, recomputed at most once a minute"""
        with self._today_lock:
            hit_time, row = self._today
            if row is None or time.time() - hit_time > TODAY_MAX_AGE:
                try:
                    row = self.compute_day(datetime.now(local_tz()).date())
                except Exception as e:
                    logger.error(f"Could not compute today's stats: {e}")
                self._today = (time.time(), row)
            return row

    # ---------- Statistics API ----------

    @staticmethod
    def summarize(df):
        if df.empty:
            return None
        days = len(df)
        energy = df['energy_kwh'].sum()
        cost = df['cost_kr'].sum()
        cop_elec = df['cop_elec_kwh'].sum()
        return {
            'days': days,
            'energy_kwh': round(float(energy), 1),
            'cost_kr': round(float(cost), 0),
            'avg_price': round(float(cost / energy), 2) if energy > 0 else None,
            'cop': round(float(df['heat_kwh'].sum() / cop_elec), 2) if cop_elec > 0.1 else None,
            'energy_per_day': round(float(energy / days), 1),
            'starts_per_day': round(float(df['compressor_starts'].sum() / days), 1),
            'hw_cycles_per_day': round(float(df['hw_cycles'].sum() / days), 1),
            'aux_hours': round(float(df['aux_hours'].sum()), 1),
            'compressor_hours': round(float(df['compressor_hours'].sum()), 1),
            'outdoor_mean': _num(round(float(df['outdoor_mean'].mean()), 1)),
            'brine_in_mean': _num(round(float(df['brine_in_mean'].mean()), 1)),
            'brine_in_min': _num(round(float(df['brine_in_min'].min()), 1)),
        }

    @staticmethod
    def group(df, by):
        if by == 'day':
            out = df.copy()
            out['label'] = out['date'].astype(str)
        else:
            out = df.copy()
            out['label'] = pd.to_datetime(out['date']).dt.strftime('%Y-%m')
            agg = {k: 'sum' for k in SUM_FIELDS}
            agg.update({k: 'mean' for k in MEAN_FIELDS})
            agg.update({k: 'min' for k in MIN_FIELDS})
            agg.update({k: 'max' for k in MAX_FIELDS})
            agg['coverage_pct'] = 'mean'
            agg['date'] = 'count'
            out = out.groupby('label', as_index=False).agg(agg).rename(columns={'date': 'days'})
            out['cop'] = (out['heat_kwh'] / out['cop_elec_kwh']).where(out['cop_elec_kwh'] > 0.1)
        cols = ['label'] + [c for c in ['days'] + SUM_FIELDS + MEAN_FIELDS + MIN_FIELDS + MAX_FIELDS +
                            ['cop', 'coverage_pct'] if c in out.columns]
        out = out[cols].round(2).astype(object)
        return out.where(out.notna(), None).to_dict('records')

    @staticmethod
    def signature(df, today):
        """Energy signature: kWh/day against mean outdoor temperature on heating days"""
        d = df[(df['outdoor_mean'] < 15) & (df['coverage_pct'] >= 80) & (df['energy_kwh'] > 0)]
        points = [{'date': str(r.date), 'outdoor': round(float(r.outdoor_mean), 1),
                   'energy_kwh': round(float(r.energy_kwh), 1), 'recent': (today - r.date).days < 30}
                  for r in d.itertuples()]
        fit = None
        if len(d) >= 5 and d['outdoor_mean'].nunique() > 1:
            a, b = np.polyfit(d['outdoor_mean'].astype(float), d['energy_kwh'].astype(float), 1)
            if a < 0:
                fit = {'slope': round(float(a), 2), 'intercept': round(float(b), 2),
                       'kwh_per_degree': round(float(-a), 2), 'balance_temp': round(float(-b / a), 1)}
        return {'points': points, 'fit': fit}

    def stats(self, by='day', days=30):
        df = self.read_all()
        if df.empty or 'coverage_pct' not in df.columns:
            return {'rows': [], 'totals': None, 'previous_totals': None, 'signature': {'points': [], 'fit': None},
                    'year_ago': None, 'today': self.today()}
        for c in SUM_FIELDS + MEAN_FIELDS + MIN_FIELDS + MAX_FIELDS + ['coverage_pct', 'cop']:
            if c not in df.columns:
                df[c] = np.nan
        df[SUM_FIELDS] = df[SUM_FIELDS].fillna(0)
        df = df[df['coverage_pct'] > 0]
        today = datetime.now(local_tz()).date()
        if days:
            cur = df[df['date'] > today - timedelta(days=days)]
            prev = df[(df['date'] > today - timedelta(days=2 * days)) & (df['date'] <= today - timedelta(days=days))]
        else:
            cur, prev = df, df.iloc[0:0]

        # Same calendar month this year and last year (brine temperature trend and costs)
        month = pd.to_datetime(df['date'])
        this_m = df[(month.dt.year == today.year) & (month.dt.month == today.month)]
        last_m = df[(month.dt.year == today.year - 1) & (month.dt.month == today.month)]
        year_ago = None
        if not last_m.empty:
            year_ago = {'month': today.strftime('%Y-%m'), 'current': self.summarize(this_m),
                        'previous_month': f'{today.year - 1}-{today.month:02d}', 'previous': self.summarize(last_m)}

        return {
            'rows': self.group(cur, by),
            'totals': self.summarize(cur),
            'previous_totals': self.summarize(prev),
            'signature': self.signature(df, today),
            'brine': [{'date': str(r.date), 'brine_in_mean': _num(r.brine_in_mean), 'brine_in_min': _num(r.brine_in_min),
                       'brine_out_mean': _num(r.brine_out_mean), 'outdoor_mean': _num(r.outdoor_mean)}
                      for r in df.itertuples()],
            'year_ago': year_ago,
            'today': self.today(),
        }
