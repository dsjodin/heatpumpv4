/**
 * Debug Tools for Heat Pump Dashboard
 * Displays all InfluxDB metrics in a table for troubleshooting
 */

let debugData = null;

// ==================== Debug Modal Management ====================

function openDebugModal() {
    const modal = new bootstrap.Modal(document.getElementById('debugModal'));
    modal.show();
    loadDebugData();
}

async function loadDebugData() {
    try {
        console.log('🔧 Loading debug metrics...');

        // Show loading state
        document.getElementById('debug-content').innerHTML = `
            <div class="text-center text-muted p-4">
                <i class="fas fa-spinner fa-spin fa-2x"></i>
                <p class="mt-2">Laddar metrics från InfluxDB...</p>
            </div>
        `;

        const response = await fetch('/api/debug/all-metrics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        debugData = await response.json();
        console.log('✅ Debug data loaded:', debugData);

        // Update header info
        document.getElementById('debug-metric-count').textContent = `${debugData.total_metrics} metrics`;
        document.getElementById('debug-brand').textContent = debugData.brand || 'Unknown';

        const timestamp = new Date(debugData.timestamp);
        document.getElementById('debug-timestamp').textContent = timestamp.toLocaleString('sv-SE');

        // Render table
        renderDebugTable(debugData.metrics);

    } catch (error) {
        console.error('❌ Failed to load debug data:', error);
        document.getElementById('debug-content').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Fel:</strong> Kunde inte ladda metrics. ${error.message}
            </div>
        `;
    }
}

function renderDebugTable(metrics) {
    if (!metrics || metrics.length === 0) {
        document.getElementById('debug-content').innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-info-circle me-2"></i>
                Inga metrics hittades i InfluxDB.
            </div>
        `;
        return;
    }

    // Build table HTML
    let html = `
        <div class="table-responsive">
            <table class="table table-sm table-striped table-hover" id="debug-metrics-table">
                <thead class="table-dark sticky-top">
                    <tr>
                        <th style="width: 5%">#</th>
                        <th style="width: 35%">Metric Name</th>
                        <th style="width: 20%">Värde</th>
                        <th style="width: 15%">Typ</th>
                        <th style="width: 25%">Senast uppdaterad</th>
                    </tr>
                </thead>
                <tbody>
    `;

    metrics.forEach((metric, index) => {
        // Format timestamp
        const timestamp = new Date(metric.timestamp);
        const timeStr = timestamp.toLocaleString('sv-SE', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        // Highlight certain metric names
        let nameClass = '';
        if (metric.name.includes('temp')) {
            nameClass = 'text-primary';
        } else if (metric.name.includes('status') || metric.name.includes('running')) {
            nameClass = 'text-success';
        } else if (metric.name.includes('alarm') || metric.name.includes('error')) {
            nameClass = 'text-danger';
        } else if (metric.name.includes('power') || metric.name.includes('consumption')) {
            nameClass = 'text-warning';
        }

        // Format value with color coding
        let valueClass = '';
        let valueDisplay = metric.formatted_value;

        if (metric.type === 'bool') {
            valueClass = metric.value ? 'text-success fw-bold' : 'text-muted';
            valueDisplay = metric.value ? 'TRUE' : 'FALSE';
        } else if (metric.type === 'int' || metric.type === 'float') {
            if (metric.value === 0) {
                valueClass = 'text-muted';
            } else if (metric.value > 0) {
                valueClass = 'text-success';
            } else {
                valueClass = 'text-danger';
            }
        }

        html += `
            <tr>
                <td class="text-muted">${index + 1}</td>
                <td>
                    <code class="${nameClass}">${metric.name}</code>
                </td>
                <td class="${valueClass}">${valueDisplay}</td>
                <td>
                    <span class="badge bg-secondary">${metric.type}</span>
                </td>
                <td class="text-muted small">${timeStr}</td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    document.getElementById('debug-content').innerHTML = html;
}

function filterDebugTable() {
    const searchTerm = document.getElementById('debug-search').value.toLowerCase();

    if (!debugData || !debugData.metrics) return;

    const filteredMetrics = debugData.metrics.filter(metric =>
        metric.name.toLowerCase().includes(searchTerm)
    );

    renderDebugTable(filteredMetrics);

    // Update count
    document.getElementById('debug-metric-count').textContent =
        `${filteredMetrics.length} / ${debugData.total_metrics} metrics`;
}

function copyDebugJSON() {
    if (!debugData) {
        alert('Ingen data att kopiera');
        return;
    }

    const jsonString = JSON.stringify(debugData, null, 2);

    // Copy to clipboard
    navigator.clipboard.writeText(jsonString).then(() => {
        // Show success feedback
        const btn = document.getElementById('btn-copy-debug');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i> Kopierat!';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-success');

        setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.classList.remove('btn-success');
            btn.classList.add('btn-primary');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Kunde inte kopiera till urklipp');
    });
}

// ==================== Event Listeners ====================

document.addEventListener('DOMContentLoaded', () => {
    // Debug button - open modal
    const debugButton = document.getElementById('btn-debug');
    if (debugButton) {
        debugButton.addEventListener('click', openDebugModal);
    }

    // Refresh button in modal
    const refreshButton = document.getElementById('btn-refresh-debug');
    if (refreshButton) {
        refreshButton.addEventListener('click', loadDebugData);
    }

    // Copy JSON button
    const copyButton = document.getElementById('btn-copy-debug');
    if (copyButton) {
        copyButton.addEventListener('click', copyDebugJSON);
    }

    // Search filter
    const searchInput = document.getElementById('debug-search');
    if (searchInput) {
        searchInput.addEventListener('input', filterDebugTable);
    }
});

console.log('🔧 Debug tools loaded');
