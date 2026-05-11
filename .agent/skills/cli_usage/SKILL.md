---
name: cli_usage
description: Comprehensive guide for using the Makix Studio CLI for TTS generation, model management, and voice cloning.
---

# Makix Studio CLI Usage Skill

This skill documents the capabilities and commands for the Makix Studio CLI, enabling agents to perform automated or interactive audio generation tasks.

## Core Modes

### 1. Interactive Mode (TUI)
Start a full-featured Text User Interface to manage models and generate audio manually.
- **Command**: `python app.py --cli`
- **Purpose**: Rapid prototyping, exploring available speakers, managing history, and real-time system monitoring.

### 2. Direct Command Mode
Execute synthesis tasks directly from the terminal without entering the TUI.
- **Command Structure**: `python app.py --text "..." [params]`
- **Purpose**: Scripting, batch processing, and non-interactive automation.

## Generation Use Cases

### Voice Cloning (Base Model)
Use a reference audio file to clone a specific voice style.
- **Requirements**: Use a model with "Base" in its name.
- **Example**: 
  ```bash
  python app.py --model ./models/Qwen3-TTS-1.7B-Base --text "Hello world" --ref-audio storage/source.wav --ref-text "Transcript of source" --play
  ```

### Custom Voice Selection
Generate audio using predefined high-quality speakers.
- **Requirements**: Use a model with "CustomVoice" in its name.
- **Example**:
  ```bash
  python app.py --text "Synthesize this text" --speaker "Ryan" --language "English" --play
  ```

### Voice Design
Generate a unique voice based on a descriptive prompt.
- **Requirements**: Use a model with "VoiceDesign" in its name.
- **Example**:
  ```bash
  python app.py --model ./models/Qwen3-TTS-1.7B-VoiceDesign --text "I am a custom voice" --instruct "A warm, gentle female voice" --play
  ```

## Parameters Reference

| Parameter | Purpose | Example |
| :--- | :--- | :--- |
| `--text` | Text to synthesize (triggers direct mode) | `--text "Hello"` |
| `--model` | Path to specific model directory | `--model ./models/Qwen-1.7B` |
| `--language`| Specify input language | `--language "French"` |
| `--speaker` | Target speaker (for CustomVoice) | `--speaker "Vivian"` |
| `--instruct`| Voice description or instruction | `--instruct "Excited tone"` |
| `--ref-audio`| Path to reference .wav for cloning | `--ref-audio path/to/file.wav`|
| `--ref-text` | Reference audio transcript | `--ref-text "Text in wav"` |
| `--play` | Auto-play audio after generation | `--play` |

## Best Practices for Agents
1. **Model Matching**: Always ensure the `--model` matches the requested mode (e.g., don't use a Base model for CustomVoice speakers).
2. **Text Preprocessing**: The CLI uses `StudioEngine` which automatically strips markdown and normalizes characters. No manual cleanup is needed.
3. **VRAM Awareness**: Before large batch tasks, check system status via `python app.py --cli` (Option 4) to ensure sufficient GPU memory.
4. **Output Management**: Generated files are stored in the `storage/` directory with unique timestamps. Metadata is saved in corresponding `.json` files.

## Troubleshooting
- **No Sound**: Ensure `ffplay` or `aplay` is installed on the system for the `--play` flag.
- **Slow Generation**: Ensure `torch.compile` cache is warm. The first run with a new model or sequence length will be slower.
- **Model Not Found**: The CLI searches in `.` and `./models/`. Provide absolute paths if the model is located elsewhere.
