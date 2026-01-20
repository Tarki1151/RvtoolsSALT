// Virtual Machines Page Module
import { fetchVMs } from './api.js';
import { currentSource, setVmsData, vmsData } from './config.js';
import { formatNumber, truncateText, escapeHtml } from './utils.js';
import { showVMDetail } from './vmDetail.js';

let debounceTimer = null;

export async function loadVMs() {
    try {
        const search = document.getElementById('filter-vm-search')?.value || '';
        const powerstate = document.getElementById('filter-powerstate')?.value || '';
        const cluster = document.getElementById('filter-cluster')?.value || '';
        const host = document.getElementById('filter-host')?.value || '';
        const os = document.getElementById('filter-os')?.value || '';
        const osType = document.getElementById('filter-os-type')?.value || '';
        const source = document.getElementById('filter-source')?.value || '';

        const params = {
            source: source || currentSource,
            search,
            powerstate,
            cluster,
            host,
            os,
            os_type: osType
        };

        const result = await fetchVMs(params);
        const data = Array.isArray(result) ? result : result.data || [];
        setVmsData(data);

        renderVMsTable(data);

        if (!Array.isArray(result)) {
            updateFilteredSummary(result.summary);
            updateFilterOptions(result.filter_options);
        }

        // Setup filter change listeners (once)
        setupFilterListeners();
    } catch (error) {
        console.error('Error loading VMs:', error);
    }
}

function setupFilterListeners() {
    const filterIds = ['filter-powerstate', 'filter-cluster', 'filter-host', 'filter-os', 'filter-os-type', 'filter-source'];

    filterIds.forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.dataset.listenerAttached) {
            el.addEventListener('change', () => loadVMs());
            el.dataset.listenerAttached = 'true';
        }
    });

    // Search with debounce
    const searchInput = document.getElementById('filter-vm-search');
    if (searchInput && !searchInput.dataset.listenerAttached) {
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => loadVMs(), 300);
        });
        searchInput.dataset.listenerAttached = 'true';
    }
}

function renderVMsTable(vms) {
    const tbody = document.querySelector('#vms-table tbody');

    if (vms.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-server"></i><p>VM bulunamadı</p></td></tr>';
        return;
    }

    tbody.innerHTML = vms.map(vm => `
        <tr onclick="window.showVMDetail('${escapeHtml(vm.VM)}', '${vm.Source}')" style="cursor: pointer;">
            <td><strong>${vm.VM}</strong></td>
            <td>
                <span class="status-badge ${vm.Powerstate === 'poweredOn' ? 'on' : 'off'}">
                    <i class="fas fa-circle"></i>
                    ${vm.Powerstate === 'poweredOn' ? 'On' : 'Off'}
                </span>
            </td>
            <td>${vm.CPUs || '-'}</td>
            <td>${formatNumber(vm.Memory)}</td>
            <td>${formatNumber(vm['Total disk capacity MiB'])}</td>
            <td>${truncateText(vm['OS according to the configuration file'], 30)}</td>
            <td>${truncateText(vm.Host, 25)}</td>
            <td>${truncateText(vm.Cluster, 25) || '-'}</td>
        </tr>
    `).join('');
}

function updateFilteredSummary(summary) {
    if (!summary) return;
    const el = (id) => document.getElementById(id);
    if (el('filt-vm-count')) el('filt-vm-count').textContent = formatNumber(summary.count);
    if (el('filt-vm-cpu')) el('filt-vm-cpu').textContent = formatNumber(summary.cpu);
    if (el('filt-vm-ram')) el('filt-vm-ram').textContent = `${formatNumber(summary.memory_gb)} GB`;
    if (el('filt-vm-disk')) el('filt-vm-disk').textContent = `${formatNumber(summary.disk_gb)} GB`;
}

function updateFilterOptions(options) {
    if (!options) return;

    // Update each filter dropdown while preserving current selection if still valid
    const updateSelect = (id, items, keepFirst = true) => {
        const select = document.getElementById(id);
        if (!select) return;

        const currentValue = select.value;

        // Build new options
        let html = keepFirst ? '<option value="">Tümü</option>' : '';
        items.forEach(item => {
            const selected = item === currentValue ? 'selected' : '';
            html += `<option value="${item}" ${selected}>${item}</option>`;
        });

        select.innerHTML = html;

        // If current value is no longer valid, reset to "Tümü"
        if (currentValue && !items.includes(currentValue)) {
            select.value = '';
        }
    };

    updateSelect('filter-cluster', options.clusters);
    updateSelect('filter-host', options.hosts);
    updateSelect('filter-os', options.os);
    updateSelect('filter-source', options.sources);

    // OS Type is static (Srv/Dsk), but update if dynamic options come from backend
    if (options.os_types) {
        const osTypeSelect = document.getElementById('filter-os-type');
        if (osTypeSelect) {
            const currentValue = osTypeSelect.value;
            let html = '<option value="">Tümü</option>';
            options.os_types.forEach(item => {
                if (item && item !== 'Unknown') {
                    const selected = item === currentValue ? 'selected' : '';
                    html += `<option value="${item}" ${selected}>${item}</option>`;
                }
            });
            osTypeSelect.innerHTML = html;
        }
    }
}

// Export dropdown toggle
document.addEventListener('DOMContentLoaded', () => {
    const exportBtn = document.getElementById('vm-export-btn');
    const exportMenu = document.getElementById('vm-export-menu');

    if (exportBtn && exportMenu) {
        exportBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            exportMenu.classList.toggle('show');
        });

        document.addEventListener('click', () => {
            exportMenu.classList.remove('show');
        });
    }
});

// CSV Export - All fields
window.exportVMsCSV = function () {
    const data = vmsData || [];

    if (data.length === 0) {
        alert('Dışa aktarılacak veri bulunamadı.');
        return;
    }

    // Get all unique keys from the first VM (all available columns)
    const allKeys = Object.keys(data[0] || {});

    // Priority columns first, then rest alphabetically
    const priorityKeys = ['VM', 'Powerstate', 'CPUs', 'Memory', 'Total disk capacity MiB', 'Host', 'Cluster', 'Datacenter'];
    const otherKeys = allKeys.filter(k => !priorityKeys.includes(k)).sort();
    const orderedKeys = [...priorityKeys.filter(k => allKeys.includes(k)), ...otherKeys];

    let csv = orderedKeys.join(',') + '\n';

    data.forEach(vm => {
        const row = orderedKeys.map(key => {
            let val = vm[key];
            if (val === null || val === undefined) val = '';
            val = String(val);
            // Escape quotes and wrap in quotes if contains comma, quote, or newline
            if (val.includes(',') || val.includes('"') || val.includes('\n')) {
                val = '"' + val.replace(/"/g, '""') + '"';
            }
            return val;
        });
        csv += row.join(',') + '\n';
    });

    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `VMs_Full_Export_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();

    document.getElementById('vm-export-menu')?.classList.remove('show');
};

// XLS Export - All fields (HTML table format that Excel can open)
window.exportVMsXLS = function () {
    const data = vmsData || [];

    if (data.length === 0) {
        alert('Dışa aktarılacak veri bulunamadı.');
        return;
    }

    // Get all unique keys from the first VM
    const allKeys = Object.keys(data[0] || {});

    // Priority columns first, then rest alphabetically
    const priorityKeys = ['VM', 'Powerstate', 'CPUs', 'Memory', 'Total disk capacity MiB', 'Host', 'Cluster', 'Datacenter'];
    const otherKeys = allKeys.filter(k => !priorityKeys.includes(k)).sort();
    const orderedKeys = [...priorityKeys.filter(k => allKeys.includes(k)), ...otherKeys];

    let html = `
        <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">
        <head><meta charset="UTF-8"></head>
        <body>
        <table border="1">
            <thead><tr>${orderedKeys.map(h => `<th>${h}</th>`).join('')}</tr></thead>
            <tbody>
    `;

    data.forEach(vm => {
        html += '<tr>';
        orderedKeys.forEach(key => {
            let val = vm[key];
            if (val === null || val === undefined) val = '';
            html += `<td>${val}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table></body></html>';

    const blob = new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `VMs_Full_Export_${new Date().toISOString().slice(0, 10)}.xls`;
    link.click();

    document.getElementById('vm-export-menu')?.classList.remove('show');
};
