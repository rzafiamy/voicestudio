
import torch
import time
import os
import re
import gc
from qwen_tts import Qwen3TTSModel

def split_old(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]

def split_new(text):
    initial = re.split(r'(?<=[.!?])\s+|\n+', text)
    segments = []
    for s in initial:
        s = s.strip()
        if not s: continue
        if len(s) > 110:
            sub = re.split(r'(?<=[,;:])\s+|(?<=\s-)\s+', s)
            segments.extend([ss.strip() for ss in sub if ss.strip()])
        else:
            segments.append(s)
    return segments

def benchmark_splitting(model_path):
    print(f"\n" + "="*60)
    print(f"🚀 BENCHMARK: {os.path.basename(model_path)}")
    print("="*60)
    
    model_wrapper = Qwen3TTSModel.from_pretrained(model_path, device_map="auto", dtype=torch.bfloat16)
    
    # Optimization settings
    torch.set_float32_matmul_precision('high')
    
    text = (
        "Salut à toi qui écoutes ça, que tu sois dev, tech lead, ou simplement quelqu'un qui suit l'IA de près - "
        "bienvenue dans cet épisode qui va peut-être te faire voir l'open source d'un œil complètement différent. "
        "Moi, ça fait un peu plus de deux ans que je suis cette révolution de l'IA de façon quasi obsessionnelle. "
        "Depuis le moment où ChatGPT a tout fait exploser fin 2022, je n'ai pas lâché le fil."
    )
    
    # Warmup
    print("🔥 Warmup...")
    with torch.inference_mode():
        _ = model_wrapper.generate_custom_voice(text="Warmup", language="French", speaker="Ryan", max_new_tokens=10)

    # 1. Old Splitting
    sentences_old = split_old(text)
    print(f"📦 Old Splitter: {len(sentences_old)} sentences in parallel")
    t0 = time.time()
    with torch.inference_mode():
        _ = model_wrapper.generate_custom_voice(text=sentences_old, language="French", speaker="Ryan", max_new_tokens=512)
    t_old = time.time() - t0
    speed_old = len(text)/t_old
    
    # 2. New Splitting
    sentences_new = split_new(text)
    print(f"📦 New Splitter: {len(sentences_new)} segments in parallel")
    t1 = time.time()
    with torch.inference_mode():
        _ = model_wrapper.generate_custom_voice(text=sentences_new, language="French", speaker="Ryan", max_new_tokens=512)
    t_new = time.time() - t1
    speed_new = len(text)/t_new
    
    print(f"\n📊 Results:")
    print(f"   - Old Speed: {speed_old:.2f} ch/s")
    print(f"   - New Speed: {speed_new:.2f} ch/s")
    print(f"   - Improvement: {speed_new/speed_old:.2f}x faster")
    
    del model_wrapper
    gc.collect()
    torch.cuda.empty_cache()
    return {"model": os.path.basename(model_path), "old": speed_old, "new": speed_new, "ratio": speed_new/speed_old}

def main():
    models = [
        "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "./models/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    ]
    
    results = []
    for m in models:
        if os.path.exists(m):
            results.append(benchmark_splitting(m))
            
    print("\n" + "="*60)
    print("🏆 FINAL COMPARISON: OLD VS NEW PIPELINE")
    print("="*60)
    print(f"{'Model':<40} | {'Old ch/s':<10} | {'New ch/s':<10} | {'Gain'}")
    print("-" * 75)
    for r in results:
        print(f"{r['model']:<40} | {r['old']:<10.2f} | {r['new']:<10.2f} | {r['ratio']:.2f}x")
    print("="*60)

if __name__ == "__main__":
    main()
