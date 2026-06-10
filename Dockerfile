# Makix Studio — Qwen3-TTS
# Base image ships torch 2.5.1 + CUDA 12.4 + Python 3.11, matching requirements.txt.
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

# ffmpeg: podcast video export · libsndfile1: soundfile backend
# build-essential: torch.compile (inductor) compiles kernels at runtime and needs a host C compiler
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Flash Attention 2 (optional — the engine falls back gracefully without it).
# Pre-built wheel matching torch 2.5 / CUDA 12 / Python 3.11 of the base image.
# Override with --build-arg FLASH_ATTN_WHEEL=<url-or-path>, or "" to skip.
ARG FLASH_ATTN_WHEEL=https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.5cxx11abiFALSE-cp311-cp311-linux_x86_64.whl
RUN if [ -n "$FLASH_ATTN_WHEEL" ]; then \
        pip install --no-cache-dir "$FLASH_ATTN_WHEEL" \
        || echo "WARNING: Flash Attention install failed — continuing without it"; \
    fi

COPY app.py engine.py cli.py ./
COPY static/ static/
COPY templates/ templates/

# Run as non-root; UID must match the host owner of the bind-mounted
# ./storage and ./models dirs (override: --build-arg APP_UID=$(id -u))
ARG APP_UID=1000
RUN useradd --create-home --uid "${APP_UID}" makix \
    && mkdir -p /app/storage /app/models /app/.torch_compile_cache /app/.hf-cache \
    && chown -R makix:makix /app
USER makix

ENV HOST=0.0.0.0 \
    PORT=8000 \
    MODELS_DIR=/app/models \
    TORCHINDUCTOR_CACHE_DIR=/app/.torch_compile_cache \
    HF_HOME=/app/.hf-cache

EXPOSE 8000

# Long start-period: first boot loads the model and may compile CUDA kernels (1-3 min)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5m --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"

CMD ["python", "app.py"]
