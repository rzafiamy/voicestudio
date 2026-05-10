#!/usr/bin/env python3
"""
Compare performance between 1.7B and 0.6B models.
"""

import time
import torch
from qwen_tts import Qwen3TTSModel

TEXT = "The quick brown fox jumps over the lazy dog. This is a medium length text to test the inference speed."

def test_model(model_path):
    print(f"\n{'='*60}")
    print(f"Testing: {model_path}")
    print(f"{'='*60}\n")
    
    torch.set_grad_enabled(False)
    
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
    
    # Test 3 times
    times = []
    for i in range(3):
        print(f"Run {i+1}/3...", end=" ", flush=True)
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
        times.append(elapsed)
        print(f"{elapsed:.2f}s ({len(TEXT)/elapsed:.2f} chars/sec)")
    
    avg_time = sum(times) / len(times)
    avg_speed = len(TEXT) / avg_time
    
    print(f"\nAverage: {avg_time:.2f}s ({avg_speed:.2f} chars/sec)")
    
    # Cleanup
    del model
    torch.cuda.empty_cache()
    
    return avg_speed

if __name__ == '__main__':
    speeds = {}
    
    # Test 1.7B model
    speeds['1.7B'] = test_model("./Qwen3-TTS-12Hz-1.7B-CustomVoice")
    
    # Test 0.6B model if available
    try:
        speeds['0.6B'] = test_model("./Qwen3-TTS-12Hz-0.6B-CustomVoice")
    except Exception as e:
        print(f"\n⚠️ 0.6B model not available: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}\n")
    
    for model, speed in speeds.items():
        print(f"{model:10} | {speed:6.2f} chars/sec")
    
    if len(speeds) == 2:
        speedup = speeds['0.6B'] / speeds['1.7B']
        print(f"\n0.6B is {speedup:.2f}x faster than 1.7B")
