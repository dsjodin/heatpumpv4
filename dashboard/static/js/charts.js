/**
 * Charts for Heat Pump Dashboard - Analys View
 * Single main chart with overlay toggle support
 */

// Global state
let mainChart = null;
let currentChartType = 'temperature';
let chartData = null;
let savedZoomState = null;  // Preserve zoom between updates

// Chart colors
const COLORS = {
    radiator_forward: '#ff6b6b',
    radiator_return: '#feca57',
    heat_carrier_forward: '#ff6b6b',  // IVT - same color as radiator_forward
    heat_carrier_return: '#feca57',   // IVT - same color as radiator_return
    hot_water_top: '#ff9ff3',
    brine_in_evaporator: '#54a0ff',
    brine_out_condenser: '#00d2d3',
    outdoor_temp: '#5f27cd',
    pressure_tube_temp: '#2c3e50',  // Dark blue for Hetgas (Thermia)
    hot_gas_compressor: '#2c3e50',  // Dark blue for Hetgas (IVT)
    indoor_temp: '#10ac84',
    degree_minutes: '#636e72',  // Integral (Thermia only)
    radiator_delta: '#e67e22',  // Orange for radiator/heat carrier delta
    brine_delta: '#9b59b6',     // Purple for brine/köldbärare delta
    power: '#f39c12',
    cop: '#27ae60',
    compressor_overlay: 'rgba(52, 152, 219, 0.15)',  // Light blue
    valve_overlay: 'rgba(255, 152, 0, 0.2)',  // Soft orange
    aux_overlay: 'rgba(231, 76, 60, 0.2)'  // Soft red
};

// Series names in Swedish
const SERIES_NAMES = {
    radiator_forward: 'Fram',
    radiator_return: 'Retur',
    heat_carrier_forward: 'Fram',  // IVT
    heat_carrier_return: 'Retur',  // IVT
    hot_water_top: 'Varmvatten',
    brine_in_evaporator: 'KB In',
    brine_out_condenser: 'KB Ut',
    outdoor_temp: 'Ute',
    pressure_tube_temp: 'Hetgas',  // Thermia
    hot_gas_compressor: 'Hetgas',  // IVT
    indoor_temp: 'Inne',
    degree_minutes: 'Integral',  // Thermia only
    radiator_delta: 'Δ Radiator',
    brine_delta: 'Δ Köldbärare',
    power_consumption: 'Effekt',
    cop: 'COP'
};

// ==================== Initialize Chart ====================

function initMainChart() {
    const container = document.getElementById('main-chart');
    if (!container) return;

    mainChart = echarts.init(container);

    // Handle resize
    window.addEventListener('resize', () => {
        if (mainChart) mainChart.resize();
    });

    // Save zoom state when user zooms
    mainChart.on('datazoom', (params) => {
        const option = mainChart.getOption();
        if (option.dataZoom && option.dataZoom.length > 0) {
            savedZoomState = {
                start: option.dataZoom[0].start,
                end: option.dataZoom[0].end
            };
        }
    });

    console.log('📊 Main chart initialized');
}

// ==================== Update Chart ====================

function updateMainChart(data) {
    if (!mainChart) initMainChart();
    if (!data) return;

    chartData = data;

    switch (currentChartType) {
        case 'temperature':
            renderTemperatureChart(data);
            break;
        case 'power':
            renderPowerChart(data);
            break;
        case 'cop':
            renderCOPChart(data);
            break;
        case 'energy':
            renderEnergyChart(data);
            break;
        default:
            renderTemperatureChart(data);
    }
}

// ==================== Temperature Chart ====================

function renderTemperatureChart(data) {
    if (!data.temperature || !data.temperature.timestamps) return;

    const timestamps = data.temperature.timestamps;
    const series = [];

    // Get visible series from checkboxes
    const visibleSeries = getVisibleSeries();

    // Get brand from schema container
    const schemaContainer = document.getElementById('schema-container');
    const brand = schemaContainer ? schemaContainer.dataset.brand : 'thermia';

    // Temperature series - format as [[timestamp, value], ...] for time axis
    // For IVT: use heat_carrier_forward/return instead of radiator_forward/return
    const tempMetrics = [
        'hot_water_top', 'brine_in_evaporator', 'brine_out_condenser', 'outdoor_temp'
    ];

    tempMetrics.forEach(metric => {
        if (data.temperature[metric] && visibleSeries.includes(metric)) {
            const formattedData = timestamps.map((t, i) => [t, data.temperature[metric][i]]);
            series.push({
                name: SERIES_NAMES[metric] || metric,
                type: 'line',
                data: formattedData,
                smooth: true,
                symbol: 'none',
                yAxisIndex: 0,
                lineStyle: { width: 2, color: COLORS[metric] },
                itemStyle: { color: COLORS[metric] }
            });
        }
    });

    // Fram (forward) - IVT uses heat_carrier_forward, Thermia uses radiator_forward
    if (visibleSeries.includes('radiator_forward')) {
        const forwardData = data.temperature.heat_carrier_forward || data.temperature.radiator_forward;
        if (forwardData) {
            const formattedData = timestamps.map((t, i) => [t, forwardData[i]]);
            series.push({
                name: 'Fram',
                type: 'line',
                data: formattedData,
                smooth: true,
                symbol: 'none',
                yAxisIndex: 0,
                lineStyle: { width: 2, color: COLORS.radiator_forward },
                itemStyle: { color: COLORS.radiator_forward }
            });
        }
    }

    // Retur (return) - IVT uses heat_carrier_return, Thermia uses radiator_return
    if (visibleSeries.includes('radiator_return')) {
        const returnData = data.temperature.heat_carrier_return || data.temperature.radiator_return;
        if (returnData) {
            const formattedData = timestamps.map((t, i) => [t, returnData[i]]);
            series.push({
                name: 'Retur',
                type: 'line',
                data: formattedData,
                smooth: true,
                symbol: 'none',
                yAxisIndex: 0,
                lineStyle: { width: 2, color: COLORS.radiator_return },
                itemStyle: { color: COLORS.radiator_return }
            });
        }
    }

    // Add Hetgas series - Thermia uses pressure_tube_temp, IVT uses hot_gas_compressor
    // Both map to the same checkbox (pressure_tube_temp)
    if (visibleSeries.includes('pressure_tube_temp')) {
        const hetgasData = data.temperature.pressure_tube_temp || data.temperature.hot_gas_compressor;
        if (hetgasData) {
            const formattedData = timestamps.map((t, i) => [t, hetgasData[i]]);
            series.push({
                name: 'Hetgas',
                type: 'line',
                data: formattedData,
                smooth: true,
                symbol: 'none',
                yAxisIndex: 0,
                lineStyle: { width: 2, color: COLORS.pressure_tube_temp, type: 'dashed' },
                itemStyle: { color: COLORS.pressure_tube_temp }
            });
        }
    }

    // Add Integral (degree_minutes) for Thermia only - uses second Y-axis
    const hasIntegral = brand === 'thermia' && data.temperature.degree_minutes && visibleSeries.includes('degree_minutes');
    if (hasIntegral) {
        const formattedData = timestamps.map((t, i) => [t, data.temperature.degree_minutes[i]]);
        series.push({
            name: SERIES_NAMES.degree_minutes,
            type: 'line',
            data: formattedData,
            smooth: true,
            symbol: 'none',
            yAxisIndex: 1,  // Secondary Y-axis (Integral)
            lineStyle: { width: 2, color: COLORS.degree_minutes, type: 'dashed' },
            itemStyle: { color: COLORS.degree_minutes }
        });
    }

    // Add Radiator Delta (Δ Radiator) - works for both Thermia and IVT
    if (data.temperature.radiator_delta && visibleSeries.includes('radiator_delta')) {
        const formattedData = timestamps.map((t, i) => [t, data.temperature.radiator_delta[i]]);
        series.push({
            name: SERIES_NAMES.radiator_delta,
            type: 'line',
            data: formattedData,
            smooth: true,
            symbol: 'none',
            yAxisIndex: 0,
            lineStyle: { width: 2, color: COLORS.radiator_delta },
            itemStyle: { color: COLORS.radiator_delta }
        });
    }

    // Add Brine/Köldbärare Delta (Δ Köldbärare)
    if (data.temperature.brine_delta && visibleSeries.includes('brine_delta')) {
        const formattedData = timestamps.map((t, i) => [t, data.temperature.brine_delta[i]]);
        series.push({
            name: SERIES_NAMES.brine_delta,
            type: 'line',
            data: formattedData,
            smooth: true,
            symbol: 'none',
            yAxisIndex: 0,
            lineStyle: { width: 2, color: COLORS.brine_delta },
            itemStyle: { color: COLORS.brine_delta }
        });
    }

    // Add overlay bands (compressor, valve, aux)
    const markAreas = buildOverlayMarkAreas(data, timestamps);
    console.log(`📊 Temperature chart: ${series.length} series, ${markAreas.length} mark areas`);

    if (series.length > 0 && markAreas.length > 0) {
        series[0].markArea = {
            silent: true,
            data: markAreas
        };
        console.log(`📊 Applied ${markAreas.length} mark areas to first series`);
    } else {
        console.log(`📊 NOT applying mark areas: series=${series.length}, markAreas=${markAreas.length}`);
    }

    // Configure Y-axes
    const yAxisConfig = [{
        type: 'value',
        name: '°C',
        axisLabel: { formatter: '{value}°C' }
    }];

    // Add secondary Y-axis for Integral if needed
    if (hasIntegral) {
        yAxisConfig.push({
            type: 'value',
            name: 'Integral',
            position: 'right',
            axisLine: { lineStyle: { color: COLORS.degree_minutes } },
            axisLabel: { formatter: '{value}' }
        });
    }

    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                if (!params || params.length === 0) return '';
                const time = new Date(params[0].value[0]);
                let result = time.toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) + '<br/>';
                params.forEach(p => {
                    if (p.value && p.value[1] !== null && p.value[1] !== undefined) {
                        // Show Integral without unit, temperatures with °C
                        const unit = p.seriesName === 'Integral' ? '' : '°C';
                        const decimals = p.seriesName === 'Integral' ? 0 : 1;
                        result += `${p.marker} ${p.seriesName}: ${p.value[1].toFixed(decimals)}${unit}<br/>`;
                    }
                });
                return result;
            }
        },
        legend: {
            data: series.map(s => s.name),
            bottom: 0,
            type: 'scroll'
        },
        grid: {
            left: 50,
            right: hasIntegral ? 60 : 20,  // Extra space for secondary Y-axis
            top: 20,
            bottom: 80
        },
        xAxis: {
            type: 'time',
            axisLabel: {
                formatter: (value) => {
                    const d = new Date(value);
                    return d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
                }
            }
        },
        yAxis: yAxisConfig,
        series: series,
        dataZoom: [
            {
                type: 'inside',
                start: savedZoomState ? savedZoomState.start : 0,
                end: savedZoomState ? savedZoomState.end : 100
            },
            {
                type: 'slider',
                start: savedZoomState ? savedZoomState.start : 0,
                end: savedZoomState ? savedZoomState.end : 100,
                height: 30,
                bottom: 30,
                showDetail: true,
                labelFormatter: (value) => {
                    const d = new Date(value);
                    return d.toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                }
            }
        ]
    };

    mainChart.setOption(option, { notMerge: true, lazyUpdate: true });
    updateChartTitle('temperature');
}

// ==================== Power Chart ====================

function renderPowerChart(data) {
    if (!data.power || !data.power.power_consumption) return;

    const series = [];

    // Power data is already in [[timestamp, value]] format
    if (data.power.power_consumption) {
        series.push({
            name: 'Effekt',
            type: 'line',
            data: data.power.power_consumption,
            smooth: true,
            symbol: 'none',
            areaStyle: { opacity: 0.3 },
            lineStyle: { width: 2, color: COLORS.power },
            itemStyle: { color: COLORS.power }
        });
    }

    // Add overlay bands
    const markAreas = buildOverlayMarkAreas(data, null);
    if (series.length > 0 && markAreas.length > 0) {
        series[0].markArea = { silent: true, data: markAreas };
    }

    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                if (!params || params.length === 0) return '';
                const time = new Date(params[0].value[0]);
                let result = time.toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) + '<br/>';
                params.forEach(p => {
                    if (p.value && p.value[1] !== null && p.value[1] !== undefined) {
                        result += `${p.marker} ${p.seriesName}: ${p.value[1].toFixed(0)} W<br/>`;
                    }
                });
                return result;
            }
        },
        grid: { left: 60, right: 20, top: 20, bottom: 80 },
        xAxis: {
            type: 'time',
            axisLabel: {
                formatter: (value) => {
                    const d = new Date(value);
                    return d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
                }
            }
        },
        yAxis: {
            type: 'value',
            name: 'W',
            axisLabel: { formatter: '{value} W' }
        },
        series: series,
        dataZoom: [
            {
                type: 'inside',
                start: savedZoomState ? savedZoomState.start : 0,
                end: savedZoomState ? savedZoomState.end : 100
            },
            {
                type: 'slider',
                start: savedZoomState ? savedZoomState.start : 0,
                end: savedZoomState ? savedZoomState.end : 100,
                height: 30,
                bottom: 30,
                showDetail: true,
                labelFormatter: (value) => {
                    const d = new Date(value);
                    return d.toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                }
            }
        ]
    };

    mainChart.setOption(option, { notMerge: false, lazyUpdate: true });
    updateChartTitle('power');
}

// ==================== COP Chart ====================

function renderCOPChart(data) {
    if (!data.cop || !data.cop.timestamps) return;

    const timestamps = data.cop.timestamps;
    const copValues = data.cop.values || data.cop.cop || [];
    const seasonalValues = data.cop.seasonal_values || [];
    const series = [];

    // Interval COP (main line)
    if (copValues.length > 0) {
        // Format as [[timestamp, value]] for time axis
        // Values are already interval-aggregated, null means no compressor activity
        const formattedData = timestamps.map((t, i) => {
            const val = copValues[i];
            return [t, (val && val >= 1) ? val : null];
        });
        series.push({
            name: 'Interval COP',
            type: 'line',
            data: formattedData,
            smooth: false,  // Step-like for interval data
            symbol: 'none',
            connectNulls: false,
            lineStyle: { width: 2, color: COLORS.cop },
            itemStyle: { color: COLORS.cop },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(39, 174, 96, 0.3)' },
                        { offset: 1, color: 'rgba(39, 174, 96, 0.05)' }
                    ]
                }
            }
        });
    }

    // Seasonal/Cumulative COP (dashed line)
    if (seasonalValues.length > 0) {
        const seasonalData = timestamps.map((t, i) => {
            const val = seasonalValues[i];
            return [t, (val && val >= 1) ? val : null];
        });
        series.push({
            name: 'Period COP',
            type: 'line',
            data: seasonalData,
            smooth: true,
            symbol: 'none',
            connectNulls: true,  // Connect across gaps for cumulative
            lineStyle: {
                width: 2,
                color: '#e74c3c',
                type: 'dashed'
            },
            itemStyle: { color: '#e74c3c' }
        });
    }

    // Add overlay bands
    const markAreas = buildOverlayMarkAreas(data, timestamps);
    if (series.length > 0 && markAreas.length > 0) {
        series[0].markArea = { silent: true, data: markAreas };
    }

    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                if (!params || params.length === 0) return '';
                const time = new Date(params[0].value[0]);
                let result = time.toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) + '<br/>';
                params.forEach(p => {
                    if (p.value && p.value[1] !== null && p.value[1] !== undefined) {
                        result += `${p.marker} ${p.seriesName}: ${p.value[1].toFixed(2)}<br/>`;
                    }
                });
                return result;
            }
        },
        legend: {
            data: ['Interval COP', 'Period COP'],
            bottom: 55,
            textStyle: { fontSize: 11 }
        },
        grid: { left: 50, right: 20, top: 20, bottom: 100 },
        xAxis: {
            type: 'time',
            axisLabel: {
                formatter: (value) => {
                    const d = new Date(value);
                    return d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
                }
            }
        },
        yAxis: {
            type: 'value',
            name: 'COP',
            min: 0,
            max: 6,
            axisLabel: { formatter: '{value}' }
        },
        series: series,
        dataZoom: [
            {
                type: 'inside',
                start: savedZoomState ? savedZoomState.start : 0,
                end: savedZoomState ? savedZoomState.end : 100
            },
            {
                type: 'slider',
                start: savedZoomState ? savedZoomState.start : 0,
                end: savedZoomState ? savedZoomState.end : 100,
                height: 30,
                bottom: 20,
                showDetail: true,
                labelFormatter: (value) => {
                    const d = new Date(value);
                    return d.toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                }
            }
        ]
    };

    mainChart.setOption(option, { notMerge: false, lazyUpdate: true });
    updateChartTitle('cop');
}

// ==================== Energy Sankey Chart ====================

function renderEnergyChart(data) {
    // Simple energy flow visualization
    const kpi = data.kpi || {};
    const energy = kpi.energy || {};
    const runtime = kpi.runtime || {};

    const totalEnergy = energy.total_kwh || 0;
    // Backend sends compressor_percent, not compressor_runtime_percent
    const compPercent = runtime.compressor_percent || 0;
    const auxPercent = runtime.aux_heater_percent || 0;

    // Estimate energy split (simplified)
    const compEnergy = totalEnergy * (compPercent / 100) * 0.8;
    const auxEnergy = totalEnergy * (auxPercent / 100) * 0.2;
    const standbyEnergy = Math.max(0, totalEnergy - compEnergy - auxEnergy);

    const option = {
        tooltip: { trigger: 'item' },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
                borderRadius: 10,
                borderColor: '#fff',
                borderWidth: 2
            },
            label: {
                show: true,
                formatter: '{b}: {d}%'
            },
            data: [
                { value: compEnergy.toFixed(1), name: 'Kompressor', itemStyle: { color: '#3498db' } },
                { value: auxEnergy.toFixed(1), name: 'Tillsats', itemStyle: { color: '#e74c3c' } },
                { value: standbyEnergy.toFixed(1), name: 'Standby', itemStyle: { color: '#95a5a6' } }
            ]
        }]
    };

    mainChart.setOption(option, { notMerge: true, lazyUpdate: true });
    updateChartTitle('energy');
}

// ==================== Overlay Mark Areas ====================

function buildOverlayMarkAreas(data, chartTimestamps) {
    const markAreas = [];

    const showCompressor = document.getElementById('overlay-compressor')?.checked;
    const showValve = document.getElementById('overlay-valve')?.checked;
    const showAux = document.getElementById('overlay-aux')?.checked;

    // Try different data sources for overlays
    // First check valve data (has compressor_status, valve_status)
    // Data format: [[timestamp, value], [timestamp, value], ...]

    // Get compressor status data
    let compressorData = null;
    let valveData = null;
    let auxData = null;

    // Check valve endpoint data
    if (data.valve) {
        console.log('📊 Valve data available:', Object.keys(data.valve));
        if (data.valve.compressor_status && Array.isArray(data.valve.compressor_status)) {
            compressorData = data.valve.compressor_status;
            console.log(`📊 Compressor data: ${compressorData.length} points`);
        }
        if (data.valve.valve_status && Array.isArray(data.valve.valve_status)) {
            valveData = data.valve.valve_status;
            console.log(`📊 Valve status data: ${valveData.length} points`);
        } else {
            console.log('📊 No valve_status data found in data.valve');
        }
    } else {
        console.log('📊 No data.valve object available');
    }

    // Check power endpoint data for aux heater
    if (data.power && data.power.additional_heat_percent && Array.isArray(data.power.additional_heat_percent)) {
        auxData = data.power.additional_heat_percent;
    }

    // Check performance data as alternative source
    if (!compressorData && data.performance && data.performance.compressor_status) {
        compressorData = data.performance.compressor_status;
    }

    // Helper function to extract periods from [[timestamp, value], ...] data
    function extractOnPeriods(dataArray, checkFn) {
        const periods = [];
        if (!dataArray || dataArray.length === 0) return periods;

        let startTime = null;
        let lastOnTime = null;

        for (let i = 0; i < dataArray.length; i++) {
            const item = dataArray[i];
            // Handle both array format [[time, value]] and object format
            let timestamp, value;
            if (Array.isArray(item)) {
                timestamp = item[0];
                value = item[1];
            } else if (typeof item === 'object') {
                timestamp = item.time || item._time;
                value = item.value || item._value;
            } else {
                continue;
            }

            const isOn = checkFn(value);

            if (isOn && startTime === null) {
                // Start of new period
                startTime = timestamp;
                lastOnTime = timestamp;
            } else if (isOn && startTime !== null) {
                // Still ON, update lastOnTime
                lastOnTime = timestamp;
            } else if (!isOn && startTime !== null) {
                // End of period - use CURRENT timestamp as end (when it turned OFF)
                // This ensures the overlay covers the full period
                periods.push({ start: startTime, end: timestamp });
                startTime = null;
                lastOnTime = null;
            }
        }

        // Close final period if still open
        if (startTime !== null && lastOnTime) {
            periods.push({ start: startTime, end: lastOnTime });
        }

        return periods;
    }

    // Find compressor ON periods
    if (showCompressor && compressorData) {
        const periods = extractOnPeriods(compressorData, v => v === 1 || v > 0);
        periods.forEach(p => {
            markAreas.push([
                { xAxis: p.start, itemStyle: { color: COLORS.compressor_overlay } },
                { xAxis: p.end }
            ]);
        });
        console.log(`📊 Compressor overlays: ${periods.length} periods`);
    }

    // Find valve hot water periods (valve status = 1)
    if (showValve && valveData) {
        const periods = extractOnPeriods(valveData, v => v === 1 || v > 0);
        periods.forEach(p => {
            markAreas.push([
                { xAxis: p.start, itemStyle: { color: COLORS.valve_overlay } },
                { xAxis: p.end }
            ]);
        });
        console.log(`📊 Valve overlays: ${periods.length} periods`);
        if (periods.length > 0) {
            console.log(`📊 First valve period: ${periods[0].start} to ${periods[0].end}`);
            console.log(`📊 Valve overlay color: ${COLORS.valve_overlay}`);
        }
    }

    // Find aux heater ON periods
    if (showAux && auxData) {
        const periods = extractOnPeriods(auxData, v => v > 0);
        periods.forEach(p => {
            markAreas.push([
                { xAxis: p.start, itemStyle: { color: COLORS.aux_overlay } },
                { xAxis: p.end }
            ]);
        });
        console.log(`📊 Aux heater overlays: ${periods.length} periods`);
    }

    return markAreas;
}

// ==================== Helper Functions ====================

function getVisibleSeries() {
    const visible = [];
    document.querySelectorAll('.series-toggle:checked').forEach(toggle => {
        visible.push(toggle.dataset.series);
    });
    return visible;
}

function updateChartTitle(chartType) {
    const titleEl = document.getElementById('chart-title');
    if (!titleEl) return;

    const titles = {
        temperature: '<i class="fas fa-temperature-high me-2"></i>Temperaturer',
        power: '<i class="fas fa-bolt me-2"></i>Effekt',
        cop: '<i class="fas fa-chart-line me-2"></i>Interval COP (15 min)',
        energy: '<i class="fas fa-pie-chart me-2"></i>Energifördelning'
    };

    titleEl.innerHTML = titles[chartType] || titles.temperature;

    // Show/hide series toggles (only for temperature chart)
    const seriesRow = document.getElementById('series-toggles-row');
    if (seriesRow) {
        seriesRow.style.display = chartType === 'temperature' ? 'block' : 'none';
    }
}

function switchChart(chartType) {
    currentChartType = chartType;
    if (chartData) {
        updateMainChart(chartData);
    }
}

function updateSeriesVisibility() {
    if (chartData && currentChartType === 'temperature') {
        renderTemperatureChart(chartData);
    }
}

function updateChartOverlays() {
    if (chartData) {
        updateMainChart(chartData);
    }
}

function resizeMainChart() {
    if (mainChart) {
        mainChart.resize();
    }
}

function resetZoomState() {
    savedZoomState = null;
    console.log('📊 Zoom state reset');
}

// ==================== Analys Stats ====================

function updateAnalysStats(data) {
    if (!data.status || !data.status.current) return;

    const current = data.status.current;
    const kpi = data.kpi || {};

    // Temperature stats (use radiator forward as example)
    if (current.radiator_forward) {
        const rf = current.radiator_forward;
        const minEl = document.getElementById('stat-min-temp');
        const maxEl = document.getElementById('stat-max-temp');
        const avgEl = document.getElementById('stat-avg-temp');
        if (minEl) minEl.textContent = rf.min !== null ? `${rf.min.toFixed(1)}°C` : '--';
        if (maxEl) maxEl.textContent = rf.max !== null ? `${rf.max.toFixed(1)}°C` : '--';
        if (avgEl) avgEl.textContent = rf.avg !== null ? `${rf.avg.toFixed(1)}°C` : '--';
    }

    // Runtime
    if (kpi.runtime) {
        const percent = kpi.runtime.compressor_runtime_percent;
        const el = document.getElementById('stat-comp-runtime');
        if (el) el.textContent = percent !== undefined ? `${percent.toFixed(1)}%` : '--';
    }

    // Energy
    if (kpi.energy) {
        const energyEl = document.getElementById('stat-energy');
        const costEl = document.getElementById('stat-cost');
        if (energyEl) energyEl.textContent = kpi.energy.total_kwh !== undefined ? `${kpi.energy.total_kwh.toFixed(1)} kWh` : '--';
        if (costEl) costEl.textContent = kpi.energy.total_cost !== undefined ? `${kpi.energy.total_cost.toFixed(0)} kr` : '--';
    }
}

// ==================== Exports ====================

window.initMainChart = initMainChart;
window.updateMainChart = updateMainChart;
window.updateAnalysStats = updateAnalysStats;
window.switchChart = switchChart;
window.updateSeriesVisibility = updateSeriesVisibility;
window.updateChartOverlays = updateChartOverlays;
window.resizeMainChart = resizeMainChart;
window.resetZoomState = resetZoomState;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initMainChart();
});

console.log('📊 Charts module loaded (Analys view)');
