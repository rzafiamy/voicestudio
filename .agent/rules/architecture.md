# Project Architecture Rules

## 1. Stack Overview
- **Backend**: FastAPI with Uvicorn.
- **Frontend**: Vanilla JS + CSS (Studio aesthetics).
- **Inference**: PyTorch + Transformers + `qwen-tts` custom library.
- **Storage**: `storage/` directory for audio `.wav` and metadata `.json`.

## 2. Text Preprocessing Flow
All text sent to the `/api/generate` endpoint must follow this pipeline:
1. **Markdown Stripping**: Convert MD to plain text via BeautifulSoup.
2. **Normalization**: Character replacements (smart quotes, dashes, etc.) and Unicode NFC normalization.
3. **Filtering**: Keep only ASCII, standard letters (multilingual), and punctuation. Drop control characters.
4. **Splitting**: Segments are split for batching (see `performance.md`).

## 3. Auth & Security
- Simple JWT-based authentication via cookies.
- Admin credentials stored in `.env`.
- CORS and Security headers handled by FastAPI defaults + manual cookie settings.

## 4. Model Management
- Models are discovered dynamically in `./models/` and `.`.
- Only one model is loaded at a time to preserve VRAM.
- Switching models triggers explicit `gc.collect()` and `torch.cuda.empty_cache()`.
