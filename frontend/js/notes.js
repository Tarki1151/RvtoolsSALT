
import { fetchNote, saveNote } from './api.js';

export class NoteManager {
    constructor() {
        this.createNoteModal();
    }

    createNoteModal() {
        if (document.getElementById('note-modal')) return;

        const modalHtml = `
            <div id="note-modal" class="modal">
                <div class="modal-content" style="max-width: 500px;">
                    <span class="close-modal">&times;</span>
                    <div class="modal-header">
                        <h2><i class="fas fa-sticky-note"></i> Not Ekle/Düzenle</h2>
                        <h4 id="note-target-title" style="margin-top: 5px; color: #aaa;"></h4>
                    </div>
                    <div class="modal-body">
                        <textarea id="note-textarea" rows="8" placeholder="Buraya notlarınızı girin..." style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-dark); color: var(--text-primary); resize: vertical;"></textarea>
                        <div style="margin-top: 5px; font-size: 0.8em; color: #888; text-align: right;">
                            Son Güncelleme: <span id="note-updated-at">-</span>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button id="save-note-btn" class="btn btn-primary"><i class="fas fa-save"></i> Kaydet</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Event Listeners
        const modal = document.getElementById('note-modal');
        const closeBtn = modal.querySelector('.close-modal');
        const saveBtn = document.getElementById('save-note-btn');

        closeBtn.onclick = () => {
            modal.style.display = 'none';
        };

        window.onclick = (event) => {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        };

        saveBtn.onclick = async () => {
            const content = document.getElementById('note-textarea').value;
            const targetType = modal.dataset.targetType;
            const targetName = modal.dataset.targetName;

            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Kaydediliyor...';
            saveBtn.disabled = true;

            try {
                const result = await saveNote(targetType, targetName, content);
                if (result.status === 'success') {
                    document.getElementById('note-updated-at').textContent = result.updated_at;

                    // Show success feedback
                    const originalText = saveBtn.innerHTML;
                    saveBtn.innerHTML = '<i class="fas fa-check"></i> Kaydedildi';
                    saveBtn.classList.add('btn-success');

                    setTimeout(() => {
                        saveBtn.innerHTML = '<i class="fas fa-save"></i> Kaydet';
                        saveBtn.classList.remove('btn-success');
                        saveBtn.disabled = false;
                        modal.style.display = 'none';
                    }, 1000);

                    // Trigger custom event so other components can update UI if needed
                    window.dispatchEvent(new CustomEvent('noteSaved', {
                        detail: { targetType, targetName, content }
                    }));
                }
            } catch (error) {
                console.error('Error saving note:', error);
                saveBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Hata';
                saveBtn.disabled = false;
            }
        };
    }

    async openNote(targetType, targetName) {
        const modal = document.getElementById('note-modal');
        const textarea = document.getElementById('note-textarea');
        const title = document.getElementById('note-target-title');
        const updatedLabel = document.getElementById('note-updated-at');
        const saveBtn = document.getElementById('save-note-btn');

        // Reset UI
        textarea.value = 'Yükleniyor...';
        textarea.disabled = true;
        title.textContent = `${targetType.toUpperCase()}: ${targetName}`;
        updatedLabel.textContent = '-';
        saveBtn.disabled = true;

        modal.dataset.targetType = targetType;
        modal.dataset.targetName = targetName;
        modal.style.display = 'flex'; // Changed to flex for centering

        try {
            const data = await fetchNote(targetType, targetName);
            textarea.value = data.note_content || '';
            updatedLabel.textContent = data.updated_at || 'Daha önce not alınmamış';
        } catch (error) {
            console.error('Error loading note:', error);
            textarea.value = 'Not yüklenirken hata oluştu.';
        } finally {
            textarea.disabled = false;
            saveBtn.disabled = false;
            textarea.focus();
        }
    }
}

// Singleton instance
export const noteManager = new NoteManager();
