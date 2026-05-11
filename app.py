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

# ── GPU optimisations ────────────────────────────────────────────────────────
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

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


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Makix Studio")
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
    local_models = [str(p) for p in Path(".").iterdir()
                    if p.is_dir() and "Qwen3-TTS" in p.name and "storage" not in p.name]
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

        model = Qwen3TTSModel.from_pretrained(model_path, low_cpu_mem_usage=True, **model_kwargs)
        model_name = model_path

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
                        text="Warmup", language="English", speaker="Ryan", max_new_tokens=20, use_cache=True
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
    try:
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

    print(f"Generating audio: {data.text[:50]}... (Type: {model_type})")
    start_time = time.time()

    try:
        with torch.inference_mode():
            if model_type == "VoiceDesign":
                if not data.instruct:
                    raise HTTPException(status_code=400,
                                        detail="VoiceDesign requires a voice description in 'instruct'")
                wavs, sr = model.generate_voice_design(
                    text=data.text, language=data.language, instruct=data.instruct, **gen_kwargs)

            elif model_type == "CustomVoice":
                wavs, sr = model.generate_custom_voice(
                    text=data.text, language=data.language, speaker=data.speaker,
                    instruct=data.instruct or None, **gen_kwargs)

            elif model_type == "Base":
                ref_audio_path = data.ref_audio_path
                x_vector_only = data.x_vector_only or not data.ref_text

                if not ref_audio_path:
                    raise HTTPException(status_code=400, detail="Base model requires 'ref_audio_path'")

                if not os.path.isabs(ref_audio_path):
                    possible = STORAGE_DIR / ref_audio_path
                    if possible.exists():
                        ref_audio_path = str(possible)

                print(f"Cloning from: {ref_audio_path} (x-vector: {x_vector_only})")
                prompt_items = model.create_voice_clone_prompt(
                    ref_audio=ref_audio_path,
                    ref_text=data.ref_text if not x_vector_only else None,
                    x_vector_only_mode=x_vector_only,
                )
                try:
                    wavs, sr = model.generate_voice_clone(
                        text=data.text, language=data.language,
                        voice_clone_prompt=prompt_items, **gen_kwargs)
                finally:
                    del prompt_items
                    gc.collect()
            else:
                raise HTTPException(status_code=500, detail=f"Unknown model type: {model_type}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - start_time
    chars_per_sec = len(data.text) / elapsed if elapsed > 0 else 0

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

    load_model(args.model)

    print(f"\n🎵 Makix Studio starting on http://{args.host}:{args.port}")
    print(f"📁 Storage: {STORAGE_DIR.absolute()}")
    print(f"🤖 Model: {model_name}\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="debug" if args.debug else "info")


if __name__ == "__main__":
    main()
