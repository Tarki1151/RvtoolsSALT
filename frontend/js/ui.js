// UI Management Layer
import { currentSource, setCurrentSource } from './config.js';
import { loadDashboard } from './dashboard.js';
import { loadVMs } from './vms.js';
import { loadReports } from './reports.js';
import { loadInventory } from './inventory.js';
import { loadHosts, loadDatastores } from './hosts.js';
import { loadOptimization } from './optimization.js';

export function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            navigateTo(page);
        });
    });
}

export function navigateTo(page) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    // Remove active from nav
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));

    // Show selected page
    document.getElementById(`page-${page}`).classList.add('active');
    document.querySelector(`[data-page="${page}"]`).classList.add('active');

    // Update page title
    const titles = {
        dashboard: 'Dashboard',
        vms: 'Virtual Machines',
        reports: 'Reports',
        inventory: 'Inventory',
        hosts: 'Hosts',
        datastores: 'Datastores',
        optimization: 'Optimization'
    };
    document.getElementById('page-title').textContent = titles[page] || page;

    // Show/hide PDF button (only on optimization page)
    const pdfDropdown = document.getElementById('header-pdf-dropdown');
    if (pdfDropdown) {
        pdfDropdown.style.display = page === 'optimization' ? 'block' : 'none';
    }

    // Load page data
    switch (page) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'vms':
            loadVMs();
            break;
        case 'reports':
            loadReports();
            break;
        case 'inventory':
            loadInventory();
            break;
        case 'hosts':
            loadHosts();
            break;
        case 'datastores':
            loadDatastores();
            break;
        case 'optimization':
            loadOptimization();
            break;
    }
}

export function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            const parent = btn.closest('.page');

            // Remove active from all tabs in this page
            parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            parent.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            // Activate clicked tab
            btn.classList.add('active');
            parent.querySelector(`#${tabId}`).classList.add('active');

            // Load tab data if needed
            loadTabData(tabId);
        });
    });
}

function loadTabData(tabId) {
    const { loadOldSnapshots, loadZombieDisks, loadResourceUsage } = require('./reports.js');

    switch (tabId) {
        case 'tab-old-snapshots':
            loadOldSnapshots();
            break;
        case 'tab-zombie-disks':
            loadZombieDisks();
            break;
        case 'tab-resource-usage':
            loadResourceUsage();
            break;
    }
}

export function initModal() {
    const modal = document.getElementById('vm-modal');
    const closeBtn = document.getElementById('modal-close');

    closeBtn?.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
}

export function initVMTabs() {
    document.querySelectorAll('.vm-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.vmtab;

            document.querySelectorAll('.vm-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.vm-tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
}

export function initSorting() {
    // Use event delegation - attach to document, filter by .sortable
    document.addEventListener('click', (e) => {
        const th = e.target.closest('.sortable');
        if (!th) return;

        const table = th.closest('table');
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));
        if (rows.length === 0) return;

        const isAsc = th.classList.contains('asc');

        // Reset all headers in this table
        table.querySelectorAll('.sortable').forEach(header => {
            header.classList.remove('asc', 'desc');
            const icon = header.querySelector('i');
            if (icon) icon.className = 'fas fa-sort';
        });

        // Set current header
        th.classList.add(isAsc ? 'desc' : 'asc');
        const icon = th.querySelector('i');
        if (icon) icon.className = `fas fa-sort-${isAsc ? 'down' : 'up'}`;

        const direction = !isAsc ? 1 : -1;
        const index = Array.from(th.parentNode.children).indexOf(th);

        rows.sort((a, b) => {
            // Skip if cell doesn't exist
            if (!a.children[index] || !b.children[index]) return 0;

            let valA = a.children[index].textContent.trim();
            let valB = b.children[index].textContent.trim();

            // Try numeric sort
            const numA = parseFloat(valA.replace(/\./g, '').replace(/,/g, '.').replace(/[^\d.-]/g, ''));
            const numB = parseFloat(valB.replace(/\./g, '').replace(/,/g, '.').replace(/[^\d.-]/g, ''));

            if (!isNaN(numA) && !isNaN(numB) && valA.match(/\d/) && valB.match(/\d/)) {
                return (numA - numB) * direction;
            }

            // String sort (Turkish locale)
            return valA.localeCompare(valB, 'tr') * direction;
        });

        rows.forEach(row => tbody.appendChild(row));
    });
}
