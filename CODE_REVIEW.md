# Code Review — heatpumpv4

**Reviewed:** 2026-07-28
**Scope:** full repository at `493d62e` (collector, dashboard, providers, Docker/compose, frontend)
**Size:** ~12.5k lines (≈5.5k Python, ≈2.1k JS, ≈2.7k HTML/CSS)

---

## 1. Verdict

This is a capable, working system. The provider abstraction is genuinely well designed, the
InfluxDB batching work has clearly paid off, and the domain modelling (COP, runtime, hot-water
cycles) shows real understanding of heat-pump behaviour.

The problems are concentrated in three places:

1. **Security** — the dashboard exposes an unauthenticated container-restart endpoint backed by a
   mounted Docker socket, and interpolates a user-controlled string straight into Flux queries
   executed with an InfluxDB **admin** token. On a home LAN this is a real escalation path.
2. **Settings that don't do anything** — 3 of the 7 fields on the settings page are written to
   `config.yaml` and then never read by the code that would use them.
3. **Dead and duplicated code** — roughly 40 % of `app.py` is unreachable, and ~1 000 lines of
   Dash-era provider code reference libraries that aren't even installed.

There are also **no tests, no CI, and no linting** anywhere in the repo. For a system that does
non-trivial numerical work (energy integration, COP, cycle detection) that is the single highest
-leverage gap.

### Scorecard

| Area | Grade | Note |
|---|---|---|
| Architecture / provider abstraction | **B+** | Clean ABC, real auto-discovery, easy to extend |
| Security | **D** | Docker socket + no auth + query injection + admin token |
| Correctness | **C** | Several silently-broken features; good domain logic underneath |
| Performance | **C+** | Big real wins, but the "parallel" layer does nothing |
| Maintainability | **C-** | ~600 dead lines in `app.py`, 3× copy-pasted functions |
| Frontend | **B-** | Solid, one broken button, hard CDN dependency |
| Ops / packaging | **C** | Works, but `debug=True` in prod and no `.env.example` |
| Testing & tooling | **F** | None exists |

---

## 2. Critical — security

### 2.1 Unauthenticated container restart over a mounted Docker socket

`docker-compose.yml:69` mounts `/var/run/docker.sock` into the dashboard container.
`dashboard/app.py:339` exposes `POST /api/restart-service` with **no authentication of any kind**.

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock   # docker-compose.yml:69
```

Two separate problems:

- **Root-equivalent access.** Any code execution inside the dashboard container — including a
  future dependency compromise — can create a privileged container and own the host. The socket
  mount is a full host escape primitive, not a restart primitive.
- **No authn/authz.** Anyone who can reach port 8050 (the whole LAN, plus anything port-forwarded)
  can restart your collector in a loop. The `RESTARTABLE_CONTAINERS` allowlist (`app.py:333`)
  correctly prevents *arbitrary* container names — that part is good — but it doesn't gate *who*
  may call it.

**Fix, in order of preference:**

1. Drop the socket entirely. Set `restart: unless-stopped` (already present) and have services
   watch `config.yaml` with a file-mtime check, re-reading settings in place. No restart needed.
2. If a restart really is required, use a tiny sidecar with a one-endpoint API and a shared secret,
   so the socket never enters the web-facing container.
3. At minimum: mount the socket read-only, put the whole app behind auth, and bind the published
   port to `127.0.0.1:8050` instead of `0.0.0.0`.

### 2.2 Flux query injection via the `range` parameter

`time_range` comes straight from client input and is interpolated into Flux with an f-string:

```python
time_range = request.args.get('range', '24h')     # app.py:962  (also socket 'change_time_range', app.py:1759)
...
|> range(start: -{time_range})                     # data_query.py:147, 165, 229, 236, 250, 264, 343
```

`_get_aggregation_window()` (`data_query.py:83`) does not raise on a malformed value — anything not
ending in `h`/`d` silently returns the `"5m"` default — so a crafted string reaches the query
unmodified. This appears in **seven** query builders across the file.

The blast radius is amplified by `docker-compose.yml:19` and `:61`: the dashboard is handed
`DOCKER_INFLUXDB_INIT_ADMIN_TOKEN`, the org admin token. Injected Flux therefore runs with full
read/write rights over every bucket, and Flux can `to()` into other buckets and (depending on build)
reach `http.post`.

**Fix:**

```python
VALID_RANGES = {'1h', '6h', '24h', '7d', '30d', '90d'}   # mirror config.yaml dashboard.time_ranges

def _validate_range(value: str) -> str:
    if value not in VALID_RANGES:
        raise ValueError(f'Invalid time range: {value!r}')
    return value
```

Validate once at each entry point (`get_initial_data`, `handle_time_range_change`,
`handle_manual_update`) and return HTTP 400 / a socket `error` event on failure. Separately, create
a **scoped read token** for the dashboard and a **write-only token** for the collector; stop reusing
the admin token.

### 2.3 `debug=True` in production

```python
socketio.run(app, host='0.0.0.0', port=8050, debug=True, use_reloader=False)   # app.py:1863
```

`debug=True` turns on Flask's debug mode and propagates verbose tracebacks. With `async_mode='eventlet'`
the Werkzeug interactive debugger isn't served, so this is not the classic RCE — but it still leaks
stack traces, file paths, and config to any client, and it contradicts `FLASK_ENV=production` in the
Dockerfile. Drive it from an env var and default to `False`.

### 2.4 Wide-open CORS plus a default secret

```python
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'heatpump-dashboard-secret-key')  # app.py:44
CORS(app)                                                                             # app.py:45 — all origins
socketio = SocketIO(app, cors_allowed_origins="*", ...)                               # app.py:50
```

`CORS(app)` with no arguments allows every origin against every route, including the state-changing
`POST /api/settings` and `POST /api/restart-service`. Any page the user visits can therefore drive
your dashboard from their browser. The hardcoded `SECRET_KEY` fallback (and the equally public one in
`docker-compose.yml:65`) means sessions are forgeable if you ever add them.

**Fix:** restrict `origins` to the dashboard's own host(s), and make `SECRET_KEY` mandatory —
fail fast at startup if it's unset rather than falling back to a published constant.

### 2.5 Front-end supply chain

Bootstrap, Font Awesome, ECharts, and Socket.IO all load from public CDNs with **no
`integrity`/SRI hashes** (`dashboard.html:9,12,18,21,684`; same in `mobile.html`, `index.html`).
Two consequences: a CDN compromise executes arbitrary JS in your dashboard, and — more practically —
**the dashboard does not work without internet access**, which is an odd property for a local
appliance monitor. Vendor the four files into `static/vendor/` and serve them locally.

---

## 3. Correctness bugs

### 3.1 Three of seven settings are no-ops 🔴

The settings page writes them; nothing reads them.

| Setting | Written at | Actually used? |
|---|---|---|
| `brand` | `app.py:279` | ✅ |
| `cop.flow_factor` | `app.py:284` | ⚠️ only at process start — see 3.2 |
| `hot_water.min_cycle_minutes` | `app.py:289` | ⚠️ only at process start — see 3.2 |
| `retention.days` | `app.py:311` | ✅ applied immediately |
| **`electricity_price`** | `app.py:306` | ❌ **never read** |
| **`collection.interval_seconds`** | `app.py:296` | ❌ **never read** |
| **`dashboard.refresh_interval`** | `app.py:301` | ❌ **never read** |

- **`electricity_price`** — every cost figure uses the hardcoded default:
  `get_kpi_data_cached(..., price_per_kwh=2.0)` at `app.py:1682`, called from `app.py:596` with no
  price argument. Change the price in the UI, restart everything: the cost KPI never moves.
- **`collection.interval_seconds`** — `collector/collector.py:281` reads only
  `os.getenv('COLLECTION_INTERVAL', '30')`. The UI even reports `needs_restart: ['collector']`
  (`app.py:295`), so the user restarts the collector and *still* sees no change. The most
  confusing possible failure mode.
- **`dashboard.refresh_interval`** — `background_updates()` hardcodes `eventlet.sleep(30)`
  (`app.py:1810`).

**Fix:** load `electricity_price` from config into `get_kpi_data_cached`; have the collector prefer
`config.yaml`'s `collection.interval_seconds` over the env var (it already reads the file for
`brand` at `collector.py:43` — extend that function); read `dashboard.refresh_interval` in the
background loop.

### 3.2 Settings changes require a restart that the UI never asks for

`HeatPumpDataQuery.__init__` (`data_query.py:51`) snapshots `cop_flow_factor` and
`hw_min_cycle_minutes` once, at import time. `needs_restart` (`app.py:273`) only ever contains
`'brand'` or `'collector'` — never `'dashboard'`. So editing the flow factor shows
"Inställningar sparade", changes nothing visible, and gives no hint why.

**Fix:** either add `'dashboard'` to `needs_restart` for those two keys, or (better) re-read
`config.yaml` per request via a small cached loader keyed on file mtime.

### 3.3 The restart button generated after saving is broken

```javascript
msg += `<br><button ... onclick="restartServices(${JSON.stringify(result.needs_restart)})">`;
// socket-client.js:625
```

`JSON.stringify(["brand"])` yields `["brand"]` — with double quotes. Injected into a
double-quoted HTML attribute via `innerHTML`, the first `"` terminates `onclick` and the handler
never runs. Build the element with `createElement` and attach the listener in JS, or at minimum use
`&quot;`-escaped single quotes.

### 3.4 NIBE support is largely non-functional

The dashboard queries a fixed set of metric names (`app.py:489-496`, `520-527`). NIBE's register
file uses different names for several of them:

| Dashboard expects | NIBE provides | Effect |
|---|---|---|
| `power_consumption` | *(absent — has `load_l1/l2/l3`)* | **COP returns empty** (`data_query.py:678`); energy + cost KPIs are 0 |
| `hot_water_top` | `warm_water_top` | Hot-water temp blank everywhere |
| `radiator_forward` | `radiator_forward_2` | Forward temp + radiator delta missing |
| `alarm_status` | *(absent)* | Alarm detection degraded to `alarm_code` only |
| `degree_minutes` | `degree_minutes_integral` | Integral panel blank |
| `pressure_tube_temp` / `hot_gas_compressor` | `hot_gas_temp` | Hetgas series missing |

`config_colors.py` already carries `warm_water_top` and `warm_water_mid` aliases, so the naming
divergence was noticed on the colour side but never on the query side.

**Fix:** add a `get_metric_aliases() -> Dict[str, str]` to `HeatPumpProvider` mapping canonical
dashboard names to brand-local names, and resolve through it in `data_query`. Rename the NIBE
registers to the canonical names where a straight rename is correct. For `power_consumption`,
either derive it from `load_l1+l2+l3` in the collector or document NIBE as COP-unsupported.

### 3.5 One malformed register kills an entire collection cycle

```python
processed_data[register_id_upper] = int(raw_value)   # collector.py:149
```

`fetch_all_data` catches only `requests.RequestException` (`collector.py:153`). A single
non-numeric or `null` value from the gateway raises `ValueError`/`TypeError`, which propagates to
`collect_once`'s bare handler (`collector.py:241`) — so **all ~40 sensors are dropped** because one
register was bad. Wrap the conversion per register, log at debug, and continue:

```python
try:
    processed_data[register_id_upper] = int(raw_value)
except (TypeError, ValueError):
    logger.debug("Skipping non-numeric register %s=%r", register_id_upper, raw_value)
```

### 3.6 Scale/sign metadata is defined but ignored

`providers/nibe/registers.py` carries `'scale': 0.1` and `'signed': True` on every register.
Neither key is read anywhere in the codebase (verified by grep). Conversion instead goes through
`should_divide_by_10()` (`base.py:425`), a **denylist** on `type`:

```python
return ['status', 'alarm', 'runtime', 'power', 'energy', 'setting', 'current']  # base.py:423
```

Two consequences:

- **Any new or misspelled `type` is silently divided by 10.** `"percentage"` is not on the list, so
  `additional_heat_percent` (`thermia/registers.py:111`, `ivt/registers.py:79`) *is* divided. If the
  H66 delivers 0-100 rather than 0-1000 for that register, every aux-heat reading and every
  aux-runtime percentage is 10× low. **Worth verifying against the live gateway** — it's a one-line
  check against `/api/debug/all-metrics`.
- **Sign handling is ad hoc.** `calculate_cop_from_pivot` filters sentinel values with the comment
  `# common: -48°C, -127°C, 0xFFFF/6553.5°C` (`data_query.py:659`) — evidence that unsigned
  wraparound has actually been observed. But that filter exists in exactly one function; the same
  bad value flows unfiltered into every chart, min/max, and status panel.

**Fix:** make `scale` (and `signed`) authoritative per register, defaulting to `1.0`; do the sentinel
filtering once in the collector, before the value ever reaches InfluxDB. That turns two scattered
heuristics into one enforced rule.

### 3.7 Hot-water cycle stats are computed from over-aggregated data

`analyze_hot_water_cycles_from_df(df, time_range)` (`app.py:548`) is fed the **batch** dataframe,
which uses `_get_aggregation_window` — `2h` buckets for a 30-day range (`data_query.py:108`).
Detecting valve transitions and per-cycle durations in 2-hour buckets is not meaningful; the
deprecated path it replaced explicitly used `aggregation_window='1m'` (`data_query.py:1191`).

Related: `get_kpi_data` widened short ranges to `7d` for hot-water stats (`app.py:1646`); the cached
replacement dropped that, so the "1h" view now reports cycles-per-day from one hour of data.

**Fix:** keep the fast path but issue one dedicated fine-grained query for `switch_valve_status` +
`power_consumption` (they're only two series — it's cheap), and restore the widened window.

### 3.8 Fabricated COP when the real value looks wrong

```python
if avg_cop < 1.5 or avg_cop > 5.0:
    avg_cop = 3.5          # app.py:1081 and again at :1140
has_data = True            # ...still reported as real
```

A genuinely poor COP of 1.3 — exactly the situation a monitoring dashboard exists to surface — is
silently replaced with a healthy-looking 3.5, and `has_data` still says the number is real. Show the
measured value, or show "insufficient data"; never substitute a plausible constant.

### 3.9 Invalid settings are accepted silently

Every validator in `save_settings` (`app.py:281-311`) follows the same shape:

```python
val = float(data['cop_flow_factor'])
if 1.0 <= val <= 5.0:
    config.setdefault('cop', {})['flow_factor'] = round(val, 2)
# else: silently discarded, response still says success
```

Out-of-range input returns `{'success': True, 'message': 'Inställningar sparade'}`. Non-numeric
input raises `ValueError` before that and returns an unhandled 500. Also, `data = request.json`
(`app.py:265`) raises 415 on a missing content-type rather than a useful error.

**Fix:** collect validation errors and return 400 with a per-field list; use
`request.get_json(silent=True)` with an explicit null check.

### 3.10 Smaller correctness notes

- **`datetime.utcnow()`** (`collector.py:227`) is deprecated from Python 3.12. Use
  `datetime.now(timezone.utc)`.
- **Polling drift** — `time.sleep(self.interval)` after a variable-duration collection
  (`collector.py:263`) makes the real period `interval + fetch_time`. Sleep to the next wall-clock
  boundary instead.
- **`BUILD_TIME`** (`app.py:20`) is evaluated at import, so it's *container start* time, not build
  time. Pass a real build arg via `ARG BUILD_TIME` in the Dockerfile.
- **Pandas `'T'` frequency alias** (`data_query.py:716`) is deprecated in pandas ≥2.2. Pinned at
  2.1.4 today, so this is a latent upgrade blocker — use `'min'`.
- **`alarm_code` is mean-aggregated.** It isn't typed `status`, so `query_metrics` averages it
  (`data_query.py:150`); `int(code)` on an averaged value across an alarm boundary can produce a
  code that never occurred. Type it as `status`, or query alarms with `last()`.

---

## 4. Architecture & maintainability

### 4.1 ~600 lines of `app.py` are unreachable

Only `fetch_all_data_batch` is ever executed. Every non-cached extractor is defined and never
called (verified: their definition is the only reference in the repo).

| Dead function | Lines | Live replacement |
|---|---|---|
| `get_cop_data` | 982-1003 | `get_cop_data_from_pivot` |
| `get_temperature_data` | 1006-1034 | `get_temperature_data_from_pivot` |
| `get_runtime_data` | 1037-1049 | `get_runtime_data_cached` |
| `get_sankey_data` | 1066-1125 | `get_sankey_data_cached` |
| `get_performance_data` | 1187-1263 | `get_performance_data_from_pivot` |
| `get_power_data` | 1266-1318 | `get_power_data_from_df` |
| `get_valve_data` | 1321-1373 | `get_valve_data_from_df` |
| `get_status_data` | 1376-1445 | `get_status_data_fully_cached` |
| `get_status_data_cached` | 1448-1511 | `get_status_data_fully_cached` |
| `get_event_log` | 1514-1532 | `get_event_log_cached` |
| `get_kpi_data` | 1636-1679 | `get_kpi_data_cached` |

Also dead: `HeatPumpDataQuery.calculate_min_max_from_df`, `get_latest_values_from_df`, and
`HeatPumpProvider.validate_register_value` (never called — so no register value is ever validated).

`get_sankey_data` / `get_sankey_data_cached` are a **60-line literal copy-paste** differing only in
where `avg_cop` comes from. The three `get_status_data*` variants are ~70 lines each and share
~90 % of their body. This is the "add a cached variant instead of parameterising" pattern applied
eleven times; every future change to the status payload has to be made in three places, and the
compiler won't tell you when you miss one.

**Fix:** delete all eleven. Where a non-cached path is genuinely wanted, make the cache an optional
parameter:

```python
def get_status_data(cop_df=None, min_max=None, latest=None, alarm=None, time_range='24h'):
    cop_df  = cop_df  if cop_df  is not None else data_query.calculate_cop(time_range)
    min_max = min_max if min_max is not None else data_query.get_min_max_values(time_range)
    ...
```

This alone takes `app.py` from 1 865 to roughly 1 100 lines.

### 4.2 ~1 000 lines of Dash-era provider code that cannot import

`providers/*/callbacks.py` and `providers/*/dashboard_components.py` (six files, ~980 lines) import
`from dash import Input, Output` and `dash_bootstrap_components`. **Neither package is in either
`requirements.txt`.** They aren't imported by the factory (`providers/__init__.py:63` only loads
`provider.py`), so they don't crash anything — they're just fossils from the pre-Flask architecture
that will mislead the next person to open the directory. Delete them; they're recoverable from git.

### 4.3 `app.py` is doing four jobs

1 865 lines mixing HTTP routes, WebSocket handlers, settings persistence, Docker control, and all
data-shaping. A modest split — no framework churn required:

```
dashboard/
  app.py              # Flask app factory + wiring only
  routes/  api.py     # /api/* HTTP routes
  routes/  ws.py      # Socket.IO handlers
  services/ payload.py    # get_*_from_pivot / _from_df builders
  services/ settings.py   # config.yaml read/write/validate
  services/ docker_ctl.py # restart (or delete with §2.1)
```

`data_query.py` (1 603 lines) similarly wants splitting into `queries.py` (Flux) and
`analytics.py` (COP / runtime / cycles). That split also makes the analytics unit-testable without
an InfluxDB, which is the precondition for §7.

### 4.4 Import-time side effects

`apply_retention_from_config()` runs at module import (`app.py:201`), and `load_provider()` /
`HeatPumpDataQuery()` construct global singletons at `app.py:78-79`. Importing `app` therefore
performs network I/O against InfluxDB, which makes the module untestable and means a slow or absent
database turns into an import failure rather than a degraded startup. Move all three into an
explicit `create_app()`.

`sys.path.insert(...)` appears in `collector.py:31`, `app.py:29`, and `data_query.py:31`. Making
`providers` a real installable package (`pyproject.toml` + `pip install -e .`) removes all three and
lets both images share one build.

### 4.5 Duplicated event-detection logic

`get_event_log` (`data_query.py:1378`, ~220 lines of `if metric == ...` branches) and
`get_event_log_from_df` (`data_query.py:492`, vectorised, table-driven) implement the same rules
twice. The vectorised one is strictly better *and* the table-driven `binary_metrics` dict is the
right design. The old one is dead — delete it.

---

## 5. Performance

### 5.1 The "parallel" fetch layer is decorative 🟡

`fetch_all_data_batch` (`app.py:479`) builds an `eventlet.GreenPool(size=10)` and spawns ten tasks
(`app.py:584-601`). But **every blocking query has already run sequentially above it** —
`calculate_runtime_stats`, `query_metrics_wide`, `calculate_cop_from_pivot`,
`analyze_hot_water_cycles_from_df`, `get_min_max_values`, `get_latest_values`,
`get_alarm_status_from_df`, `get_event_log_from_df`, all at lines 501-582.

The ten pooled tasks are pure CPU-bound pandas transforms. Eventlet green threads only interleave at
I/O yield points; CPU-bound work in a single OS thread runs strictly serially no matter how many
greenlets you spawn. The pool therefore adds complexity, an extra layer of lambdas, and per-task
timing noise for **zero** wall-clock benefit.

Two honest options:
- **Delete the pool** and call the ten builders in sequence. Same speed, ~20 fewer lines, far
  clearer.
- **Or actually parallelise** by moving the *queries* into the pool and letting the greenlets block
  on socket reads — that's the case eventlet is good at, and it's where the remaining seconds are.

`fetch_all_data_parallel` (`app.py:463`) is now a pass-through with an unused `start_time` local; it
should be inlined away.

Relatedly, the docstring "Fetch all metrics in ONE InfluxDB query" (`app.py:481`) is no longer true —
the function issues **five** round-trips (batch, viz-wide, runtime, min/max, latest). That's a
defensible design, but the comment should say so.

### 5.2 Duplicate work per connected client

```python
for client_id, client_info in list(connected_clients.items()):
    update_data = fetch_all_data_parallel(time_range)   # app.py:1825 — full pipeline, per client
```

Three browser tabs on `30d` means three complete five-query pipelines every 30 seconds against the
same data. Group clients by `time_range`, compute once per distinct range, and emit the shared
payload to each room:

```python
by_range = defaultdict(list)
for cid, info in list(connected_clients.items()):
    by_range[info.get('time_range', '24h')].append(cid)

for time_range, client_ids in by_range.items():
    payload = clean_nan_values(fetch_all_data_batch(time_range))
    payload['timestamp'] = datetime.now(timezone.utc).isoformat()
    for cid in client_ids:
        socketio.emit('graph_update', payload, room=cid)
```

A short TTL cache (10-15 s) keyed on `time_range` would additionally collapse the burst of
`change_time_range` / `request_update` / background traffic that tends to arrive together.

### 5.3 Row-at-a-time loops in the hot path

- **`calculate_runtime_stats`** (`data_query.py:975-986`, `1013-1024`) walks the dataframe with
  `df.iloc[i]` — each access is a Series construction. Vectorised equivalent:

  ```python
  comp_df = comp_df.sort_values('_time')
  dt = comp_df['_time'].diff().shift(-1).dt.total_seconds().fillna(0).clip(0, 120)
  comp_runtime_seconds = dt[comp_df['_value'] > 0].sum()
  ```

  Same for the aux loop and the starts counter — three loops become three expressions. On a 90-day
  range this is thousands of iterations per client per refresh.

- **`analyze_hot_water_cycles_from_df`** (`data_query.py:1111-1142`) is O(n²): for each cycle start
  it re-scans the whole valve dataframe (`valve_df[valve_df['_time'] > start_time]`) and then slices
  the power frame again. Pair starts to ends once with a `shift`, then use
  `pd.cut` / `searchsorted` for the power windows.

- **`get_event_log_from_df`** (`data_query.py:524`) is described as vectorised but still appends
  inside `for ts in ...` loops. Minor — bounded by edge count, not row count — but
  `df.to_dict('records')` on the filtered frame would finish the job.

### 5.4 Payload waste

`data['config']['colors']` (`app.py:615-619`) ships the full `CHART_COLORS` dict to every client on
**every** 30-second update. The frontend never reads it — `charts.js:14` defines its own private
`COLORS` constant. So it's both dead bytes and a second source of truth for the palette. Either have
`charts.js` consume `data.config.colors`, or stop sending it. (Sending it once via `/api/config` at
connect is the sensible middle ground.)

### 5.5 Logging volume

`fetch_all_data_batch` emits ~20 `logger.info` lines per fetch, including
`get_valve_data_from_df` logging the full metric-name list on every call (`app.py:929`). At one
client on a 30-second refresh that's ~2 400 INFO lines/hour of pure timing chatter. Move the timing
instrumentation to `logger.debug` and keep INFO for one summary line.

---

## 6. Frontend

**Working well:** the ECharts lifecycle in `charts.js:58-89` correctly disposes the old instance,
removes the named resize handler, and preserves zoom state across updates — that's the fix from
`7abd23f` and it's done properly.

Issues:

- **§3.3** — the post-save restart button is broken by attribute quoting.
- **CDN dependency (§2.5)** — no offline operation, no SRI.
- **`innerHTML` throughout.** `updateEventLog` (`socket-client.js:441`) interpolates `event.icon`
  and `event.event` unescaped. Today all values originate from server-side constants
  (`data_query.py:505-511`) so it isn't exploitable — but `alarm_description` derives from
  `alarm_codes[...]` with an `f"Okänd larmkod: {code}"` fallback, so the boundary is thinner than it
  looks. Prefer `textContent` for the value parts.
- **Duplicated client state.** `socket-client.js` and `mobile-client.js` each declare their own
  `currentTimeRange`/`connected` and their own socket setup. They're loaded on different pages so
  there's no collision, but the connection/reconnection logic is copy-pasted. A shared
  `socket-core.js` would cover both.
- **Timestamp format.** `_time.astype(str)` (`app.py:685`, `815`) produces
  `2026-07-28 12:00:00+00:00` — a space separator, not `T`. Safari's `Date` parser is unreliable on
  that form. `_to_chart_data` (`app.py:748`) already builds proper ISO-8601; use the same formatting
  for the `timestamps` arrays.
- **Global-namespace API.** `window.updateMainChart`, `window.resizeMainChart`,
  `window.resetZoomState`, `window.switchChart`, … with `if (window.x)` guards at every call site.
  Workable at this size; ES modules would remove the guards entirely.

---

## 7. Testing & tooling — the biggest gap

There is no `tests/` directory, no `.github/workflows/`, no linter config, no formatter config.

That matters most for the numerical core, which is exactly the code where a silent regression is
invisible: COP integration, energy accumulation, runtime percentages, cycle detection. All four are
already **pure functions over a DataFrame** — `calculate_cop_from_pivot`, `calculate_energy_costs`,
`calculate_runtime_stats`, `analyze_hot_water_cycles_from_df` — so they can be tested with a
synthetic frame and no InfluxDB at all. A first suite could be ~200 lines:

```python
def test_cop_uses_summed_energy_not_mean_of_ratios():
    df = pd.DataFrame({
        '_time': pd.date_range('2026-01-01', periods=8, freq='5min', tz='UTC'),
        'radiator_forward':  [35.0]*8,
        'radiator_return':   [30.0]*8,
        'power_consumption': [1500.0]*8,
        'compressor_status': [1]*8,
    })
    out = dq.calculate_cop_from_pivot(df, interval_minutes=15)
    # ΔT=5 × flow 2.7 = 13.5 kW thermal / 1.5 kW electric
    assert out['estimated_cop'].dropna().between(8.9, 9.1).all()

def test_sentinel_temperatures_are_excluded():
    ...  # 6553.5 / -127 must not reach the COP output

def test_runtime_percent_never_exceeds_100():
    ...  # property test over random on/off sequences
```

Recommended baseline:

```yaml
# .github/workflows/ci.yml
- ruff check .            # lint
- ruff format --check .   # format
- pytest -q               # unit tests
- docker compose config   # compose validity
```

Add `providers/` conformance tests too — a parametrised test over `get_supported_brands()` asserting
that every provider instantiates, implements the ABC, and exposes the canonical metric names would
have caught §3.4 (NIBE) the day it was written.

---

## 8. Ops, Docker, and config

- **`version: '3.8'`** (`docker-compose.yml:4`) is obsolete in Compose v2 and emits a warning.
  Remove the key.
- **No `.env.example`.** `INFLUXDB_TOKEN` has no default (`docker-compose.yml:19`), so a fresh
  `docker compose up` fails with an opaque InfluxDB error. Ship a documented template.
- **Published on `0.0.0.0`** (`docker-compose.yml:58`). Given §2.1/§2.2, bind `127.0.0.1:8050:8050`
  and front it with a reverse proxy that handles auth.
- **Duplicate healthchecks** — one in `dashboard/Dockerfile`, one in `docker-compose.yml:75`. Keep
  the Dockerfile's and drop the override, or vice versa; two definitions drift.
- **No healthcheck on the collector.** It has the most failure modes (gateway unreachable, bad
  register data) and the least observability. Have it touch a liveness file after each successful
  cycle and check that file's mtime.
- **`gcc` left in the dashboard image** (`dashboard/Dockerfile`) after pip install. If no wheel
  actually needs it, drop it; if one does, use a builder stage. Also: both images run as **root**
  — add a non-root `USER`.
- **`depends_on` without `condition: service_healthy`** means the collector can start before
  InfluxDB is accepting connections; `_setup_influxdb` then raises and the container restart-loops
  until it happens to win the race. Add a health condition.
- **`config.yaml` mounted `:ro` for the collector but read-write for the dashboard**
  (`docker-compose.yml:37` vs `:68`). That's deliberate and correct, but it means the dashboard
  process must have write permission on a host file — worth a comment so nobody "fixes" it.
- **YAML round-trip destroys comments.** `yaml.dump` in `save_settings` (`app.py:316`) rewrites
  `config.yaml` and drops every comment — and that file's comments are genuinely useful (the
  flow-factor table at `config.yaml:24-31`). Use `ruamel.yaml` to round-trip, or split the
  user-editable values into a separate `settings.yaml` and leave `config.yaml` as documentation.
- **`README.md` is one line** (`# heatpump`) while `INSTALLATION.md` and `MULTI_BRAND_README.md`
  hold the real content. Make the README the entry point and link out.
- **Two 150 KB PDFs (`C00.pdf`, `C40.pdf`) committed at the repo root.** They're the register
  specs, so keeping them is reasonable — but move them to `docs/` and reference them from the
  provider files that were derived from them.

---

## 9. What's genuinely good

Worth stating plainly, because these are the parts to build on:

- **The provider abstraction** (`providers/base.py`, `providers/__init__.py`). A real ABC with
  required/optional method separation, lazy cached properties, and filesystem auto-discovery that
  needs zero factory edits to add a brand. The docstring at `base.py:5-11` tells a new contributor
  exactly what to do. This is better than most projects this size.
- **The `_from_df` / `_from_pivot` optimisation strategy.** Fetching once and deriving many views is
  the right instinct, and the measured wins (20s → 2-3s) are real. The execution has rough edges
  (§4.1, §5.1) but the direction is correct.
- **Domain modelling in the calculations.** Capping `time_diff_hours` to avoid inflating energy
  across data gaps (`data_query.py:905`), debouncing compressor starts by 60 s
  (`data_query.py:1001`), summing energy per interval rather than averaging COP ratios
  (`data_query.py:733`) — these are the details that separate a plausible dashboard from a correct
  one, and someone clearly thought about them.
- **`_to_chart_data`** (`app.py:737`) and the vectorised `get_event_log_from_df` show the codebase
  is actively improving; the pattern just hasn't been applied everywhere yet.
- **Bilingual comments** (Swedish for domain logic, English for infrastructure) are consistent and,
  for this domain, genuinely helpful.

---

## 10. Prioritised action plan

### P0 — do first (security & silent wrongness)

| # | Item | Ref | Effort | Status |
|---|---|---|---|---|
| 1 | Remove the Docker socket mount, or put the whole app behind auth | §2.1 | M | ⬜ deferred by decision |
| 2 | Whitelist `time_range` before it reaches Flux | §2.2 | **S** | ✅ done |
| 3 | Issue scoped InfluxDB tokens; stop using the admin token | §2.2 | S | ⬜ needs deployment change |
| 4 | `debug=False` in production | §2.3 | **S** | ✅ done |
| 5 | Restrict CORS; require `SECRET_KEY` | §2.4 | **S** | ✅ done |
| 6 | Wire up `electricity_price`, `collection_interval`, `refresh_interval` | §3.1 | S | ⬜ |
| 7 | Per-register `try/except` in the collector | §3.5 | **S** | ✅ done |

Items 2, 4, 5, and 7 are roughly 20 lines total and remove most of the risk.

### P1 — next (correctness & confidence)

| # | Item | Ref | Effort | Status |
|---|---|---|---|---|
| 8 | Add pytest + ruff + a CI workflow | §7 | M | ⬜ |
| 9 | Unit-test the four numerical functions | §7 | M | ⬜ |
| 10 | Fix the restart-button quoting bug | §3.3 | **S** | ✅ done |
| 11 | Provider metric-alias layer; fix NIBE names | §3.4 | M | ⬜ |
| 12 | Stop fabricating COP 3.5 | §3.8 | **S** | ✅ done |
| 13 | Return 400 on invalid settings | §3.9 | S | ⬜ |
| 14 | Make `scale`/`signed` authoritative; verify the `percentage` ÷10 behaviour | §3.6 | M | ⬜ |
| 15 | Fine-grained query for hot-water cycles | §3.7 | S | ⬜ |

### P2 — then (cleanup & performance)

| # | Item | Ref | Effort |
|---|---|---|---|
| 16 | Delete the 11 dead `app.py` functions and the duplicate Sankey/status bodies | §4.1 | S |
| 17 | Delete the Dash-era `callbacks.py` / `dashboard_components.py` | §4.2 | **S** | ✅ done |
| 18 | Group background updates by `time_range` | §5.2 | S |
| 19 | Delete the GreenPool, or move queries into it | §5.1 | S |
| 20 | Vectorise the runtime and hot-water loops | §5.3 | M |
| 21 | Vendor the CDN assets locally | §2.5 | S |
| 22 | Split `app.py` and `data_query.py`; make `providers` an installable package | §4.3, §4.4 | L |
| 23 | Timing logs → `debug`; stop shipping colours every update | §5.4, §5.5 | **S** |
| 24 | Compose cleanup: drop `version`, add `.env.example`, non-root user, health conditions | §8 | S |

**Suggested first commit** — items 2, 4, 5, 7, 10, 12, 17. All small, all independent, and together
they close the cheapest security holes, fix two user-visible bugs, and delete ~1 000 lines of dead
code.

---

## 11. Mitigation log

**2026-07-28 — suggested first commit applied** (items 2, 4, 5, 7, 10, 12, 17).

Constraints this pass: code-only (no `docker-compose.yml` or `Dockerfile` edits), LAN-only threat
model, Docker socket mount retained by decision.

| Item | What changed |
|---|---|
| 2 | `VALID_TIME_RANGES` + `validate_time_range()` in `data_query.py`. Enforced at the three client entry points (400 / socket `error`) **and** inside `query_metrics`, `query_metrics_wide`, `get_min_max_values` — outside their `try` blocks, which would otherwise swallow the rejection into an empty DataFrame. Both `_get_aggregation_window` helpers now raise instead of silently returning `"5m"`. |
| 4 | `debug` driven by `FLASK_DEBUG`, default `False`. `log_output=True` passed explicitly so HTTP access logs survive the change. |
| 5 | `CORS(app)` registered only when `CORS_ALLOWED_ORIGINS` is set; same-origin otherwise. Socket.IO mirrors it. `SECRET_KEY` falls back to a per-process random key, never a published constant — both known-published defaults are rejected. |
| 7 | Per-register `try/except` around `int(raw_value)` in the collector, with one summary `WARNING` per cycle. |
| 10 | Restart button built via `createElement` + `addEventListener`. Also: `needs_restart` now reports real service names (`collector`/`dashboard`) instead of `brand`, which was not in `RESTARTABLE_CONTAINERS` and 400'd; `restartService` no longer throws when its button is absent. |
| 12 | Measured COP is reported as-is or the payload reports `has_data: false`. Also closed a NaN hole (every comparison against NaN is false, so an all-NaN column previously passed through as real data) and clamped the ground-energy *flow* at 0 for COP < 1 while `cop` still carries the true value. |
| 17 | Six Dash-era files deleted (~1 056 lines); `MULTI_BRAND_README.md` updated to match. |

Deferred deliberately: item 1 (socket mount), item 3 (scoped InfluxDB tokens — needs a deployment
change), and everything else in P1/P2.

---

## Appendix — verification notes

Claims in this review were checked as follows:

- Dead-code claims: `grep -rn "\bNAME\b" --include=*.py .` returning exactly 1 hit (the `def` line).
- Settings wiring: traced each config key from `save_settings` to its consumer; `electricity_price`,
  `collection.interval_seconds`, and `dashboard.refresh_interval` have no reader.
- NIBE metric names: extracted all `'name':` values per provider and diffed against the metric lists
  in `app.py:489-496` and `app.py:520-527`.
- `scale` / `signed`: `grep -rn "scale\|signed" --include=*.py .` outside `registers.py` → no hits.
- CDN/SRI: no `integrity=` attribute in any template.
- Tests/CI: no `tests/`, no `.github/`, no lint or format config in the tree.

Two items are marked **verify against your live gateway** rather than asserted, because they depend
on what the H66 actually returns: the `percentage` ÷10 behaviour (§3.6) and the frequency of
unsigned-wraparound sentinel values outside the COP path. `/api/debug/all-metrics` answers both in
about a minute.
