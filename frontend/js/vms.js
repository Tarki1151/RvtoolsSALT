// Virtual Machines Page Module
import { fetchVMs } from './api.js';
import { currentSource, setVmsData } from './config.js';
import { formatNumber, truncateText, escapeHtml } from './utils.js';
import { showVMDetail } from './vmDetail.js';

export async function loadVMs() {
    try {
        const search = document.getElementById('filter-vm-search')?.value || '';
        const powerstate = document.getElementById('filter-powerstate')?.value || '';
        const cluster = document.getElementById('filter-cluster')?.value || '';
        const host = document.getElementById('filter-host')?.value || '';
        const os = document.getElementById('filter-os')?.value || '';

        const params = {
            source: currentSource,
            search,
            powerstate,
            cluster,
            host,
            os
        };

        const result = await fetchVMs(params);
        const data = Array.isArray(result) ? result : result.data || [];
        setVmsData(data);

        renderVMsTable(data);

        if (!Array.isArray(result)) {
            updateFilteredSummary(result.summary);
            populateFilters(result.filter_options);
        }
    } catch (error) {
        console.error('Error loading VMs:', error);
    }
}

function renderVMsTable(vms) {
    const tbody = document.querySelector('#vms-table tbody');

    if (vms.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-state"><i class="fas fa-server"></i><p>VM bulunamadı</p></td></tr>';
        return;
    }

    tbody.innerHTML = vms.map(vm => `
        <tr>
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
            <td>${vm.Source || '-'}</td>
            <td>
                <button class="btn-action" onclick="window.showVMDetail('${escapeHtml(vm.VM)}', '${vm.Source}')">
                    <i class="fas fa-eye"></i> Detay
                </button>
            </td>
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

function populateFilters(options) {
    if (!options) return;

    const populate = (id, items) => {
        const select = document.getElementById(id);
        if (!select) return;
        const currentValue = select.value;

        if (select.options.length <= 1) {
            let html = '<option value="">Tümü</option>';
            items.forEach(item => {
                html += `<option value="${item}">${item}</option>`;
            });
            select.innerHTML = html;

            if (currentValue && items.includes(currentValue)) {
                select.value = currentValue;
            }
        }
    };

    populate('filter-cluster', options.clusters);
    populate('filter-host', options.hosts);
    populate('filter-os', options.os);
}
