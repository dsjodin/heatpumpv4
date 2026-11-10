/**
 * WebSocket Client for Heat Pump Dashboard
 * Two-view design: Monitor (real-time) and Analys (charts)
 */

// Per-browser preferences (selected view, range, chart); storage may be unavailable
const prefs = {
    get(key, fallback) {
        try { const v = localStorage.getItem('hp.' + key); return v === null ? fallback : JSON.parse(v); }
        catch (e) { return fallback; }
    },
    set(key, value) {
        try { localStorage.setItem('hp.' + key, JSON.stringify(value)); } catch (e) { /* ignore */ }
    }
};
window.prefs = prefs;

// Global state
const TIME_RANGES = ['1h', '6h', '24h', '7d', '30d'];
let currentTimeRange = TIME_RANGES.includes(prefs.get('timeRange')) ? prefs.get('timeRange') : '24h';
let currentView = 'monitor';
let connected = false;
let latestData = null;

// Connect to WebSocket server
console.log('Initializing Socket.IO client...');
const socket = io(window.location.origin, {
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10,
    timeout: 10000
});

// ==================== Connection Event Handlers ====================

socket.on('connect', () => {
    console.log('✅ WebSocket connected');
    connected = true;
    updateConnectionStatus(true);
    // Initial data is loaded over HTTP at page load; after a reconnect ask for fresh data
    if (hasConnected) socket.emit('request_update', { range: currentTimeRange });
    hasConnected = true;
    loadVersionInfo();
});

// Don't wait for the WebSocket handshake: start loading as soon as all scripts have run
let hasConnected = false;
document.addEventListener('DOMContentLoaded', () => loadInitialData(currentTimeRange));

socket.on('disconnect', () => {
    console.log('❌ WebSocket disconnected');
    connected = false;
    updateConnectionStatus(false);
});

socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    updateConnectionStatus(false);
});

// ==================== Data Update Handlers ====================

socket.on('graph_update', (data) => {
    // Background push for a range the user just left: ignore
    if (data.time_range && data.time_range !== currentTimeRange) return;
    console.log('📊 Received graph update');
    latestData = data;
    updateAllUI(data);
    setLoading(false);
});

socket.on('error', (data) => {
    console.error('❌ Server error:', data.message);
    setLoading(false);
});

// Spinner next to the time range selector + overlay on the chart while loading
let loadingTimer = null;
function setLoading(on) {
    const select = document.getElementById('time-range');
    const spinner = document.getElementById('range-loading');
    if (select) select.disabled = on;
    if (spinner) spinner.classList.toggle('d-none', !on);
    if (window.setChartLoading) window.setChartLoading(on);
    clearTimeout(loadingTimer);
    if (on) loadingTimer = setTimeout(() => setLoading(false), 60000);  // never spin forever
}

// ==================== HTTP Data Loading ====================

async function loadInitialData(timeRange) {
    try {
        console.log(`📥 Loading initial data for range: ${timeRange}`);
        const response = await fetch(`/api/initial-data?range=${timeRange}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        console.log('✅ Initial data loaded');
        latestData = data;
        updateAllUI(data);

    } catch (error) {
        console.error('❌ Failed to load initial data:', error);
    } finally {
        setLoading(false);
    }
}

async function loadVersionInfo() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const config = await response.json();
        const versionEl = document.getElementById('version-info');
        if (versionEl && config.version) {
            versionEl.textContent = `v${config.version}`;
            versionEl.title = `Version: ${config.version}\nBuilt: ${config.build_time || 'unknown'}`;
        }
    } catch (error) {
        console.error('Failed to load version info:', error);
    }
}

// ==================== Main UI Update Function ====================

function updateAllUI(data) {
    // Update status bar (visible in both views)
    updateStatusPills(data);

    // Update Monitor view panels
    updateMonitorPanels(data);

    // Update live schema
    if (window.updateSchema && data.status) {
        window.updateSchema(data.status.latest);
    }

    // Update event log
    if (data.events) {
        updateEventLog(data.events);
    }

    // Update Analys view (charts)
    if (window.updateMainChart) {
        window.updateMainChart(data);
    }
    if (window.updateAnalysStats) {
        window.updateAnalysStats(data);
    }

    // Time of the newest sample, and warning if it is old
    if (data.status) {
        dataTime = data.status.data_time ? new Date(data.status.data_time) : null;
        staleAfterSeconds = data.status.stale_after_seconds || 120;
    }
    updateLastUpdateTime();
}

// ==================== View Switching ====================

function switchView(viewName) {
    if (!document.getElementById(`view-${viewName}`)) viewName = 'monitor';
    currentView = viewName;
    prefs.set('view', viewName);

    // Update tab styles
    document.querySelectorAll('.view-tabs .nav-link').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');

    // Show/hide views
    document.querySelectorAll('.view-content').forEach(view => {
        view.classList.remove('active');
        view.style.display = 'none';
    });

    const targetView = document.getElementById(`view-${viewName}`);
    if (targetView) {
        targetView.classList.add('active');
        targetView.style.display = 'block';
    }

    // Resize charts when switching to analys view
    if (viewName === 'analys' && window.resizeMainChart) {
        setTimeout(() => window.resizeMainChart(), 100);
    }

    // Load settings when switching to settings view
    if (viewName === 'settings') {
        loadSettings();
    }

    if (viewName === 'stats' && window.loadStats) {
        window.loadStats();
    }

    console.log(`📱 Switched to ${viewName} view`);
}

// ==================== Status Pills Update ====================

function updateStatusPills(data) {
    if (!data.status || !data.status.current) return;
    const current = data.status.current;

    // Helper to update pill
    function updatePill(pillId, textId, isOn, onText = 'PÅ', offText = 'AV') {
        const pill = document.getElementById(pillId);
        const text = document.getElementById(textId);
        if (pill && text) {
            pill.className = `badge status-pill ${isOn ? 'status-on' : 'status-off'}`;
            text.textContent = isOn ? onText : offText;
        }
    }

    updatePill('status-compressor', 'status-comp-text', current.compressor_running);
    updatePill('status-brine-pump', 'status-brine-text', current.brine_pump_running);
    updatePill('status-radiator-pump', 'status-rad-text', current.radiator_pump_running);
    updatePill('status-aux', 'status-aux-text', current.aux_heater);

    // VVB-pump status (IVT only)
    updatePill('status-vvb-pump', 'status-vvb-text', current.vvb_pump_running);

    // Valve status
    const valvePill = document.getElementById('status-valve');
    const valveText = document.getElementById('status-valve-text');
    if (valvePill && valveText) {
        valvePill.className = 'badge status-pill status-on';
        valveText.textContent = current.switch_valve_status === 0 ? 'Radiator' : 'VV';
    }

    // Alarm status
    const alarmPill = document.getElementById('status-alarm-badge');
    const alarmText = document.getElementById('status-alarm-text');
    if (alarmPill && alarmText) {
        const hasAlarm = data.status.alarm && data.status.alarm.is_active;
        alarmPill.className = `badge status-pill ${hasAlarm ? 'status-alarm' : 'status-off'}`;
        alarmText.textContent = hasAlarm ? 'AKTIVT!' : 'OK';
    }
}

// ==================== Monitor View Panels ====================

function updateMonitorPanels(data) {
    if (!data.status || !data.status.current) return;
    const current = data.status.current;

    // Helper for safe value display
    function setValue(id, value, suffix = '', decimals = 1) {
        const el = document.getElementById(id);
        if (el && value !== null && value !== undefined) {
            el.textContent = typeof value === 'number' ? value.toFixed(decimals) + suffix : value + suffix;
        }
    }

    // Helper for setting min/max/avg
    function setMinMaxAvg(prefix, data) {
        if (!data) return;
        const minEl = document.getElementById(`${prefix}-min`);
        const avgEl = document.getElementById(`${prefix}-avg`);
        const maxEl = document.getElementById(`${prefix}-max`);
        if (minEl && data.min !== null && data.min !== undefined) {
            minEl.textContent = data.min.toFixed(1);
        }
        if (avgEl && data.avg !== null && data.avg !== undefined) {
            avgEl.textContent = data.avg.toFixed(1);
        }
        if (maxEl && data.max !== null && data.max !== undefined) {
            maxEl.textContent = data.max.toFixed(1);
        }
    }

    // Simple temperature values
    if (current.outdoor_temp) setValue('panel-outdoor-temp', current.outdoor_temp.current, '°C');
    if (current.indoor_temp) setValue('panel-indoor-temp', current.indoor_temp.current, '°C');

    // Radiator forward with min/max/avg
    if (current.radiator_forward) {
        setValue('panel-radiator-forward', current.radiator_forward.current, '°C');
        setMinMaxAvg('panel-rad-fwd', current.radiator_forward);
    }

    // Radiator return with min/max/avg
    if (current.radiator_return) {
        setValue('panel-radiator-return', current.radiator_return.current, '°C');
        setMinMaxAvg('panel-rad-ret', current.radiator_return);
    }

    // Brine in with min/max/avg
    if (current.brine_in) {
        setValue('panel-brine-in', current.brine_in.current, '°C');
        setMinMaxAvg('panel-brine-in', current.brine_in);
    }

    // Brine out with min/max/avg
    if (current.brine_out) {
        setValue('panel-brine-out', current.brine_out.current, '°C');
        setMinMaxAvg('panel-brine-out', current.brine_out);
    }

    // Hot water with min/max/avg
    if (current.hot_water) {
        setValue('panel-hotwater', current.hot_water.current, '°C');
        setMinMaxAvg('panel-hw', current.hot_water);
    }

    // Hetgas (pressure_tube_temp)
    if (current.hotgas_temp !== undefined) {
        setValue('panel-hotgas', current.hotgas_temp, '°C');
    } else if (current.pressure_tube_temp !== undefined) {
        setValue('panel-hotgas', current.pressure_tube_temp, '°C');
    }

    // Integral (degree_minutes)
    if (current.integral_value !== undefined) {
        setValue('panel-integral', current.integral_value, '', 0);
    } else if (current.degree_minutes !== undefined) {
        setValue('panel-integral', current.degree_minutes, '', 0);
    }

    // Performance panel
    setValue('panel-power', current.power, ' W', 0);
    if (current.current_cop !== null && current.current_cop !== undefined && !isNaN(current.current_cop)) {
        setValue('panel-cop', current.current_cop, '', 2);
    }

    // Runtime percentages
    if (data.kpi && data.kpi.runtime) {
        const runtime = data.kpi.runtime;
        // Backend sends compressor_percent, not compressor_runtime_percent
        if (runtime.compressor_percent !== undefined) {
            setValue('panel-comp-runtime', runtime.compressor_percent, '%');
        }
        if (runtime.compressor_starts !== undefined) {
            setValue('panel-comp-starts', runtime.compressor_starts, '', 0);
        }
        if (runtime.aux_heater_percent !== undefined) {
            setValue('panel-aux-runtime', runtime.aux_heater_percent, '%');
        }
    }

    // Energy and cost since local midnight
    if (data.today) {
        if (data.today.energy_kwh !== undefined) {
            setValue('panel-energy-today', data.today.energy_kwh, ' kWh');
        }
        if (data.today.cost_kr !== undefined) {
            setValue('panel-cost-today', data.today.cost_kr, ' kr');
        }
    }

    // Hot water stats
    if (data.kpi && data.kpi.hot_water) {
        const hw = data.kpi.hot_water;
        setValue('panel-hw-cycles', hw.total_cycles, '', 0);
        setValue('panel-hw-per-day', hw.cycles_per_day, '/dag');
        setValue('panel-hw-duration', hw.avg_duration_minutes, ' min', 0);
    }
}

// ==================== Event Log ====================

function updateEventLog(events) {
    const eventLog = document.getElementById('event-log');
    if (!eventLog) return;

    if (!events || events.length === 0) {
        eventLog.innerHTML = '<div class="text-center text-muted p-3">Inga händelser</div>';
        return;
    }

    let html = '';
    events.slice(0, 10).forEach(event => {
        let eventTime = '';
        try {
            if (event.time) {
                const date = new Date(event.time);
                eventTime = date.toLocaleString('sv-SE', {
                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                });
            }
        } catch (e) {}

        // Style based on event type
        let textClass = '';
        if (event.type === 'danger') textClass = 'text-danger fw-bold';
        else if (event.type === 'warning') textClass = 'text-warning';
        else if (event.type === 'success') textClass = 'text-success';

        // Backend sends 'event' field, not 'description'
        const eventText = event.event || event.description || '';

        html += `
            <div class="event-item small py-1 border-bottom">
                <span class="text-muted">${eventTime}</span>
                <span class="ms-2 ${textClass}">${event.icon || ''} ${eventText}</span>
            </div>
        `;
    });

    eventLog.innerHTML = html;
}

// ==================== UI Helpers ====================

function updateConnectionStatus(isConnected) {
    const badge = document.getElementById('connection-status');
    if (badge) {
        badge.className = `badge connection-badge ${isConnected ? 'connected' : 'disconnected'}`;
        badge.textContent = isConnected ? 'Ansluten' : 'Frånkopplad';
    }
}

let dataTime = null;
let staleAfterSeconds = 120;

function formatAge(seconds) {
    if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
    if (seconds < 172800) return `${Math.round(seconds / 3600)} h`;
    return `${Math.round(seconds / 86400)} dagar`;
}

// Shows the time of the newest sample; re-evaluated on a timer so it turns red without new pushes
function updateLastUpdateTime() {
    const el = document.getElementById('last-update');
    const banner = document.getElementById('stale-banner');
    const schema = document.getElementById('schema-container');
    if (!el || latestData === null) return;

    const ageSeconds = dataTime ? (Date.now() - dataTime.getTime()) / 1000 : Infinity;
    const stale = ageSeconds > staleAfterSeconds;
    const sameDay = dataTime && dataTime.toDateString() === new Date().toDateString();
    const when = !dataTime ? 'över 30 dagar'
        : sameDay ? dataTime.toLocaleTimeString('sv-SE')
        : dataTime.toLocaleString('sv-SE', { dateStyle: 'short', timeStyle: 'short' });

    el.textContent = stale ? `Ingen ny data (${dataTime ? formatAge(ageSeconds) : when})` : `Data ${when}`;
    el.classList.toggle('stale-text', stale);
    if (banner) {
        banner.classList.toggle('d-none', !stale);
        document.getElementById('stale-since').textContent = dataTime ? `${when} (${formatAge(ageSeconds)})` : when;
    }
    if (schema) schema.classList.toggle('schema-stale', stale);
}
setInterval(updateLastUpdateTime, 15000);

// ==================== Event Listeners ====================

document.addEventListener('DOMContentLoaded', () => {
    // View tab switching
    document.querySelectorAll('.view-tabs .nav-link').forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const view = e.target.closest('.nav-link').dataset.view;
            if (view) switchView(view);
        });
    });

    // Restore saved selections
    switchView(prefs.get('view', 'monitor'));
    const savedChart = prefs.get('chartType', 'temperature');
    const chartSelect = document.getElementById('chart-selector');
    if (chartSelect && [...chartSelect.options].some(o => o.value === savedChart)) {
        chartSelect.value = savedChart;
        if (window.switchChart) window.switchChart(savedChart);
    }
    const savedSeries = prefs.get('series', {});
    document.querySelectorAll('.series-toggle').forEach(t => {
        if (t.id in savedSeries) t.checked = savedSeries[t.id];
    });

    // Restart collector from the stale data banner
    const staleRestart = document.getElementById('btn-stale-restart');
    if (staleRestart) {
        staleRestart.addEventListener('click', async () => {
            const result = document.getElementById('stale-restart-result');
            staleRestart.disabled = true;
            result.textContent = 'Startar om...';
            try {
                const response = await fetch('/api/restart-service', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service: 'collector' })
                });
                result.textContent = (await response.json()).message || '';
            } catch (error) {
                result.textContent = `Fel: ${error.message}`;
            } finally {
                staleRestart.disabled = false;
            }
        });
    }

    // Time range change
    const timeRangeSelect = document.getElementById('time-range');
    if (timeRangeSelect) {
        timeRangeSelect.value = currentTimeRange;
        timeRangeSelect.addEventListener('change', (e) => {
            currentTimeRange = e.target.value;
            prefs.set('timeRange', currentTimeRange);
            console.log(`🔄 Time range: ${currentTimeRange}`);
            // Reset zoom state when time range changes
            if (window.resetZoomState) {
                window.resetZoomState();
            }
            setLoading(true);
            if (connected) {
                socket.emit('change_time_range', { range: currentTimeRange });
            } else {
                loadInitialData(currentTimeRange);
            }
        });
    }

    // Refresh button
    const refreshButton = document.getElementById('btn-refresh');
    if (refreshButton) {
        refreshButton.addEventListener('click', () => {
            console.log('🔄 Manual refresh');
            setLoading(true);
            if (connected) {
                socket.emit('request_update', { range: currentTimeRange });
            } else {
                loadInitialData(currentTimeRange);
            }
        });
    }

    // Chart selector change
    const chartSelector = document.getElementById('chart-selector');
    if (chartSelector) {
        chartSelector.addEventListener('change', (e) => {
            prefs.set('chartType', e.target.value);
            if (window.switchChart) {
                window.switchChart(e.target.value);
            }
        });
    }

    // Series toggles
    document.querySelectorAll('.series-toggle').forEach(toggle => {
        toggle.addEventListener('change', () => {
            const series = prefs.get('series', {});
            series[toggle.id] = toggle.checked;
            prefs.set('series', series);
            if (window.updateSeriesVisibility) {
                window.updateSeriesVisibility();
            }
        });
    });

    // Overlay toggles
    document.querySelectorAll('.overlay-toggle').forEach(toggle => {
        toggle.addEventListener('change', () => {
            if (window.updateChartOverlays) {
                window.updateChartOverlays();
            }
        });
    });
});

// ==================== Settings Functions ====================

async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const settings = await response.json();

        // Populate form fields
        document.getElementById('setting-brand').value = settings.brand || 'thermia';
        document.getElementById('setting-flow-factor').value = settings.cop_flow_factor || 2.7;
        document.getElementById('setting-hw-min-cycle').value = settings.hw_min_cycle_minutes || 2;
        document.getElementById('setting-electricity-price').value = settings.electricity_price ?? 2.0;
        document.getElementById('setting-price-mode').value = settings.price_mode || 'fixed';
        document.getElementById('setting-price-area').value = settings.price_area || 'SE3';
        document.getElementById('setting-price-markup').value = settings.price_markup ?? 0;
        document.getElementById('setting-price-vat').checked = settings.price_vat !== false;
        updatePriceModeFields();
        document.getElementById('setting-collection-interval').value = settings.collection_interval || 30;
        document.getElementById('setting-refresh-interval').value = settings.dashboard_refresh_interval || 30;
        document.getElementById('setting-retention-days').value = settings.retention_days || 90;

        // System info
        const sys = settings.system || {};
        document.getElementById('settings-dashboard-version').textContent = sys.dashboard_version || '--';
        document.getElementById('settings-build-time').textContent = sys.build_time || '--';

        const influx = sys.influxdb || {};
        const statusEl = document.getElementById('settings-influx-status');
        statusEl.textContent = influx.status || '--';
        statusEl.className = 'badge ' + (influx.status === 'pass' ? 'bg-success' : 'bg-danger');

        document.getElementById('settings-influx-version').textContent = influx.version || '--';

        // Current retention
        const retEl = document.getElementById('settings-current-retention');
        retEl.textContent = settings.current_retention_days > 0
            ? `${settings.current_retention_days} dagar`
            : 'Obegränsad';

        console.log('Settings loaded');
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

function updatePriceModeFields() {
    const spot = document.getElementById('setting-price-mode').value === 'spot';
    document.querySelectorAll('.spot-only').forEach(el => el.classList.toggle('d-none', !spot));
}
document.addEventListener('DOMContentLoaded', () => {
    const mode = document.getElementById('setting-price-mode');
    if (mode) mode.addEventListener('change', updatePriceModeFields);
});

async function saveSettings() {
    const btn = document.getElementById('btn-save-settings');
    const alertEl = document.getElementById('settings-alert');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Sparar...';

    try {
        const payload = {
            brand: document.getElementById('setting-brand').value,
            cop_flow_factor: parseFloat(document.getElementById('setting-flow-factor').value),
            hw_min_cycle_minutes: parseInt(document.getElementById('setting-hw-min-cycle').value),
            electricity_price: parseFloat(document.getElementById('setting-electricity-price').value),
            price_mode: document.getElementById('setting-price-mode').value,
            price_area: document.getElementById('setting-price-area').value,
            price_markup: parseFloat(document.getElementById('setting-price-markup').value),
            price_vat: document.getElementById('setting-price-vat').checked,
            collection_interval: parseInt(document.getElementById('setting-collection-interval').value),
            dashboard_refresh_interval: parseInt(document.getElementById('setting-refresh-interval').value),
            retention_days: parseInt(document.getElementById('setting-retention-days').value)
        };

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (result.success) {
            let msg = '<i class="fas fa-check me-2"></i>Inställningar sparade!';

            const needsRestart = result.needs_restart || [];
            if (needsRestart.length > 0) {
                msg += `<br><br>Ändringar kräver omstart av: <strong>${needsRestart.join(', ')}</strong><br>`;
            }

            alertEl.className = 'alert alert-success';
            alertEl.innerHTML = msg;
            if (needsRestart.length > 0) {
                const restartBtn = document.createElement('button');
                restartBtn.className = 'btn btn-warning btn-sm mt-2';
                restartBtn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Starta om nu';
                restartBtn.addEventListener('click', () => restartServices(needsRestart));
                alertEl.appendChild(restartBtn);
            }
            alertEl.classList.remove('d-none');

            // Reload settings to reflect actual state
            await loadSettings();
        } else {
            alertEl.className = 'alert alert-danger';
            alertEl.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>' + (result.message || 'Kunde inte spara');
            alertEl.classList.remove('d-none');
        }
    } catch (error) {
        alertEl.className = 'alert alert-danger';
        alertEl.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Fel: ' + error.message;
        alertEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save me-2"></i>Spara inställningar';

        // Auto-hide alert after 5 seconds
        setTimeout(() => {
            alertEl.classList.add('d-none');
        }, 5000);
    }
}

async function restartService(service) {
    const statusDiv = document.getElementById('restart-status');
    const statusAlert = document.getElementById('restart-status-alert');
    const btn = document.getElementById(`btn-restart-${service}`);

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Startar om...';

    statusDiv.classList.remove('d-none');
    statusAlert.className = 'alert alert-info mb-0 py-2';
    statusAlert.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>Startar om ${service}...`;

    try {
        const response = await fetch('/api/restart-service', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service })
        });
        const result = await response.json();

        if (result.success) {
            statusAlert.className = 'alert alert-success mb-0 py-2';
            statusAlert.innerHTML = `<i class="fas fa-check me-2"></i>${result.message}`;
        } else {
            statusAlert.className = 'alert alert-danger mb-0 py-2';
            statusAlert.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i>${result.message}`;
        }
    } catch (error) {
        statusAlert.className = 'alert alert-danger mb-0 py-2';
        statusAlert.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i>Fel: ${error.message}`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Starta om';
        setTimeout(() => statusDiv.classList.add('d-none'), 5000);
    }
}

async function restartServices(services) {
    for (const service of services) {
        await restartService(service);
    }
}

// Export for global access
window.dashboardSocket = socket;
window.switchView = switchView;
window.saveSettings = saveSettings;
window.restartService = restartService;
window.restartServices = restartServices;
window.latestData = () => latestData;

console.log('🚀 Socket client initialized (three-view design)');
