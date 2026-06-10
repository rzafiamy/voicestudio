import os
import gc
import time
import json
import re
import unicodedata
import threading
from pathlib import Path
from datetime import datetime

import numpy as np
import soundfile as sf
import torch
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from transformers import BitsAndBytesConfig
from qwen_tts import Qwen3TTSModel

# --- Constants & Defaults ---
DEFAULT_GEN_KWARGS = dict(
    max_new_tokens=2048,
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

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

CUSTOM_VOICES = {
    "Vivian": {"description": "Bright, slightly edgy young female voice", "language": "Chinese"},
    "Serena": {"description": "Warm, gentle young female voice", "language": "Chinese"},
    "Uncle_Fu": {"description": "Seasoned male voice with a low, mellow timbre", "language": "Chinese"},
    "Dylan": {"description": "Youthful Beijing male voice with a clear, natural timbre", "language": "Chinese (Beijing Dialect)"},
    "Eric": {"description": "Lively Chengdu male voice with a slightly husky brightness", "language": "Chinese (Sichuan Dialect)"},
    "Ryan": {"description": "Dynamic male voice with strong rhythmic drive", "language": "English"},
    "Aiden": {"description": "Sunny American male voice with a clear midrange", "language": "English"},
    "Ono_Anna": {"description": "Playful Japanese female voice with a light, nimble timbre", "language": "Japanese"},
    "Sohee": {"description": "Warm Korean female voice with rich emotion", "language": "Korean"},
}

SUPPORTED_LANGUAGES = [
    "Auto", "Chinese", "English", "Japanese", "Korean",
    "German", "French", "Russian", "Portuguese", "Spanish", "Italian",
]

class StudioEngine:
    def __init__(self):
        self.model = None
        self.model_name = None
        self.model_type = None
        self.model_status = {
            "status": "idle",
            "message": "Waiting for model...",
            "progress": 0,
            "elapsed": 0,
            "start_time": None,
            "last_error": None
        }
        self.model_load_lock = threading.Lock()
        self.use_compile = os.getenv("USE_COMPILE", "true").lower() == "true"
        self.load_in_4bit = os.getenv("LOAD_IN_4BIT", "false").lower() == "true"
        self.batch_size = int(os.getenv("BATCH_SIZE", "16"))
        
        self._md = MarkdownIt().enable("strikethrough")
        
        # Torch inductor cache
        self._compile_cache_dir = os.getenv("TORCHINDUCTOR_CACHE_DIR", os.path.join(os.path.dirname(__file__), ".torch_compile_cache"))
        os.environ.setdefault("TORCHINDUCTOR_CACHE_DIR", self._compile_cache_dir)
        self._compile_cache_is_warm = Path(self._compile_cache_dir).exists() and any(Path(self._compile_cache_dir).rglob("*.json"))

    def discover_local_models(self):
        roots = [Path("."), Path(os.getenv("MODELS_DIR", "./models"))]
        local_models = []
        for root in roots:
            if root.exists():
                local_models.extend([str(p) for p in root.iterdir()
                                    if p.is_dir() and "Qwen3-TTS" in p.name and "storage" not in p.name])
        local_models.sort()
        if not local_models:
            return [
                "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
                "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
                "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
                "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
            ]
        return local_models

    def load_model(self, model_path: str):
        if not self.model_load_lock.acquire(blocking=False):
            return

        try:
            self.model_status["status"] = "loading"
            self.model_status["message"] = f"Loading {os.path.basename(model_path)}..."
            self.model_status["start_time"] = time.time()
            self.model_status["progress"] = 0
            self.model_status["last_error"] = None

            if self.model is not None:
                if hasattr(self.model, "to"):
                    try: self.model.to("cpu")
                    except: pass
                del self.model
                self.model = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()

            model_path = model_path.rstrip("/")
            
            if torch.cuda.is_available():
                torch.cuda.set_device(0)
            torch.set_grad_enabled(False)

            model_kwargs = {
                "device_map": "auto",
                "dtype": torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            }

            try:
                import flash_attn
                if torch.cuda.is_available():
                    model_kwargs["attn_implementation"] = "flash_attention_2"
            except ImportError:
                pass

            if self.load_in_4bit:
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )

            self.model = Qwen3TTSModel.from_pretrained(model_path, low_cpu_mem_usage=True, **model_kwargs)
            self.model_name = model_path

            if self.use_compile:
                try:
                    if hasattr(self.model.model, "speaker_encoder") and self.model.model.speaker_encoder:
                        self.model.model.speaker_encoder = torch.compile(self.model.model.speaker_encoder, dynamic=True)
                    if hasattr(self.model.model, "speech_tokenizer") and self.model.model.speech_tokenizer:
                        self.model.model.speech_tokenizer.model = torch.compile(self.model.model.speech_tokenizer.model, dynamic=True)
                    if hasattr(self.model.model, "talker") and self.model.model.talker:
                        if not self.load_in_4bit:
                            self.model_status["status"] = "compiling"
                            self.model_status["message"] = "Optimizing neural graphs..."
                            self.model_status["progress"] = 30
                            if hasattr(self.model.model.talker, "model"):
                                self.model.model.talker.model = torch.compile(self.model.model.talker.model, dynamic=True)
                            if hasattr(self.model.model.talker, "code_predictor") and hasattr(self.model.model.talker.code_predictor, "model"):
                                self.model.model.talker.code_predictor.model = torch.compile(self.model.model.talker.code_predictor.model, dynamic=True)
                    self.model_status["progress"] = 60
                except Exception as e:
                    self.model_status["last_error"] = str(e)

            if "CustomVoice" in model_path: self.model_type = "CustomVoice"
            elif "VoiceDesign" in model_path: self.model_type = "VoiceDesign"
            elif "Base" in model_path: self.model_type = "Base"
            else: self.model_type = "CustomVoice"

            if torch.cuda.is_available():
                try:
                    self.model_status["status"] = "warming_up"
                    self.model_status["progress"] = 80
                    self.model_status["message"] = "Warming up model..."
                    warmup_text = ["Warmup sentence."]
                    with torch.inference_mode():
                        if self.model_type == "CustomVoice":
                            _ = self.model.generate_custom_voice(text=warmup_text, language="English", speaker="Ryan", max_new_tokens=20, use_cache=True)
                        elif self.model_type == "VoiceDesign":
                            _ = self.model.generate_voice_design(text=warmup_text, language="English", instruct="Warmup", max_new_tokens=20, use_cache=True)
                        elif self.model_type == "Base":
                            if hasattr(self.model, "generate_custom_voice"):
                                _ = self.model.generate_custom_voice(text=warmup_text, language="English", speaker="Ryan", max_new_tokens=20, use_cache=True)
                except Exception as e:
                    self.model_status["last_error"] = str(e)

            self.model_status["status"] = "ready"
            self.model_status["message"] = "Model ready"
            self.model_status["progress"] = 100
            self.model_status["elapsed"] = time.time() - self.model_status["start_time"]
        except Exception as e:
            self.model_status["status"] = "error"
            self.model_status["message"] = f"Error: {str(e)}"
            self.model_status["last_error"] = str(e)
            if self.model is not None:
                del self.model
                self.model = None
            gc.collect()
            raise
        finally:
            self.model_load_lock.release()

    def preprocess_text(self, text: str) -> str:
        html = self._md.render(text)
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["br", "p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "code", "tr", "td", "th"]):
            tag.insert_before("\n")
        text = soup.get_text(separator=" ")
        text = text.strip()
        replacements = {
            "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "―": "-", "…": "...", "•": ",", "‣": ",", "⁃": ",",
            " ": " ", "​": "", "‌": "", "‍": "", "﻿": "", "⁄": "/", "·": ".", "$": " dollars ", "€": " euros ", "£": " pounds ",
            "¥": " yen ", "%": " percent ", "+": " plus ", "=": " equals ", "&": " and ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = unicodedata.normalize("NFC", text)
        cleaned = []
        for ch in text:
            cat = unicodedata.category(ch)
            if ch.isascii() or cat.startswith(("L", "N", "P")): cleaned.append(ch)
            elif cat.startswith("Z"): cleaned.append(" ")
        text = "".join(cleaned)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def split_text_to_sentences(self, text: str) -> list[str]:
        initial = re.split(r'(?<=[.!?])\s+|\n+', text)
        segments = []
        for s in initial:
            s = s.strip()
            if not s: continue
            if len(s) > 110:
                sub = re.split(r'(?<=[,;:])\s+|(?<=\s-)\s+', s)
                segments.extend([ss.strip() for ss in sub if ss.strip()])
            else:
                segments.append(s)
        return segments

    def generate(self, text, language="Auto", speaker="Vivian", instruct="", ref_audio_path="", ref_text="", x_vector_only=False, kwargs=None):
        if not text: raise ValueError("Text is required")
        if self.model is None: raise ValueError("Model not loaded")

        text = self.preprocess_text(text)
        if not text: raise ValueError("Text is empty after preprocessing")

        gen_kwargs = DEFAULT_GEN_KWARGS.copy()
        if kwargs:
            for k, v in kwargs.items():
                if k in gen_kwargs: gen_kwargs[k] = v

        sentences = self.split_text_to_sentences(text)
        start_time = time.time()
        
        final_wavs = []
        current_sr = 24000

        with torch.inference_mode():
            for i in range(0, len(sentences), self.batch_size):
                batch = sentences[i:i + self.batch_size]
                if self.model_type == "VoiceDesign":
                    if not instruct: raise ValueError("VoiceDesign requires instruct")
                    wavs, sr = self.model.generate_voice_design(text=batch, language=language, instruct=instruct, **gen_kwargs)
                elif self.model_type == "CustomVoice":
                    wavs, sr = self.model.generate_custom_voice(text=batch, language=language, speaker=speaker, instruct=instruct or None, **gen_kwargs)
                elif self.model_type == "Base":
                    if not ref_audio_path: raise ValueError("Base model requires ref_audio_path")
                    if not os.path.isabs(ref_audio_path):
                        possible = STORAGE_DIR / ref_audio_path
                        if possible.exists(): ref_audio_path = str(possible)
                    
                    prompt_items = self.model.create_voice_clone_prompt(
                        ref_audio=ref_audio_path,
                        ref_text=ref_text if not (x_vector_only or not ref_text) else None,
                        x_vector_only_mode=x_vector_only or not ref_text,
                    )
                    try:
                        wavs, sr = self.model.generate_voice_clone(text=batch, language=language, voice_clone_prompt=prompt_items, **gen_kwargs)
                    finally:
                        del prompt_items
                else:
                    raise ValueError(f"Unknown model type: {self.model_type}")
                
                final_wavs.extend(wavs)
                current_sr = sr

        if not final_wavs: return None

        silence = np.zeros(int(current_sr * 0.1), dtype=np.float32)
        combined_wav = []
        for i, w in enumerate(final_wavs):
            combined_wav.append(w)
            if i < len(final_wavs) - 1:
                combined_wav.append(silence)
        
        combined_wav = np.concatenate(combined_wav)
        elapsed = time.time() - start_time
        audio_duration = len(combined_wav) / current_sr
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"audio_{timestamp}.wav"
        filepath = STORAGE_DIR / filename
        sf.write(str(filepath), combined_wav, current_sr)

        metadata = {
            "text": text,
            "language": language,
            "speaker": speaker if self.model_type == "CustomVoice" else None,
            "instruct": instruct,
            "timestamp": timestamp,
            "filename": filename,
            "model": self.model_name,
            "model_type": self.model_type,
            "elapsed_time": elapsed,
            "chars_per_sec": len(text) / elapsed if elapsed > 0 else 0,
            "rtf": elapsed / audio_duration if audio_duration > 0 else 0
        }
        with open(STORAGE_DIR / f"meta_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return metadata

    def get_history(self):
        history = []
        for meta_file in sorted(STORAGE_DIR.glob("meta_*.json"), reverse=True):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    history.append(json.load(f))
            except: pass
        return history

    def get_vram_status(self):
        if not torch.cuda.is_available():
            return None
        total = torch.cuda.get_device_properties(0).total_memory
        reserved = torch.cuda.memory_reserved(0)
        allocated = torch.cuda.memory_allocated(0)
        return {
            "total": total,
            "reserved": reserved,
            "allocated": allocated,
            "percentage": (reserved / total) * 100 if total > 0 else 0,
            "device": torch.cuda.get_device_name(0)
        }
