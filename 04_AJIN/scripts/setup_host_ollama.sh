#!/usr/bin/env bash
# AJIN host Ollama setup.
#
# macOS runs Ollama on the host so Docker can reach it through
# host.docker.internal:11434. The model root must be the Ollama "models"
# directory, not a manifest leaf directory.

set -euo pipefail

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
DEFAULT_MODELS_ROOT="<EXTERNAL_DRIVE>/.ollama/models"
MODELS_ROOT="${OLLAMA_MODELS_ROOT:-$DEFAULT_MODELS_ROOT}"
CHECK_ONLY=false
SKIP_PULL=false

log()  { printf '\033[36m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: scripts/setup_host_ollama.sh [options]

Options:
  --models-root PATH  Ollama models directory. Default: $DEFAULT_MODELS_ROOT
  --check-only        Validate path/env/server posture without installing or restarting.
  --skip-pull         Do not pull missing models.
  -h, --help          Show this help.

Notes:
  Use the parent models directory:
    <EXTERNAL_DRIVE>/.ollama/models

  Do not use the manifest leaf:
    <EXTERNAL_DRIVE>/.ollama/models/manifests/registry.ollama.ai/library
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --models-root)
      [[ $# -ge 2 ]] || err "--models-root requires a path"
      MODELS_ROOT="$2"
      shift 2
      ;;
    --check-only)
      CHECK_ONLY=true
      shift
      ;;
    --skip-pull)
      SKIP_PULL=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      ;;
  esac
done

normalize_models_root() {
  local raw="$1"
  raw="${raw%/}"
  if [[ "$raw" == */models/manifests/registry.ollama.ai/library ]]; then
    err "OLLAMA_MODELS must point to the parent models root, not the manifest leaf. Use: ${raw%/manifests/registry.ollama.ai/library}"
  fi
  if [[ "$raw" == */models/manifests* ]]; then
    err "OLLAMA_MODELS must point to the parent models root. Use the directory that contains both 'blobs' and 'manifests'."
  fi
  printf '%s\n' "$raw"
}

validate_models_root() {
  local root="$1"
  [[ -d "$root" ]] || err "Ollama models root does not exist: $root"
  [[ -d "$root/blobs" ]] || err "Missing '$root/blobs'. Use the Ollama models root, not a child directory."
  [[ -d "$root/manifests" ]] || err "Missing '$root/manifests'. Use the Ollama models root, not a child directory."
}

load_env() {
  local key="$1" default="$2"
  local val=""
  if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    val=$(grep -E "^${key}=" "${PROJECT_ROOT}/.env" | head -1 | cut -d= -f2- | xargs || true)
  fi
  printf '%s\n' "${val:-$default}"
}

ollama_ready() {
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1
}

model_installed() {
  local model="$1"
  local model_latest="${model}:latest"
  ollama list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -Eq "^(${model}|${model_latest})$"
}

start_ollama() {
  log "Ollama server restart with external SSD model root"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    launchctl setenv OLLAMA_MODELS "$MODELS_ROOT"
    launchctl setenv OLLAMA_HOST "127.0.0.1:11434"
    launchctl setenv OLLAMA_NO_CLOUD "1"
    launchctl setenv OLLAMA_KEEP_ALIVE "24h"

    if command -v brew >/dev/null 2>&1; then
      brew services restart ollama >/dev/null 2>&1 || true
    fi
    if ! ollama_ready; then
      pkill -x Ollama >/dev/null 2>&1 || true
      pkill -x ollama >/dev/null 2>&1 || true
      OLLAMA_MODELS="$MODELS_ROOT" \
      OLLAMA_HOST="127.0.0.1:11434" \
      OLLAMA_NO_CLOUD="1" \
      OLLAMA_KEEP_ALIVE="24h" \
      nohup ollama serve >/tmp/ajin_ollama_setup.log 2>&1 &
    fi
  else
    OLLAMA_MODELS="$MODELS_ROOT" \
    OLLAMA_HOST="127.0.0.1:11434" \
    OLLAMA_NO_CLOUD="1" \
    OLLAMA_KEEP_ALIVE="24h" \
    nohup ollama serve >/tmp/ajin_ollama_setup.log 2>&1 &
  fi

  for _ in {1..20}; do
    if ollama_ready; then
      log "Ollama server ready: http://127.0.0.1:11434"
      return
    fi
    sleep 1
  done
  err "Ollama server did not become ready. Check /tmp/ajin_ollama_setup.log"
}

MODELS_ROOT="$(normalize_models_root "$MODELS_ROOT")"
validate_models_root "$MODELS_ROOT"

case "$(uname -s)" in
  Darwin)
    log "macOS detected. Applying launchctl environment for Ollama app/service."
    ;;
  Linux)
    warn "Linux detected. Ensure the Ollama service user can read/write the model root."
    ;;
  *)
    err "Unsupported OS: $(uname -s)"
    ;;
esac

log "Model root: $MODELS_ROOT"
log "Model root size: $(du -sh "$MODELS_ROOT" 2>/dev/null | awk '{print $1}' || printf 'unknown')"

if [[ "$CHECK_ONLY" == "true" ]]; then
  if command -v launchctl >/dev/null 2>&1; then
    log "launchctl OLLAMA_MODELS: $(launchctl getenv OLLAMA_MODELS || true)"
  fi
  if ollama_ready; then
    log "Ollama API reachable: http://127.0.0.1:11434/api/tags"
  else
    warn "Ollama API is not currently reachable on 127.0.0.1:11434"
  fi
  exit 0
fi

if command -v ollama >/dev/null 2>&1; then
  log "Ollama installed: $(ollama --version 2>/dev/null | head -1)"
else
  log "Installing Ollama"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    command -v brew >/dev/null 2>&1 || err "Homebrew is required to install Ollama on macOS."
    brew install ollama
  else
    curl -fsSL https://ollama.com/install.sh | sh
  fi
fi

start_ollama

CHAT_LARGE=$(load_env OLLAMA_MODEL_CHAT_LARGE "qwen3.5:9b")
CHAT_SMALL=$(load_env OLLAMA_MODEL_CHAT_SMALL "qwen3.5:4b")
GEMMA_LARGE=$(load_env OLLAMA_MODEL_GEMMA_LARGE "gemma4:e4b")
EMBEDDING=$(load_env OLLAMA_MODEL_EMBEDDING "bge-m3")

log "Required AJIN models:"
for model in "$CHAT_LARGE" "$CHAT_SMALL" "$GEMMA_LARGE" "$EMBEDDING"; do
  if model_installed "$model"; then
    log "  ok: $model"
  elif [[ "$SKIP_PULL" == "true" ]]; then
    warn "  missing: $model (skip pull)"
  else
    log "  pull: $model"
    ollama pull "$model"
  fi
done

if ! ollama_ready; then
  warn "Ollama API stopped after model operations. Restarting once more."
  start_ollama
fi

log "Installed models:"
ollama list

cat <<EOF

Host Ollama is ready for AJIN.

Runtime defaults:
  OLLAMA_MODELS=$MODELS_ROOT
  OLLAMA_HOST=127.0.0.1:11434
  OLLAMA_NO_CLOUD=1
  OLLAMA_KEEP_ALIVE=24h

Docker backend:
  OLLAMA_BASE_URL=http://host.docker.internal:11434
EOF
