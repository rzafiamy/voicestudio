
import torch
import os
from qwen_tts import Qwen3TTSModel

model_path = "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice"
if not os.path.exists(model_path):
    model_path = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

print(f"Testing generation with SAFE compilation: {model_path}")

try:
    # Load in BF16 (No 4-bit)
    model_kwargs = {
        "device_map": "auto",
        "dtype": torch.bfloat16,
    }
    
    model_wrapper = Qwen3TTSModel.from_pretrained(model_path, **model_kwargs)
    model = model_wrapper.model
    
    print("🚀 Compiling (Default mode)...")
    if hasattr(model, "talker") and model.talker:
        if hasattr(model.talker, "model"):
             model.talker.model = torch.compile(model.talker.model)
        if hasattr(model.talker, "code_predictor") and hasattr(model.talker.code_predictor, "model"):
             model.talker.code_predictor.model = torch.compile(model.talker.code_predictor.model)
    
    print("🔥 Testing generation...")
    with torch.inference_mode():
        # First run (compilation)
        print("Run 1 (Warmup/Compile)...")
        _ = model_wrapper.generate_custom_voice(
            text="Test", language="English", speaker="Ryan", max_new_tokens=10
        )
        # Second run (measured)
        print("Run 2 (Optimized)...")
        import time
        t0 = time.time()
        _ = model_wrapper.generate_custom_voice(
            text="Test generation for speed check.", language="English", speaker="Ryan", max_new_tokens=20
        )
        print(f"Run 2 took: {time.time()-t0:.2f}s")
        
    print("✅ Success!")

except Exception as e:
    print(f"❌ Error caught: {e}")
    import traceback
    traceback.print_exc()
