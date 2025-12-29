// Utility Functions

export function formatNumber(num) {
    if (!num && num !== 0) return '-';
    return new Intl.NumberFormat('tr-TR').format(num);
}

export function truncateText(text, maxLength) {
    if (!text) return '-';
    text = String(text);
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

export function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
