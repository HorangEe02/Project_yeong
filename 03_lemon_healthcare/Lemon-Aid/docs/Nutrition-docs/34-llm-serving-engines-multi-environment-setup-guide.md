# 34. Ollama · MLX-LM · vLLM 다중 환경 설치·운영 가이드

> **문서 정보**
> 버전: v1.1 | 작성일: 2026-05-14 | 상태: 환경 후보 가이드 (Ollama 기본, MLX/vLLM 후속 검증) | 작성자: yeong-tech

---

## 0. 한 줄 요약

본 프로젝트의 현재 백엔드 런타임은 `LLM_PROVIDER=ollama` 만 지원한다. 이 문서는 **Mac(Apple Silicon)** 과 **Windows** 병행 개발을 위해 Ollama 기본 환경을 고정하고, MLX-LM/vLLM 은 후속 Adapter PR 전까지 실험 후보로만 정리한다. `src/llm/base.py` 는 아직 Phase 2 후반 도입 예정 인터페이스이므로, MLX/vLLM 전환은 환경 변수 한 줄만으로 끝나는 상태가 아니다.

| 환경 | 1순위 (개발) | 2순위 (실험) | 3순위 (Phase 4 출시 시) |
| --- | --- | --- | --- |
| **macOS (Apple Silicon)** | **Ollama** | MLX-LM / `vllm-mlx` | (cloud GPU 로 이전) |
| **Windows (NVIDIA GPU)** | **Ollama (winget)** | WSL2 + **vLLM** | 후속 PR 이후 검증 |
| **Linux (cloud GPU)** | vLLM 후보 | Ollama | Phase 4 이후 검증 |

---

## 1. 환경별 전제 조건 (Prerequisites)

### 1.1 macOS (Apple Silicon)

| 항목 | 요건 | 비고 |
| --- | --- | --- |
| Chip | **Apple Silicon M1 이상** (M1/M2/M3/M4) | Intel Mac 은 MLX 사용 불가 |
| macOS | **14.0 Sonoma 이상** (Ollama·MLX 공통) | MLX 일부 신규 기능은 macOS 15+ 필요 |
| 통합 메모리 | **16GB 권장**(최소), **24GB+** 권장(Qwen 3.5 9B + Gemma 4 E4B 순차 실행) | Ollama 0.19 MLX preview 검증은 공식 블로그 기준 32GB 초과 Mac 권장 |
| Python | **3.11.x 이상** (MLX-LM 요구) | 반드시 native ARM Python (`python -c "import platform; print(platform.processor())"` → `arm`) |
| Homebrew | 최신 | Ollama 설치 경로 |
| Xcode CLT | 설치 | `xcode-select --install` |

### 1.2 Windows

| 항목 | 요건 | 비고 |
| --- | --- | --- |
| OS | **Windows 10 1903+** 또는 **Windows 11** | 2026 부터 **Windows ARM64 네이티브 빌드** 제공 (Ollama) |
| RAM | **16GB+** 권장 (최소 8GB) | vLLM 실험 시 32GB+ |
| GPU (Ollama) | NVIDIA CUDA driver **525.60.13+** | Ollama 가 CUDA 런타임 자체 번들 → Toolkit 별도 설치 불요 |
| GPU (vLLM) | CUDA Toolkit **12.1** 권장 (11.8 호환) | vLLM 바이너리가 CUDA 12.1 컴파일됨 |
| WSL2 | **Ubuntu 22.04 LTS** (vLLM 실험) | WSL --install Ubuntu |
| Python | **3.10 ~ 3.12** (vLLM/WSL2) | fresh conda env 권장 |
| Docker Desktop | 4.36+ (선택) | Docker Model Runner 가 2026 부터 vLLM 통합 지원 |

### 1.3 공통 운영 정책 (재확인)

- 환자 식별 정보는 **반드시 로컬 호스트**(`127.0.0.1` / `localhost` / `::1`) 만 허용 — [docs/12 §2](./12-local-llm-ollama-migration.md)
- 외부 LLM(클라우드)은 `allow_external_llm=false` 기본 — [config.py:223~224](../backend/src/config.py)
- 모든 서빙 엔진은 [docs/33 Tier 3](./33-three-tier-ocr-pipeline-implementation-guide.md) 의 시스템 프롬프트(`OLLAMA_VISION_ASSIST_SYSTEM_PROMPT`)와 동일한 의료 표현 금지 규칙을 따른다.

---

## 2. Ollama — Mac · Windows 공통

### 2.1 채택 이유

- 본 프로젝트의 **현재 기본 LLM 서빙** ([docs/12](./12-local-llm-ollama-migration.md), [docs/33 §5](./33-three-tier-ocr-pipeline-implementation-guide.md))
- 단일 명령 설치, 모델 자동 캐싱, OpenAI 호환 API, 양 OS 모두 지원
- 2026 신규 검증 후보: Ollama 0.19 MLX preview on Apple Silicon

### 2.2 버전 기준

- **기본 요구**: 공식 macOS/Windows 설치판의 `ollama --version` 확인
- **MLX preview 검증 후보**: Ollama 0.19. 공식 블로그는 Apple Silicon에서 MLX 기반 preview와 32GB 초과 unified memory 조건을 안내한다.
- 본 프로젝트 backend 설정은 현재 특정 Ollama 버전 문자열을 강제하지 않는다. 실제 모델 tag와 `/api/chat` 동작을 smoke test로 확인한다.

### 2.3 macOS 설치

```bash
# 옵션 A: Homebrew (권장)
brew install ollama
brew services start ollama   # 백그라운드 데몬

# 옵션 B: 공식 dmg
# https://ollama.com/download/mac 에서 받아 드래그 설치

# 버전 확인
ollama --version            # >= 0.19.0
curl http://127.0.0.1:11434/api/version

# 필요 모델 풀
ollama pull qwen3.5:9b      # 텍스트 (docs/12 §3 1차 기본)
ollama pull gemma4:e4b      # 멀티모달 (docs/33 §5.3 Tier 3 이미지→텍스트)

# GGUF 직접 실행 후보 (Gemma 4 26B A4B). 실제 기본값 전환 전 smoke gate 필수.
# [dev-guides/31-gemma-4-gguf-setup-guide.md](./dev-guides/31-gemma-4-gguf-setup-guide.md)

# 동작 확인
curl http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5:9b","stream":false,"messages":[{"role":"user","content":"비타민 C 500mg을 JSON으로 정리해줘."}],"format":"json","options":{"temperature":0}}'
```

### 2.4 Windows 설치

```powershell
# 옵션 A: winget (권장)
winget install --id Ollama.Ollama --source winget

# 옵션 B: 공식 설치 프로그램
# https://ollama.com/download/windows 에서 OllamaSetup.exe 실행

# NVIDIA GPU 가속 (선택)
# 1. NVIDIA driver 525.60.13+ 만 있으면 됨 (CUDA Toolkit 불필요 — Ollama 가 런타임 번들)
# 2. 작업 관리자 → 성능 → GPU 에 사용량 표시되는지 확인

# 버전 확인 (PowerShell)
ollama --version            # >= 0.19.0
Invoke-WebRequest -Uri http://127.0.0.1:11434/api/version

# 모델 풀 + 동작 확인
ollama pull qwen3.5:9b
ollama pull gemma4:e4b
# Gemma 4 26B A4B GGUF 직접 실행 후보는 아래 가이드를 참고하여 진행
# [dev-guides/31-gemma-4-gguf-setup-guide.md](./dev-guides/31-gemma-4-gguf-setup-guide.md)
ollama list
```

### 2.5 본 프로젝트 환경변수 매핑 (`backend/.env`)

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b              # 텍스트 구조화 기본. Gemma 4 Q4는 docs/dev-guides/31 smoke gate 후 override
OLLAMA_VISION_MODEL=gemma4:e4b       # 이미지→텍스트. Gemma 4 Q4로 즉시 교체하지 않음
OLLAMA_TIMEOUT_SEC=60
OLLAMA_TEMPERATURE=0
ALLOW_EXTERNAL_LLM=false
```

→ Adapter: [`backend/src/llm/ollama.py`](../backend/src/llm/ollama.py) 의 `OllamaSupplementParser` + `backend/src/llm/ollama_vision.py` 가 그대로 사용. 코드 변경 없음.

### 2.6 smoke 테스트

```bash
python3 -c "
import httpx, json
r = httpx.post('http://127.0.0.1:11434/api/chat', json={
    'model': 'qwen3.5:9b',
    'stream': False,
    'messages': [{'role': 'user', 'content': '비타민 C 500mg, 비타민 D 1000IU 를 JSON 리스트로 정규화.'}],
    'format': 'json',
    'options': {'temperature': 0},
}, timeout=60)
r.raise_for_status()
print(json.dumps(r.json(), ensure_ascii=False, indent=2))
"
```

---

## 3. MLX-LM — macOS 전용

### 3.1 채택 이유 / 한계

- **Apple Silicon 전용**. Windows·Linux 사용 불가.
- 본 프로젝트에서는 **개발자 개인 실험** 용도 (Ollama 0.19 MLX 백엔드만으로 충분한 속도가 나오지 않을 때 비교 측정용).
- Production 후보 아님 (cloud Linux 운영 불가).
- 멀티모달은 별도 패키지 [`mlx-vlm`](https://github.com/Blaizzy/mlx-vlm) 사용.

### 3.2 버전 기준

- `mlx-lm` **>= 0.20.x** (`pip show mlx-lm`)
- `mlx-vlm` **>= 0.1.x** (Vision 패키지)
- `mlx` core **>= 0.21.x**
- Python **3.11.x 이상** native ARM (Apple Silicon)

### 3.3 macOS 설치

```bash
# 1. native ARM Python 확인
python3 -c "import platform; print(platform.processor())"   # → arm

# 2. uv (권장 패키지 매니저) 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 격리 환경 생성
uv venv .venv-mlx --python 3.12
source .venv-mlx/bin/activate

# 4. 텍스트 모델용 mlx-lm
uv pip install mlx-lm
mlx_lm.generate --help

# 5. Vision 모델용 mlx-vlm (공식 지원 모델은 후속 PoC에서 확정)
uv pip install mlx-vlm

# 6. 모델 다운로드 (예시는 텍스트 모델만 고정; vision 가중치는 후속 PoC에서 공식 지원 여부 확인)
huggingface-cli download mlx-community/Qwen3.5-9B-Instruct-4bit
```

### 3.4 OpenAI 호환 서버 실행

본 프로젝트의 Adapter 가 OpenAI 호환 API 를 가정하므로, MLX-LM 공식 서버 모드를 사용:

```bash
# 텍스트 서버 (포트 8081 — Ollama 11434 와 충돌 회피)
mlx_lm.server \
  --model mlx-community/Qwen3.5-9B-Instruct-4bit \
  --host 127.0.0.1 \
  --port 8081

# 별도 터미널에서 Vision 서버
# 모델명은 mlx-vlm 공식 지원 목록과 라이선스 확인 후 확정한다.
python -m mlx_vlm.server \
  --model <official-mlx-vlm-vision-model> \
  --port 8082
```

### 3.5 본 프로젝트 통합

MLX-LM 을 운영하려면 신규 Adapter 추가가 필요. 본 가이드는 후속 PR 에서 다음을 작성하도록 안내한다 (본 PR 범위 외):

- `backend/src/llm/mlx_openai.py` — 신규 Adapter
- `Settings`:
  - `LLM_PROVIDER=mlx_openai`
  - `MLX_BASE_URL=http://127.0.0.1:8081`
  - `MLX_VISION_BASE_URL=http://127.0.0.1:8082`
- Adapter 인터페이스는 `OllamaSupplementParser` 와 동일한 시그니처 ([`backend/src/llm/base.py`](../backend/src/llm/base.py))

### 3.6 한계·주의

- `mlx_lm.server` 의 **구조화 출력**(JSON Schema 강제)은 Ollama `format=<schema>` 만큼 안정적이지 않다. `outlines` / `guidance` 같은 추가 패키지 통합 필요.
- 모델 hot-swap 미지원 — 모델 교체 시 서버 재시작.
- 본 프로젝트의 `SupplementStructuredParseResult` 강제 검증을 위해 응답을 Pydantic 으로 재검증하는 retry 로직이 더 중요해진다.

### 3.7 smoke 테스트

```bash
curl http://127.0.0.1:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen3.5-9B-Instruct-4bit",
    "messages": [{"role": "user", "content": "비타민 C 500mg을 JSON으로 정리해줘."}],
    "temperature": 0
  }'
```

---

## 4. vLLM — Windows(WSL2) · Linux 권장

### 4.1 채택 이유 / 한계

- **Phase 4 정식 출시 + 동시 50명 이상** 에서 처리량 6× ([docs/33](./33-three-tier-ocr-pipeline-implementation-guide.md) 참조)
- **macOS 네이티브 지원 X** (Metal 백엔드 미흡). Mac 에서 굳이 시도하려면 [`vllm-mlx`](https://github.com/waybarrios/vllm-mlx) 포크.
- **CUDA 12.1 (또는 11.8) 컴파일 바이너리**. 다른 CUDA/PyTorch 버전과 ABI 충돌 → fresh conda env 필수.

### 4.2 버전 기준

- **vLLM >= 0.8.3** (2026 기준 안정)
- Python **3.10 ~ 3.12**
- CUDA Toolkit **12.1** (권장) 또는 11.8 (호환)
- PyTorch — vLLM wheel 이 자동 매칭 (수동 설치 금지)

### 4.3 Windows (WSL2) 설치

```powershell
# 1. WSL2 + Ubuntu 22.04 설치 (Windows PowerShell 관리자 권한)
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2

# 2. WSL 안으로 들어가기
wsl -d Ubuntu-22.04
```

```bash
# 3. (WSL 안) NVIDIA CUDA Toolkit 12.1 설치 — driver 는 Windows 측 사용
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install -y cuda-toolkit-12-1

# 4. miniconda 설치 (fresh env 권장)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b
~/miniconda3/bin/conda init bash
source ~/.bashrc

# 5. vLLM fresh env
conda create -n vllm python=3.12 -y
conda activate vllm
pip install --upgrade pip
pip install vllm   # CUDA 12.1 wheel 자동 매칭

# 6. 동작 확인
python -c "import vllm; print(vllm.__version__)"   # >= 0.8.3
```

### 4.4 vLLM OpenAI 호환 서버 실행

```bash
# 텍스트
vllm serve Qwen/Qwen3.5-9B-Instruct \
  --host 127.0.0.1 \
  --port 8091 \
  --dtype auto \
  --gpu-memory-utilization 0.85

# 별도 터미널에서 Vision 모델
# 모델명은 vLLM 멀티모달 지원 목록과 라이선스 확인 후 확정한다.
vllm serve <official-vllm-vision-model> \
  --host 127.0.0.1 \
  --port 8092 \
  --dtype auto \
  --gpu-memory-utilization 0.85
```

> ⚠️ `gpu-memory-utilization` 은 GPU VRAM 의 비율. 24GB GPU 에서 두 모델 동시 운영은 권장하지 않음 — 별도 GPU 또는 시간 분할 사용.

### 4.5 macOS (옵션, 실험용) — `vllm-mlx`

본 프로젝트는 Mac 에서 vLLM 운영을 권장하지 않는다. 그래도 처리량 비교를 원하면:

```bash
# 1. native ARM Python
python3 -c "import platform; print(platform.processor())"   # arm

# 2. uv venv
uv venv .venv-vllm-mlx --python 3.12
source .venv-vllm-mlx/bin/activate

# 3. vllm-mlx 설치 (Apple Silicon 포팅)
uv pip install git+https://github.com/waybarrios/vllm-mlx

# 4. 서버 실행 (OpenAI 호환)
python -m vllm_mlx.server --model mlx-community/Qwen3.5-9B-Instruct-4bit --port 8091
```

→ production 검증은 더 지켜봐야 함. 본 프로젝트는 실험 데이터 수집 용도로만 사용.

### 4.6 본 프로젝트 환경변수 매핑

```env
LLM_PROVIDER=vllm                    # 후속 Adapter + Settings 확장 이후에만 사용
VLLM_BASE_URL=http://127.0.0.1:8091  # 텍스트
VLLM_VISION_BASE_URL=http://127.0.0.1:8092
VLLM_MODEL=Qwen/Qwen3.5-9B-Instruct
VLLM_VISION_MODEL=<official-vllm-vision-model>
ALLOW_EXTERNAL_LLM=false
```

신규 Adapter: `backend/src/llm/vllm_openai.py` — Ollama Adapter 와 동일 시그니처. 본 가이드는 후속 PR 의 명세만 정의.

### 4.7 smoke 테스트

```bash
curl http://127.0.0.1:8091/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B-Instruct",
    "messages": [{"role": "user", "content": "비타민 C 500mg을 JSON으로 정리해줘."}],
    "temperature": 0,
    "response_format": {"type": "json_object"}
  }'
```

### 4.8 구조화 출력 (Pydantic JSON Schema 강제)

vLLM 의 강점. `guided_json` 또는 `xgrammar` 백엔드:

```python
from openai import OpenAI
from backend.src.models.schemas.supplement_parser import SupplementStructuredParseResult

client = OpenAI(base_url="http://127.0.0.1:8091/v1", api_key="not-needed")
resp = client.chat.completions.create(
    model="Qwen/Qwen3.5-9B-Instruct",
    messages=[...],
    extra_body={"guided_json": SupplementStructuredParseResult.model_json_schema()},
)
```

[docs/33 §5](./33-three-tier-ocr-pipeline-implementation-guide.md) 의 텍스트 구조화 단계에서 vLLM 전환 시 자동 활성.

---

## 5. 통합 활용 전략 (어떤 환경에서 무엇을 쓸지)

### 5.1 환경별 매트릭스

| 단계 / OS | macOS Apple Silicon | Windows + NVIDIA GPU | Linux cloud GPU (Phase 4) |
| --- | --- | --- | --- |
| 텍스트 LLM 기본 | **Ollama qwen3.5:9b** | **Ollama qwen3.5:9b** | vLLM 후보(후속 Adapter 필요) |
| Vision (Tier 3 이미지→텍스트) | Ollama gemma4:e4b | Ollama gemma4:e4b | vLLM vision 후보(모델 미확정) |
| 텍스트 구조화 (Tier 3 텍스트→JSON) | Ollama qwen3.5:9b | Ollama qwen3.5:9b | vLLM Qwen/Qwen3.5-9B-Instruct (`guided_json`) |
| 처리량 비교 실험 | MLX-LM (`mlx_lm.server`) 또는 `vllm-mlx` | WSL2 + vLLM | vLLM |
| 발주처 인수 데모 | Mac 에서 Ollama 단일 | Windows 에서 Ollama 단일 | vLLM 후보(해당 시점 재검증) |

### 5.2 Adapter 패턴(CLAUDE.md Rule 2) 일관 유지

세 엔진 모두 OpenAI 호환 또는 자체 호환 API 를 제공할 수 있지만, 현재 `Settings.llm_provider` 는 `ollama` 만 허용한다. MLX/vLLM 전환은 신규 Adapter, Settings 확장, DI 분기, 테스트가 모두 머지된 뒤에만 가능하다.

```
backend/src/llm/
├── base.py              # LLMAdapter ABC + analyze_text/analyze_multimodal
├── ollama.py            # 현행 (OllamaSupplementParser)
├── ollama_vision.py     # 현행 (Gemma 4 E4B vision assist 후보)
├── mlx_openai.py        # NEW (후속 PR — MLX-LM 도입 시)
└── vllm_openai.py       # NEW (후속 PR — vLLM 도입 시)
```

후속 PR 에서 `Settings.LLM_PROVIDER` 허용값과 adapter factory를 확장한다. 본 가이드는 그 분기 코드를 정의하지 않는다.

### 5.3 신규 개발자 온보딩 30분 체크리스트

**macOS:**
- [ ] `brew install ollama` + `brew services start ollama`
- [ ] `ollama --version` 확인
- [ ] MLX preview 성능 비교는 32GB 초과 Apple Silicon에서 별도 측정
- [ ] `ollama pull qwen3.5:9b && ollama pull gemma4:e4b` (Gemma 4 Q4 후보는 가이드 31 smoke gate 통과 후 `OLLAMA_MODEL`만 override)
- [ ] §2.6 smoke 테스트 통과
- [ ] [`backend/.env.example`](../backend/.env.example) → `.env` 복사 + Service Account JSON 경로 입력 ([docs/33 §4.4](./33-three-tier-ocr-pipeline-implementation-guide.md))
- [ ] `pytest backend/tests` 그린

**Windows:**
- [ ] `winget install Ollama.Ollama`
- [ ] NVIDIA driver ≥ 525.60.13 확인 (`nvidia-smi`)
- [ ] `ollama pull qwen3.5:9b && ollama pull gemma4:e4b` (Gemma 4 Q4 후보는 가이드 31 smoke gate 통과 후 `OLLAMA_MODEL`만 override)
- [ ] §2.6 smoke 테스트 통과
- [ ] `.env` 동일 작성
- [ ] `pytest backend/tests` 그린

**Phase 4 (옵션, Linux/WSL2):**
- [ ] §4.3 vLLM fresh conda env 설치
- [ ] `vllm serve Qwen/Qwen3.5-9B-Instruct --port 8091` 동작
- [ ] §4.7 smoke 통과
- [ ] 신규 `src/llm/vllm_openai.py` Adapter 가 PR 머지된 시점부터 `LLM_PROVIDER=vllm` 전환 가능

---

## 6. 트러블슈팅

### 6.1 macOS

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| `ollama list` 가 멈춤 | `ollama` 데몬 미실행 | `brew services start ollama` |
| MLX preview 성능이 기대보다 낮음 | 공식 preview 조건 또는 모델/메모리 조건 불일치 | Ollama 0.19 blog 조건(32GB 초과 Apple Silicon)과 실제 `ollama --version`/모델 tag를 재확인 |
| `python -c "import mlx"` 실패 | x86 Python 사용 중 | `uv venv --python 3.12` 로 fresh venv |
| `mlx_lm.server` 포트 충돌 | Ollama 의 11434 와 다른 포트 필요 | `--port 8081` 등 충돌 회피 |
| Vision 응답이 너무 느림 | `gemma4:e4b` 도 메모리 또는 latency 부담 | `gemma4:e2b` PoC 또는 사용자 수동 확인 화면으로 escalation |

### 6.2 Windows / WSL2

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| Ollama GPU 미사용 | NVIDIA driver 미설치 또는 525 미만 | 최신 드라이버 설치 + 재부팅 |
| WSL2 가 CPU 사용 100% | WSL 메모리 한계 (8GB 기본) | `%UserProfile%\.wslconfig` 에 `memory=24GB` 추가 |
| vLLM `CUDA out of memory` | `gpu-memory-utilization` 너무 높음 | 0.85 → 0.70 로 낮추기 |
| `pip install vllm` 컴파일 오류 | CUDA Toolkit 누락 | §4.3 단계 3 재실행 |
| vLLM 멀티모달 모델이 ChatTemplate 인식 X | tokenizer config 누락 | `--chat-template` 옵션으로 명시 또는 최신 HF 가중치 사용 |

### 6.3 공통

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| `Settings.allow_external_llm` 가드 발동 | production 환경에서 외부 LLM 호출 시도 | 기본 `false` 유지, 비식별 환경에서만 명시 활성 |
| Pydantic JSON 검증 실패 반복 | LLM 응답이 schema 위반 | retry 1회 후 사용자 수정 화면 escalation ([docs/12 §6](./12-local-llm-ollama-migration.md)) |
| 의료 표현 출력 감지 | system prompt 미적용 | [`backend/src/llm/ollama_vision.py`](../backend/src/llm/ollama_vision.py) 의 `OLLAMA_VISION_ASSIST_SYSTEM_PROMPT` 재사용 |

---

## 7. 보안·컴플라이언스 체크리스트 (재확인)

세 엔진 공통으로 다음을 운영 전 확인:

- [ ] `OLLAMA_BASE_URL` / `MLX_BASE_URL` / `VLLM_BASE_URL` 이 모두 `127.0.0.1`·`localhost`·`::1` 만 사용 ([docs/12 §2](./12-local-llm-ollama-migration.md))
- [ ] `ALLOW_EXTERNAL_LLM=false` 유지 (개발 PoC 환경에서는 비식별 데이터만)
- [ ] 모델 가중치는 공식 출처(`mlx-community`, `Qwen/`, `google/`, `ollama.com/library/`) 만 사용
- [ ] 로그에 prompt 전문 저장 금지 ([docs/12 §2.4](./12-local-llm-ollama-migration.md))
- [ ] 시스템 프롬프트의 의료 판단 금지 규칙 적용 ([docs/33 §5.4](./33-three-tier-ocr-pipeline-implementation-guide.md))
- [ ] 양자화 가중치 라이선스 확인. 모델별 라이선스는 발주처 인수 시점에 공식 모델 페이지 또는 원 배포처에서 재확인한다.

---

## 8. 도입 일정 (참고)

본 가이드는 **문서만 작성**. 실제 Adapter 도입 코드 PR 은 별도 일정:

| 단계 | 작업 | 소요 | 의존 |
| --- | --- | --- | --- |
| 0 | 본 가이드(`docs/34`) 푸시 | 본 PR | — |
| 1 | 신규 개발자 환경 셋업 검증 (Mac/Win 각 1명) | 0.5일 | 0 |
| 2 | Ollama 0.19 MLX preview 응답시간 측정(32GB 초과 Apple Silicon 조건) | 0.5일 | 1 |
| 3 | MLX-LM 직접 도입 결정 (실험 데이터로 판단) | — | 2 |
| 4 | (Phase 4 진입 시) vLLM Adapter PR — `src/llm/vllm_openai.py` 신규 | 1일 | docs/33 100장 PoC 완료 |
| 5 | 운영 환경 GPU 인스턴스 프로비저닝 + smoke | 0.5일 | 4 |

---

## 9. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
| --- | --- | --- |
| 2026-05-14 | 공식 Ollama tag 기준으로 `gemma4:e4b` / `qwen3.5:9b`를 정리하고, MLX/vLLM 항목을 후속 검증 후보로 낮춤. | yeong-tech |
| 2026-05-14 | 최초 작성. Ollama / MLX-LM / vLLM 의 Mac · Windows 환경 설치·운영 후보 정의. | yeong-tech |

## 10. 관련 문서

- [docs/Nutrition-docs/06-tech-stack.md](./06-tech-stack.md) §2.3 — pyproject extras
- [docs/Nutrition-docs/12-local-llm-ollama-migration.md](./12-local-llm-ollama-migration.md) — Ollama 운영 원칙
- [docs/Nutrition-docs/17-image-collection-consent-plan.md](./17-image-collection-consent-plan.md) §6 — 암호화·로컬 운영 정책
- [docs/Nutrition-docs/31-backend-feature-specifications.md](./31-backend-feature-specifications.md) §5 — LLM 모듈 명세
- [docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md](./33-three-tier-ocr-pipeline-implementation-guide.md) — Tier 3 멀티모달 운영안

외부 공식 문서:

- [Ollama macOS install](https://docs.ollama.com/macos)
- [Ollama is now powered by MLX](https://ollama.com/blog/mlx)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Ollama Vision](https://docs.ollama.com/capabilities/vision)
- [Ollama Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama qwen3.5](https://ollama.com/library/qwen3.5)
- [Ollama gemma4](https://ollama.com/library/gemma4)
- [MLX official docs](https://ml-explore.github.io/mlx/build/html/install.html)
- [mlx-lm PyPI](https://pypi.org/project/mlx-lm/)
- [mlx-lm GitHub](https://github.com/ml-explore/mlx-lm)
- [vLLM Installation](https://docs.vllm.ai/en/latest/getting_started/installation/)
- [vLLM GPU install](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/)
- [Docker Model Runner vLLM Windows](https://www.docker.com/blog/docker-model-runner-vllm-windows/)

비공식/실험 참고:

- [vllm-mlx (Apple Silicon)](https://github.com/waybarrios/vllm-mlx)
- [mlx-vlm GitHub](https://github.com/Blaizzy/mlx-vlm)
