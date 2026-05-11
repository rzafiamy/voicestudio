# Makix Studio | Professional Qwen3-TTS Platform

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Models-orange)](https://huggingface.co/Qwen)

A professional production environment for **Qwen3-TTS** audio models. Designed for creators, developers, and audio engineers who demand a studio-grade workflow for AI speech generation.

---

## Features

- **Cinematic Studio UI**: Deep-themed workspace inspired by high-end DAWs.
- **Multi-Paradigm Generation**:
  - **CustomVoice**: High-fidelity preset speakers for consistent branding.
  - **VoiceDesign**: Prompt-based zero-shot voice synthesis.
  - **VoiceCloning**: x-vector based cloning for authentic replicas.
- **Global Linguistic Support**: English, Chinese, Japanese, Korean, and European languages.
- **Turbocharged Engine**: KV-Cache, Flash Attention 2, CUDA-native optimizations.
- **Production Library**: Sidebar history with one-click reload and audio promotion for cloning.

---

## Requirements

- Python 3.11+
- CUDA-capable GPU (recommended: 8GB+ VRAM)
- CUDA 12.8 + PyTorch 2.10 (for Flash Attention 2)

---

## Installation

### 1. Clone and set up the environment

```bash
git clone https://github.com/rzafiamy/voicestudio.git
cd voicestudio

# Automated setup (creates venv and installs dependencies)
chmod +x setup.sh
./setup.sh
```

### 2. Install Flash Attention 2 (optional but recommended)

Flash Attention 2 significantly speeds up inference on CUDA GPUs. It is **not included in the repo** due to its size (~177MB). Install it one of the following ways:

**Option A — pip install (requires CUDA toolkit and compiler)**
```bash
pip install flash-attn --no-build-isolation
```

**Option B — Download a pre-built wheel**

Download the wheel matching your Python / CUDA / PyTorch versions from the official releases:

- [flash-attention GitHub releases](https://github.com/Dao-AILab/flash-attention/releases)

Then install it manually:
```bash
pip install flash_attn-<version>-cp311-cp311-linux_x86_64.whl
```

For Python 3.11, CUDA 12.8, PyTorch 2.10, the matching wheel filename is:
```
flash_attn-2.6.3+cu128torch2.10-cp311-cp311-linux_x86_64.whl
```

> Flash Attention is optional. The app automatically detects whether it is available and falls back gracefully if not.

### 3. Download models

Download Qwen3-TTS model weights from Hugging Face and place them in the project root:

```bash
# Example using huggingface-cli
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local-dir ./Qwen3-TTS-12Hz-1.7B-CustomVoice
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign  --local-dir ./Qwen3-TTS-12Hz-1.7B-VoiceDesign
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base         --local-dir ./Qwen3-TTS-12Hz-1.7B-Base
```

The studio auto-detects any directory matching `Qwen3-TTS-*`.

---

## ⚡ Performance & Optimization

Makix Studio uses **PyTorch 2.0+ Graph Compilation** (`torch.compile`) to achieve up to 3x faster inference speeds. This comes with a specific behavior you should be aware of:

### 1. The "First-Run" Warmup
When you load a model for the very first time (or after a major update), the application will enter an **Engine Warmup** phase. 
- **Duration**: 1 to 3 minutes.
- **What's happening?**: The system is analyzing the neural network and compiling optimized CUDA kernels specifically for your GPU architecture.
- **UI Feedback**: You will see a "Warming up engine..." progress overlay in the studio. **Do not close the application during this time.**

### 2. Persistent Cache
Once compilation is complete, the optimized kernels are stored in the `.torch_compile_cache` directory. 
- **Subsequent Restarts**: Will be nearly instantaneous.
- **First Audio Generation**: Will be as fast as the model allows, as the "heavy lifting" is already cached.

### 3. Tips for the Best Experience
- **Wait for "Ready"**: Always wait for the status indicator in the top-left to turn green before starting a large production.
- **Keep the Cache**: Do not delete the `.torch_compile_cache` folder unless you are troubleshooting or have changed your GPU.
- **Low VRAM?**: If you have less than 8GB VRAM, consider setting `LOAD_IN_4BIT=true` in your `.env` file. This disables compilation for the main transformer to save memory while keeping it for smaller sub-models.

> [!TIP]
> If you prefer instant startup and don't mind slower generation speeds, you can disable compilation entirely by setting `USE_COMPILE=false` in your `.env` file.

---

## Launch

```bash
source venv/bin/activate
python app.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice --port 5000
```

Navigate to `http://localhost:5000`.

---

## Model Directory Layout

```
voicestudio/
├── app.py
├── requirements.txt
├── setup.sh
├── static/
├── templates/
├── Qwen3-TTS-12Hz-1.7B-CustomVoice/   # downloaded separately
├── Qwen3-TTS-12Hz-1.7B-VoiceDesign/   # downloaded separately
└── Qwen3-TTS-12Hz-1.7B-Base/          # downloaded separately
```

---

## License

Distributed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.

---

<p align="center"><b>Elevating AI Audio Production to Studio Standards</b></p>
