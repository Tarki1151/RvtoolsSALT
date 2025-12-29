// Configuration and Global State
export const API_BASE = 'http://localhost:5050/api';

// DOM Elements Cache
export const elements = {
    sourceFilter: null,
    modal: null,
    modalClose: null
};

// Global State
export let currentSource = '';
export let vmsData = [];

// Charts Storage
export const charts = {
    powerstate: null,
    sources: null,
    os: null
};

// Update currentSource
export function setCurrentSource(source) {
    currentSource = source;
}

// Update vmsData
export function setVmsData(data) {
    vmsData = data;
}
