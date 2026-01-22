import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import torch
import soundfile as sf
from flask import Flask, render_template, request, jsonify, send_file
from qwen_tts import Qwen3TTSModel

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

AVAILABLE_MODELS = [
    "Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "Qwen3-TTS-12Hz-0.6B-CustomVoice",
    "Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "Qwen3-TTS-12Hz-1.7B-Base",
    "Qwen3-TTS-12Hz-0.6B-Base"
]

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

def load_model(model_path):
    """Load the TTS model"""
    global model, model_name, model_type
    print(f"Loading model: {model_path}")
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cuda:0" if torch.cuda.is_available() else "cpu",
        dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
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
    
    print(f"Model loaded successfully: {model_name} (Type: {model_type})")

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

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Get supported languages"""
    return jsonify(SUPPORTED_LANGUAGES)

@app.route('/api/generate', methods=['POST'])
def generate_audio():
    """Generate audio from text"""
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'Auto')
        speaker = data.get('speaker', 'Vivian')
        instruct = data.get('instruct', '')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        if model is None:
            return jsonify({"error": "Model not loaded"}), 500
        
        # Generate audio based on model type
        print(f"Generating audio for text: {text[:50]}... (Model type: {model_type})")
        
        if model_type == 'VoiceDesign':
            # VoiceDesign model uses instruct for voice description
            if not instruct:
                return jsonify({"error": "VoiceDesign model requires a voice description in the 'Style Instruction' field"}), 400
            
            wavs, sr = model.generate_voice_design(
                text=text,
                language=language,
                instruct=instruct,
            )
        elif model_type == 'CustomVoice':
            # CustomVoice model uses speaker selection
            wavs, sr = model.generate_custom_voice(
                text=text,
                language=language,
                speaker=speaker,
                instruct=instruct if instruct else None,
            )
        elif model_type == 'Base':
            # Base model - would need voice cloning, not implemented in web UI yet
            return jsonify({"error": "Base model requires voice cloning which is not yet supported in the web UI. Please use CustomVoice or VoiceDesign models."}), 400
        else:
            return jsonify({"error": f"Unknown model type: {model_type}"}), 500
        
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
            "model_type": model_type
        }
        
        metadata_file = STORAGE_DIR / f"meta_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Audio saved: {filename}")
        
        return jsonify({
            "success": True,
            "filename": filename,
            "timestamp": timestamp,
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
