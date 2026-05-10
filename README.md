# 🎙️ Makix Studio | Professional Qwen3-TTS Platform

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Models-orange)](https://huggingface.co/Qwen)

A high-end, professional production environment for the state-of-the-art **Qwen3-TTS** audio models. Designed for creators, developers, and audio engineers who demand a studio-grade workflow for AI speech generation.

---

## ✨ Studio Features

- 🌌 **Cinematic Studio UI**: A deep-themed, professional workspace inspired by high-end DAWs and production software.
- 🎭 **Multi-Paradigm Generation**: 
  - **CustomVoice**: High-fidelity preset speakers for consistent branding.
  - **VoiceDesign**: Prompt-based zero-shot voice synthesis.
  - **VoiceCloning**: Advanced x-vector based cloning for authentic replicas.
- 🌍 **Global Linguistic Support**: Native-level synthesis for English, Chinese, Japanese, Korean, and European languages.
- ⚡ **Turbocharged Engine**: 
  - **KV-Cache** & **Flash Attention 2** integration.
  - **CUDA-Native** optimizations for real-time inference.
  - **Torch-Inference** mode for maximum throughput.
- 📚 **Production Library**: Organized sidebar history with one-click reload and instant audio promotion for cloning references.
- 🎛️ **Precision Control**: Fine-tuned style instructions and generation parameters.

---

## 🚀 Quick Launch

### 1. Automated Setup
```bash
chmod +x setup.sh
./setup.sh
```

### 2. Launch the Studio
```bash
python app.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice --port 5000
```
Navigate to `http://localhost:5000` to enter the studio.

---

## 🛠️ Optimization Stack

Makix Studio is built for performance:
- **Architecture**: Flask + Modern Vanilla JS/CSS (No bloat).
- **GPU Acceleration**: Automated TF32, cuDNN benchmark, and VRAM management.
- **Resource Cleanup**: Intelligent GC and VRAM clearing when switching models.
- **Micro-Inference**: Optimized token-per-second ratios for long-form synthesis.

---

## 📂 Model Support

Place your Qwen3-TTS models in the root directory. The studio will auto-detect:
- `Qwen3-TTS-*-CustomVoice`
- `Qwen3-TTS-*-VoiceDesign`
- `Qwen3-TTS-*-Base` (For Cloning)

---

## 📜 License

Distributed under the **Apache License 2.0**.

---
<p align="center"><b>Elevating AI Audio Production to Studio Standards</b></p>
