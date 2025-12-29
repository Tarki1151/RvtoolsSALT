// Inventory Tree Module
import { fetchInventory, fetchInventoryDetail } from './api.js';
import { formatNumber } from './utils.js';
import { noteManager } from './notes.js';

export async function loadInventory() {
    const treeContainer = document.getElementById('inventory-tree');
    if (!treeContainer) return;

    treeContainer.innerHTML = '<div class="loading">Yükleniyor...</div>';

    try {
        const tree = await fetchInventory();
        renderInventoryTree(tree);

        // Search functionality
        const searchInput = document.getElementById('inventory-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const term = e.target.value.toLowerCase();
                document.querySelectorAll('.tree-item').forEach(item => {
                    const textEl = item.querySelector('.tree-text');
                    if (textEl) {
                        const text = textEl.textContent.toLowerCase();
                        item.style.display = text.includes(term) ? 'block' : 'none';
                    }
                });
            });
        }
    } catch (error) {
        console.error('Error loading inventory:', error);
        treeContainer.innerHTML = '<div class="error">Yükleme hatası</div>';
    }
}

function renderInventoryTree(tree) {
    const container = document.getElementById('inventory-tree');
    let html = '';

    for (const [sourceName, datacenters] of Object.entries(tree)) {
        html += `<div class="tree-item">
            <div class="tree-content" onclick="window.toggleTree(this, 'source', '${sourceName}', '${sourceName}', '', '', '')">
                <i class="fas fa-caret-right tree-toggle"></i>
                <i class="fas fa-database"></i>
                <span class="tree-text">${sourceName}</span>
            </div>
            <div class="tree-children">`;

        for (const [dcName, clusters] of Object.entries(datacenters)) {
            html += `<div class="tree-item">
                <div class="tree-content" onclick="window.toggleTree(this, 'datacenter', '${dcName}', '${sourceName}', '${dcName}', '', '')">
                    <i class="fas fa-caret-right tree-toggle"></i>
                    <i class="fas fa-building"></i>
                    <span class="tree-text">${dcName}</span>
                </div>
                <div class="tree-children">`;

            for (const [clusterName, hosts] of Object.entries(clusters)) {
                html += `<div class="tree-item">
                    <div class="tree-content" onclick="window.toggleTree(this, 'cluster', '${clusterName}', '${sourceName}', '${dcName}', '${clusterName}', '')">
                        <i class="fas fa-caret-right tree-toggle"></i>
                        <i class="fas fa-layer-group"></i>
                        <span class="tree-text">${clusterName}</span>
                    </div>
                    <div class="tree-children">`;

                for (const [hostName, vms] of Object.entries(hosts)) {
                    const vmCount = vms.length;
                    html += `<div class="tree-item">
                        <div class="tree-content" onclick="window.toggleTree(this, 'host', '${hostName}', '${sourceName}', '${dcName}', '${clusterName}', '${hostName}')">
                            <i class="fas fa-caret-right tree-toggle"></i>
                            <i class="fas fa-server"></i>
                            <span class="tree-text">${hostName} (${vmCount} VMs)</span>
                        </div>
                        <div class="tree-children">`;

                    vms.forEach(vm => {
                        const statusIcon = vm.power_state === 'poweredOn' ? 'power-off' : 'stop-circle';
                        const statusClass = vm.power_state === 'poweredOn' ? 'on' : 'off';
                        html += `<div class="tree-item">
                            <div class="tree-content vm-item" onclick="window.loadInventoryDetail('vm', '${vm.name}', '${sourceName}', '${dcName}', '${clusterName}', '${hostName}')">
                                <i class="fas fa-${statusIcon} status-${statusClass}"></i>
                                <span class="tree-text">${vm.name}</span>
                            </div>
                        </div>`;
                    });

                    html += `</div></div>`;
                }

                html += `</div></div>`;
            }

            html += `</div></div>`;
        }

        html += `</div></div>`;
    }

    container.innerHTML = html;
}

export function toggleTree(element, type, name, source, datacenter, cluster, host) {
    const parent = element.parentElement;
    const children = parent.querySelector('.tree-children');
    const toggle = element.querySelector('.tree-toggle');

    if (children) {
        children.classList.toggle('open');
        toggle?.classList.toggle('rotated');
    }

    document.querySelectorAll('.tree-content').forEach(el => el.classList.remove('active'));
    element.classList.add('active');

    loadInventoryDetail(type, name, source, datacenter, cluster, host);
}

export async function loadInventoryDetail(type, name, source, datacenter, cluster, host) {
    const detailView = document.getElementById('inventory-detail-view');
    if (!detailView) return;

    // If VM clicked, show VM detail modal
    if (type === 'vm') {
        window.showVMDetail(name, source);
        return;
    }

    // Show loading
    detailView.innerHTML = '<div class="loading">Yükleniyor...</div>';

    try {
        // Fetch VM list for selected level
        const params = {
            level: type,
            source: source || '',
            datacenter: datacenter || '',
            cluster: cluster || '',
            host: host || ''
        };

        const data = await fetchInventoryDetail(params);

        // Render VM table
        let icon = 'server';
        let colorClass = 'gradient-blue';

        switch (type) {
            case 'source': icon = 'database'; colorClass = 'gradient-blue'; break;
            case 'datacenter': icon = 'building'; colorClass = 'gradient-purple'; break;
            case 'cluster': icon = 'layer-group'; colorClass = 'gradient-orange'; break;
            case 'host': icon = 'server'; colorClass = 'gradient-green'; break;
        }

        detailView.innerHTML = `
            <div class="inventory-detail">
                <div class="inventory-header">
                    <div class="summary-card ${colorClass}" style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; align-items: center; gap: 15px;">
                            <i class="fas fa-${icon}"></i>
                            <div>
                                <h3>${name}</h3>
                                <p>${type.toUpperCase()} - ${data.vm_count} VM</p>
                            </div>
                        </div>
                        <button class="btn btn-sm btn-outline-light" id="inventory-note-btn">
                            <i class="fas fa-sticky-note"></i> Notlar
                        </button>
                    </div>
                </div>
                
                <div class="table-container">
                    <table class="data-table" id="inventory-vm-table">
                        <thead>
                            <tr>
                                <th>VM Name</th>
                                <th>Status</th>
                                <th>vCPU</th>
                                <th>RAM (GB)</th>
                                <th>Disk Allocated</th>
                                <th>Disk Used</th>
                                <th>Snapshots</th>
                                <th>Snapshot Size</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${renderVMRows(data.vms)}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        // Add event listeners
        const noteBtn = document.getElementById('inventory-note-btn');
        if (noteBtn) {
            noteBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent bubbling if needed
                noteManager.openNote(type, name);
            });
        }

        // Add click listener for VM rows to open detail
        document.querySelectorAll('#inventory-vm-table tbody tr').forEach(row => {
            row.addEventListener('click', () => {
                const nameCell = row.querySelector('td strong');
                if (nameCell && window.showVMDetail) {
                    window.showVMDetail(nameCell.textContent);
                }
            });
            row.style.cursor = 'pointer';
        });
    } catch (error) {
        console.error('Error loading inventory detail:', error);
        detailView.innerHTML = '<div class="error">Veri yükleme hatası</div>';
    }
}

function renderVMRows(vms) {
    if (!vms || vms.length === 0) {
        return '<tr><td colspan="8" class="empty-state">VM bulunamadı</td></tr>';
    }

    return vms.map(vm => {
        const statusClass = vm.powerstate === 'poweredOn' ? 'on' : 'off';
        const statusText = vm.powerstate === 'poweredOn' ? 'On' : 'Off';

        return `
            <tr>
                <td><strong>${vm.name}</strong></td>
                <td>
                    <span class="status-badge ${statusClass}">
                        <i class="fas fa-circle"></i> ${statusText}
                    </span>
                </td>
                <td>${vm.cpu_allocated} vCPU</td>
                <td>${formatNumber(vm.ram_allocated_mb / 1024)} GB</td>
                <td>${vm.disk_allocated_gb} GB</td>
                <td>${vm.disk_used_gb} GB</td>
                <td>${vm.snapshot_count}</td>
                <td>${vm.snapshot_size_gb} GB</td>
            </tr>
        `;
    }).join('');
}
