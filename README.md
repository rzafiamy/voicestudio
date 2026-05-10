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
- ⚡ **Performance Optimized**: 2x+ faster inference with KV-cache, Flash Attention 2, and GPU optimizations

## Installation

1. **Automated Setup (Recommended)**:
```bash
chmod +x setup.sh
./setup.sh
```

2. **Manual Setup**:
```bash
python3 -m venv venv
source venv/bin/activate
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

## Performance Optimizations

This application includes several optimizations to achieve **2x+ faster inference** compared to baseline:

### Automatic Optimizations

These optimizations are applied automatically when you start the server:

1. **KV-Cache**: Enabled by default to cache key-value pairs during generation (1.3-1.5x speedup)
2. **GPU Optimizations**: 
   - cuDNN auto-tuner for optimal convolution algorithms
   - TF32 precision for faster matmul on Ampere+ GPUs
   - Flash Attention 2 (if installed) for 1.5-2x speedup
3. **Optimized Parameters**: Tuned generation parameters for speed while maintaining quality
4. **Warmup Generation**: First generation optimizes CUDA kernels for subsequent runs
5. **Inference Mode**: Disables gradient computation for faster inference (1.2x speedup)

### Expected Performance

- **Baseline**: ~20 chars/sec
- **Optimized**: ~40-50 chars/sec (2-2.5x improvement)
- **First generation**: Slower due to warmup
- **Subsequent generations**: Full speed benefits

### Hardware Requirements

For best performance:
- **GPU**: NVIDIA GPU with CUDA support (RTX 3000+ series recommended)
- **VRAM**: 8GB+ for 1.7B models, 4GB+ for 0.6B models
- **PyTorch**: 2.0+ for torch.compile support
- **Flash Attention 2**: Optional but recommended (install from wheel file)

### Benchmarking

Run the benchmark script to test performance:

```bash
python benchmark.py --model ./Qwen3-TTS-12Hz-1.7B-CustomVoice
```

## License

Apache 2.0

## Credits

Powered by [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
