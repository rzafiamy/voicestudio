
import torch
import os
import sys
from qwen_tts import Qwen3TTSModel

model_path = "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice"
if not os.path.exists(model_path):
    model_path = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

print(f"Testing model: {model_path}")

try:
    model_wrapper = Qwen3TTSModel.from_pretrained(
        model_path, 
        device_map="auto", 
        dtype=torch.bfloat16
    )
    model = model_wrapper.model
    
    print(f"Model class: {type(model)}")
    if hasattr(model, "talker"):
        print("Talker found")
        if hasattr(model.talker, "code_predictor"):
            print("Code Predictor found")
            print(f"Code Predictor type: {type(model.talker.code_predictor)}")
            
    # Check flash attention
    print(f"Attn implementation: {model.config._attn_implementation}")
    
    # Check VRAM
    if torch.cuda.is_available():
        print(f"VRAM Allocated: {torch.cuda.memory_allocated()/1024**2:.2f} MB")
        print(f"VRAM Reserved: {torch.cuda.memory_reserved()/1024**2:.2f} MB")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
