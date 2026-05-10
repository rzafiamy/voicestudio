#!/usr/bin/env python3
"""
Benchmark script for Qwen3-TTS inference speed.
Tests different text lengths and reports chars/sec performance.
"""

import argparse
import time
import torch
from qwen_tts import Qwen3TTSModel

# Test texts of different lengths
TEST_TEXTS = {
    "short": "Hello world, this is a test.",  # ~28 chars
    "medium": "The quick brown fox jumps over the lazy dog. This is a medium length text to test the inference speed of the text-to-speech model. It should give us a good baseline for performance measurement.",  # ~200 chars
    "long": "In the heart of a bustling city, where towering skyscrapers kissed the clouds and the streets hummed with the rhythm of countless footsteps, there lived a young artist named Maya. She spent her days painting vibrant murals on forgotten walls, transforming dull alleyways into galleries of color and life. Each stroke of her brush told a story, a whisper of dreams and hopes that resonated with passersby. Maya believed that art had the power to heal, to inspire, and to unite people from all walks of life."  # ~500 chars
}

def benchmark_model(model_path, num_runs=3):
    """Benchmark the model with different text lengths"""
    
    print(f"\n{'='*60}")
    print(f"Benchmarking: {model_path}")
    print(f"{'='*60}\n")
    
    # Load model with optimizations
    print("Loading model...")
    
    # Disable gradients for inference
    torch.set_grad_enabled(False)
    
    model_kwargs = {
        "device_map": "cuda:0" if torch.cuda.is_available() else "cpu",
        "dtype": torch.float16 if torch.cuda.is_available() else torch.float32,  # Use float16 for speed
    }
    
    # Try to use Flash Attention 2
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
    
    # Detect model type
    if 'CustomVoice' in model_path:
        model_type = 'CustomVoice'
    elif 'VoiceDesign' in model_path:
        model_type = 'VoiceDesign'
    elif 'Base' in model_path:
        model_type = 'Base'
    else:
        model_type = 'CustomVoice'
    
    print(f"Model type: {model_type}")
    
    # Note: torch.compile is not compatible with Qwen3TTSModel wrapper
    # We still get significant speedup from other optimizations
    
    # Warmup
    if model_type == 'CustomVoice':
        print("🔥 Warming up...")
        with torch.inference_mode():
            _ = model.generate_custom_voice(
                text="Warmup generation",
                language="English",
                speaker="Ryan",
                max_new_tokens=50,
                use_cache=True
            )
        print("✅ Warmup complete\n")
    
    # Generation kwargs - use original parameters
    gen_kwargs = {
        "max_new_tokens": 2048,
        "do_sample": True,
        "top_k": 50,
        "top_p": 1.0,
        "temperature": 0.9,
        "repetition_penalty": 1.05,
        "use_cache": True,
    }
    
    # Benchmark each text length
    results = {}
    
    for length_name, text in TEST_TEXTS.items():
        print(f"\n{'─'*60}")
        print(f"Testing: {length_name.upper()} ({len(text)} chars)")
        print(f"Text: {text[:50]}...")
        print(f"{'─'*60}")
        
        times = []
        
        for run in range(num_runs):
            print(f"  Run {run + 1}/{num_runs}...", end=" ", flush=True)
            
            start_time = time.time()
            
            with torch.inference_mode():
                if model_type == 'CustomVoice':
                    wavs, sr = model.generate_custom_voice(
                        text=text,
                        language="English",
                        speaker="Ryan",
                        **gen_kwargs
                    )
                elif model_type == 'VoiceDesign':
                    wavs, sr = model.generate_voice_design(
                        text=text,
                        language="English",
                        instruct="A clear, professional male voice",
                        **gen_kwargs
                    )
                else:
                    print("Base model benchmarking not implemented (requires reference audio)")
                    continue
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            chars_per_sec = len(text) / elapsed
            
            print(f"{elapsed:.2f}s ({chars_per_sec:.2f} chars/sec)")
        
        if times:
            avg_time = sum(times) / len(times)
            avg_chars_per_sec = len(text) / avg_time
            
            results[length_name] = {
                "chars": len(text),
                "avg_time": avg_time,
                "avg_chars_per_sec": avg_chars_per_sec,
                "times": times
            }
            
            print(f"\n  Average: {avg_time:.2f}s ({avg_chars_per_sec:.2f} chars/sec)")
    
    # Summary
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}\n")
    
    for length_name, result in results.items():
        print(f"{length_name.upper():10} | {result['chars']:4} chars | "
              f"{result['avg_time']:6.2f}s | {result['avg_chars_per_sec']:6.2f} chars/sec")
    
    if results:
        overall_avg = sum(r['avg_chars_per_sec'] for r in results.values()) / len(results)
        print(f"\n{'─'*60}")
        print(f"Overall Average: {overall_avg:.2f} chars/sec")
        print(f"{'─'*60}\n")

def main():
    parser = argparse.ArgumentParser(description="Benchmark Qwen3-TTS inference speed")
    parser.add_argument(
        '--model',
        type=str,
        default='./Qwen3-TTS-12Hz-1.7B-CustomVoice',
        help='Path to the model or HuggingFace model ID'
    )
    parser.add_argument(
        '--runs',
        type=int,
        default=3,
        help='Number of runs per test (default: 3)'
    )
    
    args = parser.parse_args()
    
    if not torch.cuda.is_available():
        print("⚠️ WARNING: CUDA not available. Benchmarking on CPU will be very slow.")
        print("For accurate benchmarks, please run on a CUDA-enabled GPU.\n")
    
    benchmark_model(args.model, args.runs)

if __name__ == '__main__':
    main()
