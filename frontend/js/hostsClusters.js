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

function renderHostDetail(hostName, sourceName, dcName, clusterName) {
    const detailView = document.getElementById('hc-detail-view');
    const hostData = hostsClusterData[sourceName]?.datacenters?.[dcName]?.clusters?.[clusterName]?.hosts?.[hostName];
    if (!hostData || !detailView) return;

    // Real usage from ESXi
    const cpuUsage = hostData.cpu_usage_pct || 0;
    const ramUsage = hostData.ram_usage_pct || 0;
    // Overcommit ratios
    const vcpuRatio = hostData.vcpu_pcore_ratio || 0;
    const vramRatio = hostData.vram_pram_ratio || 0;

    let vmsTableRows = '';
    for (const vm of hostData.vms || []) {
        const statusClass = vm.powerstate === 'poweredOn' ? 'on' : 'off';
        vmsTableRows += `
            <tr onclick="window.showVMDetail && window.showVMDetail('${vm.name}', '${sourceName}')">
                <td>
                    <span class="status-indicator ${statusClass}"></span>
                    ${vm.name}
                </td>
                <td><span class="status-badge ${statusClass}">${vm.powerstate === 'poweredOn' ? 'On' : 'Off'}</span></td>
                <td>${vm.vcpu}</td>
                <td>${formatNumber(vm.ram_gb)} GB</td>
                <td>${formatNumber(vm.disk_gb)} GB</td>
                <td class="os-cell">${vm.os || '-'}</td>
            </tr>
        `;
    }

    detailView.innerHTML = `
        <div class="hc-detail-panel">
            <div class="hc-detail-header gradient-teal">
                <i class="fas fa-server"></i>
                <div>
                    <h2>${hostName}</h2>
                    <p>ESXi Host • ${clusterName}</p>
                </div>
            </div>
            
            <div class="hc-detail-stats">
                <div class="hc-mini-stat">
                    <span class="value">${hostData.total_vms || 0}</span>
                    <span class="label">Total VMs</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${hostData.powered_on || 0}</span>
                    <span class="label">Powered On</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${hostData.cpu_sockets || 0}x${hostData.cores_per_socket || 0}</span>
                    <span class="label">CPU Config</span>
                </div>
                <div class="hc-mini-stat">
                    <span class="value">${formatNumber(hostData.physical_ram_gb || 0)} GB</span>
                    <span class="label">Physical RAM</span>
                </div>
            </div>
            
            <div class="hc-host-info">
                <div class="hc-info-row">
                    <span class="label"><i class="fas fa-microchip"></i> CPU Model</span>
                    <span class="value">${hostData.cpu_model || '-'}</span>
                </div>
                <div class="hc-info-row">
                    <span class="label"><i class="fas fa-code-branch"></i> ESXi Version</span>
                    <span class="value">${hostData.esxi_version || '-'}</span>
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
                        <span class="hc-util-detail">Aktif Kullanım</span>
                    </div>
                    <div class="hc-util-row">
                        <span class="hc-util-label"><i class="fas fa-memory"></i> RAM</span>
                        <div class="hc-util-bar">
                            <div class="hc-util-fill ${ramUsage > 80 ? 'danger' : ramUsage > 60 ? 'warning' : 'success'}" style="width: ${Math.min(ramUsage, 100)}%"></div>
                        </div>
                        <span class="hc-util-value">${ramUsage.toFixed(1)}%</span>
                        <span class="hc-util-detail">Aktif Kullanım</span>
                    </div>
                </div>
            </div>
            
            <div class="hc-section">
                <h3><i class="fas fa-balance-scale"></i> Overcommit Oranları</h3>
                <div class="hc-capacity-grid">
                    <div class="hc-capacity-item">
                        <span class="label">vCPU:pCore</span>
                        <span class="value ${vcpuRatio > 4 ? 'text-warning' : ''}">${vcpuRatio}:1</span>
                    </div>
                    <div class="hc-capacity-item">
                        <span class="label">vRAM:pRAM</span>
                        <span class="value ${vramRatio > 1.5 ? 'text-warning' : ''}">${vramRatio}:1</span>
                    </div>
                    <div class="hc-capacity-item">
                        <span class="label">vCPU Count</span>
                        <span class="value">${hostData.vcpu_count || 0}</span>
                    </div>
                    <div class="hc-capacity-item">
                        <span class="label">vRAM Allocated</span>
                        <span class="value">${formatNumber(hostData.vram_gb || 0)} GB</span>
                    </div>
                </div>
            </div>
            
            <div class="hc-section">
                <h3><i class="fas fa-desktop"></i> Virtual Machines (${hostData.total_vms || 0})</h3>
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
                        <tbody>
                            ${vmsTableRows || '<tr><td colspan="6" class="empty-state">VM bulunamadı</td></tr>'}
                        </tbody>
                    </table>
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
