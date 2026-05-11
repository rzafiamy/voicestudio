# Performance Optimization Rules for Qwen3-TTS

This document outlines the critical performance patterns required to keep the Voice Studio running at high speed on modern GPUs (like RTX 40 series).

## 1. Torch Compilation Strategy
The Qwen3-TTS model is a multi-stage autoregressive Transformer. To achieve optimal speed, multiple sub-models must be compiled:
- **Non-AR models**: `speaker_encoder` and `speech_tokenizer` can be compiled with `mode="reduce-overhead"`.
- **AR models**: `talker` and `code_predictor` (sub-talker) MUST be compiled with `mode="default"`. Avoid `reduce-overhead` for these as it crashes with dynamic sequence lengths due to CUDA Graph limitations.
- **Cache Limit**: Always set `torch._dynamo.config.cache_size_limit = 512` (or higher) to prevent frequent recompilations during long-form synthesis.

## 2. Hardware Acceleration
- **TF32**: Always enable `torch.backends.cuda.matmul.allow_tf32 = True` and `torch.set_float32_matmul_precision('high')`. This provides a significant boost on Ampere and Ada GPUs.
- **Flash Attention**: Ensure `attn_implementation="flash_attention_2"` is used if the `flash-attn` package is installed. Fall back to `sdpa` otherwise.
- **BF16**: Use `torch.bfloat16` for all inference. Avoid `float32` on GPU and avoid `4-bit` (bitsandbytes) unless VRAM is extremely limited (< 4GB), as 4-bit is slower and incompatible with stable compilation.

## 3. Batching & Text Splitting
The GPU throughput is maximized by processing multiple text segments in parallel.
- **Aggressive Splitting**: Don't just split by sentences. Split long sentences at natural pauses (`,`, `;`, `:`, `-`) if they exceed ~100 characters.
- **Batch Size**: Maintain a `BATCH_SIZE` of 16. The GPU handles 16 segments almost as fast as 1 segment.
- **Padding**: The underlying model handles left-padding for the Talker. Keep segments within a batch relatively similar in length to minimize padding waste.

## 4. Cold Start & Warmup
- **Warmup Generation**: Perform a dummy generation of ~50 tokens at startup. This triggers the initial kernel compilation so the first user request doesn't bear the full cost of "baking" the model.
- **Persistence**: Be aware that the first request after a restart will still be slower as it optimizes for specific user-provided lengths.
