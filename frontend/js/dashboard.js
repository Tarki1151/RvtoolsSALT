// Dashboard Page Module
import { fetchStats, fetchOSDistribution } from './api.js';
import { charts } from './config.js';
import { formatNumber, truncateText } from './utils.js';

export async function loadDashboard() {
    try {
        const stats = await fetchStats();

        // Update stat cards
        document.getElementById('stat-total-vms').textContent = formatNumber(stats.total.vms);
        document.getElementById('stat-powered-on').textContent = formatNumber(stats.total.powered_on);
        document.getElementById('stat-powered-off').textContent = formatNumber(stats.total.powered_off);
        document.getElementById('stat-snapshots').textContent = formatNumber(stats.total.snapshots);
        document.getElementById('stat-total-cpu').textContent = formatNumber(stats.total.total_cpu);
        document.getElementById('stat-total-memory').textContent = `${formatNumber(stats.total.total_memory_gb)} GB`;
        document.getElementById('stat-total-disk').textContent = `${formatNumber(Math.round(stats.total.total_disk_gb / 1024))} TB`;
        document.getElementById('stat-old-snapshots').textContent = formatNumber(stats.total.old_snapshots);

        renderSourceCards(stats.sources);
        renderPowerStateChart(stats.total);
        renderSourcesChart(stats.sources);

        const osData = await fetchOSDistribution();
        renderOSChart(osData);

    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function renderSourceCards(sources) {
    const grid = document.getElementById('sources-grid');

    grid.innerHTML = sources.map(source => `
        <div class="source-card">
            <div class="source-card-header">
                <i class="fas fa-database"></i>
                <h3>${source.name}</h3>
            </div>
            <div class="source-stats">
                <div class="source-stat">
                    <span class="source-stat-value">${source.vms}</span>
                    <span class="source-stat-label">VM</span>
                </div>
                <div class="source-stat">
                    <span class="source-stat-value">${source.powered_on}</span>
                    <span class="source-stat-label">Powered On</span>
                </div>
                <div class="source-stat">
                    <span class="source-stat-value">${source.powered_off}</span>
                    <span class="source-stat-label">Powered Off</span>
                </div>
                <div class="source-stat">
                    <span class="source-stat-value">${source.snapshots}</span>
                    <span class="source-stat-label">Snapshots</span>
                </div>
                <div class="source-stat">
                    <span class="source-stat-value">${formatNumber(source.total_cpu)}</span>
                    <span class="source-stat-label">Total vCPU</span>
                </div>
                <div class="source-stat">
                    <span class="source-stat-value">${formatNumber(Math.round(source.total_memory_gb))} GB</span>
                    <span class="source-stat-label">Total RAM</span>
                </div>
            </div>
        </div>
    `).join('');
}

function renderPowerStateChart(total) {
    const ctx = document.getElementById('chart-powerstate').getContext('2d');

    if (charts.powerstate) charts.powerstate.destroy();

    charts.powerstate = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Powered On', 'Powered Off'],
            datasets: [{
                data: [total.powered_on, total.powered_off],
                backgroundColor: ['rgba(16, 185, 129, 0.8)', 'rgba(239, 68, 68, 0.8)'],
                borderColor: ['rgba(16, 185, 129, 1)', 'rgba(239, 68, 68, 1)'],
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9ca3af', padding: 20, font: { size: 12 } }
                }
            },
            cutout: '65%'
        }
    });
}

function renderSourcesChart(sources) {
    const ctx = document.getElementById('chart-sources').getContext('2d');

    if (charts.sources) charts.sources.destroy();

    charts.sources = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sources.map(s => s.name),
            datasets: [
                {
                    label: 'Powered On',
                    data: sources.map(s => s.powered_on),
                    backgroundColor: 'rgba(16, 185, 129, 0.8)',
                    borderRadius: 6
                },
                {
                    label: 'Powered Off',
                    data: sources.map(s => s.powered_off),
                    backgroundColor: 'rgba(239, 68, 68, 0.8)',
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9ca3af', padding: 20, font: { size: 12 } }
                }
            },
            scales: {
                x: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } },
                y: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
            }
        }
    });
}

function renderOSChart(osData) {
    const ctx = document.getElementById('chart-os').getContext('2d');

    if (charts.os) charts.os.destroy();

    const topOS = osData.slice(0, 10);
    const colors = [
        'rgba(59, 130, 246, 0.8)', 'rgba(16, 185, 129, 0.8)', 'rgba(139, 92, 246, 0.8)',
        'rgba(245, 158, 11, 0.8)', 'rgba(239, 68, 68, 0.8)', 'rgba(20, 184, 166, 0.8)',
        'rgba(236, 72, 153, 0.8)', 'rgba(234, 179, 8, 0.8)', 'rgba(168, 85, 247, 0.8)',
        'rgba(34, 197, 94, 0.8)'
    ];

    charts.os = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topOS.map(os => truncateText(os.OS, 40)),
            datasets: [{
                label: 'VM Sayısı',
                data: topOS.map(os => os['VM Count']),
                backgroundColor: colors,
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } },
                y: { grid: { display: false }, ticks: { color: '#9ca3af', font: { size: 11 } } }
            }
        }
    });
}
