/**
 * Mobile WebSocket Client for Heat Pump Dashboard
 * Simplified real-time communication for mobile devices
 */

// Global state
let currentTimeRange = '24h';
let connected = false;

// Connect to WebSocket server
console.log('Initializing Mobile Socket.IO client...');
const socket = io(window.location.origin, {
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10,
    timeout: 10000
});

// ==================== Connection Event Handlers ====================

socket.on('connect', () => {
    console.log('Mobile WebSocket connected');
    connected = true;
    updateConnectionStatus(true);
    loadInitialData(currentTimeRange);
});

socket.on('disconnect', () => {
    console.log('Mobile WebSocket disconnected');
    connected = false;
    updateConnectionStatus(false);
});

socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    updateConnectionStatus(false);
});

// ==================== Data Update Handlers ====================

socket.on('graph_update', (data) => {
    console.log('Mobile received update');
    updateMobileUI(data);
    updateLastUpdateTime();
    hideRefreshIndicator();
});

socket.on('error', (data) => {
    console.error('Server error:', data.message);
    hideRefreshIndicator();
});

// ==================== HTTP Data Loading ====================

async function loadInitialData(timeRange) {
    showRefreshIndicator();
    try {
        const response = await fetch(`/api/initial-data?range=${timeRange}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Mobile initial data loaded');
        updateMobileUI(data);
        updateLastUpdateTime();
    } catch (error) {
        console.error('Failed to load initial data:', error);
    }
    hideRefreshIndicator();
}

// ==================== UI Update Functions ====================

function updateConnectionStatus(isConnected) {
    const dot = document.getElementById('connection-dot');
    if (isConnected) {
        dot.classList.add('connected');
    } else {
        dot.classList.remove('connected');
    }
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('last-update-time').textContent = timeString;
}

function showRefreshIndicator() {
    document.getElementById('refresh-indicator').classList.add('refreshing');
}

function hideRefreshIndicator() {
    document.getElementById('refresh-indicator').classList.remove('refreshing');
}

function updateMobileUI(data) {
    if (!data) return;

    // Update main stats from status.current
    if (data.status && data.status.current) {
        const current = data.status.current;

        // Main temperatures
        if (current.outdoor_temp && current.outdoor_temp.current !== null) {
            document.getElementById('mobile-outdoor').textContent =
                current.outdoor_temp.current.toFixed(1) + '°';
        }
        if (current.indoor_temp && current.indoor_temp.current !== null) {
            document.getElementById('mobile-indoor').textContent =
                current.indoor_temp.current.toFixed(1) + '°';
        }
        if (current.hot_water && current.hot_water.current !== null) {
            document.getElementById('mobile-hotwater').textContent =
                current.hot_water.current.toFixed(0) + '°';
        }

        // COP
        if (current.current_cop !== null && current.current_cop !== undefined && !isNaN(current.current_cop)) {
            document.getElementById('mobile-cop').textContent = current.current_cop.toFixed(2);
        }

        // Power
        if (current.power !== null) {
            document.getElementById('mobile-power').textContent = current.power + 'W';
        }

        // Secondary temperatures
        if (current.brine_in && current.brine_in.current !== null) {
            document.getElementById('mobile-brine-in').textContent =
                current.brine_in.current.toFixed(1) + '°';
        }
        if (current.brine_out && current.brine_out.current !== null) {
            document.getElementById('mobile-brine-out').textContent =
                current.brine_out.current.toFixed(1) + '°';
        }
        if (current.radiator_forward && current.radiator_forward.current !== null) {
            document.getElementById('mobile-rad-forward').textContent =
                current.radiator_forward.current.toFixed(1) + '°';
        }
        if (current.radiator_return && current.radiator_return.current !== null) {
            document.getElementById('mobile-rad-return').textContent =
                current.radiator_return.current.toFixed(1) + '°';
        }

        // Status badges
        updateStatusBadge('mobile-status-compressor', 'mobile-comp-status', current.compressor_running, 'PÅ', 'AV');
        updateStatusBadge('mobile-status-brine', 'mobile-brine-status', current.brine_pump_running, 'PÅ', 'AV');
        updateStatusBadge('mobile-status-radiator', 'mobile-rad-status', current.radiator_pump_running, 'PÅ', 'AV');
        updateStatusBadge('mobile-status-aux', 'mobile-aux-status', current.aux_heater, 'PÅ', 'AV');

        // Valve status
        const valveBadge = document.getElementById('mobile-status-valve');
        const valveStatus = document.getElementById('mobile-valve-status');
        if (current.switch_valve_status !== undefined) {
            valveBadge.classList.remove('status-off');
            valveBadge.classList.add('status-on');
            valveStatus.textContent = current.switch_valve_status === 0 ? 'RAD' : 'VV';
        } else {
            valveBadge.classList.remove('status-on');
            valveBadge.classList.add('status-off');
            valveStatus.textContent = '--';
        }
    }

    // Alarm status
    if (data.status && data.status.alarm) {
        updateAlarmCard(data.status.alarm);
    }

    // KPIs
    if (data.kpi) {
        // Energy
        if (data.kpi.energy) {
            const energy = data.kpi.energy;
            document.getElementById('mobile-kpi-energy').textContent =
                energy.total_kwh ? energy.total_kwh.toFixed(1) + ' kWh' : '--';
            document.getElementById('mobile-kpi-energy-cost').textContent =
                energy.total_cost ? energy.total_cost.toFixed(0) + ' kr' : '-- kr';
        }

        // Runtime
        if (data.kpi.runtime) {
            const runtime = data.kpi.runtime;
            document.getElementById('mobile-kpi-runtime').textContent =
                runtime.compressor_percent !== undefined ? runtime.compressor_percent.toFixed(0) + '%' : '--%';
            document.getElementById('mobile-kpi-runtime-hours').textContent =
                runtime.compressor_hours !== undefined ? runtime.compressor_hours.toFixed(1) + ' tim' : '-- tim';

            document.getElementById('mobile-kpi-aux').textContent =
                runtime.aux_heater_percent !== undefined ? runtime.aux_heater_percent.toFixed(0) + '%' : '--%';
            document.getElementById('mobile-kpi-aux-hours').textContent =
                runtime.aux_heater_hours !== undefined ? runtime.aux_heater_hours.toFixed(1) + ' tim' : '-- tim';
        }

        // Hot water
        if (data.kpi.hot_water) {
            const hw = data.kpi.hot_water;
            document.getElementById('mobile-kpi-hw-cycles').textContent =
                hw.total_cycles !== undefined ? hw.total_cycles : '--';
            document.getElementById('mobile-kpi-hw-per-day').textContent =
                hw.cycles_per_day !== undefined ? hw.cycles_per_day.toFixed(1) + '/dag' : '--/dag';
        }
    }
}

function updateStatusBadge(badgeId, statusId, isOn, onText, offText) {
    const badge = document.getElementById(badgeId);
    const status = document.getElementById(statusId);

    if (isOn) {
        badge.classList.remove('status-off');
        badge.classList.add('status-on');
        status.textContent = onText;
    } else {
        badge.classList.remove('status-on');
        badge.classList.add('status-off');
        status.textContent = offText;
    }
}

function updateAlarmCard(alarm) {
    const card = document.getElementById('mobile-alarm-card');
    const icon = card.querySelector('.alarm-icon i');
    const title = document.getElementById('mobile-alarm-title');
    const desc = document.getElementById('mobile-alarm-desc');

    const alarmBadge = document.getElementById('mobile-status-alarm');
    const alarmStatus = document.getElementById('mobile-alarm-status');

    if (alarm.is_active) {
        card.classList.remove('alarm-ok');
        card.classList.add('alarm-active');
        icon.className = 'fas fa-exclamation-circle';
        title.textContent = 'LARM AKTIVT!';
        desc.textContent = alarm.description || `Kod: ${alarm.code || 'Okänd'}`;

        alarmBadge.classList.remove('status-off');
        alarmBadge.classList.add('status-alarm');
        alarmStatus.textContent = 'AKTIVT';
    } else {
        card.classList.remove('alarm-active');
        card.classList.add('alarm-ok');
        icon.className = 'fas fa-check-circle';
        title.textContent = 'Inget larm';
        desc.textContent = 'Systemet fungerar normalt';

        alarmBadge.classList.remove('status-alarm');
        alarmBadge.classList.add('status-off');
        alarmStatus.textContent = 'OK';
    }
}

// ==================== Time Range Selection ====================

document.addEventListener('DOMContentLoaded', () => {
    // Time range buttons
    const timeButtons = document.querySelectorAll('.time-btn');

    timeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            timeButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update time range and fetch new data
            currentTimeRange = btn.dataset.range;
            console.log(`Time range changed to: ${currentTimeRange}`);

            if (connected) {
                showRefreshIndicator();
                socket.emit('change_time_range', { range: currentTimeRange });
            } else {
                loadInitialData(currentTimeRange);
            }
        });
    });

    // Pull to refresh (simple tap on header)
    const header = document.querySelector('.mobile-header');
    header.addEventListener('click', () => {
        if (connected) {
            showRefreshIndicator();
            socket.emit('request_update', { range: currentTimeRange });
        } else {
            loadInitialData(currentTimeRange);
        }
    });
});

console.log('Mobile client initialized');
