"""
Electricity price per interval: spot price from elprisetjustnu.se (excl. VAT, 15 or 60 min
intervals) plus markup and VAT, or a fixed price. Fetched spot prices are stored in the
long-term bucket so each day is only downloaded once.
"""

import time
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from data_query import load_config

logger = logging.getLogger(__name__)

API_URL = 'https://www.elprisetjustnu.se/api/v1/prices/{d:%Y}/{d:%m-%d}_{area}.json'
FIRST_DAY = date(2022, 11, 1)
AREAS = ('SE1', 'SE2', 'SE3', 'SE4')
RETRY_SECONDS = 3600


def local_tz():
    try:
        return ZoneInfo(load_config().get('timezone') or 'Europe/Stockholm')
    except Exception:
        return ZoneInfo('Europe/Stockholm')


def price_config():
    cfg = load_config()
    p = cfg.get('price') or {}
    return {
        'mode': p.get('mode', 'fixed'),
        'area': p.get('area', 'SE3'),
        'markup': float(p.get('markup', 0.0)),
        'vat': bool(p.get('vat', True)),
        'fixed': float(cfg.get('electricity_price', 2.0)),
    }


class SpotPrices:
    def __init__(self, data_query, bucket):
        self.dq = data_query
        self.bucket = bucket
        self.write_api = data_query.client.write_api(write_options=SYNCHRONOUS)
        self._days = {}      # (area, date) -> pd.Series of SEK/kWh excl. VAT, UTC index
        self._failed = {}    # (area, date) -> time of last failed fetch
        self._loaded = set()  # areas read from InfluxDB

    def _load_stored(self, area):
        query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {FIRST_DAY.isoformat()}T00:00:00Z)
                |> filter(fn: (r) => r._measurement == "spot_price" and r.area == "{area}")
                |> keep(columns: ["_time", "_value"])
        '''
        self._loaded.add(area)  # once; on failure days are fetched from the API instead
        try:
            df = self.dq.query_api.query_data_frame(query)
            if isinstance(df, list):
                df = pd.concat(df, ignore_index=True) if df else pd.DataFrame()
        except Exception as e:
            logger.error(f"Could not read stored spot prices: {e}")
            return
        if df.empty:
            return
        s = df.set_index(pd.to_datetime(df['_time'], utc=True))['_value'].sort_index()
        tz = local_tz()
        for day, part in s.groupby(s.index.tz_convert(tz).date):
            self._days[(area, day)] = part
        logger.info(f"Loaded stored spot prices for {area}: {len(s)} intervals")

    def _fetch(self, area, day):
        try:
            r = requests.get(API_URL.format(d=day, area=area), timeout=10)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            rows = r.json()
        except Exception as e:
            logger.warning(f"Spot price fetch failed for {area} {day}: {e}")
            return None
        if not rows:
            return None
        s = pd.Series([float(x['SEK_per_kWh']) for x in rows],
                      index=pd.to_datetime([x['time_start'] for x in rows], utc=True)).sort_index()
        try:
            self.write_api.write(bucket=self.bucket, record=[
                Point('spot_price').tag('area', area).field('sek_per_kwh', v).time(t.to_pydatetime())
                for t, v in s.items()])
        except Exception as e:
            logger.error(f"Could not store spot prices for {area} {day}: {e}")
        return s

    def spot(self, area, day):
        """Spot prices for a local day, or None if not available (yet)"""
        if area not in self._loaded:
            self._load_stored(area)
        key = (area, day)
        if key in self._days:
            return self._days[key]
        tomorrow = datetime.now(local_tz()).date() + timedelta(days=1)
        if day < FIRST_DAY or day > tomorrow:
            return None
        if time.time() - self._failed.get(key, 0) < RETRY_SECONDS:
            return None
        s = self._fetch(area, day)
        if s is None:
            self._failed[key] = time.time()
            return None
        self._days[key] = s
        return s

    def price_series(self, start, stop):
        """Total price kr/kWh per interval start between start and stop (aware datetimes).
        None in fixed mode. Days without spot price get NaN so callers fall back to the fixed price."""
        cfg = price_config()
        if cfg['mode'] != 'spot' or cfg['area'] not in AREAS:
            return None
        tz = local_tz()
        day, last = start.astimezone(tz).date(), stop.astimezone(tz).date()
        parts = []
        while day <= last:
            s = self.spot(cfg['area'], day)
            if s is None:
                s = pd.Series([float('nan')],
                              index=[pd.Timestamp(datetime.combine(day, datetime.min.time(), tz)).tz_convert('UTC')])
            parts.append(s)
            day += timedelta(days=1)
        series = pd.concat(parts).sort_index()
        return (series + cfg['markup']) * (1.25 if cfg['vat'] else 1.0)
