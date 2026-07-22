"""환경변수 기반 설정. 값이 없어도 안전한 기본값으로 데모가 동작한다."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # local-worker/
WEB_DIR = BASE_DIR / "web"

# .env 자동 로드 (python-dotenv 없이 stdlib) — 이미 설정된 환경변수는 덮어쓰지 않음
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

DATA_ROOT = Path(os.getenv("LOCAL_STORAGE_ROOT", str(BASE_DIR / "data"))).resolve()
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_ROOT / "app.db")))

PORT = int(os.getenv("PORT", "8710"))
API_PREFIX = "/v1"

# 인증: 토큰이 있으면 요구, 없으면 데모 모드(인증 없이 동작)
LOCAL_API_TOKEN = os.getenv("LOCAL_API_TOKEN", "").strip()
AUTH_ENABLED = bool(LOCAL_API_TOKEN)

# DB 백엔드 선택: sqlite(기본, 검증됨) | postgres(Supabase, psycopg + native 타입)
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()

# 단일 로컬 사용자 (findings #1). uuid 형식 → sqlite(TEXT)·postgres(uuid) 양쪽 호환
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "00000000-0000-0000-0000-000000000001").strip()
DEFAULT_USER_EMAIL = "local@demo.local"
DEFAULT_USER_NAME = "로컬 데모 사용자"

# Provider 선택 (stub | faster_whisper), (stub | ollama)
ASR_PROVIDER = os.getenv("ASR_PROVIDER", "stub").strip()
SUMMARY_PROVIDER = os.getenv("SUMMARY_PROVIDER", "stub").strip()

# Stub 파이프라인 단계별 지연(초) — 상태 폴링을 눈에 보이게
STUB_STAGE_DELAY = float(os.getenv("STUB_STAGE_DELAY", "0.7"))

# 파이프라인을 요청 안에서 동기 실행할지. 서버리스(Vercel)는 응답을 보낸 뒤
# 백그라운드 태스크 실행이 보장되지 않으므로 1 로 둔다(stub 이라 즉시 끝난다).
SYNC_PIPELINE = os.getenv("SYNC_PIPELINE", "0") == "1"

# Slack
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
SLACK_SIMULATE = os.getenv("SLACK_SIMULATE", "1") == "1"

# --- 실제 로컬 ASR (ASR_PROVIDER=faster_whisper 일 때만) ---
# 모델: tiny/base/small/medium/large-v3 (클수록 한국어 품질↑, 속도↓)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium").strip()
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu").strip()      # Mac은 CPU(int8)
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8").strip()

# --- 화자 구분(diarization, 선택) ---
# 방식: auto(기본) | none | sherpa | pyannote
#   sherpa   = sherpa-onnx (오픈 모델, HF 토큰 불필요) — models/diarization/ 에 모델 있으면 사용
#   pyannote = pyannote.audio (HF_TOKEN + 게이트 모델 약관 동의 필요)
#   auto     = sherpa 모델 있으면 sherpa, 없고 HF_TOKEN 있으면 pyannote, 아니면 none
DIARIZER = os.getenv("DIARIZER", "auto").strip()
_DIAR_DIR = BASE_DIR / "models" / "diarization"
SHERPA_SEG_MODEL = os.getenv(
    "SHERPA_SEG_MODEL",
    str(_DIAR_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"))
SHERPA_EMB_MODEL = os.getenv("SHERPA_EMB_MODEL", str(_DIAR_DIR / "embedding.onnx"))
DIAR_NUM_SPEAKERS = int(os.getenv("DIAR_NUM_SPEAKERS", "0"))   # 0 = 자동(threshold)
DIAR_THRESHOLD = float(os.getenv("DIAR_THRESHOLD", "0.5"))

# pyannote 전용
HF_TOKEN = (os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or "").strip()
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1").strip()

# --- 실제 로컬 요약 (SUMMARY_PROVIDER=ollama 일 때만) ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").strip()
# 후보: gemma4:e4b (9.6GB), qwen3.5 (6.6GB), qwen2.5:7b, gemma2:9b 등
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b").strip()
# 추론(thinking) 제어: "false"(기본, 사고 끄기) | "true" 켜기 | "" 미전송.
# 기본 false — 추론 모델(gemma4/qwen3.5)은 요약 속도↑·JSON 안정, 비추론 모델(qwen2.5 등)은
# Ollama가 이 값을 무시하므로 어떤 모델로 바꿔도 안전하다.
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "false").strip().lower()

# --- Supabase 연결 (server 이전/저장소 전환용) ---
# URL·publishable(anon) 키는 공개용(클라이언트 임베드 안전).
# service_role 키와 DATABASE_URL(비밀번호 포함)은 절대 커밋하지 말고 .env(gitignore)에만 둔다.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_ANON_KEY)

# 파일 저장 위치: local(기본, 디스크) | supabase(Supabase Storage 비공개 버킷)
# supabase 는 서버측 service_role 키가 필요하다(버킷이 비공개이므로).
STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local").strip().lower()
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "meeting-files").strip()

DATA_ROOT.mkdir(parents=True, exist_ok=True)
