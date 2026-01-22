# Qwen-TTS CLI

A command-line interface for the Qwen3 TTS model, supporting single and batch inference with efficient custom voice generation.

## Installation

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Model**:
    Ensure you have the Qwen3 TTS model available. By default, the script looks for `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` (Hugginface ID) or you can point it to a local directory.

```bash
pip install -U "huggingface_hub[cli]"
huggingface-cli download Qwen/Qwen3-TTS-Tokenizer-12Hz --local-dir ./Qwen3-TTS-Tokenizer-12Hz
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local-dir ./Qwen3-TTS-12Hz-1.7B-CustomVoice
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign --local-dir ./Qwen3-TTS-12Hz-1.7B-VoiceDesign
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base --local-dir ./Qwen3-TTS-12Hz-1.7B-Base
huggingface-cli download Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice --local-dir ./Qwen3-TTS-12Hz-0.6B-CustomVoice
huggingface-cli download Qwen/Qwen3-TTS-12Hz-0.6B-Base --local-dir ./Qwen3-TTS-12Hz-0.6B-Base
```

4. **Dependencies**

```bash
sudo apt-get update
sudo apt-get install -y sox libsox-dev libsox-fmt-all
```


## Usage

Run the script using `python run.py`.

### Arguments

-   `--text`: One or more text strings to convert to speech.
-   `--speaker`: Speaker name(s) to use.
-   `--language`: (Optional) Language(s) of the text. Defaults to "Auto".
-   `--instruct`: (Optional) Instruction text(s) for style control (e.g., "Angry", "Happy").
-   `--output`: Output filename(s). Defaults to `output_{i}.wav`.
-   `--model`: Path to the model directory or HuggingFace ID. Default: `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`.

### Examples

**Single Inference:**
```bash
python run.py \
  --text "其实我真的有发现，我是一个特别善于观察别人情绪的人。" \
  --speaker "Vivian" \
  --language "Chinese" \
  --instruct "用特别愤怒的语气说" \
  --output "angry_vivian.wav"
```

**Batch Inference:**
```bash
python run.py \
  --text "Test one" "Test two" \
  --speaker "Speaker1" "Speaker2" \
  --output "out1.wav" "out2.wav"
```
