// Optimization Page Module
import { fetchRightSizing, fetchDiskWaste, fetchZombieDisks } from './api.js';
import { formatNumber, truncateText, escapeHtml } from './utils.js';

// Cache for filtering and PDF export
let rightSizingData = [];
let diskWasteData = [];
let zombieDisksData = [];

export async function loadOptimization() {
    // Setup PDF dropdown toggle
    setupPDFDropdown();

    await Promise.all([
        loadSavingsSummary(),
        loadRightSizing(),
        loadDiskWaste(),
        loadZombieDisks()
    ]);
}

function setupPDFDropdown() {
    const dropdownBtn = document.getElementById('pdf-dropdown-btn');
    const dropdown = document.querySelector('.pdf-dropdown');
    const dropdownContent = document.getElementById('pdf-dropdown-content');

    if (dropdownBtn && !dropdownBtn.dataset.initialized) {
        dropdownBtn.dataset.initialized = 'true';

        dropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();

            // Position the dropdown below the button
            const rect = dropdownBtn.getBoundingClientRect();
            dropdownContent.style.top = (rect.bottom + 5) + 'px';
            dropdownContent.style.right = (window.innerWidth - rect.right) + 'px';

            dropdown.classList.toggle('show');
        });

        document.addEventListener('click', () => {
            dropdown.classList.remove('show');
        });

        // Close on scroll
        window.addEventListener('scroll', () => {
            dropdown.classList.remove('show');
        }, { passive: true });
    }
}

async function loadSavingsSummary() {
    try {
        const [rightSizing, diskWaste, zombieDisks] = await Promise.all([
            fetchRightSizing(),
            fetchDiskWaste(),
            fetchZombieDisks()
        ]);

        let cpuSavings = 0;
        let ramSavings = 0;
        let diskSavings = 0;

        // Count total unique VMs affected
        const affectedVMs = new Set();

        // 1. Right Sizing Savings
        if (rightSizing.recommendations) {
            rightSizing.recommendations.forEach(rec => {
                affectedVMs.add(rec.vm);
                if (rec.resource_type === 'vCPU') cpuSavings += rec.potential_savings;
                if (rec.resource_type === 'RAM_GB') ramSavings += rec.potential_savings;
                if (rec.resource_type === 'DISK_GB') diskSavings += rec.potential_savings;
            });
        }

        // 2. Disk Waste Savings
        if (diskWaste.total_wasted_gb) {
            diskSavings += diskWaste.total_wasted_gb;
            if (diskWaste.disks) {
                diskWaste.disks.forEach(d => affectedVMs.add(d.vm));
            }
        }

        // Update UI
        document.getElementById('summary-cpu-savings').innerHTML = `${formatNumber(cpuSavings)} <small>vCPU</small>`;
        document.getElementById('summary-ram-savings').innerHTML = `${formatNumber(ramSavings)} <small>GB</small>`;
        document.getElementById('summary-disk-savings').innerHTML = `${formatNumber(diskSavings)} <small>GB</small>`;
        document.getElementById('summary-total-vms').textContent = affectedVMs.size;

    } catch (error) {
        console.error('Error loading savings summary:', error);
    }
}

async function loadRightSizing() {
    try {
        const data = await fetchRightSizing();

        // Cache for filtering
        rightSizingData = data.recommendations || [];

        document.getElementById('rightsizing-count').textContent = data.total_recommendations || 0;

        renderRightSizingTable(rightSizingData);
    } catch (error) {
        console.error('Error loading rightsizing:', error);
    }
}

function renderRightSizingTable(recommendations) {
    const tbody = document.querySelector('#rightsizing-table tbody');

    if (!recommendations || recommendations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><i class="fas fa-check-circle"></i><p>Öneri yok veya filtre sonucu boş</p></td></tr>';
        return;
    }

    tbody.innerHTML = recommendations.map(rec => {
        let severityClass = 'badge-info';
        if (rec.severity === 'HIGH') severityClass = 'badge-danger';
        else if (rec.severity === 'MEDIUM') severityClass = 'badge-warning';

        return `
            <tr data-type="${rec.type}">
                <td><strong>${rec.vm}</strong></td>
                <td><span class="badge ${severityClass}">${rec.severity}</span></td>
                <td>${formatType(rec.type)}</td>
                <td>${rec.reason}</td>
                <td>${formatValue(rec.current_value, rec.resource_type)}</td>
                <td>${formatValue(rec.recommended_value, rec.resource_type)}</td>
                <td><strong class="text-success">${formatValue(rec.potential_savings, rec.resource_type)}</strong></td>
            </tr>
        `;
    }).join('');
}

// Filter function for quick-nav buttons
window.filterRightSizing = function (type) {
    // Scroll to rightsizing section
    document.getElementById('opt-rightsizing').scrollIntoView({ behavior: 'smooth' });

    // Update active nav pill
    document.querySelectorAll('.quick-nav .nav-pill').forEach(btn => {
        btn.classList.remove('active');
        if (type === '' && btn.textContent.includes('Tümü')) {
            btn.classList.add('active');
        } else if (btn.onclick && btn.onclick.toString().includes(`'${type}'`)) {
            btn.classList.add('active');
        }
    });

    // Filter data
    let filtered = rightSizingData;
    if (type) {
        filtered = rightSizingData.filter(rec => rec.type === type);
    }

    // Update count badge
    document.getElementById('rightsizing-count').textContent = filtered.length;

    // Render filtered table
    renderRightSizingTable(filtered);
};

async function loadDiskWaste() {
    try {
        const data = await fetchDiskWaste();

        // Cache for PDF export
        diskWasteData = data.disks || [];

        document.getElementById('disk-waste-total').textContent = `${formatNumber(data.total_wasted_gb || 0)} GB`;
        document.getElementById('disk-waste-count').textContent = data.disk_count || 0;

        const tbody = document.querySelector('#disk-waste-table tbody');
        if (!data.disks || data.disks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-check-circle"></i><p>Disk atığı tespit edilmedi</p></td></tr>';
            return;
        }

        tbody.innerHTML = data.disks.map(disk => `
            <tr>
                <td><strong>${disk.vm}</strong></td>
                <td>${disk.disk_name}</td>
                <td>${formatWasteType(disk.waste_type)}</td>
                <td>${formatNumber(disk.capacity_gb)} GB</td>
                <td><strong class="text-danger">${formatNumber(disk.estimated_waste_gb)} GB</strong></td>
                <td>${disk.thin ? 'Thin' : 'Thick'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading disk waste:', error);
    }
}

async function loadZombieDisks() {
    try {
        const data = await fetchZombieDisks();

        // Cache for PDF export
        zombieDisksData = data.disks || [];

        document.getElementById('opt-zombie-count').textContent = data.disk_count || 0;
        document.getElementById('opt-zombie-vm-count').textContent = data.vm_count || 0;

        const tbody = document.querySelector('#opt-zombie-table tbody');
        if (!data.disks || data.disks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><i class="fas fa-check-circle"></i><p>Zombie disk bulunamadı</p></td></tr>';
            return;
        }

        tbody.innerHTML = data.disks.map(disk => `
            <tr>
                <td><strong>${disk.VM || 'Bilinmiyor'}</strong></td>
                <td>${disk.Cluster || '-'}</td>
                <td>${disk.Datastore || 'Unknown'}</td>
                <td title="${escapeHtml(disk.Full_Path || disk.Path)}">
                    <code style="font-size: 0.85em;">${disk.Filename || truncateText(disk.Full_Path || disk.Path, 40)}</code>
                </td>
                <td class="text-warning">
                    <i class="fas fa-exclamation-triangle"></i> 
                    ${disk.Reason || 'Orphaned disk'}
                </td>
                <td>${disk.Source || '-'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading zombie disks:', error);
    }
}

// Helper functions
function formatLabel(key) {
    const labels = {
        'power_on_ratio': 'Power On Oranı',
        'snapshot_hygiene': 'Snapshot Hijyeni',
        'disk_efficiency': 'Disk Verimliliği',
        'reservation_efficiency': 'Rezervasyon Verimliliği',
        'vm_density': 'VM Yoğunluğu'
    };
    return labels[key] || key;
}

function formatType(type) {
    const types = {
        'POWERED_OFF_DISK': 'Kapalı VM (Disk)',
        'CPU_UNDERUTILIZED': 'Düşük CPU Kullanımı',
        'CONSOLIDATE_SNAPSHOTS': 'Snapshot Birleştirme',
        'APP_OPTIMIZATION': 'Uygulama Analizi',
        'VM_TOOLS': 'VMware Tools Sorunu',
        'ZOMBIE_RESOURCE': 'Unutulmuş Kaynak (ISO)',
        'NUMA_ALIGNMENT': 'vCPU/NUMA Hizalama',
        'LEGACY_NIC': 'Eski Ağ Kartı',
        'EOL_OS': 'EOL İşletim Sistemi',
        'OLD_SNAPSHOT': 'Eski Snapshot (>7 gün)',
        'CPU_LIMIT': 'CPU Limiti (Performans)',
        'RAM_LIMIT': 'RAM Limiti (Performans)',
        'OLD_HW_VERSION': 'Eski VM Sürümü'
    };
    return types[type] || type;
}

function formatValue(value, type) {
    if (type === 'vCPU') return `${value} vCPU`;
    if (type === 'RAM_GB') return `${value} GB RAM`;
    if (type === 'DISK_GB') return `${value} GB`;
    return value;
}

function formatWasteType(type) {
    const types = {
        'THICK_POWERED_OFF': 'Kapalı VM - Thick Disk',
        'THICK_LARGE': 'Büyük Thick Disk'
    };
    return types[type] || type;
}

// PDF Export Function - Uses backend API for proper Turkish character support
window.exportOptimizationPDF = function (reportType) {
    // Open backend PDF endpoint in new tab
    window.open(`/api/reports/pdf/${reportType}`, '_blank');

    // Close dropdown
    document.querySelector('.pdf-dropdown')?.classList.remove('show');
};
