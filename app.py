import argparse
import os
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from dotenv import load_dotenv

from engine import StudioEngine, CUSTOM_VOICES, SUPPORTED_LANGUAGES

load_dotenv()

# ── Config from .env ────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "./models/Qwen3-TTS-12Hz-1.7B-CustomVoice")

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

# ── Engine Instance ──────────────────────────────────────────────────────────
engine = StudioEngine()
STORAGE_DIR = Path("storage")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load model on startup in background
    print(f"🚀 Application starting... loading default model in background: {DEFAULT_MODEL}")
    threading.Thread(target=engine.load_model, args=(DEFAULT_MODEL,), daemon=True).start()
    yield
    print("👋 Application shutting down...")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Makix Studio", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class SwitchModelRequest(BaseModel):
    model: str

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

# ── Health check (unauthenticated, used by Docker/load balancers) ────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": engine.model_name,
        "model_status": engine.model_status["status"],
    }

# ── Exception handler ─────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
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

# ── API routes ────────────────────────────────────────────────────────────────
@app.get("/api/vram")
async def get_vram_status(user: str = Depends(get_current_user)):
    vram = engine.get_vram_status()
    if not vram:
        return {"available": False, "total": 0, "allocated": 0, "reserved": 0, "free": 0, "percentage": 0}
    return {"available": True, **vram}

@app.get("/api/storage_stats")
async def get_storage_stats(user: str = Depends(get_current_user)):
    total_size = 0
    file_count = 0
    for f in STORAGE_DIR.glob("*"):
        if f.is_file():
            total_size += f.stat().st_size
            file_count += 1
    return {"total_size": total_size, "file_count": file_count}

@app.get("/api/voices")
async def get_voices(user: str = Depends(get_current_user)):
    return CUSTOM_VOICES

@app.get("/api/models")
async def get_models(user: str = Depends(get_current_user)):
    return {"models": engine.discover_local_models(), "current": engine.model_name, "type": engine.model_type}

@app.get("/api/model_status")
async def get_model_status(user: str = Depends(get_current_user)):
    import time
    status_data = engine.model_status.copy()
    if status_data["status"] in ["loading", "compiling", "warming_up"] and status_data["start_time"]:
        status_data["elapsed"] = time.time() - status_data["start_time"]
    return status_data

@app.post("/api/switch_model")
async def switch_model(data: SwitchModelRequest, user: str = Depends(get_current_user)):
    if not data.model:
        raise HTTPException(status_code=400, detail="Model path is required")
    threading.Thread(target=engine.load_model, args=(data.model,), daemon=True).start()
    return {"success": True, "message": f"Switching to {data.model} in background..."}

@app.get("/api/languages")
async def get_languages(user: str = Depends(get_current_user)):
    return SUPPORTED_LANGUAGES

@app.post("/api/generate")
async def generate_audio(data: GenerateRequest, user: str = Depends(get_current_user)):
    if engine.model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        meta = await loop.run_in_executor(None, lambda: engine.generate(
            text=data.text,
            language=data.language,
            speaker=data.speaker,
            instruct=data.instruct,
            ref_audio_path=data.ref_audio_path,
            ref_text=data.ref_text,
            x_vector_only=data.x_vector_only,
            kwargs=data.kwargs
        ))
        if not meta:
            raise HTTPException(status_code=500, detail="No audio was generated")
        return {"success": True, **meta, "metadata": meta}
    except Exception as e:
        if "required" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history(user: str = Depends(get_current_user)):
    return engine.get_history()

@app.get("/api/audio/{filename}")
async def serve_audio(filename: str, user: str = Depends(get_current_user)):
    filepath = STORAGE_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, media_type="audio/wav")

@app.post("/api/promote_audio")
async def promote_audio(data: PromoteRequest, user: str = Depends(get_current_user)):
    import json
    filepath = STORAGE_DIR / data.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    meta_filename = data.filename.replace("audio_", "meta_").replace(".wav", ".json")
    ref_text = ""
    meta_path = STORAGE_DIR / meta_filename
    if meta_path.exists():
        with open(meta_path, "r") as f:
            ref_text = json.load(f).get("text", "")
    return {"success": True, "ref_audio_path": data.filename, "ref_text": ref_text, "message": "Audio promoted to reference"}

@app.post("/api/upload_audio")
async def upload_audio(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"upload_{timestamp}_{file.filename}"
    save_path = STORAGE_DIR / safe_filename
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    return {"success": True, "filename": safe_filename, "message": "File uploaded successfully"}

@app.delete("/api/history/{timestamp}")
async def delete_history_item(timestamp: str, user: str = Depends(get_current_user)):
    meta_file = STORAGE_DIR / f"meta_{timestamp}.json"
    audio_file = STORAGE_DIR / f"audio_{timestamp}.wav"
    deleted = False
    if meta_file.exists():
        meta_file.unlink()
        deleted = True
    if audio_file.exists():
        audio_file.unlink()
        deleted = True
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True, "message": f"Session {timestamp} deleted"}

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str, user: str = Depends(get_current_user)):
    return templates.TemplateResponse(request, "index.html")

# ── Entrypoint ────────────────────────────────────────────────────────────────
def main():
    import uvicorn
    parser = argparse.ArgumentParser(description="Makix Studio — Qwen3-TTS")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", type=str, default=HOST)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    
    # Direct Generation Params
    parser.add_argument("--text", type=str, help="Text to synthesize (triggers non-interactive mode)")
    parser.add_argument("--language", type=str, help="Language")
    parser.add_argument("--speaker", type=str, help="Speaker name")
    parser.add_argument("--instruct", type=str, help="Voice instruction")
    parser.add_argument("--ref-audio", type=str, help="Reference audio path")
    parser.add_argument("--ref-text", type=str, help="Reference text")
    parser.add_argument("--play", action="store_true", help="Play after generation")

    args = parser.parse_args()

    if args.cli or args.text:
        from cli import StudioCLI
        cli = StudioCLI(args)
        try:
            cli.run()
        except KeyboardInterrupt:
            print("\nExiting...")
        return

    print(f"\n🎵 Makix Studio starting on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="debug" if args.debug else "info")

if __name__ == "__main__":
    main()
