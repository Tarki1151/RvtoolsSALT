// Reports Page Module
import { fetchPoweredOff, fetchOldSnapshots, fetchZombieDisks, fetchResourceUsage, fetchReserved } from './api.js';
import { formatNumber, truncateText, escapeHtml } from './utils.js';

export async function loadReports() {
    loadPoweredOff();
    loadReservedResources();
}

export async function loadPoweredOff() {
    try {
        const data = await fetchPoweredOff();
        document.getElementById('powered-off-count').textContent = data.length;

        // Calculate potential savings
        let totalCPU = 0, totalRAM = 0, totalDisk = 0;
        data.forEach(vm => {
            totalCPU += vm['CPUs'] || 0;
            totalRAM += vm['Memory'] || 0;
            totalDisk += vm['Total disk capacity MiB'] || 0;
        });

        document.getElementById('powered-off-cpu').textContent = formatNumber(totalCPU);
        document.getElementById('powered-off-ram').textContent = `${formatNumber(Math.round(totalRAM / 1024))} GB`;
        document.getElementById('powered-off-disk').textContent = `${formatNumber(Math.round(totalDisk / 1024))} GB`;

        const tbody = document.querySelector('#powered-off-table tbody');

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-check-circle"></i><p>Kapalı VM bulunamadı</p></td></tr>';
            return;
        }

        tbody.innerHTML = data.map(vm => `
            <tr>
                <td><strong>${vm.VM}</strong></td>
                <td>${vm.CPUs || '-'}</td>
                <td>${formatNumber(vm.Memory)}</td>
                <td>${formatNumber(vm['Total disk capacity MiB'])}</td>
                <td>${truncateText(vm['OS according to the configuration file'], 25)}</td>
                <td>${vm.Source || '-'}</td>
                <td>${truncateText(vm.Annotation, 40)}</td>
                <td>
                    <button class="btn-action" onclick="window.showVMDetail('${escapeHtml(vm.VM)}', '${vm.Source}')">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading powered off VMs:', error);
    }
}

export async function loadOldSnapshots() {
    try {
        const days = document.getElementById('snapshot-days').value || 7;
        const data = await fetchOldSnapshots(days);

        document.getElementById('old-snapshots-count').textContent = data.length;
        const tbody = document.querySelector('#old-snapshots-table tbody');

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-check-circle"></i><p>Eski snapshot bulunamadı</p></td></tr>';
            return;
        }

        tbody.innerHTML = data.map(snap => `
            <tr>
                <td><strong>${snap.VM}</strong></td>
                <td>
                    <span class="status-badge ${snap.Powerstate === 'poweredOn' ? 'on' : 'off'}">
                        ${snap.Powerstate === 'poweredOn' ? 'On' : 'Off'}
                    </span>
                </td>
                <td>${truncateText(snap.Name, 40)}</td>
                <td>${snap['Date / time']}</td>
                <td><strong style="color: var(--accent-red);">${snap['Age (days)']}</strong></td>
                <td>${formatNumber(snap['Size MiB (total)'])}</td>
                <td>${snap.Source || '-'}</td>
                <td>
                    <button class="btn-action" onclick="window.showVMDetail('${escapeHtml(snap.VM)}', '${snap.Source}')">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading old snapshots:', error);
    }
}

export async function loadZombieDisks() {
    try {
        const data = await fetchZombieDisks();

        document.getElementById('zombie-disk-count').textContent = data.disk_count;
        document.getElementById('zombie-disk-size').textContent = `${formatNumber(data.total_wasted_gb)} GB`;
        document.getElementById('zombie-vm-count').textContent = data.vm_count;

        const tbody = document.querySelector('#zombie-disks-table tbody');

        if (data.disks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-check-circle"></i><p>Zombi disk bulunamadı</p></td></tr>';
            return;
        }

        tbody.innerHTML = data.disks.map(disk => `
            <tr>
                <td><strong>${disk.VM || 'Bilinmiyor'}</strong></td>
                <td>${disk.Datastore || '-'}</td>
                <td title="${escapeHtml(disk.Path)}">${truncateText(disk.Path, 50)}</td>
                <td>${formatNumber(disk['Capacity MiB'])}</td>
                <td>${disk.Source || '-'}</td>
                <td title="${escapeHtml(disk.Message)}">${truncateText(disk.Message, 40)}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading zombie disks:', error);
    }
}

export async function loadResourceUsage() {
    try {
        const data = await fetchResourceUsage();

        // Cluster usage table
        const clusterTbody = document.querySelector('#cluster-usage-table tbody');
        clusterTbody.innerHTML = data.by_cluster.map(item => `
            <tr>
                <td>${item.Source}</td>
                <td><strong>${item.Cluster}</strong></td>
                <td>${item['vm_on']}</td>
                <td>${item['vm_off']}</td>
                <td>${formatNumber(item['cpu_on'])}</td>
                <td>${formatNumber(item['cpu_off'])}</td>
                <td>${formatNumber(item['ram_on'])}</td>
                <td>${formatNumber(item['ram_off'])}</td>
                <td>${formatNumber(item['disk_on'])}</td>
                <td>${formatNumber(item['disk_off'])}</td>
            </tr>
        `).join('');

        // Host usage table
        const hostTbody = document.querySelector('#host-usage-table tbody');
        hostTbody.innerHTML = data.by_host.map(item => `
            <tr>
                <td>${item.Source}</td>
                <td>${item.Cluster}</td>
                <td><strong>${item.Host}</strong></td>
                <td>${item['vm_on']}</td>
                <td>${item['vm_off']}</td>
                <td>${formatNumber(item['cpu_on'])}</td>
                <td>${formatNumber(item['cpu_off'])}</td>
                <td>${formatNumber(item['ram_on'])}</td>
                <td>${formatNumber(item['ram_off'])}</td>
                <td>${formatNumber(item['disk_on'])}</td>
                <td>${formatNumber(item['disk_off'])}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading resource usage:', error);
    }
}

export async function loadReservedResources() {
    try {
        const data = await fetchReserved();
        const tbody = document.querySelector('#reserved-table tbody');
        if (!tbody) return;

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-check-circle"></i><p>Reserved kaynak bulunamadı.</p></td></tr>';
            return;
        }

        tbody.innerHTML = data.map(vm => `
            <tr>
                <td><strong>${vm.VM}</strong></td>
                <td>
                    <span class="status-badge ${vm.Powerstate === 'poweredOn' ? 'on' : 'off'}">
                        ${vm.Powerstate === 'poweredOn' ? 'On' : 'Off'}
                    </span>
                </td>
                <td>${formatNumber(vm.mem_reserved_mb)} (${vm.mem_limit})</td>
                <td>${formatNumber(vm.cpu_reserved_mhz)} (${vm.cpu_limit})</td>
                <td>${vm.Cluster || '-'}</td>
                <td>${vm.Host || '-'}</td>
                <td>${vm.Source || '-'}</td>
                <td>
                    <button class="btn-action" onclick="window.showVMDetail('${escapeHtml(vm.VM)}', '${vm.Source}')">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading reserved resources:', error);
    }
}
