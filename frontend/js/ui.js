// UI Management Layer
import { loadOldSnapshots, loadZombieDisks, loadResourceUsage } from './reports.js';

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

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'block') {
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

export function initResizing() {
    // Add resizer elements to all th in .data-table
    document.querySelectorAll('.data-table thead th').forEach(th => {
        if (!th.querySelector('.resizer')) {
            const resizer = document.createElement('div');
            resizer.className = 'resizer';
            th.appendChild(resizer);
            setupResizer(th, resizer);
        }
    });

    // Apply saved widths
    applySavedColumnWidths();
}

function setupResizer(th, resizer) {
    let x = 0;
    let w = 0;

    const mouseDownHandler = function (e) {
        x = e.clientX;
        const styles = window.getComputedStyle(th);
        w = parseInt(styles.width, 10);

        document.addEventListener('mousemove', mouseMoveHandler);
        document.addEventListener('mouseup', mouseUpHandler);
        resizer.classList.add('resizing');
    };

    const mouseMoveHandler = function (e) {
        const dx = e.clientX - x;
        th.style.width = `${w + dx}px`;
    };

    const mouseUpHandler = function () {
        document.removeEventListener('mousemove', mouseMoveHandler);
        document.removeEventListener('mouseup', mouseUpHandler);
        resizer.classList.remove('resizing');
        saveColumnWidths(th.closest('table'));
    };

    resizer.addEventListener('mousedown', mouseDownHandler);
}

function saveColumnWidths(table) {
    if (!table || !table.id) return;
    const headers = table.querySelectorAll('thead th');
    const widths = Array.from(headers).map(th => {
        // Use getBoundingClientRect for precise fractional width if available, or offsetWidth
        return window.getComputedStyle(th).width;
    });
    localStorage.setItem(`table-widths-${table.id}`, JSON.stringify(widths));
}

export function applySavedColumnWidths() {
    document.querySelectorAll('.data-table').forEach(table => {
        if (!table.id) return;
        const saved = localStorage.getItem(`table-widths-${table.id}`);
        if (saved) {
            const widths = JSON.parse(saved);
            const headers = table.querySelectorAll('thead th');
            table.style.tableLayout = 'fixed'; // Ensure fixed layout when applying saved widths
            widths.forEach((width, i) => {
                if (headers[i] && width) {
                    headers[i].style.width = width;
                }
            });
        }
    });
}
