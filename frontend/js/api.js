// API Service Layer
import { API_BASE } from './config.js';

export async function fetchStats() {
    const response = await fetch(`${API_BASE}/stats`);
    return response.json();
}

export async function fetchVMs(params = {}) {
    let url = `${API_BASE}/vms?`;
    Object.keys(params).forEach(key => {
        if (params[key]) url += `${key}=${encodeURIComponent(params[key])}&`;
    });
    const response = await fetch(url);
    return response.json();
}

export async function fetchVMDetail(vmName, source) {
    const params = source ? `?source=${encodeURIComponent(source)}` : '';
    const response = await fetch(`${API_BASE}/vm/${encodeURIComponent(vmName)}${params}`);
    return response.json();
}

export async function fetchOSDistribution() {
    const response = await fetch(`${API_BASE}/reports/os-distribution`);
    return response.json();
}

export async function fetchPoweredOff() {
    const response = await fetch(`${API_BASE}/reports/powered-off`);
    return response.json();
}

export async function fetchOldSnapshots(days = 7) {
    const response = await fetch(`${API_BASE}/reports/old-snapshots?days=${days}`);
    return response.json();
}

export async function fetchZombieDisks() {
    const response = await fetch(`${API_BASE}/reports/zombie-disks`);
    return response.json();
}

export async function fetchResourceUsage() {
    const response = await fetch(`${API_BASE}/reports/resource-usage`);
    return response.json();
}

export async function fetchReserved() {
    const response = await fetch(`${API_BASE}/reports/reserved`);
    return response.json();
}


export async function fetchDatastores(source = null) {
    let url = `${API_BASE}/datastores`;
    if (source) url += `?source=${source}`;
    const response = await fetch(url);
    return response.json();
}


export async function fetchSources() {
    const response = await fetch(`${API_BASE}/sources`);
    return response.json();
}

export async function fetchRightSizing() {
    const response = await fetch(`${API_BASE}/reports/rightsizing`);
    return response.json();
}

export async function fetchDiskWaste() {
    const response = await fetch(`${API_BASE}/reports/disk-waste`);
    return response.json();
}

export async function fetchCapacityPlanning() {
    const response = await fetch(`${API_BASE}/capacity-planning`);
    return response.json();
}

export async function fetchEfficiencyScore() {
    const response = await fetch(`${API_BASE}/efficiency-score`);
    return response.json();
}


export async function fetchNote(targetType, targetName) {
    const url = `${API_BASE}/notes?target_type=${encodeURIComponent(targetType)}&target_name=${encodeURIComponent(targetName)}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch note');
    return response.json();
}

export async function saveNote(targetType, targetName, content) {
    const response = await fetch(`${API_BASE}/notes`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            target_type: targetType,
            target_name: targetName,
            note_content: content
        })
    });
    if (!response.ok) throw new Error('Failed to save note');
    return response.json();
}
