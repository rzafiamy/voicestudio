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

    form.addEventListener('submit', handleGenerate);
    textArea.addEventListener('input', updateCharCount);
    speakerSelect.addEventListener('change', updateVoiceDescription);
    modelSelect.addEventListener('change', handleModelSwitch);
    fileInput.addEventListener('change', handleFileUpload);
}

// Load voices from API
async function loadVoices() {
    try {
        const response = await fetch(`${API_BASE}/api/voices`);
        voices = await response.json();

        const speakerSelect = document.getElementById('speaker');
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
        modelSelect.innerHTML = '';

        data.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            if (model === data.current) {
                option.selected = true;
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
    const speakerGroup = document.getElementById('speaker').closest('.form-group');
    const instructGroup = document.getElementById('instructGroup');
    const instructInput = document.getElementById('instruct');
    const instructLabel = instructInput.previousElementSibling;

    // Base model cloning groups
    const refAudioGroup = document.getElementById('refAudioGroup');
    const refTextGroup = document.getElementById('refTextGroup');

    if (modelType === 'VoiceDesign') {
        // VoiceDesign Mode
        speakerGroup.style.display = 'none';
        instructGroup.style.display = 'block';
        refAudioGroup.style.display = 'none';
        refTextGroup.style.display = 'none';

        // Update instruction placeholder and make it required
        instructInput.placeholder = 'Describe the voice you want (REQUIRED for VoiceDesign model), e.g., "Male, 25 years old, cheerful and energetic"';
        instructInput.required = true;

        // Update label to show it's required
        const labelText = instructLabel.querySelector('span:last-child') || instructLabel;
        if (!labelText.textContent.includes('REQUIRED')) {
            labelText.textContent = labelText.textContent.replace('(Optional)', '(REQUIRED for VoiceDesign)');
        }
    } else if (modelType === 'CustomVoice') {
        // CustomVoice Mode
        speakerGroup.style.display = 'flex';
        instructGroup.style.display = 'block';
        refAudioGroup.style.display = 'none';
        refTextGroup.style.display = 'none';

        // Update instruction placeholder
        instructInput.placeholder = 'e.g., "Speak in a happy tone" or "Very angry voice"';
        instructInput.required = false;

        // Update label
        const labelText = instructLabel.querySelector('span:last-child') || instructLabel;
        labelText.textContent = labelText.textContent.replace('(REQUIRED for VoiceDesign)', '(Optional)');
    } else if (modelType === 'Base') {
        // Base Model (Cloning) Mode
        speakerGroup.style.display = 'none';
        instructGroup.style.display = 'none'; // Hide style instruction for base model
        refAudioGroup.style.display = 'flex';
        refTextGroup.style.display = 'flex';

        instructInput.required = false;
    }
}

// Handle model switch
async function handleModelSwitch(e) {
    const newModel = e.target.value;

    if (!newModel) return;

    // Show loading state
    const modelSelect = document.getElementById('model');
    const originalValue = modelSelect.value;
    modelSelect.disabled = true;
    showLoading();
    hideError();

    try {
        const response = await fetch(`${API_BASE}/api/switch_model`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ model: newModel })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to switch model');
        }

        const result = await response.json();

        // Update model type and UI
        modelType = result.type;
        updateUIForModelType();

        // Show success message
        hideLoading();
        showSuccess(result.message || `Switched to ${result.type} model`);

    } catch (error) {
        console.error('Error switching model:', error);
        // Revert to original value
        modelSelect.value = originalValue;
        hideLoading();
        showError(error.message || 'Failed to switch model');
    } finally {
        modelSelect.disabled = false;
    }
}

// Update voice description
function updateVoiceDescription() {
    const speaker = document.getElementById('speaker').value;
    const descElement = document.getElementById('voiceDescription');

    if (voices[speaker]) {
        const voice = voices[speaker];
        descElement.textContent = `${voice.description} (Native: ${voice.language})`;
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
        speaker: document.getElementById('speaker').value,
        instruct: document.getElementById('instruct').value,
        ref_audio_path: document.getElementById('refAudioPath').value,
        ref_text: document.getElementById('refText').value
    };

    // Validate based on model type
    if (modelType === 'Base') {
        if (!formData.ref_audio_path) {
            showError('Please select a reference audio file');
            return;
        }
        // Ref text is optional now (X-Vector mode)
        if (!formData.ref_text) {
            // Implicitly X-Vector mode
            formData.x_vector_only = true;
        }
    }

    if (!formData.text.trim()) {
        showError('Please enter some text to generate');
        return;
    }

    // Show loading state
    showLoading();
    hideError();
    hideAudioPlayer();

    try {
        const response = await fetch(`${API_BASE}/api/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Generation failed');
        }

        const result = await response.json();

        // Hide loading and show audio player
        hideLoading();
        showAudioPlayer(result);

        // Reload history
        loadHistory();

    } catch (error) {
        console.error('Error generating audio:', error);
        hideLoading();
        showError(error.message || 'Failed to generate audio');
    }
}

// Show loading state
function showLoading() {
    document.getElementById('loadingState').style.display = 'flex';
    document.getElementById('generateBtn').disabled = true;
}

// Hide loading state
function hideLoading() {
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('generateBtn').disabled = false;
}

// Show audio player
function showAudioPlayer(result) {
    const player = document.getElementById('audioPlayer');
    const audio = document.getElementById('audioElement');
    const timestamp = document.getElementById('playerTimestamp');

    audio.src = `${API_BASE}/api/audio/${result.filename}`;
    timestamp.textContent = `Generated: ${formatTimestamp(result.timestamp)}`;

    player.style.display = 'block';

    // Auto play
    audio.play().catch(err => console.log('Auto-play prevented:', err));
}

// Hide audio player
function hideAudioPlayer() {
    document.getElementById('audioPlayer').style.display = 'none';
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';

    // Auto-hide after 5 seconds
    setTimeout(() => {
        hideError();
    }, 5000);
}

// Show success message
function showSuccess(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    errorDiv.style.background = 'var(--md-primary-container)';
    errorDiv.style.color = 'var(--md-on-primary-container)';
    errorDiv.style.borderLeftColor = 'var(--md-primary)';

    // Auto-hide after 3 seconds
    setTimeout(() => {
        hideError();
    }, 3000);
}

// Hide error message
function hideError() {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.style.display = 'none';
    // Reset to error styling
    errorDiv.style.background = 'var(--md-error-container)';
    errorDiv.style.color = 'var(--md-error)';
    errorDiv.style.borderLeftColor = 'var(--md-error)';
}

// Load history
async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/history`);
        const history = await response.json();

        const historyList = document.getElementById('historyList');

        if (history.length === 0) {
            historyList.innerHTML = '<p class="empty-state">No generations yet. Create your first audio!</p>';
            return;
        }

        historyList.innerHTML = '';

        history.forEach(item => {
            const historyItem = createHistoryItem(item);
            historyList.appendChild(historyItem);
        });

    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// Create history item element
function createHistoryItem(item) {
    const div = document.createElement('div');
    div.className = 'history-item';

    const speakerBadge = item.speaker ? `<span class="speaker-badge">${escapeHtml(item.speaker)}</span>` : '';
    const instructText = item.instruct ? `<p><strong>Style:</strong> ${escapeHtml(item.instruct)}</p>` : '';

    // Add "Use as Reference" button
    const useRefBtn = `
        <button onclick="promoteToRef('${item.filename}')" class="btn-sm btn-outline" style="margin-left: 10px; padding: 2px 8px; font-size: 0.8rem; cursor: pointer; border-radius: 4px; border: 1px solid var(--md-primary); background: transparent; color: var(--md-primary);">
            Use for Cloning
        </button>
    `;

    div.innerHTML = `
        <div class="history-header">
            <div class="history-meta">
                ${speakerBadge}
                ${useRefBtn}
                <div class="timestamp">${formatTimestamp(item.timestamp)}</div>
            </div>
        </div>
        <div class="history-text">${escapeHtml(item.text)}</div>
        <p style="font-size: 0.85rem; color: var(--md-on-surface-variant); margin-top: 0.5rem;">
            <strong>Language:</strong> ${escapeHtml(item.language)}
        </p>
        ${instructText}
        <div class="history-audio">
            <audio controls>
                <source src="${API_BASE}/api/audio/${item.filename}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
    `;

    return div;
}

// Format timestamp
function formatTimestamp(timestamp) {
    // Format: YYYYMMDD_HHMMSS_microseconds
    const year = timestamp.substring(0, 4);
    const month = timestamp.substring(4, 6);
    const day = timestamp.substring(6, 8);
    const hour = timestamp.substring(9, 11);
    const minute = timestamp.substring(11, 13);
    const second = timestamp.substring(13, 15);

    return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Handle file upload
async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Show uploading text
    const nameSpan = document.getElementById('refAudioName');
    nameSpan.textContent = "Uploading...";

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/api/upload_audio`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Upload failed');
        }

        const result = await response.json();

        // Update UI
        nameSpan.textContent = file.name;
        document.getElementById('refAudioPath').value = result.filename;
        showSuccess('File uploaded successfully');

    } catch (error) {
        console.error('Error uploading file:', error);
        nameSpan.textContent = "Upload failed";
        showError('Failed to upload file');
    }
}

// Promote generated audio to reference
async function promoteToRef(filename) {
    // Check if we are in Base mode, if not switch or warn
    if (modelType !== 'Base') {
        const confirmSwitch = confirm('Voice cloning requires the Base model. Do you want to switch to a Base model if available?');
        if (confirmSwitch) {
            // Find a base model
            const modelSelect = document.getElementById('model');
            let baseModel = null;
            for (let i = 0; i < modelSelect.options.length; i++) {
                if (modelSelect.options[i].value.includes('Base')) {
                    baseModel = modelSelect.options[i].value;
                    break;
                }
            }

            if (baseModel) {
                modelSelect.value = baseModel;
                // Trigger change event manually
                const event = new Event('change');
                modelSelect.dispatchEvent(event);
            } else {
                showError('No Base model available to switch to.');
                return;
            }
        } else {
            return;
        }
    }

    try {
        const response = await fetch(`${API_BASE}/api/promote_audio`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: filename })
        });

        if (!response.ok) {
            throw new Error('Promotion failed');
        }

        const result = await response.json();

        // Update UI
        document.getElementById('refAudioPath').value = result.ref_audio_path;
        document.getElementById('refText').value = result.ref_text;
        document.getElementById('refAudioName').textContent = result.ref_audio_path; // Or show "Promoted from history"

        showSuccess('Audio set as cloning reference');

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });

    } catch (error) {
        console.error('Error promoting audio:', error);
        showError('Failed to set audio as reference');
    }
}

// Expose promoteToRef to global scope
window.promoteToRef = promoteToRef;
