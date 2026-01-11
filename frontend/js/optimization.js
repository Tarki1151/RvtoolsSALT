// Optimization Page Module
import { fetchRightSizing, fetchDiskWaste, fetchZombieDisks } from './api.js';
import { formatNumber, truncateText, escapeHtml } from './utils.js';

// Cache for filtering and PDF export
let allPools = [];
let rightSizingData = [];
let diskWasteData = [];
let zombieDisksData = [];
let selectedType = '';
let selectedClusters = new Set();

export async function loadOptimization() {
    // Setup PDF dropdown toggle
    setupPDFDropdown();

    // Setup custom tooltips
    setupTooltips();

    await Promise.all([
        loadSavingsSummary(),
        loadRightSizing(),
        loadDiskWaste(),
        loadZombieDisks()
    ]);
}

// Custom rich tooltip for optimization types
function setupTooltips() {
    // Remove existing tooltip container if any
    document.querySelector('.tooltip-container')?.remove();

    // Create tooltip container
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip-container';
    document.body.appendChild(tooltip);

    // Event delegation for opt-type-badge OR rightsizing table rows
    document.addEventListener('mouseover', (e) => {
        // Check for badge first
        let badge = e.target.closest('.opt-type-badge');
        let type = badge?.dataset?.type;

        // If no badge, check for table row in rightsizing table
        if (!type) {
            const row = e.target.closest('#rightsizing-table tbody tr');
            if (row) {
                type = row.dataset.type;
            }
        }

        if (!type) return;

        const info = window.OPTIMIZATION_TYPES?.[type];
        if (!info) return;

        // Build rich tooltip content
        let vmInfoHtml = '';
        const row = badge ? badge.closest('tr') : e.target.closest('#rightsizing-table tbody tr');
        if (row && row.dataset.vm) {
            vmInfoHtml = `
                <div class="tooltip-vm-context">
                    <i class="fas fa-info-circle"></i>
                    <span><strong>DC:</strong> ${row.dataset.dc || '-'}</span> | 
                    <span><strong>Cluster:</strong> ${row.dataset.cluster || '-'}</span>
                </div>
            `;
        }

        tooltip.innerHTML = `
            <div class="tooltip-title">
                <i class="fas ${info.icon}"></i>
                ${info.label}
            </div>
            ${vmInfoHtml}
            <div class="tooltip-desc">${info.desc}</div>
            <div class="tooltip-action">
                <strong>📋 Öneri:</strong> ${info.action}
            </div>
        `;

        // Position tooltip near mouse
        const target = badge || e.target.closest('#rightsizing-table tbody tr');
        if (target) {
            const rect = target.getBoundingClientRect();
            tooltip.style.left = Math.min(rect.left + 20, window.innerWidth - 370) + 'px';
            tooltip.style.top = (rect.bottom + 8) + 'px';
            tooltip.classList.add('visible');
        }
    });

    document.addEventListener('mouseout', (e) => {
        const badge = e.target.closest('.opt-type-badge');
        const row = e.target.closest('#rightsizing-table tbody tr');
        if (badge || row) {
            tooltip.classList.remove('visible');
        }
    });
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

        renderHierarchyFilter();

        document.getElementById('rightsizing-count').textContent = data.total_recommendations || 0;

        applyAllFilters();
    } catch (error) {
        console.error('Error loading rightsizing:', error);
    }
}

function renderHierarchyFilter() {
    const container = document.getElementById('opt-hierarchy-filter');
    if (!container) return;

    const geoMap = {};
    rightSizingData.forEach(rec => {
        const dc = rec.datacenter || 'Unknown DC';
        const cluster = rec.cluster || 'Unknown Cluster';
        if (!geoMap[dc]) geoMap[dc] = new Set();
        geoMap[dc].add(cluster);
    });

    let html = '';
    const dcs = Object.keys(geoMap).sort();

    // Default: Select all clusters initially
    selectedClusters.clear();
    dcs.forEach(dc => {
        geoMap[dc].forEach(cluster => selectedClusters.add(cluster));
    });

    dcs.forEach(dc => {
        const clusters = Array.from(geoMap[dc]).sort();
        html += `
            <div class="hierarchy-item">
                <div class="dc-item">
                    <input type="checkbox" id="dc-${dc}" checked onclick="window.toggleOptDC('${dc}', this)">
                    <label for="dc-${dc}">${dc}</label>
                </div>
                <div class="cluster-list" id="clusters-of-${dc}">
                    ${clusters.map(cluster => `
                        <div class="cluster-item">
                            <input type="checkbox" name="opt-cluster" value="${cluster}" checked 
                                   data-dc="${dc}" onclick="window.toggleOptCluster(this)">
                            <label title="${cluster}">${cluster}</label>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html || '<div class="p-2 text-muted small">Konum verisi yok.</div>';
}

window.toggleOptDC = (dc, checkbox) => {
    const clusterChecks = document.querySelectorAll(`.cluster-list#clusters-of-${dc.replace(/'/g, "\\'")} input[type="checkbox"]`);
    clusterChecks.forEach(cb => {
        cb.checked = checkbox.checked;
        if (checkbox.checked) selectedClusters.add(cb.value);
        else selectedClusters.delete(cb.value);
    });
    applyAllFilters();
};

window.toggleOptCluster = (checkbox) => {
    if (checkbox.checked) selectedClusters.add(checkbox.value);
    else selectedClusters.delete(checkbox.value);

    // Update DC parent if all clusters are unchecked or any unchecked
    const dc = checkbox.dataset.dc;
    const dcCheck = document.getElementById(`dc-${dc}`);
    const dcClusters = document.querySelectorAll(`.cluster-item input[data-dc="${dc}"]`);
    const allChecked = Array.from(dcClusters).every(cb => cb.checked);
    if (dcCheck) dcCheck.checked = allChecked;

    applyAllFilters();
};

function applyAllFilters() {
    let filtered = rightSizingData;

    // Filter by Type
    if (selectedType) {
        filtered = filtered.filter(rec => rec.type === selectedType);
    }

    // Filter by Cluster
    filtered = filtered.filter(rec => selectedClusters.has(rec.cluster || 'Unknown Cluster'));

    document.getElementById('rightsizing-count').textContent = filtered.length;
    renderRightSizingTable(filtered);
}

function renderRightSizingTable(recommendations) {
    const tbody = document.querySelector('#rightsizing-table tbody');

    if (!recommendations || recommendations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><i class="fas fa-check-circle"></i><p>Öneri yok veya filtre sonucu boş</p></td></tr>';
        return;
    }

    tbody.innerHTML = recommendations.map(rec => {
        let severityClass = 'badge-info';
        if (rec.severity === 'CRITICAL' || rec.severity === 'HIGH') severityClass = 'badge-danger';
        else if (rec.severity === 'MEDIUM') severityClass = 'badge-warning';
        else if (rec.severity === 'LOW') severityClass = 'badge-success';

        return `
            <tr data-type="${rec.type}" data-vm="${rec.vm}" data-cluster="${rec.cluster || '-'}" data-dc="${rec.datacenter || '-'}" 
                onclick="window.showVMDetail('${escapeHtml(rec.vm)}', '${rec.source}')" style="cursor: pointer;">
                <td><strong>${rec.vm}</strong></td>
                <td><small class="text-muted">${rec.host || '-'}</small></td>
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
    selectedType = type;

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

    applyAllFilters();
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
            <tr onclick="window.showVMDetail('${escapeHtml(disk.vm)}', '${disk.source}')" style="cursor: pointer;">
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
            <tr ${disk.VM && disk.VM !== 'Bilinmiyor' ? `onclick="window.showVMDetail('${escapeHtml(disk.VM)}', '${disk.Source}')" style="cursor: pointer;"` : ''}>
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

// Optimization type definitions with explanations
const OPTIMIZATION_TYPES = {
    'POWERED_OFF_DISK': {
        label: 'Kapalı VM (Disk)',
        icon: 'fa-power-off',
        color: 'warning',
        desc: 'VM kapalı durumda ancak disk alanı hala kullanılıyor.',
        action: 'VM artık gerekmiyorsa silin veya disk\'i arşivleyin. DR için gerekliyse belgelendirin.'
    },
    'CPU_UNDERUTILIZED': {
        label: 'Düşük CPU Kullanımı',
        icon: 'fa-chart-line',
        color: 'info',
        desc: 'vCPU kullanımı sürekli %50\'nin altında. Fazla vCPU scheduler overhead\'i artırır.',
        action: 'vCPU sayısını azaltın. NUMA uyumu için: Cores per Socket = Host NUMA core sayısına bölünebilir olmalı (örn: 8 vCPU = 1x8 veya 2x4).'
    },
    'CONSOLIDATE_SNAPSHOTS': {
        label: 'Snapshot Birleştirme',
        icon: 'fa-layer-group',
        color: 'warning',
        desc: 'Birden fazla snapshot zinciri mevcut. I/O performansını düşürür.',
        action: 'Snapshot\'ları birleştirin veya gereksizleri silin. Her snapshot I/O gecikmesi ekler.'
    },
    'APP_OPTIMIZATION': {
        label: 'Uygulama Analizi',
        icon: 'fa-cogs',
        color: 'info',
        desc: 'Uygulama türüne göre kaynak optimizasyonu önerisi.',
        action: 'Uygulamanın gerçek ihtiyaçlarına göre kaynakları ayarlayın.'
    },
    'VM_TOOLS': {
        label: 'VMware Tools',
        icon: 'fa-tools',
        color: 'warning',
        desc: 'VMware Tools kurulu değil veya eski sürüm.',
        action: 'Güncel VMware Tools kurun. Performans ve yönetim özelliklerini etkiler.'
    },
    'ZOMBIE_RESOURCE': {
        label: 'Unutulmuş Kaynak',
        icon: 'fa-ghost',
        color: 'warning',
        desc: 'Bağlı CD/ISO veya kullanılmayan cihaz tespit edildi.',
        action: 'Bağlı medyayı çıkarın. vMotion\'ı engelleyebilir ve güvenlik riski oluşturur.'
    },
    'NUMA_ALIGNMENT': {
        label: 'NUMA Hizalama',
        icon: 'fa-microchip',
        color: 'info',
        desc: 'Tek sayıda vCPU atanmış. NUMA optimizasyonu bozuluyor. Modern CPU\'larda her NUMA node çift sayıda core içerir.',
        action: 'Örnek: 5 vCPU → 6 vCPU yapın. VM Settings > CPU > Cores per Socket ayarını fiziksel NUMA node core sayısına bölünebilir yapın. Örn: 8 vCPU için 2 socket x 4 core veya 1 socket x 8 core kullanın.'
    },
    'LEGACY_NIC': {
        label: 'Eski Ağ Kartı',
        icon: 'fa-ethernet',
        color: 'warning',
        desc: 'E1000 gibi eski NIC kullanılıyor. VMXNET3\'e göre yavaş.',
        action: 'VMXNET3\'e geçin. 10x daha iyi performans, düşük CPU kullanımı.'
    },
    'EOL_OS': {
        label: 'EOL İşletim Sistemi',
        icon: 'fa-skull',
        color: 'danger',
        desc: 'İşletim sistemi artık desteklenmiyor (End-of-Life).',
        action: 'Güvenlik yamaları almıyorsunuz! Acil olarak yeni OS\'e migrate edin.'
    },
    'OLD_SNAPSHOT': {
        label: 'Eski Snapshot',
        icon: 'fa-camera',
        color: 'warning',
        desc: 'Snapshot 7 günden eski. Performansı düşürür, disk büyümesine neden olur.',
        action: 'Artık gerekmiyorsa silin. Snapshot uzun süreli yedek değildir.'
    },
    'CPU_LIMIT': {
        label: 'CPU Limiti',
        icon: 'fa-tachometer-alt',
        color: 'warning',
        desc: 'CPU limit ayarlanmış. Kaynak olsa bile VM kullanamıyor.',
        action: 'Limiti kaldırın. Reservation tercih edilir, limit performans sorunlarına yol açar.'
    },
    'RAM_LIMIT': {
        label: 'RAM Limiti',
        icon: 'fa-tachometer-alt',
        color: 'warning',
        desc: 'Memory limit ayarlanmış. Swapping\'e zorluyor.',
        action: 'Limiti kaldırın. Memory limit neredeyse hiçbir zaman doğru çözüm değildir.'
    },
    'OLD_HW_VERSION': {
        label: 'Eski VM Sürümü',
        icon: 'fa-box',
        color: 'info',
        desc: 'VM hardware versiyonu ESXi\'nin desteklediğinden düşük.',
        action: 'VM\'i kapatıp hardware upgrade yapın. Yeni özellikler ve performans kazanın.'
    },
    'MEMORY_BALLOON': {
        label: 'Memory Ballooning',
        icon: 'fa-exclamation-triangle',
        color: 'danger',
        desc: 'Host RAM\'i yetersiz, VM\'den memory geri alınıyor. Kritik performans sorunu!',
        action: 'Host\'a RAM ekleyin veya VM\'leri başka host\'a taşıyın. Acil müdahale gerekli!'
    },
    'MEMORY_SWAP': {
        label: 'Memory Swapping',
        icon: 'fa-exclamation-circle',
        color: 'danger',
        desc: 'VM memory\'si diske swap ediliyor. Ciddi performans kaybı!',
        action: 'Host\'a RAM ekleyin veya VM\'leri dengeleyin. Swap = çok yavaş performans.'
    },
    'HOST_CPU_OVERCOMMIT': {
        label: 'Host CPU Overcommit',
        icon: 'fa-server',
        color: 'warning',
        desc: 'vCPU:pCore oranı eşik değerin üstünde. CPU contention riski.',
        action: 'VM\'leri başka host\'lara dağıtın veya vCPU\'ları azaltın.'
    },
    'DATASTORE_LOW_SPACE': {
        label: 'Datastore Düşük Alan',
        icon: 'fa-database',
        color: 'danger',
        desc: 'Datastore\'da boş alan kritik seviyede. Out-of-space riski!',
        action: 'Acil temizlik yapın: eski snapshot, orphan disk, template. Veya kapasite ekleyin.'
    },
    'DATASTORE_OVERCOMMIT': {
        label: 'Datastore Overcommit',
        icon: 'fa-database',
        color: 'warning',
        desc: 'Provisioned alan fiziksel kapasiteyi aşıyor.',
        action: 'Thin provisioned disk\'ler büyüdükçe yer kalmayabilir. İzleyin veya kapasite ekleyin.'
    },
    'FLOPPY_CONNECTED': {
        label: 'Floppy Bağlı',
        icon: 'fa-save',
        color: 'info',
        desc: 'Eski floppy sürücü bağlı. Güvenlik riski ve migration engelleyebilir.',
        action: 'Floppy\'yi disconnect edin veya kaldırın.'
    },
    'STORAGE_OVERPROVISIONED': {
        label: 'Storage Fazla Provision',
        icon: 'fa-hdd',
        color: 'info',
        desc: 'Provisioned alan, kullanılan alandan çok yüksek.',
        action: 'Disk\'i küçültün veya thin provisioning kullanın. Gereksiz kapasite tutmayın.'
    }
};

function formatType(type) {
    const info = OPTIMIZATION_TYPES[type];
    if (!info) return type;

    // Return span with tooltip data attributes
    return `<span class="opt-type-badge" data-type="${type}" title="${info.desc}\n\n📋 Öneri: ${info.action}">
        <i class="fas ${info.icon}"></i> ${info.label}
    </span>`;
}

// Expose for potential external use
window.OPTIMIZATION_TYPES = OPTIMIZATION_TYPES;

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
