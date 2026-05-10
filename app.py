import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
import torch
import soundfile as sf
from flask import Flask, render_template, request, jsonify, send_file
from qwen_tts import Qwen3TTSModel

# GPU Optimizations
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True  # Enable cuDNN auto-tuner for optimal convolution algorithms
    torch.backends.cuda.matmul.allow_tf32 = True  # Enable TF32 for faster matmul on Ampere+ GPUs
    torch.backends.cudnn.allow_tf32 = True

app = Flask(__name__)

# Global model instance
model = None
model_name = None
model_type = None  # 'CustomVoice', 'VoiceDesign', or 'Base'
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

# Available voices for CustomVoice models
CUSTOM_VOICES = {
    "Vivian": {"description": "Bright, slightly edgy young female voice", "language": "Chinese"},
    "Serena": {"description": "Warm, gentle young female voice", "language": "Chinese"},
    "Uncle_Fu": {"description": "Seasoned male voice with a low, mellow timbre", "language": "Chinese"},
    "Dylan": {"description": "Youthful Beijing male voice with a clear, natural timbre", "language": "Chinese (Beijing Dialect)"},
    "Eric": {"description": "Lively Chengdu male voice with a slightly husky brightness", "language": "Chinese (Sichuan Dialect)"},
    "Ryan": {"description": "Dynamic male voice with strong rhythmic drive", "language": "English"},
    "Aiden": {"description": "Sunny American male voice with a clear midrange", "language": "English"},
    "Ono_Anna": {"description": "Playful Japanese female voice with a light, nimble timbre", "language": "Japanese"},
    "Sohee": {"description": "Warm Korean female voice with rich emotion", "language": "Korean"}
}

def discover_local_models():
    """Discover available models in the current directory"""
    local_models = []
    current_dir = Path('.')
    
    # Look for model directories
    for item in current_dir.iterdir():
        if item.is_dir() and 'Qwen3-TTS' in item.name and 'storage' not in item.name:
            local_models.append(str(item))
            
    local_models.sort()
    
    # Only if no local models found, provide defaults
    if not local_models:
        return [
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
        ]
    
    return local_models

AVAILABLE_MODELS = discover_local_models()

SUPPORTED_LANGUAGES = [
    "Auto",
    "Chinese",
    "English",
    "Japanese",
    "Korean",
    "German",
    "French",
    "Russian",
    "Portuguese",
    "Spanish",
    "Italian"
]

import gc

def load_model(model_path):
    """Load the TTS model"""
    global model, model_name, model_type
    
    # Unload existing model if present to free VRAM
    if model is not None:
        print(f"Unloading previous model: {model_name}")
        try:
            # Move to CPU first to help torch release CUDA handles
            if hasattr(model, 'to'):
                model.to('cpu')
        except:
            pass
        del model
        model = None
        gc.collect()
        gc.collect() # Double collect for circular references
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()
            time.sleep(0.2)

            
    model_path = model_path.rstrip('/')
    print(f"Loading model: {model_path}")
    try:
        # Ensure we are on the correct device
        if torch.cuda.is_available():
            torch.cuda.set_device(0)
            
        # Disable gradient computation globally for inference
        torch.set_grad_enabled(False)
        
        # Load with Flash Attention 2 if available
        model_kwargs = {
            "device_map": "auto", # Let accelerate handle the placement optimally
            "dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
        }
        
        # Try to use Flash Attention 2 (requires both the package and CUDA)
        try:
            import flash_attn
            if torch.cuda.is_available():
                model_kwargs["attn_implementation"] = "flash_attention_2"
                print("⚡ Flash Attention 2 enabled")
            else:
                print("⚠️ Flash Attention 2 skipped (no CUDA), using default attention")
        except ImportError:
            print("⚠️ Flash Attention 2 not found, using default attention")

        model = Qwen3TTSModel.from_pretrained(
            model_path,
            low_cpu_mem_usage=True,
            **model_kwargs
        )
        
        model_name = model_path
        
        # Detect model type from path
        if 'CustomVoice' in model_path:
            model_type = 'CustomVoice'
        elif 'VoiceDesign' in model_path:
            model_type = 'VoiceDesign'
        elif 'Base' in model_path:
            model_type = 'Base'
        else:
            model_type = 'CustomVoice'  # Default
        
        # Warmup generation to optimize CUDA kernels
        if torch.cuda.is_available() and model_type == 'CustomVoice':
            try:
                print("🔥 Running warmup generation...")
                # Use inference_mode and be very conservative with tokens
                with torch.inference_mode():
                    # Check if speaker exists in the newly loaded model if possible
                    # but since we don't have easy access to the list yet, we'll just try
                    _ = model.generate_custom_voice(
                        text="Warmup",
                        language="English",
                        speaker="Ryan",
                        max_new_tokens=20, # Minimal tokens for warmup
                        use_cache=True
                    )
                print("✅ Warmup complete")
            except Exception as e:
                print(f"⚠️ Warmup failed (non-critical): {e}")
        
        print(f"Model loaded successfully: {model_name} (Type: {model_type})")
    except Exception as e:
        print(f"CRITICAL: Failed to load model: {str(e)}")
        # If loading fails, ensure we clean up
        if model is not None:
            del model
            model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        raise e

@app.route('/api/vram', methods=['GET'])
def get_vram_status():
    """Get GPU memory usage status"""
    if not torch.cuda.is_available():
        return jsonify({
            "available": False,
            "total": 0,
            "allocated": 0,
            "reserved": 0,
            "free": 0,
            "percentage": 0
        })
    
    try:
        # torch.cuda.memory_reserved is what is actually claimed from the OS
        # torch.cuda.memory_allocated is what is currently used by tensors
        total = torch.cuda.get_device_properties(0).total_memory
        allocated = torch.cuda.memory_allocated(0)
        reserved = torch.cuda.memory_reserved(0)
        
        # We'll use 'reserved' as the main metric since it shows what the app has "taken"
        # but 'allocated' is also important.
        percentage = (reserved / total) * 100 if total > 0 else 0
        
        return jsonify({
            "available": True,
            "total": total,
            "allocated": allocated,
            "reserved": reserved,
            "percentage": percentage,
            "device": torch.cuda.get_device_name(0)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """Serve the main UI"""
    return render_template('index.html')

@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Get available voices"""
    return jsonify(CUSTOM_VOICES)

@app.route('/api/models', methods=['GET'])
def get_models():
    """Get available models"""
    return jsonify({
        "models": AVAILABLE_MODELS,
        "current": model_name,
        "type": model_type
    })

@app.route('/api/switch_model', methods=['POST'])
def switch_model():
    """Switch to a different model"""
    try:
        data = request.json
        new_model_path = data.get('model')
        
        if not new_model_path:
            return jsonify({"error": "Model path is required"}), 400
        
        if new_model_path not in AVAILABLE_MODELS:
            return jsonify({"error": f"Model {new_model_path} not found in available models"}), 400
        
        # Load the new model
        print(f"Switching to model: {new_model_path}")
        load_model(new_model_path)
        
        return jsonify({
            "success": True,
            "model": model_name,
            "type": model_type,
            "message": f"Successfully switched to {model_type} model"
        })
        
    except Exception as e:
        print(f"Error switching model: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Get supported languages"""
    return jsonify(SUPPORTED_LANGUAGES)

DEFAULT_GEN_KWARGS = dict(
    max_new_tokens=2048,  # Keep original for quality
    do_sample=True,
    top_k=50,
    top_p=1.0,
    temperature=0.9,
    repetition_penalty=1.05,
    subtalker_dosample=True,
    subtalker_top_k=50,
    subtalker_top_p=1.0,
    subtalker_temperature=0.9,
)

@app.route('/api/generate', methods=['POST'])
def generate_audio():
    """Generate audio from text"""
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'Auto')
        speaker = data.get('speaker', 'Vivian')
        instruct = data.get('instruct', '')
        
        # Generation control parameters
        gen_kwargs = DEFAULT_GEN_KWARGS.copy()
        user_kwargs = data.get('kwargs', {})
        # Update with user provided kwargs if any, ensuring type safety could be added here
        for k, v in user_kwargs.items():
            if k in gen_kwargs:
                gen_kwargs[k] = v

        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        if model is None:
            return jsonify({"error": "Model not loaded"}), 500
        
        # Generate audio based on model type
        print(f"Generating audio for text: {text[:50]}... (Model type: {model_type})")
        
        start_time = time.time()
        
        # Use inference_mode for better performance (disables gradient computation)
        with torch.inference_mode():
            if model_type == 'VoiceDesign':
                # VoiceDesign model uses instruct for voice description
                if not instruct:
                    return jsonify({"error": "VoiceDesign model requires a voice description in the 'Style Instruction' field"}), 400
                
                wavs, sr = model.generate_voice_design(
                    text=text,
                    language=language,
                    instruct=instruct,
                    **gen_kwargs
                )
            elif model_type == 'CustomVoice':
                # CustomVoice model uses speaker selection
                wavs, sr = model.generate_custom_voice(
                    text=text,
                    language=language,
                    speaker=speaker,
                    instruct=instruct if instruct else None,
                    **gen_kwargs
                )
            elif model_type == 'Base':
                # Base model - Voice Cloning
                ref_audio_path = data.get('ref_audio_path')
                ref_text = data.get('ref_text')
                
                # Use 'xvec_only' if user requests it OR if ref_text is missing
                x_vector_only_mode = data.get('x_vector_only', False)
                if not ref_text:
                    x_vector_only_mode = True
                
                if not ref_audio_path:
                    return jsonify({"error": "Base model requires 'ref_audio_path' for voice cloning"}), 400
                    
                if not os.path.isabs(ref_audio_path):
                    possible_path = STORAGE_DIR / ref_audio_path
                    if possible_path.exists():
                        ref_audio_path = str(possible_path)
                
                print(f"Cloning voice from: {ref_audio_path} (X-Vector Mode: {x_vector_only_mode})")
                
                # Create prompt
                prompt_items = model.create_voice_clone_prompt(
                    ref_audio=ref_audio_path,
                    ref_text=ref_text if not x_vector_only_mode else None,
                    x_vector_only_mode=x_vector_only_mode
                )
                
                try:
                    wavs, sr = model.generate_voice_clone(
                        text=text,
                        language=language,
                        voice_clone_prompt=prompt_items,
                        **gen_kwargs
                    )
                finally:
                    # Cleanup tensors
                    del prompt_items
                    gc.collect()
            else:
                return jsonify({"error": f"Unknown model type: {model_type}"}), 500

        
        end_time = time.time()
        elapsed_time = end_time - start_time
        chars_per_sec = len(text) / elapsed_time if elapsed_time > 0 else 0
        
        # Save audio with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"audio_{timestamp}.wav"
        filepath = STORAGE_DIR / filename
        
        sf.write(str(filepath), wavs[0], sr)
        
        # Save metadata
        metadata = {
            "text": text,
            "language": language,
            "speaker": speaker if model_type == 'CustomVoice' else None,
            "instruct": instruct,
            "timestamp": timestamp,
            "filename": filename,
            "model": model_name,
            "model_type": model_type,
            "elapsed_time": elapsed_time,
            "chars_per_sec": chars_per_sec
        }
        
        metadata_file = STORAGE_DIR / f"meta_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Audio saved: {filename}")
        
        return jsonify({
            "success": True,
            "filename": filename,
            "timestamp": timestamp,
            "elapsed_time": elapsed_time,
            "chars_per_sec": chars_per_sec,
            "metadata": metadata
        })
        
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get generation history"""
    try:
        history = []
        
        # Read all metadata files
        for meta_file in sorted(STORAGE_DIR.glob("meta_*.json"), reverse=True):
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                history.append(metadata)
        
        return jsonify(history)
        
    except Exception as e:
        print(f"Error getting history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/audio/<filename>', methods=['GET'])
def serve_audio(filename):
    """Serve audio file"""
    try:
        filepath = STORAGE_DIR / filename
        if not filepath.exists():
            return jsonify({"error": "File not found"}), 404
        
        return send_file(filepath, mimetype='audio/wav')
        
    except Exception as e:
        print(f"Error serving audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/promote_audio', methods=['POST'])
def promote_audio():
    """Promote a generated audio to be used as reference"""
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
             return jsonify({"error": "Filename is required"}), 400
             
        filepath = STORAGE_DIR / filename
        if not filepath.exists():
            return jsonify({"error": "File not found"}), 404
            
        # Get associated metadata to find text
        meta_filename = filename.replace('audio_', 'meta_').replace('.wav', '.json')
        meta_filepath = STORAGE_DIR / meta_filename
        
        ref_text = ""
        if meta_filepath.exists():
            with open(meta_filepath, 'r') as f:
                meta = json.load(f)
                ref_text = meta.get('text', '')
        
        return jsonify({
            "success": True,
            "ref_audio_path": filename, # Client can use filename, backend resolves it
            "ref_text": ref_text,
            "message": "Audio promoted to reference"
        })
        
    except Exception as e:
        print(f"Error promoting audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload_audio', methods=['POST'])
def upload_audio():
    """Upload an audio file for reference"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        if file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Sanitize filename
            safe_filename = f"upload_{timestamp}_{file.filename}"
            save_path = STORAGE_DIR / safe_filename
            file.save(save_path)
            
            return jsonify({
                "success": True,
                "filename": safe_filename,
                "message": "File uploaded successfully"
            })
            
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        return jsonify({"error": str(e)}), 500

def main():
    parser = argparse.ArgumentParser(description="Qwen3-TTS Web UI")
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to run the server on (default: 5000)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to run the server on (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='./Qwen3-TTS-12Hz-1.7B-CustomVoice',
        help='Path to the model or HuggingFace model ID'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )
    
    args = parser.parse_args()
    
    # Load model
    load_model(args.model)
    
    # Run server
    print(f"\n🎵 Qwen3-TTS Web UI starting on http://{args.host}:{args.port}")
    print(f"📁 Storage directory: {STORAGE_DIR.absolute()}")
    print(f"🤖 Model: {model_name}\n")
    
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()
