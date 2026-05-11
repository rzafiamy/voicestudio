// API Base URL
const API_BASE = '';

// Fetch wrapper — redirects to /login on 401
async function apiFetch(url, options = {}) {
    const res = await fetch(url, options);
    if (res.status === 401) {
        window.location.href = '/login';
        return null;
    }
    return res;
}

// Global state
let voices = {};
let currentAudio = null;
let modelType = 'CustomVoice';  // Track current model type
let historyData = [];           // Store history for searching
let synthesisTimerInterval = null;
let synthesisStartTime = 0;
let wavesurfer = null;         // Wavesurfer instance
let currentViewItem = null;    // Track currently viewed history item
let modelStatusInterval = null;

/**
 * Stop all active audio playback
 */
function stopAllAudio() {
    // Stop floating player
    const floatingAudio = document.getElementById('audioElement');
    if (floatingAudio) {
        floatingAudio.pause();
    }
    
    // Stop wavesurfer
    if (wavesurfer && wavesurfer.isPlaying()) {
        wavesurfer.pause();
    }
}

/**
 * Client-side Routing System
 */
function navigateTo(path, pushState = true) {
    if (pushState) {
        window.history.pushState({}, '', path);
    }
    handleRouting();
}

async function handleRouting() {
    const path = window.location.pathname;
    
    // 1. History Item View: /history/{timestamp}
    if (path.startsWith('/history/')) {
        const timestamp = path.replace('/history/', '');
        
        // Wait for history if not yet loaded
        if (!historyData || historyData.length === 0) {
            const data = await loadHistory();
            if (!data || data.length === 0) {
                navigateTo('/studio');
                return;
            }
        }
        
        const item = historyData.find(h => h.timestamp === timestamp);
        if (item) {
            switchToViewMode(item, false); // false to avoid redundant pushState
            
            // Highlight in sidebar if it exists
            updateSidebarSelection(timestamp);
        } else {
            // Item not found, fallback to studio
            navigateTo('/studio');
        }
        return;
    }
    
    // 2. Studio / Home: / or /studio
    if (path === '/' || path === '/studio') {
        switchToEditMode(null, false);
        updateSidebarSelection(null);
        return;
    }
    
    // Default fallback
    if (path !== '/help' && path !== '/login') {
        // Only redirect if it's not a known non-app path
        // (FastAPI handles help and login, but they might be hit if routing is loose)
    }
}

function updateSidebarSelection(timestamp) {
    document.querySelectorAll('.history-item').forEach(el => {
        const isMatch = el.dataset.timestamp === timestamp;
        el.classList.toggle('active', isMatch);
    });
}



// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    // Initialize sidebar state immediately to prevent flicker
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        document.body.classList.add('sidebar-collapsed');
    }
    loadVoices();
    loadLanguages();
    loadModels();
    loadHistory().then(() => {
        // Handle routing after history is loaded
        handleRouting();
    });
    setupEventListeners();
    
    window.addEventListener('popstate', handleRouting);
    
    // Start model status polling
    checkModelStatus();

    // Initial VRAM check and set interval
    updateVRAMStatus();
    updateStorageStatus();
    setInterval(updateVRAMStatus, 3000);
    setInterval(updateStorageStatus, 10000); // Storage less frequent
});

// VRAM Monitoring
async function updateVRAMStatus(isManual = false) {
    const refreshBtn = document.getElementById('vramRefreshBtn');
    if (isManual && refreshBtn) {
        refreshBtn.classList.add('spinning');
    }

    try {
        const response = await apiFetch(`${API_BASE}/api/vram`);
        if (!response) return;
        const data = await response.json();
        
        const monitor = document.getElementById('vramMonitor');
        const text = document.getElementById('vramText');
        const fill = document.getElementById('vramFill');
        
        if (!data.available) {
            if (monitor) monitor.style.display = 'none';
            return;
        }
        
        if (monitor) monitor.style.display = 'flex';
        
        // Convert to GB
        const totalGB = (data.total / (1024 ** 3)).toFixed(1);
        const reservedGB = (data.reserved / (1024 ** 3)).toFixed(1);
        const allocatedGB = (data.allocated / (1024 ** 3)).toFixed(1);
        
        if (text) text.textContent = `${reservedGB} / ${totalGB} GB`;
        
        if (fill) {
            const percentage = data.percentage;
            fill.style.width = `${percentage}%`;
            
            // Update color based on usage
            fill.classList.remove('warning', 'critical');
            if (percentage > 90) {
                fill.classList.add('critical');
            } else if (percentage > 75) {
                fill.classList.add('warning');
            }
        }
    } catch (error) {
        console.error('Error fetching VRAM status:', error);
    } finally {
        if (isManual && refreshBtn) {
            // Keep spinning for at least 500ms for visual feedback
            setTimeout(() => {
                refreshBtn.classList.remove('spinning');
            }, 500);
        }
    }
}

// Storage Monitoring
async function updateStorageStatus() {
    try {
        const response = await apiFetch(`${API_BASE}/api/storage_stats`);
        if (!response) return;
        const data = await response.json();
        
        const text = document.getElementById('storageText');
        const fill = document.getElementById('storageFill');
        
        if (!text || !fill) return;

        const sizeMB = (data.total_size / (1024 * 1024)).toFixed(1);
        const sizeGB = (data.total_size / (1024 ** 3)).toFixed(2);
        
        if (data.total_size > (1024 ** 3)) {
            text.textContent = `${sizeGB} GB`;
        } else {
            text.textContent = `${sizeMB} MB`;
        }

        // We assume 2GB is the soft limit for the bar visualization
        const softLimit = 2 * (1024 ** 3);
        const percentage = Math.min((data.total_size / softLimit) * 100, 100);
        fill.style.width = `${percentage}%`;

    } catch (error) {
        console.error('Error fetching storage status:', error);
    }
}

function countWords(text) {
    if (!text) return 0;
    return text.trim().split(/\s+/).filter(word => word.length > 0).length;
}

// Helper for friendly model names
function getFriendlyModelInfo(technicalName) {
    let name = technicalName.split('/').pop(); // Default
    let feature = "Advanced TTS Generation";
    let icon = "cpu";
    let typeClass = "model";
    let cssClass = "default";

    if (technicalName.includes('CustomVoice')) {
        const isPro = technicalName.includes('1.7B');
        name = isPro ? "Pro Speech" : "Fast Speech";
        feature = isPro ? "Max fidelity, high-end presets" : "Fast generation, curated voices";
        icon = "music";
        typeClass = "voice";
        cssClass = isPro ? "studio-pro" : "studio-turbo";
    } else if (technicalName.includes('VoiceDesign')) {
        name = "Voice Design";
        feature = "Generate unique voices from text";
        icon = "wand-2";
        typeClass = "voice";
        cssClass = "voice-designer";
    } else if (technicalName.includes('Base')) {
        name = "Voice Clone";
        feature = "Clone any voice from a reference audio";
        icon = "copy";
        typeClass = "cloning";
        cssClass = "clone-pro";
    }

    return { name, feature, icon, typeClass, cssClass };
}


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
    
    const searchInput = document.getElementById('historySearch');
    if (searchInput) searchInput.addEventListener('input', handleSearch);

    if (newSessionBtn) newSessionBtn.addEventListener('click', () => {
        showModal('confirmModal', () => {
            performReset();
        });
    });

    // Custom Select Event Listeners
    const speakerTrigger = document.getElementById('speakerTrigger');
    const modelTrigger = document.getElementById('modelTrigger');

    if (speakerTrigger) {
        speakerTrigger.onclick = (e) => {
            e.stopPropagation();
            toggleDropdown('speakerOptions');
        };
    }

    if (modelTrigger) {
        modelTrigger.onclick = (e) => {
            e.stopPropagation();
            toggleDropdown('modelOptions');
        };
    }

    // Close dropdowns on click outside
    window.onclick = () => {
        toggleDropdown('speakerOptions', false);
        toggleDropdown('modelOptions', false);
    };

    // Edit in studio button
    const editBtn = document.getElementById('editInStudioBtn');
    if (editBtn) {
        editBtn.onclick = () => {
            if (currentViewItem) {
                switchToEditMode(currentViewItem);
            }
        };
    }

    // Copy transcript button
    const copyBtn = document.getElementById('copyTranscriptBtn');
    if (copyBtn) {
        copyBtn.onclick = () => {
            if (currentViewItem) {
                navigator.clipboard.writeText(currentViewItem.text).then(() => {
                    showSuccess('Script copied to clipboard');
                });
            }
        };
    }

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.onclick = async () => {
            await fetch('/logout', { method: 'POST' });
            window.location.href = '/login';
        };
    }

    // Sidebar Toggle Logic
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            document.body.classList.toggle('sidebar-collapsed');
            const isCollapsed = document.body.classList.contains('sidebar-collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        });
    }

    // Modal close listeners
    document.getElementById('modalCancel').onclick = () => hideModal('confirmModal');
    document.getElementById('modalConfirm').onclick = () => {
        const modal = document.getElementById('confirmModal');
        if (modal.onConfirm) modal.onConfirm();
        hideModal('confirmModal');
    };

    // VRAM Refresh listener
    const vramRefreshBtn = document.getElementById('vramRefreshBtn');
    if (vramRefreshBtn) {
        vramRefreshBtn.onclick = (e) => {
            e.stopPropagation();
            updateVRAMStatus(true);
        };
    }
}



function toggleDropdown(id, force) {
    const options = document.getElementById(id);
    const trigger = document.getElementById(id.replace('Options', 'Trigger'));
    
    if (!options) return;

    const isShowing = force !== undefined ? force : !options.classList.contains('show');
    
    // Close all first
    document.querySelectorAll('.custom-select-options').forEach(opt => opt.classList.remove('show'));
    document.querySelectorAll('.custom-select-trigger').forEach(trig => trig.classList.remove('active'));

    if (isShowing) {
        options.classList.add('show');
        if (trigger) trigger.classList.add('active');
    }
}

// Load voices from API
async function loadVoices() {
    try {
        const response = await apiFetch(`${API_BASE}/api/voices`);
        voices = await response.json();

        const speakerSelect = document.getElementById('speaker');
        const speakerOptions = document.getElementById('speakerOptions');
        const speakerValue = document.getElementById('speakerValue');
        
        if (!speakerSelect || !speakerOptions) return;
        
        speakerSelect.innerHTML = '';
        speakerOptions.innerHTML = '';

        const voiceKeys = Object.keys(voices);

        voiceKeys.forEach(speaker => {
            // Update hidden select
            const option = document.createElement('option');
            option.value = speaker;
            option.textContent = speaker;
            speakerSelect.appendChild(option);

            // Create beautiful option
            const voice = voices[speaker];
            const opt = document.createElement('div');
            opt.className = 'custom-select-option';
            opt.dataset.value = speaker;
            
            opt.innerHTML = `
                <div class="option-icon">
                    <i data-lucide="mic-2"></i>
                </div>
                <div class="option-info">
                    <div class="option-label">${speaker}</div>
                    <div class="option-sublabel">${voice.language || 'Multi'}</div>
                </div>
            `;

            opt.onclick = (e) => {
                e.stopPropagation();
                selectVoice(speaker);
                toggleDropdown('speakerOptions', false);
            };

            speakerOptions.appendChild(opt);
        });

        // Set first voice as default
        if (voiceKeys.length > 0) {
            selectVoice(voiceKeys[0]);
        }

        // Initialize Lucide icons
        if (window.lucide) lucide.createIcons();
    } catch (error) {
        console.error('Error loading voices:', error);
        showError('Failed to load voices');
    }
}

function selectVoice(speaker) {
    const speakerSelect = document.getElementById('speaker');
    const speakerValue = document.getElementById('speakerValue');
    const speakerOptions = document.getElementById('speakerOptions');
    
    speakerSelect.value = speaker;
    if (speakerValue) speakerValue.textContent = speaker;
    
    // Update active state in options
    document.querySelectorAll('#speakerOptions .custom-select-option').forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.value === speaker);
    });
    
    updateVoiceDescription();
}

// Load languages from API
async function loadLanguages() {
    try {
        const response = await apiFetch(`${API_BASE}/api/languages`);
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
        const response = await apiFetch(`${API_BASE}/api/models`);
        const data = await response.json();

        const modelSelect = document.getElementById('model');
        const modelOptions = document.getElementById('modelOptions');
        const modelValue = document.getElementById('modelValue');
        
        if (!modelSelect || !modelOptions) return;

        modelSelect.innerHTML = '';
        modelOptions.innerHTML = '';

        const modelOrder = ['0.6B-CustomVoice', '1.7B-CustomVoice', '1.7B-Base', '1.7B-VoiceDesign'];
        data.models.sort((a, b) => {
            const ai = modelOrder.findIndex(k => a.includes(k));
            const bi = modelOrder.findIndex(k => b.includes(k));
            return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
        });

        data.models.forEach(model => {
            const info = getFriendlyModelInfo(model);

            // Update hidden select
            const option = document.createElement('option');
            option.value = model;
            option.textContent = info.name;
            modelSelect.appendChild(option);

            // Create beautiful option
            const opt = document.createElement('div');
            opt.className = 'custom-select-option';
            opt.dataset.value = model;
            opt.innerHTML = `
                <div class="option-icon">
                    <i data-lucide="${info.icon}"></i>
                </div>
                <div class="option-info">
                    <div class="option-label">${info.name}</div>
                    <div class="option-sublabel">${info.feature}</div>
                </div>
            `;

            if (model === data.current) {
                option.selected = true;
                opt.classList.add('selected');
                if (modelValue) modelValue.textContent = info.name;
                const display = document.getElementById('currentModelDisplay');
                if (display) display.textContent = info.name;
            }

            opt.onclick = (e) => {
                e.stopPropagation();
                if (opt.classList.contains('selected')) {
                    toggleDropdown('modelOptions', false);
                    return;
                }
                handleModelSwitch({ target: { value: model } });
                toggleDropdown('modelOptions', false);
            };

            modelOptions.appendChild(opt);
        });

        // Update model type and UI
        if (data.type) {
            modelType = data.type;
            updateUIForModelType();
        }

        updateWorkbenchVisibility();

        // Initialize Lucide icons
        if (window.lucide) lucide.createIcons();
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

    // Update UI immediately
    const modelValue = document.getElementById('modelValue');
    const info = getFriendlyModelInfo(newModel);
    if (modelValue) modelValue.textContent = info.name;
    
    document.querySelectorAll('#modelOptions .custom-select-option').forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.value === newModel);
    });

    try {
        const response = await apiFetch(`${API_BASE}/api/switch_model`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: newModel })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || error.error || 'Failed to switch model');
        }

        // After successful switch trigger, start polling for status
        checkModelStatus();

    } catch (error) {
        console.error('Error switching model:', error);
        showError(error.message);
        // Revert UI on error
        loadModels(); 
    }
}

/**
 * Poll model status until ready
 */
async function checkModelStatus() {
    if (modelStatusInterval) clearInterval(modelStatusInterval);
    
    const overlay = document.getElementById('modelLoadingState');
    const title = document.getElementById('modelLoadingTitle');
    const message = document.getElementById('modelLoadingMessage');
    const progressFill = document.getElementById('modelLoadingProgress');
    const timeDisplay = document.getElementById('modelLoadingTime');
    const stepDisplay = document.getElementById('modelLoadingStep');
    const percentDisplay = document.getElementById('modelLoadingPercent');

    const updateUI = (data) => {
        if (data.status === 'ready') {
            overlay.style.display = 'none';
            if (modelStatusInterval) {
                clearInterval(modelStatusInterval);
                modelStatusInterval = null;
            }
            loadModels(); // Refresh models to get the current one
            return true;
        }

        overlay.style.display = 'flex';
        
        // Map status to friendly titles
        const statusMap = {
            'loading': 'Loading Weights',
            'compiling': 'Optimizing Graph',
            'warming_up': 'Engine Warmup',
            'error': 'Loading Failed'
        };

        title.textContent = statusMap[data.status] || 'Initialising';
        message.textContent = data.message;
        progressFill.style.width = `${data.progress}%`;
        timeDisplay.textContent = `${data.elapsed.toFixed(1)}s`;
        percentDisplay.textContent = `${Math.round(data.progress)}%`;

        if (data.status === 'loading') stepDisplay.textContent = 'Step 1/3: Loading weights';
        else if (data.status === 'compiling') stepDisplay.textContent = 'Step 2/3: Neural graph optimization';
        else if (data.status === 'warming_up') stepDisplay.textContent = 'Step 3/3: First-run GPU warmup';
        
        if (data.status === 'error') {
            title.style.color = '#ef4444';
            message.style.color = '#ef4444';
            if (modelStatusInterval) {
                clearInterval(modelStatusInterval);
                modelStatusInterval = null;
            }
        }
        return false;
    };

    // First check
    try {
        const res = await apiFetch(`${API_BASE}/api/model_status`);
        if (res) {
            const data = await res.json();
            if (updateUI(data)) return;
        }
    } catch (e) {
        console.error("Failed to check model status", e);
    }

    modelStatusInterval = setInterval(async () => {
        try {
            const res = await apiFetch(`${API_BASE}/api/model_status`);
            if (!res) return;
            const data = await res.json();
            updateUI(data);
        } catch (e) {
            console.error("Error in model status poll:", e);
        }
    }, 1000);
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
    const wordCountEl = document.getElementById('wordCount');
    if (wordCountEl) wordCountEl.textContent = countWords(text);
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
        const response = await apiFetch(`${API_BASE}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || error.error || 'Generation failed');
        }

        const result = await response.json();
        hideLoading();
        showAudioPlayer(result);
        loadHistory();
        updateStorageStatus(); // Update storage after new file is created

    } catch (error) {
        console.error('Error generating audio:', error);
        hideLoading();
        showError(error.message);
    }
}

// Update workbench visibility based on selection
function updateWorkbenchVisibility() {
    const modelSelect = document.getElementById('model');
    const workbench = document.getElementById('workbenchSection');
    const emptyState = document.getElementById('emptyState');
    
    const hasSelection = modelSelect && modelSelect.value !== "";
    
    if (hasSelection) {
        if (workbench) workbench.style.display = 'flex';
        if (emptyState) emptyState.style.display = 'none';
    } else {
        if (workbench) workbench.style.display = 'none';
        if (emptyState) emptyState.style.display = 'flex';
    }
    
    if (window.lucide) lucide.createIcons();
}

function showLoading() {

    const loader = document.getElementById('loadingState');
    if (loader) loader.style.display = 'flex';
    document.getElementById('generateBtn').disabled = true;

    // Start timer
    synthesisStartTime = Date.now();
    const timerDisplay = document.getElementById('synthesisTimer');
    const progressBar = document.getElementById('synthesisProgress');
    
    if (timerDisplay) timerDisplay.textContent = '0.0s';
    if (progressBar) progressBar.style.width = '0%';

    synthesisTimerInterval = setInterval(() => {
        const elapsed = (Date.now() - synthesisStartTime) / 1000;
        if (timerDisplay) timerDisplay.textContent = `${elapsed.toFixed(1)}s`;
        
        // Simulate progress (slows down as it gets higher)
        if (progressBar) {
            let progress = (1 - Math.exp(-elapsed / 10)) * 95; // Asymptotically approaches 95%
            progressBar.style.width = `${progress}%`;
        }
    }, 100);
}

function hideLoading() {
    const loader = document.getElementById('loadingState');
    if (loader) loader.style.display = 'none';
    document.getElementById('generateBtn').disabled = false;

    // Stop timer
    if (synthesisTimerInterval) {
        clearInterval(synthesisTimerInterval);
        synthesisTimerInterval = null;
    }
    if (window.lucide) lucide.createIcons();
}

// Mode Switching Logic
async function switchToViewMode(item, updateUrl = true) {
    stopAllAudio();
    currentViewItem = item;
    
    if (updateUrl) {
        window.history.pushState({}, '', `/history/${item.timestamp}`);
    }
    const form = document.getElementById('generateForm');
    const view = document.getElementById('sessionView');
    const emptyState = document.getElementById('emptyState');
    const workbench = document.getElementById('workbenchSection');

    // Show workbench if it was hidden
    if (workbench) workbench.style.display = 'flex';
    if (emptyState) emptyState.style.display = 'none';

    // Toggle containers
    if (form) form.style.display = 'none';
    if (view) view.style.display = 'flex';

    // Populate View with Markdown support
    const viewText = document.getElementById('viewText');
    if (window.marked) {
        viewText.innerHTML = marked.parse(item.text);
    } else {
        viewText.textContent = item.text;
    }
    
    document.getElementById('viewTimestamp').textContent = formatRelativeTime(item.timestamp);
    document.getElementById('viewDuration').textContent = item.elapsed_time ? `${item.elapsed_time.toFixed(2)}s` : 'N/A';
    document.getElementById('viewWordCount').textContent = countWords(item.text);
    document.getElementById('viewEfficiency').textContent = item.chars_per_sec ? `${item.chars_per_sec.toFixed(1)} ch/s` : 'N/A';
    
    const modelInfo = getFriendlyModelInfo(item.model || '');
    document.getElementById('viewModelName').textContent = modelInfo.name;
    
    // Set icon for model badge
    const modelBadgeIcon = document.querySelector('#viewModelBadge i');
    if (modelBadgeIcon) modelBadgeIcon.setAttribute('data-lucide', modelInfo.icon);

    if (item.speaker) {
        document.getElementById('viewVoiceBadge').style.display = 'flex';
        document.getElementById('viewVoiceName').textContent = item.speaker;
    } else {
        document.getElementById('viewVoiceBadge').style.display = 'none';
    }

    // Set title based on content snippet
    const snippet = item.text.length > 30 ? item.text.substring(0, 30) + '...' : item.text;
    document.getElementById('viewTitle').textContent = snippet || 'Studio Session';

    // Initialize/Refresh Wavesurfer
    initWavesurfer(`${API_BASE}/api/audio/${item.filename}`);

    if (window.lucide) lucide.createIcons();
}

function initWavesurfer(audioUrl) {
    if (wavesurfer) {
        wavesurfer.destroy();
    }

    wavesurfer = WaveSurfer.create({
        container: '#waveform',
        waveColor: '#4f46e5',
        progressColor: '#8b5cf6',
        cursorColor: '#8b5cf6',
        barWidth: 2,
        barRadius: 3,
        responsive: true,
        height: 80,
        normalize: true,
        url: audioUrl
    });

    const playBtn = document.getElementById('playPauseBtn');
    const playIcon = document.getElementById('playIcon');
    const waveTime = document.getElementById('waveTime');

    playBtn.onclick = () => wavesurfer.playPause();

    wavesurfer.on('play', () => {
        playIcon.setAttribute('data-lucide', 'pause');
        lucide.createIcons();
    });

    wavesurfer.on('pause', () => {
        playIcon.setAttribute('data-lucide', 'play');
        lucide.createIcons();
    });

    wavesurfer.on('audioprocess', () => {
        const currentTime = formatTime(wavesurfer.getCurrentTime());
        const duration = formatTime(wavesurfer.getDuration());
        waveTime.textContent = `${currentTime} / ${duration}`;
    });

    wavesurfer.on('ready', () => {
        const duration = formatTime(wavesurfer.getDuration());
        waveTime.textContent = `00:00 / ${duration}`;
    });
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function switchToEditMode(item = null, updateUrl = true) {
    stopAllAudio();
    if (updateUrl) {
        window.history.pushState({}, '', '/studio');
    }

    const form = document.getElementById('generateForm');
    const view = document.getElementById('sessionView');
    
    if (form) form.style.display = 'block';
    if (view) view.style.display = 'none';

    if (item) {
        // Populate form from item
        document.getElementById('text').value = item.text;
        if (item.language) document.getElementById('language').value = item.language;
        if (item.instruct !== undefined) document.getElementById('instruct').value = item.instruct;
        
        // Model switch
        const currentModel = document.getElementById('model').value;
        if (item.model && item.model !== currentModel) {
            handleModelSwitch({ target: { value: item.model } }).then(() => {
                if (item.speaker && modelType === 'CustomVoice') {
                    selectVoice(item.speaker);
                }
            });
        } else {
            if (item.speaker && modelType === 'CustomVoice') {
                selectVoice(item.speaker);
            }
        }
    }
    
    updateCharCount();
    if (window.lucide) lucide.createIcons();
}

function showAudioPlayer(result) {
    const player = document.getElementById('audioPlayer');
    const audio = document.getElementById('audioElement');
    const timestamp = document.getElementById('playerTimestamp');
    const metrics = document.getElementById('playerMetrics');

    audio.src = `${API_BASE}/api/audio/${result.filename}`;
    timestamp.textContent = `${formatTimestamp(result.timestamp)} (${formatRelativeTime(result.timestamp)})`;

    if (result.elapsed_time) {
        metrics.textContent = `${result.elapsed_time.toFixed(2)}s | ${result.chars_per_sec.toFixed(1)} ch/s`;
    }

    player.classList.add('visible');
    audio.play().catch(err => console.log('Autoplay prevented'));
}

function closeAudioPlayer() {
    const player = document.getElementById('audioPlayer');
    const audio = document.getElementById('audioElement');
    if (player) player.classList.remove('visible');
    if (audio) {
        audio.pause();
        audio.src = '';
    }
}

function showError(message) {
    const container = document.getElementById('errorMessage');
    const toast = document.createElement('div');
    toast.className = 'toast error';
    toast.innerHTML = `<i data-lucide="alert-circle"></i> <span>${message}</span>`;
    container.appendChild(toast);
    lucide.createIcons();
    setTimeout(() => toast.remove(), 5000);
}

function showSuccess(message) {
    const container = document.getElementById('errorMessage');
    const toast = document.createElement('div');
    toast.className = 'toast success';
    toast.innerHTML = `<i data-lucide="check-circle"></i> <span>${message}</span>`;
    container.appendChild(toast);
    lucide.createIcons();
    setTimeout(() => toast.remove(), 3000);
}

// History Handling
async function loadHistory() {
    try {
        const response = await apiFetch(`${API_BASE}/api/history`);
        historyData = await response.json();
        renderHistory(historyData);
        return historyData;
    } catch (error) {
        console.error('Error loading history:', error);
        return [];
    }
}

function renderHistory(data) {
    const historyList = document.getElementById('historyList');

    if (data.length === 0) {
        historyList.innerHTML = '<p class="empty-state">No productions yet</p>';
        return;
    }

    historyList.innerHTML = '';
    data.forEach(item => {
        const el = createHistoryItem(item);
        historyList.appendChild(el);
    });
    
    // Render Lucide icons
    if (window.lucide) lucide.createIcons();
}

function handleSearch(e) {
    const query = e.target.value.toLowerCase();
    const filtered = historyData.filter(item => 
        item.text.toLowerCase().includes(query) || 
        (item.speaker && item.speaker.toLowerCase().includes(query))
    );
    renderHistory(filtered);
}

function createHistoryItem(item) {
    const div = document.createElement('div');
    div.className = 'history-item';
    div.dataset.timestamp = item.timestamp;
    
    const info = getFriendlyModelInfo(item.model || '');

    div.innerHTML = `
        <div class="item-app-icon ${info.cssClass}">
            <i data-lucide="${info.icon}"></i>
        </div>
        <div class="history-item-body">
            <div class="history-item-header">
                <span class="history-item-model">${info.name}</span>
                <span class="history-item-time">${formatRelativeTime(item.timestamp)}</span>
            </div>
            <div class="history-item-text">${item.text}</div>
            <div class="history-item-footer">
                <div class="history-item-voice">
                    <i data-lucide="mic-2"></i>
                    <span>${item.speaker || (item.model_type === 'Base' ? 'Reference' : 'AI Generated')}</span>
                </div>
            </div>
        </div>
    `;
    div.onclick = () => {
        // Mark as active
        updateSidebarSelection(item.timestamp);
        
        // SWITCH TO VIEW MODE
        switchToViewMode(item);
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

function parseTimestamp(ts) {
    // Expected format: YYYYMMDD_HHMMSS[_...]
    const year = parseInt(ts.substring(0, 4));
    const month = parseInt(ts.substring(4, 6)) - 1; // 0-indexed
    const day = parseInt(ts.substring(6, 8));
    const hour = parseInt(ts.substring(9, 11));
    const minute = parseInt(ts.substring(11, 13));
    const second = parseInt(ts.substring(13, 15)) || 0;
    return new Date(year, month, day, hour, minute, second);
}

function formatRelativeTime(ts) {
    if (!ts) return 'Unknown time';
    
    const date = parseTimestamp(ts);
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);

    // Future dates (possible if clock drift)
    if (diffInSeconds < 0) return 'Just now';

    if (diffInSeconds < 60) return 'Just now';
    
    if (diffInSeconds < 3600) {
        const minutes = Math.floor(diffInSeconds / 60);
        return `${minutes} min ago`;
    }
    
    if (diffInSeconds < 86400) {
        const hours = Math.floor(diffInSeconds / 3600);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }
    
    // Yesterday check
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
        return 'Yesterday';
    }

    if (diffInSeconds < 604800) { // < 1 week
        const days = Math.floor(diffInSeconds / 86400);
        return `${days} day${days > 1 ? 's' : ''} ago`;
    }

    if (diffInSeconds < 2592000) { // < 30 days
        const weeks = Math.floor(diffInSeconds / 604800);
        return `${weeks} week${weeks > 1 ? 's' : ''} ago`;
    }
    
    if (diffInSeconds < 31536000) { // < 1 year
        const months = Math.floor(diffInSeconds / 2592000);
        return `${months} month${months > 1 ? 's' : ''} ago`;
    }

    const years = Math.floor(diffInSeconds / 31536000);
    return `${years} year${years > 1 ? 's' : ''} ago`;
}

async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const nameSpan = document.getElementById('refAudioName');
    nameSpan.textContent = "Uploading asset...";

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await apiFetch(`${API_BASE}/api/upload_audio`, {
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
    // This is now handled by the event listener calling showModal
}

function showModal(id, onConfirm) {
    const modal = document.getElementById(id);
    modal.classList.add('active');
    modal.onConfirm = onConfirm;
}

function hideModal(id) {
    const modal = document.getElementById(id);
    modal.classList.remove('active');
}

function performReset() {
    document.getElementById('text').value = '';
    document.getElementById('instruct').value = '';
    document.getElementById('refAudioPath').value = '';
    document.getElementById('refText').value = '';
    document.getElementById('refAudioName').textContent = 'Click to upload or drag reference audio (wav/mp3)';
    
    // Clear history selection
    document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'));

    // Reset voice selection
    const voiceKeys = Object.keys(voices);
    if (voiceKeys.length > 0) selectVoice(voiceKeys[0]);

    // Reset player
    closeAudioPlayer();
    
    // Reset UI mode
    navigateTo('/studio');
    
    showSuccess('New session started');
}

