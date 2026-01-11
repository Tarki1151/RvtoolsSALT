// Risks Module
let allRisks = [];
let currentCategory = 'all';

export async function loadRisks() {
    const tbody = document.querySelector('#risks-table tbody');
    const aiContent = document.getElementById('risk-ai-content');

    // Show loading states
    tbody.innerHTML = '<tr><td colspan="6" class="text-center p-5"><div class="spinner-border text-primary"></div><p class="mt-2">Riskler analiz ediliyor...</p></td></tr>';
    aiContent.innerHTML = '<div class="loading">AI analiz motoru verileri işliyor (Grok-4)...</div>';

    try {
        const response = await fetch('/api/risks');
        const data = await response.json();

        if (data.error) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Hata: ${data.error}</td></tr>`;
            return;
        }

        allRisks = data.risks || [];

        // Update Stats
        document.getElementById('risk-stat-critical').textContent = data.stats.critical_count;
        document.getElementById('risk-stat-high').textContent = data.stats.high_count;
        document.getElementById('risk-stat-medium').textContent = data.stats.medium_count;

        // Update Tab Counts
        updateTabCounts();

        // Render AI Insight
        if (window.marked && window.marked.parse) {
            aiContent.innerHTML = window.marked.parse(data.ai_insight);
        } else {
            aiContent.innerHTML = data.ai_insight.replace(/\n/g, '<br>');
        }

        // Initialize Tabs
        initRiskTabs();

        // Initialize Modal Close
        initRiskModal();

        // Initial Render
        renderRiskTable();

    } catch (error) {
        console.error('Error loading risks:', error);
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Veri yüklenemedi.</td></tr>';
    }
}

function updateTabCounts() {
    document.getElementById('risk-count-all').textContent = allRisks.length;
    document.getElementById('risk-count-soft').textContent = allRisks.filter(r => r.category === 'Software').length;
    document.getElementById('risk-count-hard').textContent = allRisks.filter(r => r.category === 'Hardware').length;
    document.getElementById('risk-count-hyp').textContent = allRisks.filter(r => r.category === 'Hypervisor').length;
    document.getElementById('risk-count-ops').textContent = allRisks.filter(r => r.category === 'Operation').length;
}

function initRiskTabs() {
    document.querySelectorAll('.risk-tab-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.risk-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.riskCat;
            renderRiskTable();
        };
    });
}

function renderRiskTable() {
    const tbody = document.querySelector('#risks-table tbody');
    const filteredRisks = currentCategory === 'all'
        ? allRisks
        : allRisks.filter(r => r.category === currentCategory);

    if (filteredRisks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center p-5">Bu kategoride risk tespit edilmedi.</td></tr>';
        return;
    }

    tbody.innerHTML = filteredRisks.map((risk, index) => `
        <tr class="risk-row risk-row-${risk.severity.toLowerCase()}" onclick="window.showRiskDetail(${index}, '${currentCategory}', event)">
            <td><strong>${risk.target}</strong></td>
            <td><span class="badge bg-secondary">${risk.category}</span></td>
            <td><span class="status-badge ${getSeverityClass(risk.severity)}">${risk.severity}</span></td>
            <td class="text-truncate-2">${risk.description}</td>
            <td class="text-truncate-2">${risk.recommendation}</td>
            <td class="small text-muted">${risk.source}</td>
        </tr>
    `).join('');
}

window.showRiskDetail = (index, cat, event) => {
    // Clear previous active rows
    document.querySelectorAll('#risks-table tr').forEach(r => r.classList.remove('active-row'));
    // Add active class to clicked row
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active-row');
    }

    const filtered = cat === 'all' ? allRisks : allRisks.filter(r => r.category === cat);
    const risk = filtered[index];
    if (!risk) return;

    const modal = document.getElementById('risk-detail-modal');
    const body = document.getElementById('risk-detail-body');

    body.innerHTML = `
        <div class="risk-detail-header mb-4">
            <div class="d-flex justify-content-between align-items-center">
                <span class="status-badge ${getSeverityClass(risk.severity)} mb-2">${risk.severity} Risk</span>
                <span class="text-muted small">${risk.source}</span>
            </div>
            <h1 class="h3 mt-2">${risk.target}</h1>
            <span class="badge bg-primary">${risk.category} / ${risk.type}</span>
        </div>
        
        <div class="risk-detail-section mb-4">
            <h4 class="h6 text-uppercase fw-bold text-muted mb-2"> <i class="fas fa-exclamation-circle me-2"></i> Risk Açıklaması</h4>
            <div class="risk-detail-box p-3 rounded bg-dark-soft">
                ${risk.description}
            </div>
        </div>

        <div class="risk-detail-section mb-4">
            <h4 class="h6 text-uppercase fw-bold text-muted mb-2"> <i class="fas fa-lightbulb me-2"></i> Öneri / Çözüm</h4>
            <div class="risk-detail-box p-3 rounded bg-teal-soft">
                ${risk.recommendation}
            </div>
        </div>
    `;

    modal.style.display = 'block';
};

function initRiskModal() {
    const modal = document.getElementById('risk-detail-modal');
    const closeBtn = document.getElementById('risk-modal-close');

    closeBtn.onclick = () => modal.style.display = 'none';

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') modal.style.display = 'none';
    });

    window.onclick = (event) => {
        if (event.target == modal) modal.style.display = 'none';
    };
}

function getSeverityClass(severity) {
    switch (severity.toLowerCase()) {
        case 'critical': return 'off';
        case 'high': return 'text-warning';
        case 'medium': return 'on';
        default: return '';
    }
}
