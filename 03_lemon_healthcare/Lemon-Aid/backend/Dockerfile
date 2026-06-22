FROM python:3.13-slim

ARG INSTALL_LOCAL_OCR=true
ARG INSTALL_VISION=false
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG PRELOAD_PADDLEOCR=false
ARG PRELOAD_PADDLEOCR_LANGUAGE=korean

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/Nutrition-backend:/app/ai_agent_chat/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true \
    YOLO_CONFIG_DIR=/home/lemon/.config/Ultralytics

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        curl \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv \
    && groupadd --system lemon \
    && useradd --system --gid lemon --create-home --home-dir /home/lemon lemon

COPY requirements.txt pyproject.toml ./

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "${INSTALL_LOCAL_OCR}" = "true" ]; then \
        pip install "paddlepaddle==3.2.0" "paddleocr>=3.6,<3.7"; \
    fi \
    && if [ "${INSTALL_VISION}" = "true" ]; then \
        pip install --index-url "${TORCH_INDEX_URL}" "torch>=2.2" "torchvision>=0.17" \
        && pip install "ultralytics>=8.1" "transformers<5" "numpy"; \
    fi

# Install gosu in its own layer AFTER the cached pip install so adding it does not
# invalidate the expensive torch/paddle/ocr layers; used by docker-entrypoint.sh.
RUN apt-get update \
    && apt-get install --no-install-recommends -y gosu \
    && rm -rf /var/lib/apt/lists/*

COPY alembic.ini ./
COPY alembic ./alembic
COPY Nutrition-backend ./Nutrition-backend
COPY Nutrition-backend/data/nutrition_reference ./data/nutrition_reference
COPY Food-backend ./Food-backend
COPY ai_agent_chat ./ai_agent_chat
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN if [ "${PRELOAD_PADDLEOCR}" = "true" ]; then \
        LOCAL_OCR_LANGUAGE="${PRELOAD_PADDLEOCR_LANGUAGE}" python scripts/preload_paddleocr.py; \
    fi \
    && mkdir -p /home/lemon/.paddlex \
    && mkdir -p /home/lemon/.config/Ultralytics \
    && mkdir -p /home/lemon/.cache/huggingface/hub \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown -R lemon:lemon /app /home/lemon /opt/venv

# No USER directive: the container starts as root so docker-entrypoint.sh can fix
# ownership of the root-owned model-cache named volumes (lemon-aid-hf-cache,
# lemon-aid-paddle-cache), then drops to the unprivileged lemon user via gosu.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
