/**
 * Statistik view: daily/monthly energy and cost, energy signature and borehole trend
 * Data from /api/stats (long-term daily statistics)
 */

const STATS_COLORS = {
    energy: '#f39c12',
    cost: '#e74c3c',
    outdoor: '#5f27cd',
    brine_in: '#54a0ff',
    brine_out: '#00d2d3',
    older: '#adb5bd',
    recent: '#ff6b35',
    fit: '#2c3e50'
};

// lower: a decrease is good (green); null: no judgement
const STATS_KPIS = [
    { key: 'energy_kwh', label: 'Energi', unit: 'kWh', decimals: 0, lower: true },
    { key: 'cost_kr', label: 'Kostnad', unit: 'kr', decimals: 0, lower: true },
    { key: 'avg_price', label: 'Snittpris', unit: 'kr/kWh', decimals: 2, lower: true },
    { key: 'cop', label: 'COP', unit: '', decimals: 2, lower: false },
    { key: 'outdoor_mean', label: 'Ute medel', unit: '°C', decimals: 1, lower: null, delta: true },
    { key: 'starts_per_day', label: 'Starter/dygn', unit: '', decimals: 1, lower: true },
    { key: 'hw_cycles_per_day', label: 'VV-cykler/dygn', unit: '', decimals: 1, lower: null },
    { key: 'aux_hours', label: 'Tillsats', unit: 'h', decimals: 1, lower: true }
];

const statsCharts = {};
let statsRequest = 0;  // only the newest request is rendered

function statsChart(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    if (!statsCharts[id]) {
        statsCharts[id] = echarts.init(el);
        window.addEventListener('resize', () => statsCharts[id].resize());
    }
    return statsCharts[id];
}

function fmt(value, decimals) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    return Number(value).toLocaleString('sv-SE', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

async function loadStats() {
    const request = ++statsRequest;
    const group = document.getElementById('stats-group').value;
    const days = document.getElementById('stats-days').value;
    window.prefs.set('statsGroup', group);
    window.prefs.set('statsDays', days);
    Object.values(statsCharts).forEach(c => c.resize());  // may have been resized while hidden
    Object.values(statsCharts).forEach(c => c.showLoading('default', { text: 'Laddar...', color: '#ff6b35' }));
    try {
        const response = await fetch(`/api/stats?group=${group}&days=${days}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (request === statsRequest) renderStats(data, group, days);
    } catch (error) {
        console.error('Failed to load stats:', error);
        document.getElementById('stats-info').textContent = `Kunde inte hämta statistik: ${error.message}`;
    } finally {
        if (request === statsRequest) Object.values(statsCharts).forEach(c => c.hideLoading());
    }
}

function renderStats(data, group, days) {
    const empty = !data.rows || data.rows.length === 0;
    document.getElementById('stats-empty').classList.toggle('d-none', !empty);
    renderStatsKpis(data.totals, data.previous_totals, days);
    renderEnergyChart(data.rows || [], group);
    renderSignature(data.signature || { points: [], fit: null });
    renderBrine(data.brine || [], data.year_ago);
    renderStatsTable(data.rows || [], group);
}

function renderStatsKpis(totals, previous, days) {
    const container = document.getElementById('stats-kpis');
    if (!totals) {
        container.innerHTML = '';
        return;
    }
    // Only compare when the previous period is (almost) as long as the current one
    const comparable = previous && previous.days >= 0.8 * totals.days;
    const prevText = days === '0' ? '' : comparable ? 'mot perioden före' : 'ingen jämförelse';
    container.innerHTML = STATS_KPIS.map(k => {
        const value = totals[k.key];
        let change = '';
        if (comparable && value !== null && previous[k.key] !== null && previous[k.key] !== undefined) {
            const prev = previous[k.key];
            let text, diff;
            if (k.delta) {
                diff = value - prev;
                text = `${diff >= 0 ? '+' : ''}${fmt(diff, 1)} ${k.unit}`;
            } else if (prev !== 0) {
                diff = (value - prev) / Math.abs(prev) * 100;
                text = `${diff >= 0 ? '+' : ''}${fmt(diff, 0)}%`;
            }
            if (text) {
                const good = k.lower === null || Math.abs(diff) < 1 ? '' : (diff < 0) === k.lower ? 'change-good' : 'change-bad';
                change = `<div class="stats-change ${good}" title="Föregående: ${fmt(prev, k.decimals)} ${k.unit}">${text}</div>`;
            }
        }
        return `
            <div class="col-6 col-md-3 col-xl">
                <div class="stats-kpi">
                    <div class="stats-kpi-label">${k.label}</div>
                    <div class="stats-kpi-value">${fmt(value, k.decimals)} <small>${k.unit}</small></div>
                    ${change || `<div class="stats-change">${prevText}</div>`}
                </div>
            </div>`;
    }).join('');
}

function renderEnergyChart(rows, group) {
    const chart = statsChart('stats-energy-chart');
    if (!chart) return;
    const labels = rows.map(r => r.label);
    chart.setOption({
        tooltip: {
            trigger: 'axis',
            formatter: params => {
                const row = rows[params[0].dataIndex];
                const lines = [`<b>${row.label}</b>${group === 'month' ? ` (${row.days} dygn)` : ''}`];
                params.forEach(p => {
                    const unit = p.seriesName === 'Kostnad' ? 'kr' : p.seriesName === 'Ute' ? '°C' : 'kWh';
                    lines.push(`${p.marker}${p.seriesName}: ${fmt(Array.isArray(p.value) ? p.value[1] : p.value, unit === 'kWh' ? 1 : unit === 'kr' ? 0 : 1)} ${unit}`);
                });
                if (row.cop) lines.push(`COP: ${fmt(row.cop, 2)}`);
                if (row.coverage_pct < 80) lines.push(`<span style="color:#e74c3c">Ofullständig data (${fmt(row.coverage_pct, 0)}%)</span>`);
                return lines.join('<br>');
            }
        },
        legend: { data: ['Energi', 'Kostnad', 'Ute'], top: 0 },
        grid: { left: 50, right: 90, top: 35, bottom: 30 },
        xAxis: { type: 'category', data: labels, axisLabel: { formatter: v => group === 'day' ? v.slice(5) : v } },
        yAxis: [
            { type: 'value', name: 'kWh', position: 'left' },
            { type: 'value', name: 'kr', position: 'right', splitLine: { show: false } },
            { type: 'value', name: '°C', position: 'right', offset: 45, splitLine: { show: false } }
        ],
        series: [
            {
                name: 'Energi', type: 'bar', yAxisIndex: 0,
                data: rows.map(r => ({ value: r.energy_kwh, itemStyle: { opacity: r.coverage_pct < 80 ? 0.4 : 1 } })),
                itemStyle: { color: STATS_COLORS.energy }
            },
            {
                name: 'Kostnad', type: 'line', yAxisIndex: 1, data: rows.map(r => r.cost_kr),
                itemStyle: { color: STATS_COLORS.cost }, lineStyle: { width: 2 }, symbolSize: 4
            },
            {
                name: 'Ute', type: 'line', yAxisIndex: 2, data: rows.map(r => r.outdoor_mean),
                itemStyle: { color: STATS_COLORS.outdoor }, lineStyle: { width: 1.5, type: 'dashed' }, symbol: 'none'
            }
        ]
    }, true);
}

function renderSignature(sig) {
    const chart = statsChart('stats-signature-chart');
    const text = document.getElementById('signature-text');
    if (!chart) return;
    const fit = sig.fit;
    const n = sig.points.length;
    if (fit) {
        text.textContent = `Ca ${fmt(fit.kwh_per_degree, 1)} kWh mer per dygn för varje grad kallare ute. ` +
            `Värmebehovet upphör vid ca ${fmt(fit.balance_temp, 1)} °C. Baserat på ${n} dygn under 15 °C. ` +
            `Om de senaste dygnen ligger över linjen går det åt mer energi än vanligt för samma utetemperatur.`;
    } else {
        text.textContent = `Behöver minst 5 kompletta dygn med utetemperatur under 15 °C (har ${n}).`;
    }

    const series = [
        {
            name: 'Äldre', type: 'scatter', symbolSize: 7,
            data: sig.points.filter(p => !p.recent).map(p => [p.outdoor, p.energy_kwh, p.date]),
            itemStyle: { color: STATS_COLORS.older }
        },
        {
            name: 'Senaste 30 dygnen', type: 'scatter', symbolSize: 8,
            data: sig.points.filter(p => p.recent).map(p => [p.outdoor, p.energy_kwh, p.date]),
            itemStyle: { color: STATS_COLORS.recent }
        }
    ];
    if (fit && n) {
        const xs = sig.points.map(p => p.outdoor);
        const x0 = Math.min(...xs);
        const x1 = Math.min(Math.max(...xs), fit.balance_temp);
        series.push({
            name: 'Trend', type: 'line', symbol: 'none',
            data: [[x0, fit.slope * x0 + fit.intercept], [x1, fit.slope * x1 + fit.intercept]],
            lineStyle: { color: STATS_COLORS.fit, width: 1.5, type: 'dashed' }, itemStyle: { color: STATS_COLORS.fit }
        });
    }
    chart.setOption({
        tooltip: {
            trigger: 'item',
            formatter: p => p.seriesName === 'Trend' ? 'Trendlinje'
                : `${p.value[2]}<br>Ute: ${fmt(p.value[0], 1)} °C<br>Energi: ${fmt(p.value[1], 1)} kWh`
        },
        legend: { top: 0 },
        grid: { left: 50, right: 20, top: 35, bottom: 40 },
        xAxis: { type: 'value', name: 'Ute medel (°C)', nameLocation: 'middle', nameGap: 25, scale: true },
        yAxis: { type: 'value', name: 'kWh/dygn', min: 0 },
        series
    }, true);
}

function renderBrine(brine, yearAgo) {
    const chart = statsChart('stats-brine-chart');
    const text = document.getElementById('brine-text');
    if (!chart) return;

    const mins = brine.map(r => r.brine_in_min).filter(v => v !== null);
    const parts = [];
    if (mins.length) parts.push(`Lägsta köldbärare in hittills: ${fmt(Math.min(...mins), 1)} °C.`);
    if (yearAgo && yearAgo.current && yearAgo.previous) {
        parts.push(`Medel in ${yearAgo.month}: ${fmt(yearAgo.current.brine_in_mean, 1)} °C ` +
            `(${yearAgo.previous_month}: ${fmt(yearAgo.previous.brine_in_mean, 1)} °C, ` +
            `ute ${fmt(yearAgo.current.outdoor_mean, 1)} mot ${fmt(yearAgo.previous.outdoor_mean, 1)} °C).`);
    } else {
        parts.push('Jämförelse mot samma månad i fjol visas när det finns ett års historik.');
    }
    parts.push('En köldbärartemp som sjunker år från år vid samma utetemp tyder på att borrhålet kyls ur.');
    text.textContent = parts.join(' ');

    const line = (key, name, color, extra = {}) => ({
        name, type: 'line', symbol: 'none', connectNulls: false,
        data: brine.map(r => [r.date, r[key]]),
        itemStyle: { color }, lineStyle: Object.assign({ width: 2, color }, extra)
    });
    chart.setOption({
        tooltip: { trigger: 'axis', valueFormatter: v => `${fmt(v, 1)} °C` },
        legend: { top: 0 },
        grid: { left: 45, right: 45, top: 35, bottom: 55 },
        xAxis: { type: 'time' },
        yAxis: [
            { type: 'value', name: 'KB °C', scale: true },
            { type: 'value', name: 'Ute °C', scale: true, splitLine: { show: false } }
        ],
        dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 5 }],
        series: [
            line('brine_in_mean', 'KB in medel', STATS_COLORS.brine_in),
            line('brine_in_min', 'KB in min', STATS_COLORS.brine_in, { type: 'dotted', width: 1.5 }),
            line('brine_out_mean', 'KB ut medel', STATS_COLORS.brine_out),
            Object.assign(line('outdoor_mean', 'Ute', STATS_COLORS.older, { width: 1 }), { yAxisIndex: 1 })
        ]
    }, true);
}

function renderStatsTable(rows, group) {
    const body = document.getElementById('stats-table-body');
    body.innerHTML = rows.slice().reverse().map(r => {
        const partial = r.coverage_pct < 80;
        return `<tr class="${partial ? 'text-muted' : ''}" title="${partial ? `Ofullständig data (${fmt(r.coverage_pct, 0)}%)` : ''}">
            <td>${r.label}${group === 'month' ? ` <small>(${r.days} d)</small>` : ''}${partial ? ' *' : ''}</td>
            <td>${fmt(r.energy_kwh, 1)}</td><td>${fmt(r.cost_kr, 0)}</td><td>${fmt(r.cop, 2)}</td>
            <td>${fmt(r.outdoor_mean, 1)}</td><td>${fmt(r.brine_in_mean, 1)}</td>
            <td>${fmt(r.compressor_starts, 0)}</td><td>${fmt(r.hw_cycles, 0)}</td><td>${fmt(r.aux_hours, 1)}</td>
        </tr>`;
    }).join('');
}

// Scripts load at the end of <body>, so the controls exist already
(() => {
    const group = document.getElementById('stats-group');
    const days = document.getElementById('stats-days');
    if (!group || !days) return;
    group.value = window.prefs.get('statsGroup', 'day');
    days.value = window.prefs.get('statsDays', '30');
    if (!group.value) group.value = 'day';
    if (!days.value) days.value = '30';
    group.addEventListener('change', loadStats);
    days.addEventListener('change', loadStats);
})();

window.loadStats = loadStats;
