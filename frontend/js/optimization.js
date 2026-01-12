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
        loadRightSizing()
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

    let currentType = null;

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

        currentType = type;

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
            <div class="tooltip-ai-section">
                <button class="btn-ai-advice" onclick="event.stopPropagation(); window.getOptRemediation('${type}', '${info.label}')">
                    <i class="fas fa-robot"></i> Detaylı Çözüm
                </button>
                <div class="tooltip-ai-result" id="opt-ai-result"></div>
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
        // Don't hide if mouse is over the tooltip itself
        if (e.relatedTarget && e.relatedTarget.closest('.tooltip-container')) return;
        if (badge || row) {
            tooltip.classList.remove('visible');
        }
    });

    // Keep tooltip visible when hovering over it
    tooltip.addEventListener('mouseenter', () => {
        tooltip.classList.add('visible');
    });
    tooltip.addEventListener('mouseleave', () => {
        tooltip.classList.remove('visible');
    });
}

// AI remediation for optimization types
window.getOptRemediation = async function (type, label) {
    const resultDiv = document.getElementById('opt-ai-result');
    if (!resultDiv) return;

    resultDiv.innerHTML = '<span class="loading-remediation"><i class="fas fa-spinner fa-spin"></i> Öneriler yükleniyor...</span>';

    const info = window.OPTIMIZATION_TYPES?.[type];
    const message = `VMware ${label}: ${info?.desc || ''}`;

    try {
        const response = await fetch(`/api/ai/remediation?message=${encodeURIComponent(message)}`);
        const data = await response.json();

        if (data.remediation) {
            resultDiv.innerHTML = `<div class="hc-remediation visible"><div class="hc-remediation-body">${data.remediation}</div></div>`;
        } else {
            resultDiv.innerHTML = '<span class="text-muted">Öneri oluşturulamadı.</span>';
        }
    } catch (error) {
        console.error('Optimization remediation error:', error);
        resultDiv.innerHTML = '<span class="text-danger">Hata oluştu.</span>';
    }
};

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

// Savings summary now calculated inside loadRightSizing to use the central data

async function loadRightSizing() {
    try {
        const data = await fetchRightSizing();

        // Cache for filtering
        rightSizingData = data.recommendations || [];

        // Update Summary Dashboard
        updateSummaryDashboard(rightSizingData);

        renderHierarchyFilter();

        document.getElementById('rightsizing-count').textContent = data.total_recommendations || 0;

        applyAllFilters();
    } catch (error) {
        console.error('Error loading rightsizing:', error);
    }
}

function updateSummaryDashboard(recommendations) {
    let cpuSavings = 0;
    let ramSavings = 0;
    let diskSavings = 0;
    const affectedVMs = new Set();

    recommendations.forEach(rec => {
        affectedVMs.add(rec.vm);
        if (rec.resource_type === 'vCPU') cpuSavings += rec.potential_savings;
        if (rec.resource_type === 'RAM_GB') ramSavings += rec.potential_savings;
        if (rec.resource_type === 'DISK_GB' || rec.resource_type === 'Storage') {
            diskSavings += rec.potential_savings || 0;
        }
    });

    document.getElementById('summary-cpu-savings').innerHTML = `${formatNumber(cpuSavings)} <small>vCPU</small>`;
    document.getElementById('summary-ram-savings').innerHTML = `${formatNumber(ramSavings)} <small>GB</small>`;
    document.getElementById('summary-disk-savings').innerHTML = `${formatNumber(diskSavings)} <small>GB</small>`;
    document.getElementById('summary-total-vms').textContent = affectedVMs.size;
}

function renderHierarchyFilter() {
    const container = document.getElementById('opt-hierarchy-filter');
    if (!container) return;

    const geoMap = {};
    const foundClusters = new Set();

    rightSizingData.forEach(rec => {
        const dc = rec.datacenter || 'Unknown DC';
        const cluster = rec.cluster || 'Unknown Cluster';
        if (!geoMap[dc]) geoMap[dc] = new Set();
        geoMap[dc].add(cluster);
        foundClusters.add(cluster);
    });

    // Populate selectedClusters if it was empty (initial load)
    if (selectedClusters.size === 0) {
        foundClusters.forEach(c => selectedClusters.add(c));
    }

    let html = '';
    const dcs = Object.keys(geoMap).sort();
    dcs.forEach(dc => {
        const clusters = Array.from(geoMap[dc]).sort();
        const allChecked = clusters.every(c => selectedClusters.has(c));

        html += `
            <div class="dc-group mb-2">
                <div class="dc-header">
                    <input type="checkbox" id="dc-${dc}" ${allChecked ? 'checked' : ''} onclick="window.toggleOptDC('${dc}', this)">
                    <label for="dc-${dc}"><strong>${dc}</strong></label>
                </div>
                <div class="cluster-list ms-3" id="clusters-of-${dc}">
                    ${clusters.map(cluster => `
                        <div class="cluster-item">
                            <input type="checkbox" value="${cluster}" data-dc="${dc}" ${selectedClusters.has(cluster) ? 'checked' : ''} onclick="window.toggleOptCluster(this)">
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
    'LOW_CPU_USAGE': {
        label: 'Düşük CPU Kullanımı',
        icon: 'fa-chart-line',
        color: 'info',
        desc: 'vCPU kullanımı sürekli %10\'un altında. Fazla vCPU scheduler overhead\'i artırır.',
        action: 'vCPU sayısını azaltın. Mevcut kullanım vCPU kapasitesinin çok altında.'
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
    'ZOMBIE_DISK': {
        label: 'Zombie Disk',
        icon: 'fa-ghost',
        color: 'danger',
        desc: 'Datastore\'da sahipsiz disk dosyası bulundu. Hiçbir VM\'e bağlı değil.',
        action: 'Bu disk dosyasını silin veya ilişkili VM\'i bulun.'
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
