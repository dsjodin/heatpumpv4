/**
 * WebSocket Client for Heat Pump Dashboard
 * Two-view design: Monitor (real-time) and Analys (charts)
 */

// Global state
let currentTimeRange = '24h';
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
    loadInitialData(currentTimeRange);
    loadVersionInfo();
});

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
    console.log('📊 Received graph update');
    latestData = data;
    updateAllUI(data);
});

socket.on('error', (data) => {
    console.error('❌ Server error:', data.message);
});

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

    // Update schema overlays
    updateSchemaTemps(data);

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

    // Update last update time
    updateLastUpdateTime();
}

// ==================== View Switching ====================

function switchView(viewName) {
    currentView = viewName;

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

    // Energy and cost
    if (data.kpi && data.kpi.energy) {
        const energy = data.kpi.energy;
        if (energy.total_kwh !== undefined) {
            setValue('panel-energy-today', energy.total_kwh, ' kWh');
        }
        if (energy.total_cost !== undefined) {
            setValue('panel-cost-today', energy.total_cost, ' kr');
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

// ==================== Schema Overlay Updates ====================

function updateSchemaTemps(data) {
    if (!data.status || !data.status.current) return;
    const current = data.status.current;

    const schemaContainer = document.getElementById('schema-container');
    const brand = schemaContainer ? schemaContainer.dataset.brand : 'thermia';

    function setOverlayActive(elementId, isActive) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.toggle('active', isActive);
        }
    }

    // Temperature text displays
    const textOutdoor = document.getElementById('text-outdoor_temp');
    if (textOutdoor && current.outdoor_temp && current.outdoor_temp.current !== null) {
        textOutdoor.textContent = `${current.outdoor_temp.current.toFixed(1)}°C`;
    }

    const textHotgas = document.getElementById('text-hotgas_temp');
    if (textHotgas) {
        if (current.hotgas_temp !== undefined && current.hotgas_temp !== null) {
            textHotgas.textContent = `${current.hotgas_temp.toFixed(1)}°C`;
        } else if (current.pressure_tube_temp !== undefined && current.pressure_tube_temp !== null) {
            textHotgas.textContent = `${current.pressure_tube_temp.toFixed(1)}°C`;
        }
    }

    const textIntegral = document.getElementById('text-integral_value');
    if (textIntegral) {
        if (current.integral_value !== undefined && current.integral_value !== null) {
            textIntegral.textContent = current.integral_value.toFixed(0);
        } else if (current.degree_minutes !== undefined && current.degree_minutes !== null) {
            textIntegral.textContent = current.degree_minutes.toFixed(0);
        }
    }

    const textKBIn = document.getElementById('text-KB_in_temp');
    if (textKBIn && current.brine_in && current.brine_in.current !== null) {
        textKBIn.textContent = `${current.brine_in.current.toFixed(1)}°C`;
    }

    const textKBOut = document.getElementById('text-KB_out_temp');
    if (textKBOut && current.brine_out && current.brine_out.current !== null) {
        textKBOut.textContent = `${current.brine_out.current.toFixed(1)}°C`;
    }

    const textHotwater = document.getElementById('text-hotwater_temp');
    if (textHotwater && current.hot_water && current.hot_water.current !== null) {
        textHotwater.textContent = `${current.hot_water.current.toFixed(1)}°C`;
    }

    const textRadForward = document.getElementById('text-radiator_forward_temp');
    if (textRadForward && current.radiator_forward && current.radiator_forward.current !== null) {
        textRadForward.textContent = `${current.radiator_forward.current.toFixed(1)}°C`;
    }

    const textRadReturn = document.getElementById('text-radiator_return_temp');
    if (textRadReturn && current.radiator_return && current.radiator_return.current !== null) {
        textRadReturn.textContent = `${current.radiator_return.current.toFixed(1)}°C`;
    }

    // Overlay animations
    setOverlayActive('overlay-BV_komp_anim', current.compressor_running === true);
    setOverlayActive('overlay-3kw_on', current.aux_heater === true);
    setOverlayActive('overlay-KB_snurr', current.brine_pump_running === true);
    setOverlayActive('overlay-RAD_snurr', current.radiator_pump_running === true);
    setOverlayActive('overlay-RAD_pil', current.switch_valve_status === 0);

    const showVVPil = current.switch_valve_status !== undefined &&
                      current.switch_valve_status !== null &&
                      current.switch_valve_status > 0;
    setOverlayActive('overlay-VV_pil', showVVPil);

    const showRadHot = current.switch_valve_status === 0 ||
                       (current.radiator_forward &&
                        current.radiator_forward.current !== null &&
                        current.radiator_forward.current > 32);
    setOverlayActive('overlay-RAD_hot', showRadHot);

    const showVVHot = current.switch_valve_status !== undefined &&
                      current.switch_valve_status !== null &&
                      current.switch_valve_status > 0;
    setOverlayActive('overlay-VV_hot', showVVHot);

    if (brand === 'ivt') {
        // VB-snurr (VVB pump) uses pump_heat_circuit status
        setOverlayActive('overlay-VB_snurr', current.vvb_pump_running === true);
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

function updateLastUpdateTime() {
    const el = document.getElementById('last-update');
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleTimeString('sv-SE');
    }
}

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

    // Time range change
    const timeRangeSelect = document.getElementById('time-range');
    if (timeRangeSelect) {
        timeRangeSelect.addEventListener('change', (e) => {
            currentTimeRange = e.target.value;
            console.log(`🔄 Time range: ${currentTimeRange}`);
            // Reset zoom state when time range changes
            if (window.resetZoomState) {
                window.resetZoomState();
            }
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
            if (connected) {
                socket.emit('request_update', { range: currentTimeRange });
            } else {
                loadInitialData(currentTimeRange);
            }
        });
    }

    // Price input change
    const priceInput = document.getElementById('price-input');
    if (priceInput) {
        priceInput.addEventListener('change', () => {
            console.log(`💰 Price: ${priceInput.value} kr/kWh`);
            if (connected) {
                socket.emit('request_update', { range: currentTimeRange, price: parseFloat(priceInput.value) });
            }
        });
    }

    // Chart selector change
    const chartSelector = document.getElementById('chart-selector');
    if (chartSelector) {
        chartSelector.addEventListener('change', (e) => {
            if (window.switchChart) {
                window.switchChart(e.target.value);
            }
        });
    }

    // Series toggles
    document.querySelectorAll('.series-toggle').forEach(toggle => {
        toggle.addEventListener('change', () => {
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
        document.getElementById('setting-electricity-price').value = settings.electricity_price || 2.0;
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
            alertEl.className = 'alert alert-success';
            alertEl.innerHTML = '<i class="fas fa-check me-2"></i>Inställningar sparade!';

            if (result.needs_restart && result.needs_restart.length > 0) {
                // Build the restart button as a real element with a real
                // listener. Interpolating JSON.stringify(...) into an onclick
                // attribute injected via innerHTML meant the first double quote
                // of ["collector"] terminated the attribute, so the handler
                // never ran.
                const services = result.needs_restart;

                const note = document.createElement('div');
                note.className = 'mt-2';
                note.appendChild(document.createTextNode('Ändringar kräver omstart av: '));

                const strong = document.createElement('strong');
                strong.textContent = services.join(', ');
                note.appendChild(strong);

                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn btn-warning btn-sm mt-2 d-block';
                btn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Starta om nu';
                btn.addEventListener('click', () => restartServices(services));

                alertEl.appendChild(note);
                alertEl.appendChild(btn);
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
    // The per-service button only exists on the settings panel; this is also
    // called from the post-save prompt, where it may not be rendered.
    const btn = document.getElementById(`btn-restart-${service}`);

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Startar om...';
    }

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
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Starta om';
        }
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
