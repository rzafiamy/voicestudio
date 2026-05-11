
import torch
import torch._dynamo
import time
import os
import gc
import json
from qwen_tts import Qwen3TTSModel

def benchmark_model(model_path):
    print(f"\n" + "="*60)
    print(f"🚀 BENCHMARKING: {os.path.basename(model_path)}")
    print("="*60)
    
    try:
        model_kwargs = {
            "device_map": "auto",
            "dtype": torch.bfloat16,
        }
        
        # 1. Load
        t_load = time.time()
        model_wrapper = Qwen3TTSModel.from_pretrained(model_path, **model_kwargs)
        model = model_wrapper.model
        load_time = time.time() - t_load
        print(f"✅ Loaded in {load_time:.2f}s")

        # 2. Compile
        print("🛠️ Compiling Transformers...")
        if hasattr(model, "talker") and model.talker:
            if hasattr(model.talker, "model"):
                model.talker.model = torch.compile(model.talker.model)
            if hasattr(model.talker, "code_predictor") and hasattr(model.talker.code_predictor, "model"):
                model.talker.code_predictor.model = torch.compile(model.talker.code_predictor.model)
        
        # 3. Warmup
        print("🔥 Warming up (Compiling kernels)...")
        test_text = "Ceci est un test de performance court pour la compilation."
        with torch.inference_mode():
            if "CustomVoice" in model_path:
                _ = model_wrapper.generate_custom_voice(text=test_text, language="French", speaker="Ryan", max_new_tokens=20)
            elif "VoiceDesign" in model_path:
                _ = model_wrapper.generate_voice_design(text=test_text, language="French", instruct="A warm female voice.", max_new_tokens=20)
            elif "Base" in model_path:
                # We need a dummy audio for clone
                dummy_wav = torch.zeros(24000*2).numpy()
                prompt = model_wrapper.create_voice_clone_prompt(ref_audio=(dummy_wav, 24000), x_vector_only_mode=True)
                _ = model_wrapper.generate_voice_clone(text=test_text, language="French", voice_clone_prompt=prompt, max_new_tokens=20)

        # 4. Real Benchmark
        benchmark_text = (
            "Salut à toi qui écoutes ça, que tu sois dev, tech lead, ou simplement quelqu'un qui suit l'IA de près - "
            "bienvenue dans cet épisode qui va peut-être te faire voir l'open source d'un œil complètement différent."
        )
        print(f"📊 Measuring performance on {len(benchmark_text)} characters...")
        
        t0 = time.time()
        with torch.inference_mode():
            if "CustomVoice" in model_path:
                wavs, sr = model_wrapper.generate_custom_voice(text=benchmark_text, language="French", speaker="Ryan", max_new_tokens=512)
            elif "VoiceDesign" in model_path:
                wavs, sr = model_wrapper.generate_voice_design(text=benchmark_text, language="French", instruct="A warm female voice.", max_new_tokens=512)
            elif "Base" in model_path:
                dummy_wav = torch.zeros(24000*2).numpy()
                prompt = model_wrapper.create_voice_clone_prompt(ref_audio=(dummy_wav, 24000), x_vector_only_mode=True)
                wavs, sr = model_wrapper.generate_voice_clone(text=benchmark_text, language="French", voice_clone_prompt=prompt, max_new_tokens=512)
        
        elapsed = time.time() - t0
        audio_duration = sum(len(w) for w in wavs) / sr
        rtf = elapsed / audio_duration if audio_duration > 0 else 0
        ch_s = len(benchmark_text) / elapsed
        
        print(f"\n📊 RESULTS for {os.path.basename(model_path)}:")
        print(f"   - Elapsed Time: {elapsed:.2f}s")
        print(f"   - Audio Length: {audio_duration:.2f}s")
        print(f"   - Real-Time Factor (RTF): {rtf:.2f}")
        print(f"   - Throughput: {ch_s:.2f} ch/s")
        print(f"   - VRAM Peak: {torch.cuda.max_memory_allocated()/1024**2:.2f} MB")
        
        # Cleanup
        del model
        del model_wrapper
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        
        return {"model": os.path.basename(model_path), "ch_s": ch_s, "rtf": rtf, "elapsed": elapsed}

    except Exception as e:
        print(f"❌ Failed benchmark for {model_path}: {e}")
        return None

def main():
    torch.set_float32_matmul_precision('high')
    torch._dynamo.config.cache_size_limit = 512
    
    models = [
        "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "./models/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "./models/Qwen3-TTS-12Hz-1.7B-Base",
        "./models/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    ]
    
    results = []
    for m in models:
        if os.path.exists(m):
            res = benchmark_model(m)
            if res:
                results.append(res)
    
    print("\n" + "="*60)
    print("🏆 FINAL BENCHMARK SUMMARY")
    print("="*60)
    print(f"{'Model':<40} | {'Speed (ch/s)':<12} | {'RTF':<6}")
    print("-" * 65)
    for r in results:
        print(f"{r['model']:<40} | {r['ch_s']:<12.2f} | {r['rtf']:<6.2f}")
    print("="*60)

if __name__ == "__main__":
    main()
