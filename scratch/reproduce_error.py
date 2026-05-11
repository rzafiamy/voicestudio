
import torch
import os
from qwen_tts import Qwen3TTSModel
from transformers import BitsAndBytesConfig

model_path = "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice"
if not os.path.exists(model_path):
    model_path = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

print(f"Testing generation with compilation: {model_path}")

try:
    # Load in 4-bit to reproduce the error
    model_kwargs = {
        "device_map": "auto",
        "dtype": torch.bfloat16,
        "quantization_config": BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
    }
    
    model_wrapper = Qwen3TTSModel.from_pretrained(model_path, **model_kwargs)
    model = model_wrapper.model
    
    print("🚀 Compiling...")
    if hasattr(model, "talker") and model.talker:
        if hasattr(model.talker, "model"):
             model.talker.model = torch.compile(model.talker.model, mode="reduce-overhead")
    
    print("🔥 Testing generation...")
    with torch.inference_mode():
        _ = model_wrapper.generate_custom_voice(
            text="Test", language="English", speaker="Ryan", max_new_tokens=10
        )
    print("✅ Success!")

except Exception as e:
    print(f"❌ Error caught: {e}")
    import traceback
    traceback.print_exc()
