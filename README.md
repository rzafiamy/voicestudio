# Qwen3-TTS Web UI

A beautiful Material Design 3 web interface for testing the Qwen3-TTS audio model.

## Features

- 🎨 **Beautiful MD3 Design**: Modern, minimalist interface with smooth animations
- 🎤 **Voice Selection**: Choose from 9 premium voices covering multiple languages
- 🌍 **Multi-Language Support**: 10+ languages including Chinese, English, Japanese, Korean, and more
- 🔄 **Dynamic Model Switching**: Switch between CustomVoice, VoiceDesign, and Base models on-the-fly without restarting
- 🎛️ **Parameter Control**: Fine-tune generation with style instructions
- 📝 **Text-to-Speech**: Convert any text to natural-sounding speech
- 🔊 **Audio Playback**: Built-in player for immediate listening
- 📚 **Generation History**: View and replay all generated audio with timestamps
- 💾 **Persistent Storage**: All generations saved with metadata
- 🤖 **Auto Model Discovery**: Automatically detects locally downloaded models

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure you have the Qwen3-TTS model downloaded locally or accessible via HuggingFace.

## Usage

### Start the Web Server

```bash
python app.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice --port 5000
```

#### Arguments

- `--port`: Port to run the server on (default: 5000)
- `--host`: Host to bind to (default: 0.0.0.0)
- `--model`: Path to the model or HuggingFace model ID (default: ./Qwen3-TTS-12Hz-1.7B-CustomVoice)
- `--debug`: Run in debug mode

### Access the Web UI

Open your browser and navigate to:
```
http://localhost:5000
```

## Available Voices

| Voice | Description | Native Language |
|-------|-------------|-----------------|
| Vivian | Bright, slightly edgy young female voice | Chinese |
| Serena | Warm, gentle young female voice | Chinese |
| Uncle_Fu | Seasoned male voice with a low, mellow timbre | Chinese |
| Dylan | Youthful Beijing male voice | Chinese (Beijing Dialect) |
| Eric | Lively Chengdu male voice | Chinese (Sichuan Dialect) |
| Ryan | Dynamic male voice with strong rhythmic drive | English |
| Aiden | Sunny American male voice | English |
| Ono_Anna | Playful Japanese female voice | Japanese |
| Sohee | Warm Korean female voice | Korean |

## Supported Languages

- Auto (automatic detection)
- Chinese
- English
- Japanese
- Korean
- German
- French
- Russian
- Portuguese
- Spanish
- Italian

## Storage

All generated audio files and metadata are stored in the `storage/` directory:

- `audio_YYYYMMDD_HHMMSS_microseconds.wav` - Audio files
- `meta_YYYYMMDD_HHMMSS_microseconds.json` - Metadata (text, parameters, timestamp)

## CLI Usage (Original)

You can still use the original CLI interface:

```bash
python run.py --text "Hello world" --speaker Ryan --language English
```

## Requirements

- Python 3.8+
- CUDA-capable GPU (recommended) or CPU
- 8GB+ RAM
- Qwen3-TTS model files

## Download models

### Download through Hugging Face

```bash
pip install -U "huggingface_hub[cli]"
hf download Qwen/Qwen3-TTS-Tokenizer-12Hz --local-dir ./Qwen3-TTS-Tokenizer-12Hz
hf download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local-dir ./Qwen3-TTS-12Hz-1.7B-CustomVoice
hf download Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign --local-dir ./Qwen3-TTS-12Hz-1.7B-VoiceDesign
hf download Qwen/Qwen3-TTS-12Hz-1.7B-Base --local-dir ./Qwen3-TTS-12Hz-1.7B-Base
hf download Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice --local-dir ./Qwen3-TTS-12Hz-0.6B-CustomVoice
hf download Qwen/Qwen3-TTS-12Hz-0.6B-Base --local-dir ./Qwen3-TTS-12Hz-0.6B-Base
```

## License

Apache 2.0

## Credits

Powered by [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
