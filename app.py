import argparse
import gc
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

import numpy as np
import soundfile as sf
import torch
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from transformers import BitsAndBytesConfig
from qwen_tts import Qwen3TTSModel

load_dotenv()

# ── Config from .env ────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "./Qwen3-TTS-12Hz-1.7B-CustomVoice")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "2048"))
USE_COMPILE = os.getenv("USE_COMPILE", "true").lower() == "true"
LOAD_IN_4BIT = os.getenv("LOAD_IN_4BIT", "false").lower() == "true"
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "16"))

# ── GPU optimisations ────────────────────────────────────────────────────────
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.set_float32_matmul_precision('high')
    import torch._dynamo
    torch._dynamo.config.cache_size_limit = 512

# ── Auth helpers ─────────────────────────────────────────────────────────────
HASHED_ADMIN_PASSWORD = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt())


def verify_password(plain: str) -> bool:
    return bcrypt.checkpw(plain.encode(), HASHED_ADMIN_PASSWORD)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load model on startup
    print(f"🚀 Application starting... loading default model: {DEFAULT_MODEL}")
    try:
        load_model(DEFAULT_MODEL)
    except Exception as e:
        print(f"❌ Failed to load default model on startup: {e}")
    yield
    # Cleanup on shutdown
    print("👋 Application shutting down...")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Makix Studio", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Model globals ─────────────────────────────────────────────────────────────
model = None
model_name = None
model_type = None
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

DEFAULT_GEN_KWARGS = dict(
    max_new_tokens=MAX_NEW_TOKENS,
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


def discover_local_models():
    roots = [Path("."), Path("models")]
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


AVAILABLE_MODELS = discover_local_models()


def load_model(model_path: str):
    global model, model_name, model_type

    if model is not None:
        print(f"Unloading previous model: {model_name}")
        try:
            if hasattr(model, "to"):
                model.to("cpu")
        except Exception:
            pass
        del model
        model = None
        gc.collect()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()
            time.sleep(0.2)

    model_path = model_path.rstrip("/")
    print(f"Loading model: {model_path}")
    try:
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
                print("⚡ Flash Attention 2 enabled")
            else:
                print("⚠️ Flash Attention 2 skipped (no CUDA)")
        except ImportError:
            print("⚠️ Flash Attention 2 not found")

        if LOAD_IN_4BIT:
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            print("💎 Loading in 4-bit mode (NF4)")

        model = Qwen3TTSModel.from_pretrained(model_path, low_cpu_mem_usage=True, **model_kwargs)
        model_name = model_path

        if USE_COMPILE:
            try:
                print("🚀 Compiling sub-models...")
                # Non-autoregressive sub-models
                if hasattr(model.model, "speaker_encoder") and model.model.speaker_encoder:
                    model.model.speaker_encoder = torch.compile(model.model.speaker_encoder, mode="reduce-overhead")
                
                if hasattr(model.model, "speech_tokenizer") and model.model.speech_tokenizer:
                    model.model.speech_tokenizer.model = torch.compile(model.model.speech_tokenizer.model, mode="reduce-overhead")
                
                # Main Transformers (Talker and Code Predictor)
                if hasattr(model.model, "talker") and model.model.talker:
                    if LOAD_IN_4BIT:
                        print("⚠️ Skipping talker compilation in 4-bit mode (unstable).")
                    else:
                        print("🚀 Compiling talker and code_predictor...")
                        # Use default mode to avoid CUDA Graph issues with dynamic shapes
                        if hasattr(model.model.talker, "model"):
                            model.model.talker.model = torch.compile(model.model.talker.model)
                        
                        if hasattr(model.model.talker, "code_predictor") and hasattr(model.model.talker.code_predictor, "model"):
                            model.model.talker.code_predictor.model = torch.compile(model.model.talker.code_predictor.model)
                
                print("✨ Compilation successful")
            except Exception as e:
                print(f"⚠️ Compilation failed: {e}")

        if "CustomVoice" in model_path:
            model_type = "CustomVoice"
        elif "VoiceDesign" in model_path:
            model_type = "VoiceDesign"
        elif "Base" in model_path:
            model_type = "Base"
        else:
            model_type = "CustomVoice"

        if torch.cuda.is_available() and model_type == "CustomVoice":
            try:
                print("🔥 Running warmup generation...")
                with torch.inference_mode():
                    _ = model.generate_custom_voice(
                        text="Warmup generation for compilation.", language="English", speaker="Ryan", max_new_tokens=50, use_cache=True
                    )
                print("✅ Warmup complete")
            except Exception as e:
                print(f"⚠️ Warmup failed (non-critical): {e}")

        print(f"Model loaded: {model_name} (Type: {model_type})")
    except Exception as e:
        print(f"CRITICAL: Failed to load model: {e}")
        if model is not None:
            del model
            model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        raise


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class SwitchModelRequest(BaseModel):
    model: str


_md = MarkdownIt().enable("strikethrough")


def _strip_markdown(text: str) -> str:
    """Convert markdown to plain text via HTML render → BeautifulSoup strip."""
    html = _md.render(text)
    soup = BeautifulSoup(html, "html.parser")
    # Replace <br> / block tags with newlines before stripping tags
    for tag in soup.find_all(["br", "p", "li", "h1", "h2", "h3", "h4", "h5", "h6",
                               "blockquote", "pre", "code", "tr", "td", "th"]):
        tag.insert_before("\n")
    return soup.get_text(separator=" ")


_CHAR_REPLACEMENTS = {
    # Typographic quotes → straight quotes
    "‘": "'", "’": "'", "“": '"', "”": '"',
    # Dashes
    "–": "-", "—": "-", "―": "-",
    # Ellipsis
    "…": "...",
    # Bullet / list markers
    "•": ",", "‣": ",", "⁃": ",",
    # Non-breaking / zero-width spaces
    " ": " ", "​": "", "‌": "", "‍": "", "﻿": "",
    # Fraction slash, middle dot
    "⁄": "/", "·": ".",
    # Currency symbols → words (extend as needed)
    "$": " dollars ", "€": " euros ", "£": " pounds ", "¥": " yen ",
    "%": " percent ",
    # Math symbols
    "+": " plus ", "=": " equals ",
    "&": " and ",
}

_KEEP_PUNCTUATION = set(".,!?;:-'\"()")


def preprocess_text(text: str) -> str:
    """Normalize text before passing it to TTS to avoid unknown tokens."""
    # 0. Convert markdown to plain text (removes #, *, _, `, >, ~, links, etc.)
    text = _strip_markdown(text)

    # 1. Strip leading/trailing whitespace
    text = text.strip()

    # 2. Apply explicit character replacements first
    for src, dst in _CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)

    # 3. Normalize unicode (NFC) so composed forms are consistent
    text = unicodedata.normalize("NFC", text)

    # 4. Drop remaining non-ASCII / control characters that are not
    #    standard punctuation or letters
    cleaned = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch.isascii():
            cleaned.append(ch)
        elif cat.startswith("L"):   # Letter (any script)
            cleaned.append(ch)
        elif cat.startswith("N"):   # Number
            cleaned.append(ch)
        elif cat.startswith("P"):   # Punctuation
            cleaned.append(ch)
        elif cat.startswith("Z"):   # Separator → space
            cleaned.append(" ")
        # Everything else (symbols, control chars, surrogates) is dropped
    text = "".join(cleaned)

    # 5. Collapse multiple consecutive spaces / blank lines
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 6. Final strip
    return text.strip()


def split_text_to_sentences(text: str) -> list[str]:
    """Split text into segments for batch processing, balancing length and natural pauses."""
    # 1. Initial split by major punctuation (. ! ?) or newlines
    initial = re.split(r'(?<=[.!?])\s+|\n+', text)
    
    segments = []
    for s in initial:
        s = s.strip()
        if not s:
            continue
            
        # 2. If a segment is still very long, split by secondary punctuation (, ; : or -)
        # This allows much better batch parallelism without significantly hurting prosody.
        if len(s) > 110:
            # Split by , ; : or - (if preceded by space)
            sub = re.split(r'(?<=[,;:])\s+|(?<=\s-)\s+', s)
            segments.extend([ss.strip() for ss in sub if ss.strip()])
        else:
            segments.append(s)
            
    return segments


class GenerateRequest(BaseModel):
    text: str
    language: str = "Auto"
    speaker: str = "Vivian"
    instruct: str = ""
    ref_audio_path: str = ""
    ref_text: str = ""
    x_vector_only: bool = False
    kwargs: dict = {}


class PromoteRequest(BaseModel):
    filename: str


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
async def login(data: LoginRequest):
    if data.username != ADMIN_USERNAME or not verify_password(data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": data.username})
    response = JSONResponse({"success": True})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ── Exception handler: redirect to login on 401 ───────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # API calls expect JSON; browser navigations get a redirect
        accept = request.headers.get("accept", "")
        if "text/html" in accept and not request.url.path.startswith("/api/"):
            return RedirectResponse(url="/login")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# ── UI route ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: str = Depends(get_current_user)):
    return templates.TemplateResponse(request, "index.html")


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request, user: str = Depends(get_current_user)):
    return templates.TemplateResponse(request, "help.html")



# ── API routes (all protected) ────────────────────────────────────────────────
@app.get("/api/vram")
async def get_vram_status(user: str = Depends(get_current_user)):
    if not torch.cuda.is_available():
        return {"available": False, "total": 0, "allocated": 0, "reserved": 0, "free": 0, "percentage": 0}
    
    def fetch_vram():
        total = torch.cuda.get_device_properties(0).total_memory
        allocated = torch.cuda.memory_allocated(0)
        reserved = torch.cuda.memory_reserved(0)
        percentage = (reserved / total) * 100 if total > 0 else 0
        return {
            "available": True,
            "total": total,
            "allocated": allocated,
            "reserved": reserved,
            "percentage": percentage,
            "device": torch.cuda.get_device_name(0),
        }

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fetch_vram)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/storage_stats")
async def get_storage_stats(user: str = Depends(get_current_user)):
    def calc_size():
        total_size = 0
        file_count = 0
        for f in STORAGE_DIR.glob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1
        return {"total_size": total_size, "file_count": file_count}

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, calc_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/voices")
async def get_voices(user: str = Depends(get_current_user)):
    return CUSTOM_VOICES


@app.get("/api/models")
async def get_models(user: str = Depends(get_current_user)):
    return {"models": AVAILABLE_MODELS, "current": model_name, "type": model_type}


@app.post("/api/switch_model")
async def switch_model(data: SwitchModelRequest, user: str = Depends(get_current_user)):
    if not data.model:
        raise HTTPException(status_code=400, detail="Model path is required")
    if data.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Model {data.model} not found")
    try:
        load_model(data.model)
        return {"success": True, "model": model_name, "type": model_type,
                "message": f"Successfully switched to {model_type} model"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/languages")
async def get_languages(user: str = Depends(get_current_user)):
    return SUPPORTED_LANGUAGES


@app.post("/api/generate")
async def generate_audio(data: GenerateRequest, user: str = Depends(get_current_user)):
    if not data.text:
        raise HTTPException(status_code=400, detail="Text is required")
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    data.text = preprocess_text(data.text)
    if not data.text:
        raise HTTPException(status_code=400, detail="Text is empty after preprocessing")

    gen_kwargs = DEFAULT_GEN_KWARGS.copy()
    for k, v in data.kwargs.items():
        if k in gen_kwargs:
            gen_kwargs[k] = v

    sentences = split_text_to_sentences(data.text)
    print(f"Generating audio for {len(sentences)} sentences in batches of {BATCH_SIZE}...")
    start_time = time.time()
    
    final_wavs = []
    sample_rate = 24000

    if model_type == "VoiceDesign" and not data.instruct:
        raise HTTPException(status_code=400, detail="VoiceDesign requires a voice description in 'instruct'")
    if model_type == "Base" and not data.ref_audio_path:
        raise HTTPException(status_code=400, detail="Base model requires 'ref_audio_path'")

    def perform_generation():
        with torch.inference_mode():
            final_wavs = []
            current_sr = 24000
            
            for i in range(0, len(sentences), BATCH_SIZE):
                batch = sentences[i:i + BATCH_SIZE]
                
                if model_type == "VoiceDesign":
                    wavs, sr = model.generate_voice_design(
                        text=batch, language=data.language, instruct=data.instruct, **gen_kwargs)

                elif model_type == "CustomVoice":
                    wavs, sr = model.generate_custom_voice(
                        text=batch, language=data.language, speaker=data.speaker,
                        instruct=data.instruct or None, **gen_kwargs)

                elif model_type == "Base":
                    ref_audio_path = data.ref_audio_path
                    x_vector_only = data.x_vector_only or not data.ref_text

                    if not os.path.isabs(ref_audio_path):
                        possible = STORAGE_DIR / ref_audio_path
                        if possible.exists():
                            ref_audio_path = str(possible)

                    prompt_items = model.create_voice_clone_prompt(
                        ref_audio=ref_audio_path,
                        ref_text=data.ref_text if not x_vector_only else None,
                        x_vector_only_mode=x_vector_only,
                    )
                    try:
                        wavs, sr = model.generate_voice_clone(
                            text=batch, language=data.language,
                            voice_clone_prompt=prompt_items, **gen_kwargs)
                    finally:
                        del prompt_items
                
                else:
                    raise ValueError(f"Unknown model type: {model_type}")
                
                final_wavs.extend(wavs)
                current_sr = sr

            # Concatenate all wavs with a small silence (0.1s)
            if final_wavs:
                silence = np.zeros(int(current_sr * 0.1), dtype=np.float32)
                combined_wav = []
                for i, w in enumerate(final_wavs):
                    combined_wav.append(w)
                    if i < len(final_wavs) - 1:
                        combined_wav.append(silence)
                return np.concatenate(combined_wav), current_sr, final_wavs
            else:
                return None, current_sr, []

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        combined_wav, final_sr, all_wavs = await loop.run_in_executor(None, perform_generation)
        
        if combined_wav is None:
            raise HTTPException(status_code=500, detail="No audio was generated")

        wavs = [combined_wav]
        sr = final_sr
        final_wavs = all_wavs # for duration calc

    except Exception as e:
        print(f"Error generating audio: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - start_time
    # Calculate total audio duration across all sentences for accurate RTF
    total_audio_samples = sum(len(w) for w in all_wavs) if 'all_wavs' in locals() else len(combined_wav)
    audio_duration = total_audio_samples / final_sr if 'final_sr' in locals() else (len(combined_wav) / 24000)
    rtf = elapsed / audio_duration if audio_duration > 0 else 0
    chars_per_sec = len(data.text) / elapsed if elapsed > 0 else 0
    
    print(f"✅ Generation complete in {elapsed:.2f}s | Speed: {chars_per_sec:.2f} ch/s | RTF: {rtf:.2f}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"audio_{timestamp}.wav"
    filepath = STORAGE_DIR / filename
    sf.write(str(filepath), wavs[0], sr)

    metadata = {
        "text": data.text,
        "language": data.language,
        "speaker": data.speaker if model_type == "CustomVoice" else None,
        "instruct": data.instruct,
        "timestamp": timestamp,
        "filename": filename,
        "model": model_name,
        "model_type": model_type,
        "elapsed_time": elapsed,
        "chars_per_sec": chars_per_sec,
    }
    with open(STORAGE_DIR / f"meta_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Audio saved: {filename}")
    return {"success": True, "filename": filename, "timestamp": timestamp,
            "elapsed_time": elapsed, "chars_per_sec": chars_per_sec, "metadata": metadata}


@app.get("/api/history")
async def get_history(user: str = Depends(get_current_user)):
    try:
        history = []
        for meta_file in sorted(STORAGE_DIR.glob("meta_*.json"), reverse=True):
            with open(meta_file, "r", encoding="utf-8") as f:
                history.append(json.load(f))
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audio/{filename}")
async def serve_audio(filename: str, user: str = Depends(get_current_user)):
    filepath = STORAGE_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, media_type="audio/wav")


@app.post("/api/promote_audio")
async def promote_audio(data: PromoteRequest, user: str = Depends(get_current_user)):
    if not data.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    filepath = STORAGE_DIR / data.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    meta_filename = data.filename.replace("audio_", "meta_").replace(".wav", ".json")
    ref_text = ""
    meta_path = STORAGE_DIR / meta_filename
    if meta_path.exists():
        with open(meta_path, "r") as f:
            ref_text = json.load(f).get("text", "")

    return {"success": True, "ref_audio_path": data.filename, "ref_text": ref_text,
            "message": "Audio promoted to reference"}


@app.post("/api/upload_audio")
async def upload_audio(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"upload_{timestamp}_{file.filename}"
    save_path = STORAGE_DIR / safe_filename
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    return {"success": True, "filename": safe_filename, "message": "File uploaded successfully"}


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str, user: str = Depends(get_current_user)):
    # This serves as a fallback for frontend routing
    return templates.TemplateResponse(request, "index.html")


# ── Entrypoint ────────────────────────────────────────────────────────────────
def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Makix Studio — Qwen3-TTS")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", type=str, default=HOST)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"\n🎵 Makix Studio starting on http://{args.host}:{args.port}")
    print(f"📁 Storage: {STORAGE_DIR.absolute()}")
    print(f"🤖 Model: {model_name}\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="debug" if args.debug else "info")


if __name__ == "__main__":
    main()
