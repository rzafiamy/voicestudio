
import torch
import time
import os
import gc
from qwen_tts import Qwen3TTSModel

def test_speed(model_path, use_compile=True):
    print(f"\n🚀 Testing: {os.path.basename(model_path)} (Compile={use_compile})")
    
    model_kwargs = {
        "device_map": "auto",
        "dtype": torch.bfloat16,
    }
    
    model_wrapper = Qwen3TTSModel.from_pretrained(model_path, **model_kwargs)
    model = model_wrapper.model
    
    if use_compile:
        print("🛠️ Compiling Code Predictor & Encoders...")
        if hasattr(model, "speaker_encoder") and model.speaker_encoder:
            model.speaker_encoder = torch.compile(model.speaker_encoder)
        if hasattr(model, "speech_tokenizer") and model.speech_tokenizer:
            model.speech_tokenizer.model = torch.compile(model.speech_tokenizer.model)
        if hasattr(model, "talker") and hasattr(model.talker, "code_predictor"):
            model.talker.code_predictor.model = torch.compile(model.talker.code_predictor.model)
        # Note: We skip compiling the main talker Transformer for stability in this benchmark
    
    text = (
        "Salut à toi qui écoutes ça, que tu sois dev, tech lead, ou simplement quelqu'un qui suit l'IA de près - "
        "bienvenue dans cet épisode qui va peut-être te faire voir l'open source d'un œil complètement différent."
    )
    
    # Warmup
    with torch.inference_mode():
        if "CustomVoice" in model_path:
            _ = model_wrapper.generate_custom_voice(text="Warmup", language="French", speaker="Ryan", max_new_tokens=20)
        elif "VoiceDesign" in model_path:
            _ = model_wrapper.generate_voice_design(text="Warmup", language="French", instruct="Female", max_new_tokens=20)
        elif "Base" in model_path:
            _ = model_wrapper.generate_voice_clone(text="Warmup", language="French", ref_audio=(torch.zeros(24000).numpy(), 24000), x_vector_only_mode=True, max_new_tokens=20)

    # Benchmark
    t0 = time.time()
    with torch.inference_mode():
        if "CustomVoice" in model_path:
            wavs, sr = model_wrapper.generate_custom_voice(text=text, language="French", speaker="Ryan", max_new_tokens=512)
        elif "VoiceDesign" in model_path:
            wavs, sr = model_wrapper.generate_voice_design(text=text, language="French", instruct="Female", max_new_tokens=512)
        elif "Base" in model_path:
            wavs, sr = model_wrapper.generate_voice_clone(text=text, language="French", ref_audio=(torch.zeros(24000).numpy(), 24000), x_vector_only_mode=True, max_new_tokens=512)
    
    elapsed = time.time() - t0
    ch_s = len(text) / elapsed
    print(f"✅ Result: {ch_s:.2f} ch/s ({elapsed:.2f}s)")
    
    del model
    del model_wrapper
    gc.collect()
    torch.cuda.empty_cache()
    return ch_s

def main():
    torch.set_float32_matmul_precision('high')
    models = [
        "./models/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "./models/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    ]
    
    for m in models:
        if os.path.exists(m):
            test_speed(m, use_compile=False) # Baseline
            test_speed(m, use_compile=True)  # Optimized

if __name__ == "__main__":
    main()
