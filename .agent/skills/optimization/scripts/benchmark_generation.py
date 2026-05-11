
import torch
import time
import os
import sys
from qwen_tts import Qwen3TTSModel

def run_benchmark():
    model_path = os.getenv("DEFAULT_MODEL", "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    if not os.path.exists(model_path):
        print(f"Model {model_path} not found.")
        return

    print(f"🚀 Loading model for benchmark: {model_path}")
    
    # Standard optimized config
    model_kwargs = {
        "device_map": "auto",
        "dtype": torch.bfloat16,
    }
    
    torch.set_float32_matmul_precision('high')
    
    model_wrapper = Qwen3TTSModel.from_pretrained(model_path, **model_kwargs)
    model = model_wrapper.model
    
    print("🛠️ Compiling...")
    if hasattr(model, "talker") and model.talker:
        model.talker.model = torch.compile(model.talker.model)
    
    test_text = "Ceci est un test de performance pour le système de synthèse vocale. Nous vérifions si la vitesse de génération est optimale après les changements de compilation."
    
    print("🔥 Starting Warmup...")
    with torch.inference_mode():
        _ = model_wrapper.generate_custom_voice(text="Warmup", language="French", speaker="Ryan", max_new_tokens=20)
    
    print("📊 Measuring Performance...")
    t0 = time.time()
    with torch.inference_mode():
        wavs, sr = model_wrapper.generate_custom_voice(
            text=test_text, 
            language="French", 
            speaker="Ryan", 
            max_new_tokens=512
        )
    elapsed = time.time() - t0
    ch_s = len(test_text) / elapsed
    
    print(f"\n✅ Results:")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Speed: {ch_s:.2f} ch/s")
    print(f"VRAM: {torch.cuda.memory_allocated()/1024**2:.2f} MB")

if __name__ == "__main__":
    run_benchmark()
