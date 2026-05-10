# 🎙️ Qwen3-TTS Web Studio

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Models-orange)](https://huggingface.co/Qwen)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

A premium, Material Design 3 powered web interface for the state-of-the-art **Qwen3-TTS** audio models. Experience high-fidelity text-to-speech with real-time optimization and professional voice design.

---

## ✨ Key Features

- 🎨 **Premium MD3 Design**: A sleek, modern interface with fluid animations and responsive layout.
- 🎤 **Pro Voice Selection**: Instant access to 9+ premium voices across multiple languages and dialects.
- 🌍 **Global Support**: Full support for English, Chinese, Japanese, Korean, French, German, and more.
- 🔄 **Dynamic Model Switching**: Hot-swap between `CustomVoice`, `VoiceDesign`, and `Base` models without downtime.
- ⚡ **Accelerated Inference**: Built-in support for **KV-Cache**, **Flash Attention 2**, and **CUDA** optimizations (2x+ speedup).
- 💾 **Studio-Grade Storage**: Automatic persistence of generated audio with rich metadata in a structured library.
- 🎛️ **Precision Control**: Fine-tune your audio output with style instructions and advanced generation parameters.

---

## 🚀 Quick Start

### 1. Automated Setup (Recommended)
The easiest way to get started is using our automated setup script:
```bash
chmod +x setup.sh
./setup.sh
```

### 2. Manual Installation
If you prefer manual control:
```bash
# Create environment
python3 -m venv venv
source venv/bin/activate

# Install core dependencies
pip install -r requirements.txt

# (Optional) Install Flash Attention 2 for 2x speedup
# If you have a compatible GPU, you can install it via pip or download a pre-built wheel
# from https://github.com/DAO-AILab/flash-attention/releases
pip install flash-attn --no-build-isolation
```

### 3. Launch the Studio
```bash
python app.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice --port 5000
```
Then navigate to `http://localhost:5000`.

---

## 📂 Model Discovery

The application automatically detects models in the root directory. To download official models:

```bash
pip install -U "huggingface_hub[cli]"

# Example: Download the 1.7B CustomVoice model
hf download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local-dir ./Qwen3-TTS-12Hz-1.7B-CustomVoice
```

---

## 🛠️ Performance Optimizations

This studio is engineered for speed. By default, it applies:
- **KV-Cache**: Significant speedup for long sequences.
- **TF32 Precision**: Leverages Ampere+ GPU architectures.
- **Inference Mode**: Optimized memory usage and throughput.
- **Warmup Phase**: Initial JIT optimization for subsequent calls.

---

## 📊 Benchmarking
Test your hardware performance with our built-in benchmark tool:
```bash
python benchmark.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice
```

---

## 📜 License

Distributed under the **Apache License 2.0**. See `LICENSE` for more information.

---

## 🙌 Credits
- **Model Architecture**: [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) by the Qwen Team.
- **UI/UX**: Powered by Material Design 3 and Flask.

---
<p align="center">Made with ❤️ for the AI Audio Community</p>
