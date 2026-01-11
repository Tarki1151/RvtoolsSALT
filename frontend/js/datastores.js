// Datastores Module
import { fetchDatastores } from './api.js';
import { currentSource } from './config.js';
import { formatNumber } from './utils.js';

let allDatastores = [];
let hideLocal = false;
let currentSort = {
    column: 'Name',
    direction: 'asc'
};

export async function loadDatastores() {
    try {
        const datastores = await fetchDatastores(currentSource);
        allDatastores = datastores;

        // Update Stats
        let totalCapMiB = 0;
        let totalFreeMiB = 0;
        datastores.forEach(ds => {
            totalCapMiB += ds['Capacity MiB'] || 0;
            totalFreeMiB += ds['Free MiB'] || 0;
        });

        document.getElementById('ds-stat-count').textContent = datastores.length;
        document.getElementById('ds-stat-capacity').textContent = `${(totalCapMiB / 1024 / 1024).toFixed(2)} TB`;
        document.getElementById('ds-stat-free').textContent = `${(totalFreeMiB / 1024 / 1024).toFixed(2)} TB`;

        renderDatastoreTree();
        renderDatastoreTable(allDatastores);

        // Init search
        const searchInput = document.getElementById('ds-search-input');
        if (searchInput) {
            searchInput.oninput = () => {
                applyFilters();
            };
        }

        // Init toggle local
        const toggleBtn = document.getElementById('btn-toggle-local-ds');
        if (toggleBtn) {
            toggleBtn.onclick = () => {
                hideLocal = !hideLocal;
                toggleBtn.classList.toggle('active');
                toggleBtn.querySelector('span').textContent = hideLocal ? 'Lokal Diskleri Göster' : 'Lokal Diskleri Gizle';
                applyFilters();
            };
        }

        // Init Sorting
        initSorting();

    } catch (error) {
        console.error('Error loading datastores:', error);
    }
}

function renderDatastoreTree() {
    const treeEl = document.getElementById('ds-tree');
    if (!treeEl) return;

    // Group by Source
    const sources = [...new Set(allDatastores.map(ds => ds.Source))];

    treeEl.innerHTML = sources.map(source => `
        <div class="hc-source-group">
            <div class="hc-node hc-node-source active" onclick="window.filterDatastoresBySource('${source}')">
                <i class="fas fa-database"></i>
                <span>${source}</span>
            </div>
            <div class="hc-children" style="display: block;">
                ${allDatastores.filter(ds => ds.Source === source).slice(0, 15).map(ds => `
                    <div class="hc-node hc-node-host" onclick="window.highlightDatastore('${ds.Name}')">
                        <i class="fas fa-hdd"></i>
                        <span>${ds.Name}</span>
                    </div>
                `).join('')}
                ${allDatastores.filter(ds => ds.Source === source).length > 15 ?
            `<div class="hc-node hc-node-more small text-muted ms-4">... ve ${allDatastores.filter(ds => ds.Source === source).length - 15} daha</div>`
            : ''}
            </div>
        </div>
    `).join('');
}

window.filterDatastoresBySource = (source) => {
    const filtered = allDatastores.filter(ds => ds.Source === source);
    renderDatastoreTable(filtered);
};

window.highlightDatastore = (name) => {
    const filtered = allDatastores.filter(ds => ds.Name === name);
    renderDatastoreTable(filtered);
};

function applyFilters() {
    const term = document.getElementById('ds-search-input')?.value.toLowerCase() || '';
    let filtered = [...allDatastores];

    if (term) {
        filtered = filtered.filter(ds =>
            ds.Name.toLowerCase().includes(term) ||
            (ds.Vendor && ds.Vendor.toLowerCase().includes(term)) ||
            (ds.Model && ds.Model.toLowerCase().includes(term))
        );
    }

    if (hideLocal) {
        // Exclude datastores with only 1 host (usually local)
        filtered = filtered.filter(ds => (ds['# Hosts'] || 0) > 1);
    }

    // Apply Sorting
    filtered.sort((a, b) => {
        let valA, valB;

        if (currentSort.column === 'usedPct') {
            const capA = a['Capacity MiB'] || 0;
            const freeA = a['Free MiB'] || 0;
            valA = capA > 0 ? ((capA - freeA) / capA * 100) : 0;

            const capB = b['Capacity MiB'] || 0;
            const freeB = b['Free MiB'] || 0;
            valB = capB > 0 ? ((capB - freeB) / capB * 100) : 0;
        } else {
            valA = a[currentSort.column];
            valB = b[currentSort.column];
        }

        if (valA === undefined || valA === null) valA = '';
        if (valB === undefined || valB === null) valB = '';

        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();

        if (valA < valB) return currentSort.direction === 'asc' ? -1 : 1;
        if (valA > valB) return currentSort.direction === 'asc' ? 1 : -1;
        return 0;
    });

    renderDatastoreTable(filtered);
    updateSortIcons();
}

function initSorting() {
    const table = document.getElementById('datastores-table');
    if (!table) return;

    table.querySelectorAll('th.sortable').forEach(th => {
        th.style.cursor = 'pointer';
        th.onclick = () => {
            const col = th.dataset.sort;
            if (currentSort.column === col) {
                currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.column = col;
                currentSort.direction = 'asc';
            }
            applyFilters();
        };
    });
}

function updateSortIcons() {
    document.querySelectorAll('#datastores-table th.sortable').forEach(th => {
        const icon = th.querySelector('i');
        if (!icon) return;

        if (th.dataset.sort === currentSort.column) {
            icon.className = `fas fa-sort-${currentSort.direction === 'asc' ? 'up' : 'down'}`;
            th.classList.add('sorted');
        } else {
            icon.className = 'fas fa-sort text-muted';
            th.classList.remove('sorted');
        }
    });
}

window.selectDatastoreRow = (event) => {
    document.querySelectorAll('#datastores-table tr').forEach(r => r.classList.remove('active-row'));
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active-row');
    }
};

function renderDatastoreTable(data) {
    const tbody = document.querySelector('#datastores-table tbody');
    if (!tbody) return;

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><i class="fas fa-search"></i><p>Datastore bulunamadı</p></td></tr>';
        return;
    }

    tbody.innerHTML = data.map(ds => {
        const capacityGb = (ds['Capacity MiB'] || 0) / 1024;
        const freeGb = (ds['Free MiB'] || 0) / 1024;
        const usedPct = capacityGb > 0 ? ((capacityGb - freeGb) / capacityGb * 100).toFixed(1) : 0;

        let storageInfo = '-';
        if (ds.Vendor || ds.Model) {
            storageInfo = `
                <div class="storage-info">
                    <strong>${ds.Vendor || ''}</strong>
                    <div class="small text-muted">${ds.Model || ''}</div>
                </div>
            `;
        }

        return `
            <tr onclick="window.selectDatastoreRow(event)">
                <td>
                    <div class="ds-name-cell">
                        <i class="fas fa-database text-teal"></i>
                        <strong>${ds.Name}</strong>
                    </div>
                </td>
                <td><span class="badge bg-secondary">${ds.Type || '-'}</span></td>
                <td>${storageInfo}</td>
                <td>${formatNumber(Math.round(capacityGb))} GB</td>
                <td>${formatNumber(Math.round(freeGb))} GB</td>
                <td>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill ${usedPct > 90 ? 'bg-danger' : usedPct > 75 ? 'bg-warning' : 'bg-success'}" 
                             style="width: ${usedPct}%"></div>
                        <span class="progress-label">${usedPct}%</span>
                    </div>
                </td>
                <td><span class="badge bg-primary">${ds['# VMs'] || 0}</span></td>
            </tr>
        `;
    }).join('');
}
