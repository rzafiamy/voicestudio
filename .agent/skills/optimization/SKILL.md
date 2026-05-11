---
name: qwen_tts_optimization
description: Specialized skill for optimizing Qwen3-TTS performance and stability.
---

# Qwen3-TTS Optimization Skill

This skill provides the knowledge and tools to diagnose and fix performance issues in the Makix Qwen-TTS Studio.

## Core Capabilities
1. **Dynamic Batch Optimization**: Analyze text and apply optimal splitting strategies to maximize GPU utilization.
2. **Compilation Management**: Apply targeted `torch.compile` settings that balance speed and stability.
3. **Hardware Tuning**: Configure TF32, SDPA, and BF16 for specific GPU architectures.

## Usage Instructions
When a user reports slow generation speeds:
1. **Check the Splitter**: Ensure `split_text_to_sentences` is splitting long sentences into segments < 110 characters.
2. **Verify Compile Mode**: Check if `talker.model` is being compiled with `mode="default"`. If it's using `reduce-overhead`, it might crash with dynamic shapes.
3. **VRAM Check**: Ensure `LOAD_IN_4BIT` is `False` if VRAM > 6GB.
4. **TF32 Status**: Ensure `torch.set_float32_matmul_precision('high')` is set.

## Diagnostic Script
Use `scripts/benchmark_generation.py` to test the current throughput.

## Common Troubleshooting
- **Error: CUDA Graphs overwritten**: This means `reduce-overhead` was used on a dynamic sequence. Switch to `default` compilation mode.
- **Speed < 30 ch/s**: Check if sentences are too long or if 4-bit is enabled.
- **High latency on first run**: Expected behavior for `torch.compile`. Do not optimize further unless it persists after 3 runs.
