#!/usr/bin/env python3
"""
Quick performance test to compare before/after optimizations.
"""

import time
import torch
from qwen_tts import Qwen3TTSModel

# Test text
TEXT = "The quick brown fox jumps over the lazy dog. This is a medium length text to test the inference speed."

def test_performance(model_path):
    print(f"Testing: {model_path}\n")
    
    # Disable gradients
    torch.set_grad_enabled(False)
    
    # Load model
    model_kwargs = {
        "device_map": "cuda:0" if torch.cuda.is_available() else "cpu",
        "dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
    }
    
    try:
        import flash_attn
        model_kwargs["attn_implementation"] = "flash_attention_2"
        print("⚡ Flash Attention 2 enabled")
    except ImportError:
        print("⚠️ Flash Attention 2 not found")
    
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        low_cpu_mem_usage=True,
        **model_kwargs
    )
    
    # Warmup
    print("Warming up...")
    with torch.inference_mode():
        _ = model.generate_custom_voice(
            text="Warmup",
            language="English",
            speaker="Ryan",
            max_new_tokens=50,
            use_cache=True
        )
    
    # Test
    print(f"\nGenerating: {TEXT}\n")
    
    start = time.time()
    with torch.inference_mode():
        wavs, sr = model.generate_custom_voice(
            text=TEXT,
            language="English",
            speaker="Ryan",
            max_new_tokens=2048,
            do_sample=True,
            top_k=50,
            top_p=1.0,
            temperature=0.9,
            use_cache=True
        )
    elapsed = time.time() - start
    
    chars_per_sec = len(TEXT) / elapsed
    
    print(f"Time: {elapsed:.2f}s")
    print(f"Speed: {chars_per_sec:.2f} chars/sec")
    print(f"Text length: {len(TEXT)} chars")

if __name__ == '__main__':
    test_performance("./Qwen3-TTS-12Hz-1.7B-CustomVoice")
