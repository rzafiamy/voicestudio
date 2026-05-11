# 📊 Makix Qwen-TTS Performance Benchmark

This document tracks the performance optimizations and benchmarks for the Qwen3-TTS model within the Voice Studio environment.

## 💻 Hardware Environment
- **GPU**: NVIDIA GeForce RTX 4070 Laptop GPU (8GB VRAM)
- **Architecture**: Ada Lovelace (Supports BF16, TF32, Flash Attention 2)
- **OS**: Linux (Ubuntu/Debian based)

## 🚀 Optimization Stack
The following optimizations have been implemented to achieve a **~2.8x speed improvement**:

| Optimization | Description | Impact |
| :--- | :--- | :--- |
| **BF16 Inference** | Switched from 4-bit to native `bfloat16`. | Faster compute, higher quality, avoids dequantization lag. |
| **Torch Compile** | Compiled `code_predictor`, `speaker_encoder`, and `tokenizer`. | ~25% reduction in per-token latency. |
| **Aggressive Splitting** | Smart text splitting at `, ; : -` for long sentences. | Massive increase in GPU occupancy via batch parallelism. |
| **TF32 & Matmul** | Enabled `TensorFloat32` and `high` precision matmul. | Optimized throughput for Ada Lovelace Tensor Cores. |
| **Async Executor** | Offloaded generation to a thread pool to keep the FastAPI loop responsive. | Smoother UI and better concurrency. |

---

## 🏆 Performance Comparison (0.6B Model)
Tested using a 208-character French text.

| Metric | Baseline (Initial) | Optimized (Current) | Gain |
| :--- | :--- | :--- | :--- |
| **Throughput** | 24.5 ch/s | **68.6 ch/s** | **2.80x** |
| **Total Time** | 23.48s | **8.15s** | **-65%** |
| **RTF (Real-Time Factor)** | 1.60 | **0.55** | **Synthesis > Real-time** |
| **Batch Occupancy** | 3/16 | **7-12/16** | **High Utilization** |

---

## 📏 Model Comparison (Optimized)

| Model Architecture | VRAM Usage | Avg. Speed | Notes |
| :--- | :--- | :--- | :--- |
| **Qwen3-0.6B-Custom** | ~2.5 GB | 68.6 ch/s | Extremely fast, very stable on 8GB VRAM. |
| **Qwen3-1.7B-Custom** | ~5.8 GB | 45.2 ch/s* | High quality. Requires `BATCH_SIZE <= 8` to avoid OOM. |
| **Qwen3-1.7B-Base** | ~6.2 GB | 42.1 ch/s* | Voice cloning mode. High quality, heavy VRAM load. |

*\*Estimated based on safe batch sizes.*

---

## ⚠️ Known Issues & Constraints
- **Cold Start**: The first generation after a restart takes **~60-90s** due to `torch.compile` kernel generation. Subsequent runs are near-instant.
- **VRAM Out-of-Memory**: When using 1.7B models, do not use more than 8 parallel segments on an 8GB GPU. If OOM occurs, reduce `BATCH_SIZE` in `.env`.
- **Compile Modes**: Using `mode="reduce-overhead"` on the main Talker Transformer is unstable with dynamic lengths. We use `mode="default"`.

## 🧪 How to Reproduce
Run the automated benchmark script:
```bash
./venv/bin/python scratch/splitting_benchmark.py
```
This script compares the old single-sentence pipeline against the new multi-segment parallel pipeline.
