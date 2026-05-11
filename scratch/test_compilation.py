
import torch
import os
import sys
from qwen_tts import Qwen3TTSModel

model_path = "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice"
if not os.path.exists(model_path):
    model_path = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

print(f"Testing compilation target: {model_path}")

try:
    model_wrapper = Qwen3TTSModel.from_pretrained(
        model_path, 
        device_map="auto", 
        dtype=torch.bfloat16
    )
    model = model_wrapper.model
    
    # Simulate app.py compilation logic
    print("🚀 Simulating app.py compilation...")
    if hasattr(model, "talker") and model.talker:
        print("Compiling talker and code_predictor...")
        if hasattr(model.talker, "model"):
             model.talker.model = torch.compile(model.talker.model, mode="reduce-overhead")
        if hasattr(model.talker, "code_predictor") and hasattr(model.talker.code_predictor, "model"):
             model.talker.code_predictor.model = torch.compile(model.talker.code_predictor.model, mode="reduce-overhead")
    
    print("✅ Compilation targets reached successfully.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
