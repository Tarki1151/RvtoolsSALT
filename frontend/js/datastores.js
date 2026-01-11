// Hosts and Datastores Module
import { fetchDatastores } from './api.js';
import { currentSource } from './config.js';
import { formatNumber } from './utils.js';


export async function loadDatastores() {
    try {
        const datastores = await fetchDatastores(currentSource);
        const tbody = document.querySelector('#datastores-table tbody');

        if (datastores.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><i class="fas fa-database"></i><p>Datastore bulunamadı</p></td></tr>';
            return;
        }

        tbody.innerHTML = datastores.map(ds => {
            const capacity = ds['Capacity MiB'] || 0;
            const free = ds['Free MiB'] || 0;
            const used = capacity > 0 ? ((capacity - free) / capacity * 100).toFixed(1) : 0;

            return `
                <tr>
                    <td><strong>${ds.Name}</strong></td>
                    <td>${ds.Type || '-'}</td>
                    <td>${formatNumber(capacity)}</td>
                    <td>${formatNumber(free)}</td>
                    <td>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${used}%"></div>
                            <span class="progress-text">${used}%</span>
                        </div>
                    </td>
                    <td>${ds['# VMs'] || 0}</td>
                    <td>${ds['# Hosts'] || 0}</td>
                    <td>${ds.Source || '-'}</td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading datastores:', error);
    }
}
