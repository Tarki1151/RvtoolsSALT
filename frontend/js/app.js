// Main Application Orchestrator
import { elements, setCurrentSource } from './config.js';
import { initTabs, initModal, initVMTabs, initSorting } from './ui.js';
import { loadDashboard } from './dashboard.js';
import { loadVMs } from './vms.js';
import { loadReports, loadOldSnapshots, loadZombieDisks, loadResourceUsage } from './reports.js';
import { fetchSources } from './api.js';
import { showVMDetail } from './vmDetail.js';
import { toggleTree, loadInventoryDetail } from './inventory.js';

// Make functions globally accessible for onclick handlers
window.showVMDetail = showVMDetail;
window.toggleTree = toggleTree;
window.loadInventoryDetail = loadInventoryDetail;

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
    console.log('RVTools Visualization Dashboard - Loading...');

    // Cache DOM elements
    elements.sourceFilter = document.getElementById('source-filter');
    elements.modal = document.getElementById('vm-modal');
    elements.modalClose = document.getElementById('modal-close');

    // Initialize UI components
    initNavigation();
    initTabs();
    initModal();
    initVMTabs();
    initSorting();
    initFilters();

    // Load initial data
    await loadInitialData();

    console.log('RVTools Visualization Dashboard - Ready');
});

function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', async (e) => {
            e.preventDefault();
            const page = item.dataset.page;

            // Hide all & remove active
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));

            // Show selected
            document.getElementById(`page-${page}`).classList.add('active');
            item.classList.add('active');

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

            // Load data
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
                    const { loadInventory } = await import('./inventory.js');
                    loadInventory();
                    break;
                case 'hosts':
                    const { loadHosts } = await import('./hosts.js');
                    loadHosts();
                    break;
                case 'datastores':
                    const { loadDatastores } = await import('./hosts.js');
                    loadDatastores();
                    break;
                case 'optimization':
                    const { loadOptimization } = await import('./optimization.js');
                    loadOptimization();
                    break;
            }
        });
    });
}

async function loadInitialData() {
    try {
        const sources = await fetchSources();

        elements.sourceFilter.innerHTML = '<option value="">Tüm Kaynaklar</option>';
        sources.forEach(source => {
            elements.sourceFilter.innerHTML += `<option value="${source.name}">${source.name}</option>`;
        });

        loadDashboard();
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

function initFilters() {
    // Source filter
    elements.sourceFilter.addEventListener('change', (e) => {
        setCurrentSource(e.target.value);

        // Reset other filters
        if (document.getElementById('filter-cluster')) document.getElementById('filter-cluster').value = '';
        if (document.getElementById('filter-host')) document.getElementById('filter-host').value = '';
        if (document.getElementById('filter-os')) document.getElementById('filter-os').value = '';
        if (document.getElementById('filter-powerstate')) document.getElementById('filter-powerstate').value = '';
        if (document.getElementById('filter-vm-search')) document.getElementById('filter-vm-search').value = '';

        loadDashboard();
        if (document.getElementById('page-vms').classList.contains('active')) {
            loadVMs();
        }
    });

    // Filter button
    document.getElementById('btn-filter-vms')?.addEventListener('click', loadVMs);

    // Auto-reload on dropdown change
    ['filter-powerstate', 'filter-cluster', 'filter-host', 'filter-os'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', loadVMs);
    });

    // Snapshot filter button
    const snapshotBtn = document.getElementById('btn-filter-snapshots');
    if (snapshotBtn) snapshotBtn.addEventListener('click', loadOldSnapshots);

    // Enter key for VM search
    document.getElementById('filter-vm-search')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loadVMs();
    });
}
