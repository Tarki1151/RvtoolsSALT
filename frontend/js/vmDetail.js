// VM Detail Modal Module
import { fetchVMDetail } from './api.js';
import { formatNumber, truncateText, escapeHtml } from './utils.js';
import { noteManager } from './notes.js';


export async function showVMDetail(vmName, source) {
    const modal = document.getElementById('vm-modal');
    document.getElementById('modal-vm-name').textContent = vmName;

    // Reset to first tab
    document.querySelectorAll('.vm-tab-btn').forEach((btn, i) => {
        btn.classList.toggle('active', i === 0);
    });
    document.querySelectorAll('.vm-tab-content').forEach((content, i) => {
        content.classList.toggle('active', i === 0);
    });

    modal.classList.add('active');
    loadVMDetail(vmName, source);
}

async function loadVMDetail(vmName, source) {
    try {
        const data = await fetchVMDetail(vmName, source);

        if (data.error) {
            console.error(data.error);
            return;
        }

        renderVMInfo(data.info);
        renderVMDisks(data.disks);
        renderVMNetwork(data.networks);
        renderVMSnapshots(data.snapshots);
    } catch (error) {
        console.error('Error loading VM detail:', error);
    }
}

function renderVMInfo(info) {
    // Render Resource Summary Cards
    const summaryContainer = document.getElementById('vm-resource-summary');
    if (summaryContainer) {
        summaryContainer.innerHTML = `
            <div class="summary-card gradient-purple" style="flex: 1; min-width: 120px; padding: 10px;">
                <i class="fas fa-microchip"></i>
                <div>
                    <h3 style="font-size: 1.2rem;">${info.CPUs || '-'} vCPU</h3>
                    <p>CPU</p>
                </div>
            </div>
            <div class="summary-card gradient-blue" style="flex: 1; min-width: 120px; padding: 10px;">
                <i class="fas fa-memory"></i>
                <div>
                    <h3 style="font-size: 1.2rem;">${formatNumber(info.Memory)} MB</h3>
                    <p>RAM</p>
                </div>
            </div>
            <div class="summary-card gradient-pink" style="flex: 1; min-width: 120px; padding: 10px;">
                <i class="fas fa-hdd"></i>
                <div>
                    <h3 style="font-size: 1.2rem;">${formatNumber(info['Total disk capacity MiB'])} MiB</h3>
                    <p>Disk</p>
                </div>
            </div>
             <div class="summary-card gradient-teal" style="flex: 1; min-width: 120px; padding: 10px;">
                <i class="fas fa-power-off"></i>
                <div>
                    <h3 style="font-size: 1.2rem; text-transform: capitalize;">${info.Powerstate === 'poweredOn' ? 'On' : 'Off'}</h3>
                    <p>Durum</p>
                </div>
            </div>
            <div class="summary-card" style="flex: 1; min-width: 120px; padding: 10px; cursor: pointer; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1);" id="vm-detail-note-btn">
                <i class="fas fa-sticky-note" style="color: #ffd700;"></i>
                <div>
                    <h3 style="font-size: 1.2rem;">Notlar</h3>
                    <p>Düzenle</p>
                </div>
            </div>
        `;

        const noteBtn = document.getElementById('vm-detail-note-btn');
        if (noteBtn) {
            noteBtn.addEventListener('click', () => {
                noteManager.openNote('vm', info.VM);
            });
        }
    }

    const grid = document.getElementById('vm-info-grid');

    const fields = [
        { key: 'VM', label: 'VM Adı' },
        { key: 'Powerstate', label: 'Durum' },
        { key: 'CPUs', label: 'vCPU' },
        { key: 'Memory', label: 'RAM (MB)' },
        { key: 'Total disk capacity MiB', label: 'Toplam Disk (MiB)' },
        { key: 'OS according to the configuration file', label: 'İşletim Sistemi' },
        { key: 'Primary IP Address', label: 'IP Adresi' },
        { key: 'DNS Name', label: 'DNS Adı' },
        { key: 'Host', label: 'Host' },
        { key: 'Cluster', label: 'Cluster' },
        { key: 'Datacenter', label: 'Datacenter' },
        { key: 'HW version', label: 'HW Versiyonu' },
        { key: 'VMware Tools Running', label: 'VMware Tools' },
        { key: 'Creation date', label: 'Oluşturulma Tarihi' },
        { key: 'Source', label: 'Kaynak' },
        { key: 'Annotation', label: 'Açıklama', wide: true }
    ];

    grid.innerHTML = fields.map(field => {
        const value = info[field.key] || '-';
        return `
            <div class="vm-info-item ${field.wide ? 'wide' : ''}">
                <label>${field.label}</label>
                <span>${value}</span>
            </div>
        `;
    }).join('');
}

function renderVMDisks(disks) {
    const tbody = document.querySelector('#vm-disks-table tbody');

    if (disks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><i class="fas fa-hdd"></i><p>Disk bulunamadı</p></td></tr>';
        return;
    }

    tbody.innerHTML = disks.map(disk => `
        <tr>
            <td>${disk.Disk || '-'}</td>
            <td>${formatNumber(disk['Capacity MiB'])}</td>
            <td>${disk.Thin ? 'Evet' : 'Hayır'}</td>
            <td>${disk.Path || '-'}</td>
            <td>${disk['Disk Mode'] || '-'}</td>
        </tr>
    `).join('');
}

function renderVMNetwork(networks) {
    const tbody = document.querySelector('#vm-network-table tbody');

    if (networks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state"><i class="fas fa-network-wired"></i><p>Network bulunamadı</p></td></tr>';
        return;
    }

    tbody.innerHTML = networks.map(net => `
        <tr>
            <td>${net['Network name'] || '-'}</td>
            <td>${net['IP Address'] || net['IP address'] || '-'}</td>
            <td>${net['MAC Address'] || net['MAC address'] || '-'}</td>
            <td>${net['Adapter type'] || '-'}</td>
        </tr>
    `).join('');
}

function renderVMSnapshots(snapshots) {
    const tbody = document.querySelector('#vm-snapshots-table tbody');

    if (snapshots.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state"><i class="fas fa-camera"></i><p>Snapshot bulunamadı</p></td></tr>';
        return;
    }

    tbody.innerHTML = snapshots.map(snap => `
        <tr>
            <td>${snap['Name'] || '-'}</td>
            <td>${snap['Date / time'] || '-'}</td>
            <td>${formatNumber(snap['Size MiB (total)'])}</td>
            <td>${snap['Description'] || '-'}</td>
        </tr>
    `).join('');
}
