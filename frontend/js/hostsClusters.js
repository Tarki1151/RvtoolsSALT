// Hosts & Clusters Module - vCenter 8 Style
import { formatNumber } from './utils.js';

let hostsClusterData = null;
let currentSelection = { type: null, path: [] };

export async function loadHostsClusters() {
    const treeContainer = document.getElementById('hc-tree');
    const detailView = document.getElementById('hc-detail-view');

    if (!treeContainer) return;

    treeContainer.innerHTML = '<div class="loading">Yükleniyor...</div>';

    try {
        const response = await fetch('/api/hosts-clusters');
        hostsClusterData = await response.json();

        renderTree(hostsClusterData);
        renderSummaryDashboard();

        // Search functionality
        const searchInput = document.getElementById('hc-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                filterTree(e.target.value.toLowerCase());
            });
        }
    } catch (error) {
        console.error('Error loading hosts & clusters:', error);
        treeContainer.innerHTML = '<div class="error">Veri yüklenirken hata oluştu</div>';
    }
}

function renderTree(data) {
    const container = document.getElementById('hc-tree');
    let html = '';

    for (const [sourceName, sourceData] of Object.entries(data)) {
        const dcCount = Object.keys(sourceData.datacenters || {}).length;

        html += `
        <div class="hc-tree-item" data-type="source" data-name="${sourceName}">
            <div class="hc-tree-content" onclick="window.hcToggleTree(this, 'source', '${sourceName}')">
                <i class="fas fa-caret-right hc-tree-toggle"></i>
                <i class="fas fa-cloud hc-icon-vcenter"></i>
                <span class="hc-tree-label">${sourceName}</span>
                <span class="hc-tree-badge">${dcCount} DC</span>
            </div>
            <div class="hc-tree-children">`;

        for (const [dcName, dcData] of Object.entries(sourceData.datacenters || {})) {
            const clusterCount = Object.keys(dcData.clusters || {}).length;

            html += `
            <div class="hc-tree-item" data-type="datacenter" data-name="${dcName}">
                <div class="hc-tree-content" onclick="window.hcToggleTree(this, 'datacenter', '${dcName}', '${sourceName}')">
                    <i class="fas fa-caret-right hc-tree-toggle"></i>
                    <i class="fas fa-building hc-icon-datacenter"></i>
                    <span class="hc-tree-label">${dcName}</span>
                    <span class="hc-tree-badge">${clusterCount} Cluster</span>
                </div>
                <div class="hc-tree-children">`;

            for (const [clusterName, clData] of Object.entries(dcData.clusters || {})) {
                const hostCount = Object.keys(clData.hosts || {}).length;

                html += `
                <div class="hc-tree-item" data-type="cluster" data-name="${clusterName}">
                    <div class="hc-tree-content" onclick="window.hcToggleTree(this, 'cluster', '${clusterName}', '${sourceName}', '${dcName}')">
                        <i class="fas fa-caret-right hc-tree-toggle"></i>
                        <i class="fas fa-layer-group hc-icon-cluster"></i>
                        <span class="hc-tree-label">${clusterName}</span>
                        <span class="hc-tree-badge">${hostCount} Host</span>
                    </div>
                    <div class="hc-tree-children">`;

                for (const [hostName, hostData] of Object.entries(clData.hosts || {})) {
                    const vmCount = hostData.vms?.length || 0;
                    const poweredOn = hostData.powered_on || 0;

                    html += `
                    <div class="hc-tree-item" data-type="host" data-name="${hostName}">
                        <div class="hc-tree-content" onclick="window.hcSelectHost(this, '${hostName}', '${sourceName}', '${dcName}', '${clusterName}')">
                            <i class="fas fa-server hc-icon-host"></i>
                            <span class="hc-tree-label">${hostName}</span>
                            <span class="hc-tree-badge">${poweredOn}/${vmCount} VMs</span>
                        </div>
                    </div>`;
                }

                html += `</div></div>`;
            }

            html += `</div></div>`;
        }

        html += `</div></div>`;
    }

    container.innerHTML = html || '<div class="empty-state"><i class="fas fa-info-circle"></i><p>Veri bulunamadı</p></div>';
}

function renderSummaryDashboard() {
    const detailView = document.getElementById('hc-detail-view');
    if (!detailView || !hostsClusterData) return;

    // Calculate totals
    let totalDatacenters = 0;
    let totalClusters = 0;
    let totalHosts = 0;
    let totalVMs = 0;
    let totalPoweredOn = 0;
    let totalVCPU = 0;
    let totalRAM = 0;
    let totalPhysicalCores = 0;
    let totalPhysicalRAM = 0;
    let avgCpuUsage = 0;
    let avgRamUsage = 0;
    let hostCount = 0;

    for (const sourceData of Object.values(hostsClusterData)) {
        for (const dcData of Object.values(sourceData.datacenters || {})) {
            totalDatacenters++;
            totalVMs += dcData.total_vms || 0;
            totalPoweredOn += dcData.powered_on || 0;
            totalVCPU += dcData.total_vcpu || 0;
            totalRAM += dcData.total_ram_gb || 0;
            totalPhysicalCores += dcData.total_physical_cores || 0;
            totalPhysicalRAM += dcData.total_physical_ram_gb || 0;
            avgCpuUsage += (dcData.avg_cpu_usage_pct || 0) * (dcData.host_count || 0);
            avgRamUsage += (dcData.avg_ram_usage_pct || 0) * (dcData.host_count || 0);
            hostCount += dcData.host_count || 0;

            for (const clData of Object.values(dcData.clusters || {})) {
                totalClusters++;
                totalHosts += clData.host_count || 0;
            }
        }
    }

    const cpuRatio = totalPhysicalCores > 0 ? (totalVCPU / totalPhysicalCores).toFixed(2) : 0;
    const ramRatio = totalPhysicalRAM > 0 ? (totalRAM / totalPhysicalRAM).toFixed(2) : 0;
    avgCpuUsage = hostCount > 0 ? (avgCpuUsage / hostCount).toFixed(1) : 0;
    avgRamUsage = hostCount > 0 ? (avgRamUsage / hostCount).toFixed(1) : 0;

    detailView.innerHTML = `
        <div class="hc-summary-dashboard">
            <div class="hc-summary-header">
                <h2><i class="fas fa-tachometer-alt"></i> Genel Bakış</h2>
                <p>vCenter altyapı özeti</p>
            </div>
            
            <div class="hc-summary-stats">
                <div class="hc-stat-card gradient-purple">
                    <div class="hc-stat-icon"><i class="fas fa-building"></i></div>
                    <div class="hc-stat-content">
                        <h3>${totalDatacenters}</h3>
                        <p>Datacenter</p>
                    </div>
                </div>
                <div class="hc-stat-card gradient-orange">
                    <div class="hc-stat-icon"><i class="fas fa-layer-group"></i></div>
                    <div class="hc-stat-content">
                        <h3>${totalClusters}</h3>
                        <p>Cluster</p>
                    </div>
                </div>
                <div class="hc-stat-card gradient-teal">
                    <div class="hc-stat-icon"><i class="fas fa-server"></i></div>
                    <div class="hc-stat-content">
                        <h3>${totalHosts}</h3>
                        <p>ESXi Host</p>
                    </div>
                </div>
                <div class="hc-stat-card gradient-blue">
                    <div class="hc-stat-icon"><i class="fas fa-desktop"></i></div>
                    <div class="hc-stat-content">
                        <h3>${totalVMs}</h3>
                        <p>Virtual Machines</p>
                    </div>
                </div>
            </div>
            
            <div class="hc-resource-overview">
                <div class="hc-resource-card">
                    <div class="hc-resource-header">
                        <i class="fas fa-microchip"></i>
                        <span>CPU Kapasitesi</span>
                    </div>
                    <div class="hc-resource-body">
                        <div class="hc-resource-metric">
                            <span class="label">Gerçek Kullanım (Ort.)</span>
                            <span class="value ${parseFloat(avgCpuUsage) > 70 ? 'text-warning' : 'text-success'}">${avgCpuUsage}%</span>
                        </div>
                        <div class="hc-resource-metric">
                            <span class="label">vCPU:pCore Oranı</span>
                            <span class="value ${parseFloat(cpuRatio) > 4 ? 'text-warning' : ''}">${cpuRatio}:1</span>
                        </div>
                        <div class="hc-resource-metric">
                            <span class="label">Physical Cores</span>
                            <span class="value">${formatNumber(totalPhysicalCores)}</span>
                        </div>
                    </div>
                </div>
                
                <div class="hc-resource-card">
                    <div class="hc-resource-header">
                        <i class="fas fa-memory"></i>
                        <span>Memory Kapasitesi</span>
                    </div>
                    <div class="hc-resource-body">
                        <div class="hc-resource-metric">
                            <span class="label">Gerçek Kullanım (Ort.)</span>
                            <span class="value ${parseFloat(avgRamUsage) > 80 ? 'text-warning' : 'text-success'}">${avgRamUsage}%</span>
                        </div>
                        <div class="hc-resource-metric">
                            <span class="label">vRAM:pRAM Oranı</span>
                            <span class="value ${parseFloat(ramRatio) > 1.5 ? 'text-warning' : ''}">${ramRatio}:1</span>
                        </div>
                        <div class="hc-resource-metric">
                            <span class="label">Physical RAM</span>
                            <span class="value">${formatNumber(totalPhysicalRAM)} GB</span>
                        </div>
                    </div>
                </div>
                
                <div class="hc-resource-card">
                    <div class="hc-resource-header">
                        <i class="fas fa-power-off"></i>
                        <span>VM Durumu</span>
                    </div>
                    <div class="hc-resource-body">
                        <div class="hc-resource-metric">
                            <span class="label">Powered On</span>
                            <span class="value text-success">${totalPoweredOn}</span>
                        </div>
                        <div class="hc-resource-metric">
                            <span class="label">Powered Off</span>
                            <span class="value text-danger">${totalVMs - totalPoweredOn}</span>
                        </div>
                        <div class="hc-resource-metric">
                            <span class="label">On Ratio</span>
                            <span class="value">${totalVMs > 0 ? ((totalPoweredOn / totalVMs) * 100).toFixed(1) : 0}%</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="hc-cluster-list">
                <h3><i class="fas fa-layer-group"></i> Cluster Durumu</h3>
                <div class="hc-cluster-grid">
                    ${renderClusterCards()}
                </div>
            </div>
        </div>
    `;
}

function renderClusterCards() {
    let html = '';

    for (const [sourceName, sourceData] of Object.entries(hostsClusterData)) {
        for (const [dcName, dcData] of Object.entries(sourceData.datacenters || {})) {
            for (const [clusterName, clData] of Object.entries(dcData.clusters || {})) {
                // REAL usage from ESXi
                const cpuUsage = clData.avg_cpu_usage_pct || 0;
                const ramUsage = clData.avg_ram_usage_pct || 0;
                // Overcommit ratios
                const vcpuRatio = clData.vcpu_pcore_ratio || 0;
                const vramRatio = clData.vram_pram_ratio || 0;

                const cpuClass = cpuUsage > 70 ? 'danger' : cpuUsage > 50 ? 'warning' : 'success';
                const ramClass = ramUsage > 80 ? 'danger' : ramUsage > 60 ? 'warning' : 'success';

                html += `
                <div class="hc-cluster-card" onclick="window.hcShowClusterDetail('${clusterName}', '${sourceName}', '${dcName}')">
                    <div class="hc-cluster-header">
                        <i class="fas fa-layer-group"></i>
                        <span class="hc-cluster-name">${clusterName}</span>
                    </div>
                    <div class="hc-cluster-meta">
                        <span><i class="fas fa-server"></i> ${clData.host_count || 0} Hosts</span>
                        <span><i class="fas fa-desktop"></i> ${clData.total_vms || 0} VMs</span>
                    </div>
                    <div class="hc-cluster-bars">
                        <div class="hc-bar-group">
                            <span class="hc-bar-label">CPU</span>
                            <div class="hc-bar-track">
                                <div class="hc-bar-fill ${cpuClass}" style="width: ${Math.min(cpuUsage, 100)}%"></div>
                            </div>
                            <span class="hc-bar-value">${cpuUsage.toFixed(0)}%</span>
                        </div>
                        <div class="hc-bar-group">
                            <span class="hc-bar-label">RAM</span>
                            <div class="hc-bar-track">
                                <div class="hc-bar-fill ${ramClass}" style="width: ${Math.min(ramUsage, 100)}%"></div>
                            </div>
                            <span class="hc-bar-value">${ramUsage.toFixed(0)}%</span>
                        </div>
                    </div>
                    <div class="hc-cluster-ratios">
                        <span class="ratio-badge ${vcpuRatio > 4 ? 'warning' : ''}">
                            <i class="fas fa-microchip"></i> ${vcpuRatio}:1
                        </span>
                        <span class="ratio-badge ${vramRatio > 1.5 ? 'warning' : ''}">
                            <i class="fas fa-memory"></i> ${vramRatio}:1
                        </span>
                    </div>
                </div>`;
            }
        }
    }

    return html || '<p class="text-muted">Cluster bulunamadı</p>';
}

// Toggle tree expansion
window.hcToggleTree = function (element, type, name, source, datacenter) {
    const parent = element.parentElement;
    const children = parent.querySelector('.hc-tree-children');
    const toggle = element.querySelector('.hc-tree-toggle');

    if (children) {
        children.classList.toggle('open');
        toggle?.classList.toggle('rotated');
    }

    // Select and show details
    document.querySelectorAll('.hc-tree-content').forEach(el => el.classList.remove('active'));
    element.classList.add('active');

    switch (type) {
        case 'source':
            renderSourceDetail(name);
            break;
        case 'datacenter':
            renderDatacenterDetail(name, source);
            break;
        case 'cluster':
            renderClusterDetail(name, source, datacenter);
            break;
    }
};

// Select host
window.hcSelectHost = function (element, hostName, source, datacenter, cluster) {
    document.querySelectorAll('.hc-tree-content').forEach(el => el.classList.remove('active'));
    element.classList.add('active');
    renderHostDetail(hostName, source, datacenter, cluster);
};

// Show cluster detail (from card click)
window.hcShowClusterDetail = function (clusterName, source, datacenter) {
    renderClusterDetail(clusterName, source, datacenter);
};

function renderSourceDetail(sourceName) {
    const detailView = document.getElementById('hc-detail-view');
    const sourceData = hostsClusterData[sourceName];
    if (!sourceData || !detailView) return;

    let totalVMs = 0, totalHosts = 0, totalClusters = 0;

    for (const dcData of Object.values(sourceData.datacenters || {})) {
        totalVMs += dcData.total_vms || 0;
        totalClusters += Object.keys(dcData.clusters || {}).length;
        for (const clData of Object.values(dcData.clusters || {})) {
            totalHosts += clData.host_count || 0;
        }
    }

    detailView.innerHTML = `
        <div class="hc-detail-panel">
            <div class="hc-detail-header gradient-blue">
                <i class="fas fa-cloud"></i>
                <div>
                    <h2>${sourceName}</h2>
                    <p>vCenter Server</p>
                </div>
            </div>
            <div class="hc-detail-stats">
                <div class="hc-mini-stat">
                    <span class="value">${Object.keys(sourceData.datacenters || {}).length}</span>
                    <span class="label">Datacenters</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${totalClusters}</span>
                    <span class="label">Clusters</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${totalHosts}</span>
                    <span class="label">Hosts</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${totalVMs}</span>
                    <span class="label">VMs</span>
                </div>
            </div>
        </div>
    `;
}

function renderDatacenterDetail(dcName, sourceName) {
    const detailView = document.getElementById('hc-detail-view');
    const dcData = hostsClusterData[sourceName]?.datacenters?.[dcName];
    if (!dcData || !detailView) return;

    const avgCpu = dcData.avg_cpu_usage_pct || 0;
    const avgRam = dcData.avg_ram_usage_pct || 0;

    detailView.innerHTML = `
        <div class="hc-detail-panel">
            <div class="hc-detail-header gradient-purple">
                <i class="fas fa-building"></i>
                <div>
                    <h2>${dcName}</h2>
                    <p>Datacenter</p>
                </div>
            </div>
            <div class="hc-detail-stats">
                <div class="hc-mini-stat">
                    <span class="value">${dcData.cluster_count || 0}</span>
                    <span class="label">Clusters</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${dcData.host_count || 0}</span>
                    <span class="label">Hosts</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${dcData.total_vms || 0}</span>
                    <span class="label">VMs</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${dcData.powered_on || 0}</span>
                    <span class="label">Powered On</span>
                </div>
            </div>
            
            <div class="hc-section">
                <h3><i class="fas fa-chart-bar"></i> Ortalama Kullanım</h3>
                <div class="hc-utilization-bars">
                    <div class="hc-util-row">
                        <span class="hc-util-label"><i class="fas fa-microchip"></i> CPU</span>
                        <div class="hc-util-bar">
                            <div class="hc-util-fill ${avgCpu > 70 ? 'danger' : avgCpu > 50 ? 'warning' : 'success'}" style="width: ${Math.min(avgCpu, 100)}%"></div>
                        </div>
                        <span class="hc-util-value">${avgCpu.toFixed(1)}%</span>
                        <span class="hc-util-detail">Gerçek Kullanım</span>
                    </div>
                    <div class="hc-util-row">
                        <span class="hc-util-label"><i class="fas fa-memory"></i> RAM</span>
                        <div class="hc-util-bar">
                            <div class="hc-util-fill ${avgRam > 80 ? 'danger' : avgRam > 60 ? 'warning' : 'success'}" style="width: ${Math.min(avgRam, 100)}%"></div>
                        </div>
                        <span class="hc-util-value">${avgRam.toFixed(1)}%</span>
                        <span class="hc-util-detail">Gerçek Kullanım</span>
                    </div>
                </div>
            </div>
            
            <div class="hc-section">
                <h3><i class="fas fa-server"></i> Kapasite</h3>
                <div class="hc-capacity-grid">
                    <div class="hc-capacity-item">
                        <span class="label">Total vCPU</span>
                        <span class="value">${formatNumber(dcData.total_vcpu || 0)}</span>
                    </div>
                    <div class="hc-capacity-item">
                        <span class="label">Total vRAM</span>
                        <span class="value">${formatNumber(dcData.total_ram_gb || 0)} GB</span>
                    </div>
                    <div class="hc-capacity-item">
                        <span class="label">Physical Cores</span>
                        <span class="value">${formatNumber(dcData.total_physical_cores || 0)}</span>
                    </div>
                    <div class="hc-capacity-item">
                        <span class="label">Physical RAM</span>
                        <span class="value">${formatNumber(dcData.total_physical_ram_gb || 0)} GB</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderClusterDetail(clusterName, sourceName, dcName) {
    const detailView = document.getElementById('hc-detail-view');
    const clData = hostsClusterData[sourceName]?.datacenters?.[dcName]?.clusters?.[clusterName];
    if (!clData || !detailView) return;

    // Real usage
    const cpuUsage = clData.avg_cpu_usage_pct || 0;
    const ramUsage = clData.avg_ram_usage_pct || 0;
    // Overcommit ratios
    const vcpuRatio = clData.vcpu_pcore_ratio || 0;
    const vramRatio = clData.vram_pram_ratio || 0;

    let hostsTableRows = '';
    for (const [hostName, hostData] of Object.entries(clData.hosts || {})) {
        const hCpuUsage = hostData.cpu_usage_pct || 0;
        const hRamUsage = hostData.ram_usage_pct || 0;
        const hVcpuRatio = hostData.vcpu_pcore_ratio || 0;

        hostsTableRows += `
            <tr onclick="window.hcSelectHostFromTable('${hostName}', '${sourceName}', '${dcName}', '${clusterName}')">
                <td><i class="fas fa-server"></i> ${hostName}</td>
                <td>${hostData.total_vms || 0}</td>
                <td>${hostData.powered_on || 0}</td>
                <td class="${hVcpuRatio > 4 ? 'text-warning' : ''}">${hVcpuRatio}:1</td>
                <td>
                    <div class="hc-inline-bar">
                        <div class="hc-inline-fill ${hCpuUsage > 70 ? 'danger' : hCpuUsage > 50 ? 'warning' : 'success'}" style="width: ${Math.min(hCpuUsage, 100)}%"></div>
                    </div>
                    <span>${hCpuUsage.toFixed(0)}%</span>
                </td>
                <td>
                    <div class="hc-inline-bar">
                        <div class="hc-inline-fill ${hRamUsage > 80 ? 'danger' : hRamUsage > 60 ? 'warning' : 'success'}" style="width: ${Math.min(hRamUsage, 100)}%"></div>
                    </div>
                    <span>${hRamUsage.toFixed(0)}%</span>
                </td>
            </tr>
        `;
    }

    detailView.innerHTML = `
        <div class="hc-detail-panel">
            <div class="hc-detail-header gradient-orange">
                <i class="fas fa-layer-group"></i>
                <div>
                    <h2>${clusterName}</h2>
                    <p>Cluster • ${dcName}</p>
                </div>
            </div>
            
            <div class="hc-detail-stats">
                <div class="hc-mini-stat">
                    <span class="value">${clData.host_count || 0}</span>
                    <span class="label">Hosts</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${clData.total_vms || 0}</span>
                    <span class="label">VMs</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${clData.powered_on || 0}</span>
                    <span class="label">Powered On</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value ${vcpuRatio > 4 ? 'text-warning' : ''}">${vcpuRatio}:1</span>
                    <span class="label">vCPU:pCore</span>
                </div>
            </div>
            
            <div class="hc-section">
                <h3><i class="fas fa-chart-bar"></i> Gerçek Kullanım (ESXi Reported)</h3>
                <div class="hc-utilization-bars">
                    <div class="hc-util-row">
                        <span class="hc-util-label"><i class="fas fa-microchip"></i> CPU</span>
                        <div class="hc-util-bar">
                            <div class="hc-util-fill ${cpuUsage > 70 ? 'danger' : cpuUsage > 50 ? 'warning' : 'success'}" style="width: ${Math.min(cpuUsage, 100)}%"></div>
                        </div>
                        <span class="hc-util-value">${cpuUsage.toFixed(1)}%</span>
                        <span class="hc-util-detail">Ortalama</span>
                    </div>
                    <div class="hc-util-row">
                        <span class="hc-util-label"><i class="fas fa-memory"></i> RAM</span>
                        <div class="hc-util-bar">
                            <div class="hc-util-fill ${ramUsage > 80 ? 'danger' : ramUsage > 60 ? 'warning' : 'success'}" style="width: ${Math.min(ramUsage, 100)}%"></div>
                        </div>
                        <span class="hc-util-value">${ramUsage.toFixed(1)}%</span>
                        <span class="hc-util-detail">Ortalama</span>
                    </div>
                </div>
            </div>
            
            <div class="hc-section">
                <h3><i class="fas fa-server"></i> Hosts</h3>
                <div class="table-container">
                    <table class="data-table compact">
                        <thead>
                            <tr>
                                <th>Host</th>
                                <th>VMs</th>
                                <th>On</th>
                                <th>vCPU:pCore</th>
                                <th>CPU %</th>
                                <th>RAM %</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${hostsTableRows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

window.hcSelectHostFromTable = function (hostName, source, datacenter, cluster) {
    renderHostDetail(hostName, source, datacenter, cluster);
};

async function renderHostDetail(hostName, sourceName, dcName, clusterName) {
    const detailView = document.getElementById('hc-detail-view');
    const hostData = hostsClusterData[sourceName]?.datacenters?.[dcName]?.clusters?.[clusterName]?.hosts?.[hostName];
    if (!hostData || !detailView) return;

    // Show loading state first
    detailView.innerHTML = `
        <div class="hc-detail-panel fade-in">
            <div class="hc-detail-header gradient-teal">
                <i class="fas fa-server"></i>
                <div>
                    <h2>${hostName}</h2>
                    <p>ESXi Host • ${clusterName}</p>
                </div>
            </div>
            <div class="loading-container p-5 text-center">
                <div class="spinner-border text-teal mb-3"></div>
                <div class="loading">Sistem verileri ve donanım bileşenleri analiz ediliyor...</div>
            </div>
        </div>
    `;

    try {
        const hwResponse = await fetch(`/api/host_hardware/${hostName}`);
        const hwData = await hwResponse.json();

        const hw = hwData.hardware || {};
        const nics = hwData.nics || [];
        const hbas = hwData.hbas || [];
        const vmks = hwData.vmks || [];
        const storagePaths = hwData.storage_paths || [];
        const healthIssues = hwData.health || [];
        const partitionAlerts = hwData.partitions || [];
        const snapshots = hwData.snapshots || [];

        const totalAlerts = healthIssues.length + partitionAlerts.length;

        // Real usage from ESXi
        const cpuUsage = hostData.cpu_usage_pct || 0;
        const ramUsage = hostData.ram_usage_pct || 0;
        const vcpuRatio = hostData.vcpu_pcore_ratio || 0;
        const vramRatio = hostData.vram_pram_ratio || 0;

        // Render Tabs
        detailView.innerHTML = `
            <div class="hc-detail-panel fade-in">
                <div class="hc-detail-header gradient-teal">
                    <i class="fas fa-server"></i>
                    <div>
                        <h2>${hostName}</h2>
                        <p>ESXi Host • ${clusterName}</p>
                    </div>
                    <div class="hc-header-status">
                        <span class="status-badge ${hw['in Maintenance Mode'] ? 'off' : 'on'}">
                            ${hw['in Maintenance Mode'] ? 'Maintenance' : 'Connected'}
                        </span>
                    </div>
                </div>
                
                <div class="hc-tabs">
                    <button class="hc-tab-btn active" onclick="window.hcSwitchTab(this, 'summary')">Özet</button>
                    <button class="hc-tab-btn" onclick="window.hcSwitchTab(this, 'hardware')">Donanım & BIOS</button>
                    <button class="hc-tab-btn" onclick="window.hcSwitchTab(this, 'network')">Network (${nics.length + vmks.length})</button>
                    <button class="hc-tab-btn" onclick="window.hcSwitchTab(this, 'storage')">Storage (${storagePaths.length || hbas.length})</button>
                    <button class="hc-tab-btn" onclick="window.hcSwitchTab(this, 'health')">Sağlık & Uyarılar ${totalAlerts > 0 ? `<span class="badge bg-danger ms-1">${totalAlerts}</span>` : ''}</button>
                    <button class="hc-tab-btn" onclick="window.hcSwitchTab(this, 'vms')">VM'ler (${hostData.total_vms || 0})</button>
                </div>

                <div id="hc-tab-content">
                    ${renderSummaryTab(hostData, hw, cpuUsage, ramUsage, vcpuRatio, vramRatio)}
                </div>
            </div>
        `;

        // Store data globally for tab switching
        window.currentHostContext = {
            hostData, hw, nics, hbas, vmks, storagePaths,
            healthIssues, partitionAlerts, snapshots,
            sourceName, clusterName,
            cpuUsage, ramUsage, vcpuRatio, vramRatio
        };

    } catch (error) {
        console.error('Error loading hardware details:', error);
        // Fallback to basic view if hardware API fails
        renderBasicHostDetail(hostData, hostName, clusterName, sourceName);
    }
}

function renderSummaryTab(hostData, hw, cpuUsage, ramUsage, vcpuRatio, vramRatio) {
    return `
        <div class="hc-tab-pane active" id="summary">
            <div class="hc-detail-stats">
                <div class="hc-mini-stat">
                    <span class="value">${hostData.total_vms || 0} / ${hostData.powered_on || 0}</span>
                    <span class="label">VM (Toplam / Açık)</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${hw['# CPU'] || 0}x / ${hw['# Cores'] || 0}</span>
                    <span class="label">CPU Config (Socket/Core)</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${formatNumber(hostData.physical_ram_gb || 0)} GB</span>
                    <span class="label">Fiziksel RAM</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${hw['ESX Version']?.split(' ').pop() || '-'}</span>
                    <span class="label">Build No</span>
                </div>
            </div>

            <div class="hc-grid-2">
                <div class="hc-section">
                    <h3><i class="fas fa-chart-line"></i> Performans Metrikleri</h3>
                    <div class="hc-utilization-bars">
                        <div class="hc-util-row">
                            <span class="hc-util-label">CPU Usage</span>
                            <div class="hc-util-bar"><div class="hc-util-fill ${cpuUsage > 80 ? 'danger' : cpuUsage > 60 ? 'warning' : 'success'}" style="width: ${cpuUsage}%"></div></div>
                            <span class="hc-util-value">${cpuUsage.toFixed(1)}%</span>
                        </div>
                        <div class="hc-util-row">
                            <span class="hc-util-label">RAM Usage</span>
                            <div class="hc-util-bar"><div class="hc-util-fill ${ramUsage > 85 ? 'danger' : ramUsage > 70 ? 'warning' : 'success'}" style="width: ${ramUsage}%"></div></div>
                            <span class="hc-util-value">${ramUsage.toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="hc-capacity-grid mt-3">
                        <div class="hc-capacity-item"><span class="label">vCPU:pCore</span><span class="value ${vcpuRatio > 4 ? 'text-warning' : ''}">${vcpuRatio}:1</span></div>
                        <div class="hc-capacity-item"><span class="label">vRAM:pRAM</span><span class="value ${vramRatio > 1.5 ? 'text-warning' : ''}">${vramRatio}:1</span></div>
                    </div>
                </div>
                <div class="hc-section">
                    <h3><i class="fas fa-id-card"></i> Sistem Kimlik Bilgileri</h3>
                    <div class="hc-property-list">
                        <div class="prop"><span class="key">Vendor</span><span class="val">${hw.Vendor || '-'}</span></div>
                        <div class="prop"><span class="key">Model</span><span class="val">${hw.Model || '-'}</span></div>
                        <div class="prop"><span class="key">Serial</span><span class="val">${hw['Serial number'] || '-'}</span></div>
                        <div class="prop"><span class="key">Domain</span><span class="val">${hw.Domain || '-'}</span></div>
                        <div class="prop"><span class="key">ESXi Vers.</span><span class="val">${hw['ESX Version'] || '-'}</span></div>
                    </div>
                </div>
            </div>

            <div class="hc-section mt-4">
                <h3><i class="fas fa-key"></i> Lisans ve Operasyonel Bilgiler</h3>
                <div class="hc-property-list">
                    <div class="prop"><span class="key">Atanmış Lisans</span><span class="val">${hw['Assigned License(s)'] || 'Lisans Bilgisi Yok'}</span></div>
                    <div class="prop"><span class="key">Power Policy</span><span class="val">${hw['Host Power Policy'] || '-'}</span></div>
                    <div class="prop"><span class="key">Boot Zamanı</span><span class="val">${hw['Boot time'] || '-'}</span></div>
                </div>
            </div>
        </div>
    `;
}

window.hcSwitchTab = function (btn, tabId) {
    // Update button states
    document.querySelectorAll('.hc-tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const content = document.getElementById('hc-tab-content');
    const ctx = window.currentHostContext;
    if (!ctx) return;

    switch (tabId) {
        case 'summary': content.innerHTML = renderSummaryTab(ctx.hostData, ctx.hw, ctx.cpuUsage, ctx.ramUsage, ctx.vcpuRatio, ctx.vramRatio); break;
        case 'hardware': content.innerHTML = renderHardwareTab(ctx.hw); break;
        case 'network': content.innerHTML = renderNetworkTab(ctx.nics, ctx.vmks); break;
        case 'storage': content.innerHTML = renderStorageTab(ctx.hbas, ctx.storagePaths); break;
        case 'health': content.innerHTML = renderHealthTab(ctx.healthIssues, ctx.partitionAlerts, ctx.snapshots); break;
        case 'vms': content.innerHTML = renderVMsTab(ctx.hostData.vms, ctx.sourceName); break;
    }
};

function renderHardwareTab(hw) {
    return `
        <div class="hc-tab-pane active fade-in">
            <div class="hc-grid-2">
                <div class="hc-section">
                    <h3><i class="fas fa-microchip"></i> İşlemci (CPU) Detayları</h3>
                    <div class="hc-property-list">
                        <div class="prop"><span class="key">Model</span><span class="val">${hw['CPU Model'] || '-'}</span></div>
                        <div class="prop"><span class="key">Speed</span><span class="val">${hw.Speed || 0} MHz</span></div>
                        <div class="prop"><span class="key">Socket Sayısı</span><span class="val">${hw['# CPU'] || 0}</span></div>
                        <div class="prop"><span class="key">Çekirdek/Socket</span><span class="val">${hw['Cores per CPU'] || 0}</span></div>
                        <div class="prop"><span class="key">Hyperthreading</span><span class="val">${hw['HT Active'] ? 'Aktif' : 'Pasif'}</span></div>
                        <div class="prop"><span class="key">EVC Mode</span><span class="val">${hw['Current EVC'] || 'N/A'}</span></div>
                    </div>
                </div>
                <div class="hc-section">
                    <h3><i class="fas fa-info-circle"></i> BIOS & Anakart</h3>
                    <div class="hc-property-list">
                        <div class="prop"><span class="key">BIOS Üretici</span><span class="val">${hw['BIOS Vendor'] || '-'}</span></div>
                        <div class="prop"><span class="key">BIOS Sürümü</span><span class="val">${hw['BIOS Version'] || '-'}</span></div>
                        <div class="prop"><span class="key">BIOS Tarihi</span><span class="val">${hw['BIOS Date'] || '-'}</span></div>
                        <div class="prop"><span class="key">Service Tag</span><span class="val">${hw['Service tag'] || '-'}</span></div>
                        <div class="prop"><span class="key">UUID</span><span class="val small">${hw.UUID || '-'}</span></div>
                    </div>
                </div>
            </div>
            <div class="hc-section mt-4">
                <h3><i class="fas fa-network-wired"></i> Ağ Servisleri</h3>
                <div class="hc-property-list grid-cols-2">
                    <div class="prop"><span class="key">DNS Sunucuları</span><span class="val">${hw['DNS Servers'] || '-'}</span></div>
                    <div class="prop"><span class="key">NTP Sunucuları</span><span class="val">${hw['NTP Server(s)'] || '-'}</span></div>
                    <div class="prop"><span class="key">NTPD Durumu</span><span class="val">${hw['NTPD running'] ? 'Çalışıyor' : 'Duru'}</span></div>
                    <div class="prop"><span class="key">Zaman Dilimi</span><span class="val">${hw['Time Zone Name'] || '-'} (${hw['Time Zone'] || ''})</span></div>
                </div>
            </div>
        </div>
    `;
}

function renderNetworkTab(nics, vmks) {
    let nicRows = nics.length ? nics.map(nic => `
        <tr>
            <td><i class="fas fa-ethernet text-primary"></i> <strong>${nic['Network Device'] || '-'}</strong></td>
            <td><span class="badge ${parseFloat(nic.Speed) >= 10000 ? 'gradient-blue' : 'bg-secondary'}">${nic.Speed > 0 ? (nic.Speed / 1000 + ' Gbps') : (nic.Duplex === 'Link is down!' ? 'Down' : '-')}</span></td>
            <td>${nic.Duplex || '-'}</td>
            <td><code>${nic.MAC || '-'}</code></td>
            <td>${nic.Switch || '-'}</td>
            <td>${nic.Driver || '-'}</td>
        </tr>
    `).join('') : '<tr><td colspan="6" class="text-center text-muted">Fiziksel NIC bulunamadı</td></tr>';

    let vmkRows = vmks.length ? vmks.map(vmk => `
        <tr>
            <td><i class="fas fa-network-wired text-teal"></i> <strong>${vmk.Device || '-'}</strong></td>
            <td>${vmk['Port Group'] || '-'}</td>
            <td><strong>${vmk['IP Address'] || '-'}</strong></td>
            <td>${vmk['Subnet mask'] || '-'}</td>
            <td>${vmk.Gateway || '-'}</td>
            <td>${vmk.MTU || '-'}</td>
        </tr>
    `).join('') : '<tr><td colspan="6" class="text-center text-muted">VMKernel adaptörü bulunamadı</td></tr>';

    return `
        <div class="hc-tab-pane active fade-in">
            <div class="hc-section">
                <h3><i class="fas fa-ethernet"></i> Fiziksel Adaptörler (NICs)</h3>
                <div class="table-container mb-4">
                    <table class="data-table">
                        <thead>
                            <tr><th>Device</th><th>Hız</th><th>Status/Duplex</th><th>MAC</th><th>Switch</th><th>Driver</th></tr>
                        </thead>
                        <tbody>${nicRows}</tbody>
                    </table>
                </div>
            </div>
            
            <div class="hc-section">
                <h3><i class="fas fa-network-wired"></i> VMKernel Adaptörleri (VMKs)</h3>
                <div class="table-container">
                    <table class="data-table">
                        <thead>
                            <tr><th>Interface</th><th>Port Group</th><th>IP Address</th><th>Mask</th><th>Gateway</th><th>MTU</th></tr>
                        </thead>
                        <tbody>${vmkRows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

function renderStorageTab(hbas, storagePaths) {
    if (!hbas.length && !storagePaths.length) return '<div class="p-4 text-center text-muted">Depolama bilgisi bulunamadı</div>';

    let hbaRows = hbas.length ? hbas.map(hba => `
        <tr>
            <td><i class="fas fa-microchip text-warning"></i> <strong>${hba.Device || '-'}</strong></td>
            <td>${hba.Type || '-'}</td>
            <td>${hba.Model || '-'}</td>
            <td><span class="status-badge ${hba.Status === 'online' ? 'on' : 'off'}">${hba.Status || '-'}</span></td>
            <td><code>${hba.WWN || '-'}</code></td>
            <td>${hba.Driver || '-'}</td>
        </tr>
    `).join('') : '<tr><td colspan="6" class="text-center text-muted">HBA kartı bulunamadı</td></tr>';

    let pathRows = storagePaths.length ? storagePaths.map(path => `
        <tr>
            <td><i class="fas fa-hdd text-muted"></i> <strong>${path.Vendor || '-'} ${path.Model || ''}</strong></td>
            <td><span class="badge bg-dark">${path.Policy || '-'}</span></td>
            <td><span class="text-success">${path['Oper. State'] || '-'}</span></td>
            <td>${path['Datastore'] || '-'}</td>
            <td><code class="small" title="${path.Disk}">${path.Disk?.substring(0, 15)}...</code></td>
            <td>${path['Queue depth'] || '-'}</td>
        </tr>
    `).join('') : '<tr><td colspan="6" class="text-center text-muted">Fiziksel depolama yolu (MultiPath) bulunamadı</td></tr>';

    return `
        <div class="hc-tab-pane active fade-in">
            <div class="hc-section">
                <h3><i class="fas fa-microchip"></i> Host Bus Adapters (HBAs)</h3>
                <div class="table-container mb-4">
                    <table class="data-table">
                        <thead>
                            <tr><th>Device</th><th>Tip</th><th>Model</th><th>Durum</th><th>WWN/Target</th><th>Driver</th></tr>
                        </thead>
                        <tbody>${hbaRows}</tbody>
                    </table>
                </div>
            </div>

            <div class="hc-section">
                <h3><i class="fas fa-hdd"></i> Fiziksel Diskler & MultiPath</h3>
                <div class="table-container">
                    <table class="data-table compact">
                        <thead>
                            <tr><th>Storage Model</th><th>Policy</th><th>State</th><th>Datastore</th><th>Identifier</th><th>Queue</th></tr>
                        </thead>
                        <tbody>${pathRows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

function renderVMsTab(vms, sourceName) {
    if (!vms || !vms.length) return '<div class="p-4 text-center text-muted">Bu host üzerinde VM bulunmuyor</div>';

    let rows = vms.map(vm => {
        const statusClass = vm.powerstate === 'poweredOn' ? 'on' : 'off';
        return `
            <tr onclick="window.showVMDetail && window.showVMDetail('${vm.name}', '${sourceName}')">
                <td><span class="status-indicator ${statusClass}"></span> ${vm.name}</td>
                <td><span class="status-badge ${statusClass}">${vm.powerstate === 'poweredOn' ? 'On' : 'Off'}</span></td>
                <td>${vm.vcpu}</td>
                <td>${formatNumber(vm.ram_gb)} GB</td>
                <td>${formatNumber(vm.disk_gb)} GB</td>
                <td class="os-cell">${vm.os || '-'}</td>
            </tr>
        `;
    }).join('');

    return `
        <div class="hc-tab-pane active fade-in">
            <div class="table-container">
                <table class="data-table compact">
                    <thead>
                        <tr>
                            <th>VM Name</th>
                            <th>Status</th>
                            <th>vCPU</th>
                            <th>RAM</th>
                            <th>Disk</th>
                            <th>OS</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>
    `;
}

function renderBasicHostDetail(hostData, hostName, clusterName, sourceName) {
    // Original simplified view if hardware fetch fails
    const detailView = document.getElementById('hc-detail-view');
    detailView.innerHTML = `
        <div class="hc-detail-panel">
            <div class="hc-detail-header gradient-teal">
                <i class="fas fa-server"></i>
                <h2>${hostName} (Kısıtlı Görünüm)</h2>
            </div>
            <div class="p-4">Donanım bilgileri alınamadı. Sadece temel bilgiler gösteriliyor.</div>
            ${renderVMsTab(hostData.vms, sourceName)}
        </div>
    `;
}

function renderHealthTab(health, partitions, snapshots) {
    let healthRows = health.length ? health.map(h => `
        <div class="hc-alert-item ${h['Message type'] === 'Critical' ? 'critical' : 'warning'}">
            <div class="hc-alert-icon"><i class="fas ${h['Message type'] === 'Critical' ? 'fa-times-circle' : 'fa-exclamation-triangle'}"></i></div>
            <div class="hc-alert-content">
                <strong>${h.Name || 'Genel'}</strong>
                <p>${h.Message}</p>
            </div>
        </div>
    `).join('') : '<div class="p-3 text-muted">Belirlenmiş bir sağlık sorunu bulunamadı.</div>';

    let partitionRows = partitions.length ? partitions.map(p => `
        <tr>
            <td><strong>${p.VM}</strong></td>
            <td>${p.Disk || '-'}</td>
            <td>${formatNumber(p['Capacity MiB'] / 1024)} GB</td>
            <td><span class="text-danger"><strong>%${p['Free %']}</strong></span></td>
            <td>${formatNumber(p['Free MiB'] / 1024)} GB</td>
        </tr>
    `).join('') : '<tr><td colspan="5" class="text-center text-muted">Kritik seviyede dolu disk bulunamadı.</td></tr>';

    let snapRows = snapshots.length ? snapshots.map(s => `
        <tr>
            <td><strong>${s.VM}</strong></td>
            <td>${s.Name || '-'}</td>
            <td>${formatNumber(s['Size MiB (total)'] / 1024)} GB</td>
            <td>${s['Date / time'] || '-'}</td>
        </tr>
    `).join('') : '<tr><td colspan="4" class="text-center text-muted">Snapshot bulunamadı.</td></tr>';

    return `
        <div class="hc-tab-pane active fade-in">
            <div class="hc-section">
                <h3><i class="fas fa-heartbeat"></i> RVTools Sağlık Kontrolleri</h3>
                <div class="hc-alerts-list mb-4">
                    ${healthRows}
                </div>
            </div>

            <div class="hc-grid-2">
                <div class="hc-section">
                    <h3><i class="fas fa-exclamation-circle"></i> VM OS-Disk Uyarıları (< %10 Boş)</h3>
                    <div class="table-container">
                        <table class="data-table compact">
                            <thead>
                                <tr><th>VM</th><th>Disk</th><th>Kapasite</th><th>Boş %</th><th>Boş GB</th></tr>
                            </thead>
                            <tbody>${partitionRows}</tbody>
                        </table>
                    </div>
                </div>

                <div class="hc-section">
                    <h3><i class="fas fa-camera"></i> Güncel Snapshotlar</h3>
                    <div class="table-container">
                        <table class="data-table compact">
                            <thead>
                                <tr><th>VM</th><th>Snapshot Adı</th><th>Boyut</th><th>Tarih</th></tr>
                            </thead>
                            <tbody>${snapRows}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function filterTree(searchTerm) {
    const items = document.querySelectorAll('.hc-tree-item');

    if (!searchTerm) {
        items.forEach(item => {
            item.style.display = '';
            item.classList.remove('search-match');
        });
        return;
    }

    items.forEach(item => {
        const label = item.querySelector('.hc-tree-label');
        if (label) {
            const text = label.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                item.style.display = '';
                item.classList.add('search-match');
                // Expand parents
                let parent = item.parentElement;
                while (parent) {
                    if (parent.classList.contains('hc-tree-children')) {
                        parent.classList.add('open');
                        const toggle = parent.previousElementSibling?.querySelector('.hc-tree-toggle');
                        toggle?.classList.add('rotated');
                    }
                    parent = parent.parentElement;
                }
            } else {
                item.style.display = 'none';
                item.classList.remove('search-match');
            }
        }
    });
}
