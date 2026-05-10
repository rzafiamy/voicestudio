// API Base URL
const API_BASE = '';

// Global state
let voices = {};
let currentAudio = null;
let modelType = 'CustomVoice';  // Track current model type

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadVoices();
    loadLanguages();
    loadModels();
    loadHistory();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    const form = document.getElementById('generateForm');
    const textArea = document.getElementById('text');
    const speakerSelect = document.getElementById('speaker');
    const modelSelect = document.getElementById('model');
    const fileInput = document.getElementById('refAudioFile');
    const newSessionBtn = document.getElementById('newSessionBtn');

    form.addEventListener('submit', handleGenerate);
    textArea.addEventListener('input', updateCharCount);
    if (speakerSelect) speakerSelect.addEventListener('change', updateVoiceDescription);
    modelSelect.addEventListener('change', handleModelSwitch);
    fileInput.addEventListener('change', handleFileUpload);
    if (newSessionBtn) newSessionBtn.addEventListener('click', resetEditor);
}

// Load voices from API
async function loadVoices() {
    try {
        const response = await fetch(`${API_BASE}/api/voices`);
        voices = await response.json();

        const speakerSelect = document.getElementById('speaker');
        if (!speakerSelect) return;
        
        speakerSelect.innerHTML = '';

        Object.keys(voices).forEach(speaker => {
            const option = document.createElement('option');
            option.value = speaker;
            option.textContent = speaker;
            speakerSelect.appendChild(option);
        });

        // Set first voice as default and update description
        if (Object.keys(voices).length > 0) {
            speakerSelect.value = Object.keys(voices)[0];
            updateVoiceDescription();
        }
    } catch (error) {
        console.error('Error loading voices:', error);
        showError('Failed to load voices');
    }
}

// Load languages from API
async function loadLanguages() {
    try {
        const response = await fetch(`${API_BASE}/api/languages`);
        const languages = await response.json();

        const languageSelect = document.getElementById('language');
        if (!languageSelect) return;
        
        languageSelect.innerHTML = '';

        languages.forEach(lang => {
            const option = document.createElement('option');
            option.value = lang;
            option.textContent = lang;
            languageSelect.appendChild(option);
        });

        // Set Auto as default
        languageSelect.value = 'Auto';
    } catch (error) {
        console.error('Error loading languages:', error);
        showError('Failed to load languages');
    }
}

// Load models from API
async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/api/models`);
        const data = await response.json();

        const modelSelect = document.getElementById('model');
        const display = document.getElementById('currentModelDisplay');
        
        modelSelect.innerHTML = '';

        data.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            // Shorten name for display
            const shortName = model.split('/').pop();
            option.textContent = shortName;
            if (model === data.current) {
                option.selected = true;
                if (display) display.textContent = shortName;
            }
            modelSelect.appendChild(option);
        });

        // Update model type and UI
        if (data.type) {
            modelType = data.type;
            updateUIForModelType();
        }
    } catch (error) {
        console.error('Error loading models:', error);
        showError('Failed to load models');
    }
}

// Update UI based on model type
function updateUIForModelType() {
    const speakerGroup = document.getElementById('speakerGroup');
    const instructGroup = document.getElementById('instructGroup');
    const instructInput = document.getElementById('instruct');
    
    // Base model cloning groups
    const refAudioGroup = document.getElementById('refAudioGroup');
    const refTextGroup = document.getElementById('refTextGroup');

    // Default visibility
    if (speakerGroup) speakerGroup.style.display = 'flex';
    if (instructGroup) instructGroup.style.display = 'flex';
    if (refAudioGroup) refAudioGroup.style.display = 'none';
    if (refTextGroup) refTextGroup.style.display = 'none';

    if (modelType === 'VoiceDesign') {
        if (speakerGroup) speakerGroup.style.display = 'none';
        instructInput.placeholder = 'Describe voice (e.g. "Male, deep, calm")';
        instructInput.required = true;
    } else if (modelType === 'CustomVoice') {
        instructInput.placeholder = 'Style (e.g. "Happy", "Sad")';
        instructInput.required = false;
    } else if (modelType === 'Base') {
        if (speakerGroup) speakerGroup.style.display = 'none';
        if (instructGroup) instructGroup.style.display = 'none';
        if (refAudioGroup) refAudioGroup.style.display = 'flex';
        if (refTextGroup) refTextGroup.style.display = 'flex';
        instructInput.required = false;
    }
}

// Handle model switch
async function handleModelSwitch(e) {
    const newModel = e.target.value;
    if (!newModel) return;

    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/api/switch_model`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: newModel })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to switch model');
        }

        const result = await response.json();
        modelType = result.type;
        
        // Update display name
        const display = document.getElementById('currentModelDisplay');
        if (display) display.textContent = newModel.split('/').pop();
        
        updateUIForModelType();
        hideLoading();
        showSuccess(`Active Model: ${result.type}`);

    } catch (error) {
        console.error('Error switching model:', error);
        hideLoading();
        showError(error.message);
    }
}

// Update voice description
function updateVoiceDescription() {
    const speaker = document.getElementById('speaker').value;
    const descElement = document.getElementById('voiceDescription');

    if (voices[speaker]) {
        const voice = voices[speaker];
        descElement.textContent = voice.description;
    } else {
        descElement.textContent = '';
    }
}

// Update character count
function updateCharCount() {
    const text = document.getElementById('text').value;
    document.getElementById('charCount').textContent = text.length;
}

// Handle form submission
async function handleGenerate(e) {
    e.preventDefault();

    const formData = {
        text: document.getElementById('text').value,
        language: document.getElementById('language').value,
        speaker: document.getElementById('speaker') ? document.getElementById('speaker').value : '',
        instruct: document.getElementById('instruct').value,
        ref_audio_path: document.getElementById('refAudioPath').value,
        ref_text: document.getElementById('refText').value
    };

    if (modelType === 'Base' && !formData.ref_audio_path) {
        showError('Reference audio required for cloning');
        return;
    }

    if (!formData.text.trim()) {
        showError('Please enter some text');
        return;
    }

    showLoading();

    try {
        const response = await fetch(`${API_BASE}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Generation failed');
        }

        const result = await response.json();
        hideLoading();
        showAudioPlayer(result);
        loadHistory();

    } catch (error) {
        console.error('Error generating audio:', error);
        hideLoading();
        showError(error.message);
    }
}

function showLoading() {
    const loader = document.getElementById('loadingState');
    if (loader) loader.style.display = 'flex';
    document.getElementById('generateBtn').disabled = true;
}

function hideLoading() {
    const loader = document.getElementById('loadingState');
    if (loader) loader.style.display = 'none';
    document.getElementById('generateBtn').disabled = false;
}

function showAudioPlayer(result) {
    const player = document.getElementById('audioPlayer');
    const audio = document.getElementById('audioElement');
    const timestamp = document.getElementById('playerTimestamp');
    const metrics = document.getElementById('playerMetrics');

    audio.src = `${API_BASE}/api/audio/${result.filename}`;
    timestamp.textContent = formatTimestamp(result.timestamp);

    if (result.elapsed_time) {
        metrics.textContent = `${result.elapsed_time.toFixed(2)}s | ${result.chars_per_sec.toFixed(1)} ch/s`;
    }

    player.classList.add('visible');
    audio.play().catch(err => console.log('Autoplay prevented'));
}

function showError(message) {
    const container = document.getElementById('errorMessage');
    const toast = document.createElement('div');
    toast.className = 'toast error';
    toast.innerHTML = `<span class="material-icons">error_outline</span> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function showSuccess(message) {
    const container = document.getElementById('errorMessage');
    const toast = document.createElement('div');
    toast.className = 'toast success';
    toast.innerHTML = `<span class="material-icons">check_circle_outline</span> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// History Handling
async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/history`);
        const history = await response.json();
        const historyList = document.getElementById('historyList');

        if (history.length === 0) {
            historyList.innerHTML = '<p class="empty-state">No productions yet</p>';
            return;
        }

        historyList.innerHTML = '';
        history.forEach(item => {
            const el = createHistoryItem(item);
            historyList.appendChild(el);
        });
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

function createHistoryItem(item) {
    const div = document.createElement('div');
    div.className = 'history-item';
    
    // Add active state if it's the current playing audio (optional)
    
    div.innerHTML = `
        <div class="history-item-header">
            <span>${item.speaker || (item.model_type === 'Base' ? 'Clone' : 'Design')}</span>
            <span>${formatTimeOnly(item.timestamp)}</span>
        </div>
        <div class="history-item-text">${item.text}</div>
    `;
    
    div.onclick = () => {
        // Switch to this audio in the player
        showAudioPlayer({
            filename: item.filename,
            timestamp: item.timestamp,
            elapsed_time: item.elapsed_time,
            chars_per_sec: item.chars_per_sec
        });
        
        // Mark as active
        document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'));
        div.classList.add('active');
        
        // Load into editor? (Maybe optional)
        document.getElementById('text').value = item.text;
        updateCharCount();
    };

    return div;
}

function formatTimestamp(ts) {
    // YYYYMMDD_HHMMSS
    return `${ts.substring(0,4)}-${ts.substring(4,6)}-${ts.substring(6,8)} ${ts.substring(9,11)}:${ts.substring(11,13)}`;
}

function formatTimeOnly(ts) {
    return `${ts.substring(9,11)}:${ts.substring(11,13)}`;
}

async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const nameSpan = document.getElementById('refAudioName');
    nameSpan.textContent = "Uploading asset...";

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/api/upload_audio`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        nameSpan.textContent = file.name;
        document.getElementById('refAudioPath').value = result.filename;
        showSuccess('Asset uploaded');
    } catch (error) {
        nameSpan.textContent = "Upload failed";
        showError('Asset upload failed');
    }
}

async function promoteToRef(filename) {
    // (Existing logic for promotion if needed)
    // For now the UI triggers it from JS if we had a button in history
}

function resetEditor() {
    if (confirm('Start a new session? This will clear your current script and reference settings.')) {
        document.getElementById('text').value = '';
        document.getElementById('instruct').value = '';
        document.getElementById('refAudioPath').value = '';
        document.getElementById('refText').value = '';
        document.getElementById('refAudioName').textContent = 'Click to upload or drag reference audio (wav/mp3)';
        
        // Reset player
        document.getElementById('audioPlayer').classList.remove('visible');
        document.getElementById('audioElement').pause();
        document.getElementById('audioElement').src = '';
        
        updateCharCount();
        showSuccess('New session started');
    }
}
