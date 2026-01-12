// DR Analysis Module
import { formatNumber } from './utils.js';

export async function loadDR() {
    const container = document.querySelector('.dr-container');
    if (!container) return;

    // Show loading states
    document.getElementById('dr-dc-flows').innerHTML = '<div class="loading">Yükleniyor...</div>';
    document.getElementById('dr-sites').innerHTML = '<div class="loading">Yükleniyor...</div>';

    try {
        const response = await fetch('/api/dr-analysis');
        const data = await response.json();

        if (data.error) {
            console.error('DR Analysis error:', data.error);
            document.getElementById('dr-dc-flows').innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        // Update summary stats
        updateSummary(data.summary);

        // Render DC flows
        renderDCFlows(data.dc_flows);

        // Render DR sites capacity
        renderDRSites(data.dr_sites);

        // Render matched pairs table
        renderMatchedPairs(data.matched_pairs);

        // Render unprotected critical VMs
        renderUnprotectedVMs(data.unprotected_critical);

    } catch (error) {
        console.error('Error loading DR analysis:', error);
        document.getElementById('dr-dc-flows').innerHTML = '<div class="error">Veri yüklenemedi</div>';
    }
}

function updateSummary(summary) {
    document.getElementById('dr-total-production').textContent = formatNumber(summary.total_production_vms);
    document.getElementById('dr-total-replicated').textContent = formatNumber(summary.total_replicated_vms);
    document.getElementById('dr-coverage-pct').textContent = `${summary.replication_coverage_pct}%`;
    document.getElementById('dr-unprotected').textContent = formatNumber(summary.unprotected_vm_count);
}

function renderDCFlows(flows) {
    const container = document.getElementById('dr-dc-flows');

    if (!flows || flows.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-info-circle"></i><p>Replikasyon akışı tespit edilmedi</p></div>';
        return;
    }

    container.innerHTML = flows.map(flow => `
        <div class="dr-flow-card">
            <div class="dr-flow-header">
                <span class="dr-flow-source">${flow.source_dc || 'Bilinmiyor'}</span>
                <i class="fas fa-arrow-right"></i>
                <span class="dr-flow-target">${flow.target_dc || 'Bilinmiyor'}</span>
            </div>
            <div class="dr-flow-stats">
                <div class="dr-flow-stat">
                    <span class="value">${flow.vm_count}</span>
                    <span class="label">VM</span>
                </div>
                <div class="dr-flow-stat">
                    <span class="value">${flow.total_vcpu}</span>
                    <span class="label">vCPU</span>
                </div>
                <div class="dr-flow-stat">
                    <span class="value">${formatNumber(flow.total_memory_gb)}</span>
                    <span class="label">GB RAM</span>
                </div>
                <div class="dr-flow-stat">
                    <span class="value">${formatNumber(flow.total_disk_gb)}</span>
                    <span class="label">GB Disk</span>
                </div>
            </div>
        </div>
    `).join('');
}

function renderDRSites(sites) {
    const container = document.getElementById('dr-sites');

    if (!sites || sites.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-info-circle"></i><p>DR site tespit edilmedi</p></div>';
        return;
    }

    container.innerHTML = sites.map(site => {
        const readinessClass = site.readiness_score >= 80 ? 'good' : site.readiness_score >= 50 ? 'warning' : 'critical';
        const feasibleIcon = site.failover_feasible ? 'fa-check-circle text-success' : 'fa-times-circle text-danger';
        const feasibleText = site.failover_feasible ? 'Failover Uygun' : 'Kapasite Yetersiz';

        return `
            <div class="dr-site-card">
                <div class="dr-site-header">
                    <h4><i class="fas fa-building"></i> ${site.datacenter}</h4>
                    <span class="dr-readiness-score ${readinessClass}">${site.readiness_score}%</span>
                </div>
                
                <div class="dr-site-meta">
                    <span><i class="fas fa-server"></i> ${site.host_count} Host</span>
                    <span><i class="fas fa-copy"></i> ${site.replicated_vm_count} VM</span>
                </div>

                <div class="dr-site-capacity">
                    <div class="dr-capacity-row">
                        <span class="label">CPU Kapasitesi</span>
                        <div class="dr-capacity-bar">
                            <div class="dr-capacity-used" style="width: ${Math.min(site.current_cpu_usage_pct, 100)}%"></div>
                            <div class="dr-capacity-required" style="width: ${Math.min(site.cpu_capacity_ratio, 100)}%"></div>
                        </div>
                        <span class="value">${site.current_cpu_usage_pct}% / +${site.cpu_capacity_ratio}%</span>
                    </div>
                    <div class="dr-capacity-row">
                        <span class="label">Memory Kapasitesi</span>
                        <div class="dr-capacity-bar">
                            <div class="dr-capacity-used" style="width: ${Math.min(site.current_mem_usage_pct, 100)}%"></div>
                            <div class="dr-capacity-required" style="width: ${Math.min(site.mem_capacity_ratio, 100)}%"></div>
                        </div>
                        <span class="value">${site.current_mem_usage_pct}% / +${site.mem_capacity_ratio}%</span>
                    </div>
                </div>

                <div class="dr-site-requirements">
                    <span><strong>Gerekli:</strong> ${site.required_vcpu} vCPU, ${formatNumber(site.required_memory_gb)} GB RAM</span>
                </div>

                <div class="dr-site-feasibility ${site.failover_feasible ? 'feasible' : 'not-feasible'}">
                    <i class="fas ${feasibleIcon}"></i>
                    <span>${feasibleText}</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderMatchedPairs(pairs) {
    const tbody = document.querySelector('#dr-pairs-table tbody');

    if (!pairs || pairs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-state"><i class="fas fa-info-circle"></i><p>Eşleştirilmiş VM çifti bulunamadı</p></td></tr>';
        return;
    }

    tbody.innerHTML = pairs.map(pair => `
        <tr>
            <td><strong>${pair.production_vm}</strong></td>
            <td>${pair.production_dc || '-'}</td>
            <td>${pair.production_cluster || '-'}</td>
            <td><span class="badge bg-secondary">${pair.replica_vm}</span></td>
            <td>${pair.replica_dc || '-'}</td>
            <td>${pair.replica_cluster || '-'}</td>
            <td>${pair.vcpu}</td>
            <td>${formatNumber(pair.memory_gb)}</td>
            <td>${formatNumber(pair.disk_gb)}</td>
        </tr>
    `).join('');
}

function renderUnprotectedVMs(vms) {
    const tbody = document.querySelector('#dr-unprotected-table tbody');

    if (!vms || vms.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><i class="fas fa-check-circle text-success"></i><p>Tüm kritik VM\'ler korunuyor</p></td></tr>';
        return;
    }

    tbody.innerHTML = vms.map(vm => `
        <tr class="warning-row">
            <td><strong>${vm.VM}</strong></td>
            <td>${vm.Datacenter || '-'}</td>
            <td>${vm.Cluster || '-'}</td>
            <td>${vm.vcpu}</td>
            <td>${formatNumber(vm.memory_gb)}</td>
            <td>${formatNumber(vm.disk_gb)}</td>
            <td>${vm.OS ? vm.OS.substring(0, 30) + (vm.OS.length > 30 ? '...' : '') : '-'}</td>
        </tr>
    `).join('');
}
