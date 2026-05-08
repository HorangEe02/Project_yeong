# 백엔드 LLM 멀티 라우터 — 상세 구현 계획서

> **모듈명**: `core/llm_router.py` + `core/providers/*`
> **목표 시간**: 2~2.5시간
> **선행 조건**: Ollama 모델 8 종 설치 완료 ✅, Gemini API 키 발급 필요
> **사용처**: Day 4 C AI 도우미 / Day 5 비전 / Day 8 B 문서 작성 / Day 9 D 법규 / 기타 LLM 사용 페이지
> **작성일**: 2026-04-27

---

## 목차

1. [목적 + 요구사항](#1-목적--요구사항)
2. [아키텍처 다이어그램](#2-아키텍처-다이어그램)
3. [프로바이더 능력 매트릭스](#3-프로바이더-능력-매트릭스)
4. [모드별 라우팅 정책](#4-모드별-라우팅-정책)
5. [폴백 체인 + Circuit Breaker](#5-폴백-체인--circuit-breaker)
6. [SSE 스트리밍 통합](#6-sse-스트리밍-통합)
7. [환경변수 + 설정](#7-환경변수--설정)
8. [파일 구조](#8-파일-구조)
9. [API 설계 (인터페이스)](#9-api-설계-인터페이스)
10. [구현 단계 (3 페이즈)](#10-구현-단계-3-페이즈)
11. [테스트 전략](#11-테스트-전략)
12. [검증 체크리스트](#12-검증-체크리스트)
13. [위험 요소 + 완화](#13-위험-요소--완화)
14. [의존성 추가](#14-의존성-추가)

---

## 1. 목적 + 요구사항

### 1-1. 비즈니스 요구사항

| # | 요구사항 | 근거 |
|:--:|---|---|
| 1 | **3 프로바이더 폴백** Gemini → Ollama → LM Studio | 사용자 결정 (2026-04-27) |
| 2 | **온프레미스 우선** 옵션 (한국어·민감 정보) | 아진산업 보안 정책 |
| 3 | **외부 API 활용** (Gemini 1순위, 인터넷 가능 시) | Wifi 확보됨 |
| 4 | **비전 모델** 지원 (이미지 분석) | 기능 C: 부품 사진, 도면 |
| 5 | **모드별 모델 선택** | 한국어/빠른응답/품질/비전 |
| 6 | **SSE 스트리밍** | 토큰 단위 클라이언트 표시 |
| 7 | **자동 복구** (failure → 1분 후 재시도) | 본선 데모 안정성 |
| 8 | **메트릭 수집** | 어느 프로바이더 사용했는지 추적 |

### 1-2. 비기능 요구사항

| 항목 | 목표 |
|---|---|
| **응답 시작 시간** | <500ms (첫 토큰까지) |
| **장애 감지 시간** | <2초 (health check) |
| **폴백 속도** | <500ms (다음 프로바이더로 전환) |
| **MacBook M4 Pro 메모리 안전** | 동시 로드 ≤14GB (qwen3.5:9b + bge-m3 + 1 추가) |
| **테스트 가능** | 각 프로바이더 mock 가능 |

### 1-3. 비범위 (Out-of-scope)
- ❌ 모델 fine-tuning
- ❌ 자동 모델 선택 (사용량 기반 학습)
- ❌ 비용 최적화 알고리즘
- ❌ 멀티 GPU 분산

---

## 2. 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│  React 프론트엔드 (useSSE 훅)                           │
└────────────────────┬────────────────────────────────────┘
                     │ POST /api/onboarding/chat (SSE)
                     ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI Router (backend/routers/onboarding.py)         │
│  ├─ 인증 검증 (Firebase ID Token)                        │
│  ├─ 입력 살균 (sanitize_llm_input)                       │
│  └─ LLMRouter.stream() 호출                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  LLMRouter (core/llm_router.py) ⭐                       │
│  ├─ select_provider(mode, has_image)                     │
│  ├─ check_circuit_breaker()                              │
│  ├─ stream_with_fallback()                               │
│  └─ record_metric()                                      │
└──────┬──────────────────┬──────────────────┬────────────┘
       │ 1순위            │ 2순위             │ 3순위
       ▼                  ▼                   ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
│ Gemini       │  │ Ollama           │  │ LM Studio    │
│ Provider     │  │ Provider         │  │ Provider     │
├──────────────┤  ├──────────────────┤  ├──────────────┤
│ google-genai │  │ httpx + ollama   │  │ httpx (OpenAI│
│              │  │ /api/chat        │  │ 호환 /v1)    │
│ • 2.5 Pro    │  │ • qwen3.5:9b     │  │ • 로컬 GGUF  │
│ • Vision     │  │ • exaone3.5      │  │ (옵션)       │
│ • 빠름       │  │ • gemma4:e2b     │  │              │
│ • 비용 ↑     │  │ • bge-m3         │  │              │
└──────┬───────┘  └────────┬─────────┘  └──────┬───────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
│ Google API   │  │ MacBook localhost│  │ MacBook       │
│ (인터넷)     │  │ :11434           │  │ :1234         │
└──────────────┘  └──────────────────┘  └──────────────┘
```

---

## 3. 프로바이더 능력 매트릭스

각 프로바이더가 잘하는 영역과 한계:

| 능력 | Gemini 2.5 Pro | Ollama (Qwen 3.5) | Ollama (EXAONE) | Ollama (Gemma 4) | LM Studio |
|---|:--:|:--:|:--:|:--:|:--:|
| **속도 (M4 Pro)** | 50~80 tok/s | 30~50 | 35~55 | 40~60 (e2b) | 변수 |
| **첫 토큰 (TTFT)** | 200~400ms | 800~1500ms | 동일 | 동일 | 변수 |
| **한국어 품질** | 🟢 우수 | 🟡 보통 | 🟢 **최고** | 🟡 보통 | 변수 |
| **영어 품질** | 🟢 최고 | 🟢 우수 | 🟡 보통 | 🟢 우수 | 변수 |
| **비전 (이미지)** | ✅ Vision | ❌ | ❌ | ✅ gemma4 | ❌ (대부분) |
| **임베딩** | ❌ (별도 API) | ❌ | ❌ | ❌ | ❌ |
| **컨텍스트 윈도우** | 1M tokens | 128k | 32k | 128k | 변수 |
| **JSON 모드** | ✅ | 🟡 prompt 의존 | 🟡 | 🟡 | 변수 |
| **Function calling** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **인터넷 의존** | 🔴 필수 | ✅ 로컬 | ✅ 로컬 | ✅ 로컬 | ✅ 로컬 |
| **비용** | 유료 (free tier) | 무료 | 무료 | 무료 | 무료 |
| **데이터 외부 노출** | ⚠️ Google 서버 | ✅ 사내 | ✅ 사내 | ✅ 사내 | ✅ 사내 |

### 별도: 임베딩 (RAG용)
| 항목 | bge-m3 (Ollama) |
|---|---|
| 차원 | 1024 |
| 한국어 지원 | 우수 |
| 사용처 | ChromaDB Few-shot RAG / 인원 시맨틱 |
| 라우팅 | **Ollama 단독** (대안 없음, 차원 호환) |

---

## 4. 모드별 라우팅 정책

### 4-1. 모드 정의 (`LLMMode`)

| 모드 | 의미 | 사용 페이지 |
|---|---|---|
| `chat` | 일반 대화 (기본) | C 도우미 |
| `chat_korean` | 한국어 강조 | C 도우미 (한국어 사용자) |
| `vision` | 이미지 + 텍스트 | C 도우미 비전 |
| `draft` | 문서 작성 (긴 응답) | B 문서 작성 |
| `summary` | 요약 (짧은 응답) | A 검색 / D 법규 |
| `intent` | 의도 분류 (단답) | A / C |
| `embedding` | 임베딩 (벡터) | RAG |
| `json` | 구조화 응답 | F 에러 검색 |

### 4-2. 라우팅 매트릭스

> **사용자 정책 갱신 (2026-04-27)**: Gemini **2.5 Pro** + qwen3.5(4b/9b) + gemma4(e2b/e4b) + bge-m3 풀만 사용. EXAONE 제외 — 시연 시 "다양한 오픈 LLM 비교(qwen3.5 vs gemma4)" 강조.

| 모드 | 1순위 | 2순위 | 3순위 |
|---|---|---|---|
| `chat` | **Gemini 2.5 Pro** | Ollama qwen3.5:9b | Ollama gemma4:e4b |
| `chat_korean` | **Gemini 2.5 Pro** | Ollama qwen3.5:9b | Ollama gemma4:e4b |
| `vision` | **Gemini 2.5 Pro Vision** | Ollama gemma4:e4b | — |
| `draft` | **Ollama qwen3.5:9b** (사내 보안 우선) | Ollama gemma4:e4b | Gemini 2.5 Pro |
| `summary` | **Gemini 2.5 Pro** (빠름) | Ollama qwen3.5:4b | Ollama gemma4:e2b |
| `intent` | **로컬 TF-IDF** (5ms) | Gemini 2.5 Pro | — |
| `embedding` | **Ollama bge-m3** | — (대안 없음) | — |
| `json` | **Gemini 2.5 Pro** (JSON 모드 우수) | Ollama qwen3.5:9b | Ollama gemma4:e4b |

### 4-3. 라우팅 결정 로직

```python
def select_provider(mode: LLMMode, has_image: bool, internet_available: bool) -> Provider:
    # 1. 비전이면 Gemini Vision 또는 Gemma 4
    if has_image:
        return GeminiVision if internet_available else OllamaGemma4
    
    # 2. 임베딩은 무조건 Ollama bge-m3
    if mode == 'embedding':
        return OllamaBgeM3
    
    # 3. 한국어 우선 → EXAONE
    if mode == 'chat_korean':
        return OllamaExaone if ollama_healthy else Gemini
    
    # 4. 일반 chat / summary → Gemini 우선
    if mode in ('chat', 'summary', 'json') and internet_available:
        return Gemini
    
    # 5. draft → 한국어 일관성 위해 Ollama
    if mode == 'draft':
        return OllamaQwen35_9b
    
    # 6. fallback
    return OllamaQwen35_9b
```

---

## 5. 폴백 체인 + Circuit Breaker

### 5-1. 폴백 체인 동작

```
요청 → 1순위 시도 → 성공? → 응답
              ↓ 실패
            2순위 시도 → 성공? → 응답
                      ↓ 실패
                    3순위 시도 → 성공? → 응답
                              ↓ 실패
                            에러 반환 (모든 프로바이더 실패)
```

### 5-2. Circuit Breaker 상태

```
[CLOSED] ─── 실패 N회 ───→ [OPEN]
                            │
                  60초 대기  │
                            ↓
[HALF_OPEN] ←─── 1회 시도
   │ 성공
   ▼
[CLOSED]
```

| 상태 | 동작 |
|---|---|
| `CLOSED` | 정상 — 요청 통과 |
| `OPEN` | 차단 — 즉시 다음 프로바이더 폴백 (호출 안 함) |
| `HALF_OPEN` | 1회 시도 — 성공 시 CLOSED, 실패 시 OPEN 유지 |

### 5-3. 실패 판정 기준
| 조건 | 실패 카운트 |
|---|:--:|
| HTTP 5xx | +1 |
| 타임아웃 (30s) | +1 |
| Connection refused | +1 |
| 토큰 한도 초과 (Gemini 429) | **다른 종류** (별도 임계치) |
| 인증 실패 (401) | **즉시 OPEN** (재시도 무의미) |

**임계치**:
- 일반 실패: 3회 → OPEN
- 인증 실패: 1회 → OPEN
- Recovery: 60초 후 HALF_OPEN

---

## 6. SSE 스트리밍 통합

### 6-1. 통일된 토큰 스트림 인터페이스

각 프로바이더 → 공통 `StreamEvent` 타입으로 정규화:

```python
class StreamEvent(TypedDict):
    type: Literal["token", "metadata", "error", "done"]
    content: str | None
    metadata: dict[str, Any] | None
```

### 6-2. SSE 응답 형식 (FastAPI → React useSSE 호환)

```
data: {"type":"metadata","metadata":{"provider":"gemini","model":"gemini-2.5-pro"}}

data: {"type":"token","content":"안녕"}

data: {"type":"token","content":"하세요"}

data: {"type":"done","metadata":{"tokens":234,"latency_ms":1240}}
```

### 6-3. 폴백 시 SSE 처리

폴백 발생 시 클라이언트에 알리지 않음 (UX 부드러움) — 단, metadata에 실제 사용 프로바이더 표기.

```
data: {"type":"metadata","metadata":{"provider":"ollama","fallback_from":"gemini"}}
```

---

## 7. 환경변수 + 설정

### 7-1. `.env` 파일 (백엔드)

```bash
# Gemini API (Google AI Studio 또는 Vertex AI)
GEMINI_API_KEY=AIzaSy...

# Ollama (로컬)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=60

# LM Studio (로컬 OpenAI 호환)
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio        # 임의 토큰 (LM Studio는 검증 안 함)
LM_STUDIO_TIMEOUT=60

# 라우터 설정
LLM_ROUTER_FALLBACK_ENABLED=true
LLM_ROUTER_CIRCUIT_BREAKER_THRESHOLD=3
LLM_ROUTER_CIRCUIT_RECOVERY_SEC=60
LLM_ROUTER_HEALTH_CHECK_TIMEOUT=2

# 메트릭
LLM_METRICS_ENABLED=true
LLM_METRICS_LOG_LEVEL=INFO
```

### 7-2. 모델 매핑 (`config.py`)

```python
# 사용자 정책 (2026-04-27): Gemini 2.5 Pro + qwen3.5(4b/9b) + gemma4(e2b/e4b) + bge-m3
# ollama_alt 는 ollama_primary 실패 시 사용할 보조 모델 (체인 4단계 — Gemini → ollama → ollama_alt → LM Studio)
MODEL_MAP = {
    "chat":         {"gemini": "gemini-2.5-pro", "ollama": "qwen3.5:9b", "ollama_alt": "gemma4:e4b", "lm_studio": "default"},
    "chat_korean":  {"gemini": "gemini-2.5-pro", "ollama": "qwen3.5:9b", "ollama_alt": "gemma4:e4b", "lm_studio": "default"},
    "vision":       {"gemini": "gemini-2.5-pro", "ollama": "gemma4:e4b", "ollama_alt": None,         "lm_studio": None},
    "draft":        {"gemini": "gemini-2.5-pro", "ollama": "qwen3.5:9b", "ollama_alt": "gemma4:e4b", "lm_studio": "default"},
    "summary":      {"gemini": "gemini-2.5-pro", "ollama": "qwen3.5:4b", "ollama_alt": "gemma4:e2b", "lm_studio": "default"},
    "json":         {"gemini": "gemini-2.5-pro", "ollama": "qwen3.5:9b", "ollama_alt": "gemma4:e4b", "lm_studio": None},
    "embedding":    {"gemini": None,             "ollama": "bge-m3",    "ollama_alt": None,         "lm_studio": None},
}
```

> **체인 빌더 주의**: `_build_chain()` 은 모드별 `gemini → ollama_primary → ollama_alt → lm_studio` 순으로 후보를 만들되, `None` 인 항목은 스킵. `draft` 처럼 `ollama` 가 1순위인 모드는 순서를 재배열한다.

---

## 8. 파일 구조

### 8-1. 신규/갱신 파일

```
ajin-ai-assistant-react/
├── core/
│   ├── llm_router.py                    ⭐ 메인 라우터 (250줄)
│   ├── llm_client.py                    (기존 — Ollama 직접 호출, 보존)
│   ├── llm_health.py                    ⭐ Circuit breaker (120줄)
│   ├── llm_metrics.py                   ⭐ 메트릭 (80줄)
│   ├── llm_types.py                     ⭐ 공통 타입 (60줄)
│   └── providers/
│       ├── __init__.py
│       ├── base.py                      ⭐ Provider Protocol (50줄)
│       ├── gemini_provider.py           ⭐ Google Gemini (180줄)
│       ├── ollama_provider.py           ⭐ Ollama (150줄, llm_client 재사용)
│       └── lm_studio_provider.py        ⭐ LM Studio OpenAI 호환 (120줄)
├── backend/
│   └── routers/
│       └── onboarding.py                갱신 — LLMRouter 사용
├── tests/
│   └── test_llm_router.py               ⭐ 단위 테스트 (200줄)
├── requirements.txt                     갱신 — google-genai 추가
└── .env                                  갱신 — API 키
```

### 8-2. 합계 추정
- 신규: **~1,210줄** (8 파일)
- 갱신: 2 파일

---

## 9. API 설계 (인터페이스)

### 9-1. `core/llm_types.py`

```python
from typing import TypedDict, Literal, AsyncIterator
from enum import Enum

class LLMMode(str, Enum):
    CHAT = "chat"
    CHAT_KOREAN = "chat_korean"
    VISION = "vision"
    DRAFT = "draft"
    SUMMARY = "summary"
    INTENT = "intent"
    EMBEDDING = "embedding"
    JSON = "json"

class StreamEvent(TypedDict):
    type: Literal["token", "metadata", "error", "done"]
    content: str | None
    metadata: dict | None

class StreamRequest(TypedDict, total=False):
    prompt: str
    mode: LLMMode
    image_bytes: bytes | None
    history: list[dict]
    max_tokens: int
    temperature: float
```

### 9-2. `core/providers/base.py`

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from core.llm_types import StreamEvent, StreamRequest

class LLMProvider(ABC):
    name: str
    
    @abstractmethod
    async def health_check(self) -> bool: ...
    
    @abstractmethod
    async def stream(self, req: StreamRequest, model: str) -> AsyncIterator[StreamEvent]: ...
    
    @abstractmethod
    async def embed(self, text: str, model: str) -> list[float]: ...
    
    @abstractmethod
    def supports_mode(self, mode: LLMMode) -> bool: ...
```

### 9-3. `core/llm_router.py` (메인)

```python
class LLMRouter:
    def __init__(self):
        self.providers = {
            "gemini": GeminiProvider(),
            "ollama": OllamaProvider(),
            "lm_studio": LMStudioProvider(),
        }
        self.health = HealthRegistry()
        self.metrics = MetricsRecorder()
    
    async def stream(
        self,
        prompt: str,
        mode: LLMMode = LLMMode.CHAT,
        image_bytes: bytes | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamEvent]:
        chain = self._build_chain(mode, has_image=image_bytes is not None)
        for provider, model in chain:
            if not self.health.is_available(provider.name):
                continue
            try:
                yield {"type": "metadata", "content": None, "metadata": {"provider": provider.name, "model": model}}
                async for ev in provider.stream({"prompt": prompt, "mode": mode, "image_bytes": image_bytes, **kwargs}, model=model):
                    yield ev
                self.health.record_success(provider.name)
                return
            except Exception as e:
                self.health.record_failure(provider.name, e)
                self.metrics.record_failure(provider.name, str(e))
                continue
        yield {"type": "error", "content": "모든 LLM 프로바이더가 응답하지 않습니다.", "metadata": None}
    
    async def embed(self, text: str) -> list[float]:
        return await self.providers["ollama"].embed(text, model="bge-m3")
    
    def _build_chain(self, mode: LLMMode, has_image: bool) -> list[tuple[LLMProvider, str]]:
        # 라우팅 매트릭스 (4-2)에 따라 폴백 체인 구성
        ...
```

### 9-4. FastAPI 라우터 통합 (`backend/routers/onboarding.py`)

```python
from core.llm_router import LLMRouter, LLMMode
from sse_starlette.sse import EventSourceResponse

_router = LLMRouter()

@router.post("/chat")
async def chat(req: ChatRequest):
    async def event_stream():
        async for ev in _router.stream(
            prompt=req.query,
            mode=LLMMode.CHAT_KOREAN if req.language == "ko" else LLMMode.CHAT,
            history=req.history,
        ):
            yield {"data": json.dumps(ev)}
    return EventSourceResponse(event_stream())
```

---

## 10. 구현 단계 (3 페이즈)

### Phase 1 — 기본 구조 (1h, 우선순위 1)
- [ ] `core/llm_types.py` 작성 (LLMMode, StreamEvent, StreamRequest)
- [ ] `core/providers/base.py` ABC
- [ ] `core/providers/ollama_provider.py` (기존 llm_client 재사용)
- [ ] `core/providers/gemini_provider.py` (`google-genai` SDK)
- [ ] `core/llm_router.py` 라우팅 + 폴백 (간소화 버전)
- [ ] `.env` 갱신 + `requirements.txt` 갱신

### Phase 2 — 안정성 (45min, 우선순위 2)
- [ ] `core/llm_health.py` Circuit breaker
- [ ] `core/providers/lm_studio_provider.py` (OpenAI 호환)
- [ ] `core/llm_metrics.py` 메트릭 수집
- [ ] FastAPI 통합 (`backend/routers/onboarding.py` 갱신)
- [ ] SSE EventSourceResponse 통합

### Phase 3 — 검증 (45min, 우선순위 3)
- [ ] `tests/test_llm_router.py` 단위 테스트 (각 프로바이더 mock)
- [ ] 통합 테스트 — 실제 Ollama 호출
- [ ] 폴백 시나리오 — Gemini 실패 → Ollama 자동 전환
- [ ] 비전 시나리오 — 이미지 입력
- [ ] 한국어 vs 영어 자동 라우팅
- [ ] 임베딩 호출 검증

---

## 11. 테스트 전략

### 11-1. 단위 테스트 (mock 기반)

```python
@pytest.fixture
def mock_router():
    router = LLMRouter()
    router.providers["gemini"] = MockGemini(fail=False)
    router.providers["ollama"] = MockOllama(fail=False)
    return router

@pytest.mark.asyncio
async def test_basic_chat(mock_router):
    events = [ev async for ev in mock_router.stream("hello", LLMMode.CHAT)]
    assert events[0]["metadata"]["provider"] == "gemini"
    assert any(ev["type"] == "token" for ev in events)

@pytest.mark.asyncio
async def test_fallback_to_ollama(mock_router):
    mock_router.providers["gemini"] = MockGemini(fail=True)
    events = [ev async for ev in mock_router.stream("hello", LLMMode.CHAT)]
    assert events[0]["metadata"]["provider"] == "ollama"

@pytest.mark.asyncio
async def test_korean_mode_uses_exaone(mock_router):
    events = [ev async for ev in mock_router.stream("안녕", LLMMode.CHAT_KOREAN)]
    assert events[0]["metadata"]["model"] == "exaone3.5"
```

### 11-2. 통합 테스트 시나리오 (실제 호출)

| # | 시나리오 | 기대 결과 |
|:--:|---|---|
| 1 | Gemini 정상 호출 | gemini-2.5-pro 응답 |
| 2 | Gemini API 키 무효 → 자동 Ollama 폴백 | qwen3.5:9b 응답 |
| 3 | Ollama 종료 → Gemini만 응답 | gemini 응답 |
| 4 | Ollama + Gemini 모두 다운 → LM Studio | LM Studio 응답 또는 에러 |
| 5 | 한국어 입력 → exaone3.5 우선 | exaone3.5 응답 |
| 6 | 비전 이미지 입력 → Gemini Vision | 이미지 분석 응답 |
| 7 | 임베딩 호출 → bge-m3 | 1024차원 벡터 |
| 8 | Circuit breaker — 3회 실패 후 OPEN | 4번째 호출 시 즉시 폴백 |
| 9 | 60초 후 HALF_OPEN 복구 | 1회 시도 |
| 10 | SSE 토큰 단위 스트리밍 | 클라이언트가 토큰 수신 |

---

## 12. 검증 체크리스트

Phase 3 마감 시 모두 ✓ 처리:

- [ ] **Phase 1**: 기본 라우터 + Gemini + Ollama 동작
- [ ] **Phase 2**: Circuit breaker + LM Studio + 메트릭
- [ ] **Phase 3**: 단위 테스트 10/10 통과
- [ ] `python -c "from core.llm_router import LLMRouter; r = LLMRouter()"` 정상
- [ ] `curl POST /api/onboarding/chat` SSE 응답 검증
- [ ] Gemini 강제 실패 시 Ollama 폴백 자동 수행
- [ ] 한국어 입력 시 EXAONE 라우팅
- [ ] 비전 모드 + Gemini Vision 동작
- [ ] 임베딩 차원 1024 검증
- [ ] 메트릭 로그 파일 생성 (`logs/llm_metrics.log`)
- [ ] FastAPI Swagger `/docs` 에서 chat 엔드포인트 확인

---

## 13. 위험 요소 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | **Gemini API 키 미발급** | 🔴 | 사용자 발급 필요 (5분 — Google AI Studio) |
| 2 | **google-genai SDK API 변경** | 🟡 | 버전 핀 (`google-genai==0.5.0` 등) |
| 3 | **Ollama 모델 메모리 부족** (M4 Pro 24GB) | 🟡 | Configuration A 준수, gemma4:26b/nemotron 사용 금지 |
| 4 | **SSE 스트리밍 끊김** (Cloudflare Tunnel) | 🟡 | nginx-style timeout 600s, keepalive |
| 5 | **JSON 모드 Ollama 미지원** | 🟢 | prompt에 "JSON only" 강제 + parse 실패 시 재시도 |
| 6 | **임베딩 차원 불일치** | 🟢 | bge-m3 단독 사용 (Gemini 임베딩 차단) |
| 7 | **LM Studio 미실행 시 connection refused** | 🟢 | 정상 — 폴백 체인이 처리 |
| 8 | **Circuit breaker 잘못 OPEN** | 🟡 | 임계치 신중 (3회 / 60초) + 수동 reset 명령 |
| 9 | **테스트 시 실제 API 비용** | 🟡 | mock 우선, 실제 호출은 통합 테스트 한 번만 |
| 10 | **메트릭 로그 디스크 폭발** | 🟢 | rotating file handler (10MB × 5 백업) |

---

## 14. 의존성 추가

### 14-1. `requirements.txt` 추가 항목

```
# Gemini SDK (Google GenAI)
google-genai>=0.5.0

# SSE for FastAPI
sse-starlette>=2.0.0

# Async HTTP (이미 있을 수 있음)
httpx>=0.27.0

# JSON streaming
ijson>=3.2.3                  # 옵션 (Gemini stream JSON parsing)
```

### 14-2. 이미 존재하는 의존성
- `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `httpx` ✓
- `langchain-ollama`, `chromadb` ✓ (기존 llm_client.py)

### 14-3. Gemini API 키 발급 안내

**옵션 A**: Google AI Studio (무료 tier 강함, 권장)
1. https://aistudio.google.com/app/apikey
2. "Create API key" → 새 프로젝트 또는 기존 프로젝트
3. 발급된 키 → `.env` 의 `GEMINI_API_KEY=AIzaSy...`
4. 무료 tier: gemini-2.5-pro 60 req/min, gemini-1.5-flash 1500 req/day

**옵션 B**: Vertex AI (프로덕션, 결제 필요)
- Google Cloud Console → Vertex AI 활성화
- 서비스 계정 키 (JSON)
- 본 계획은 Option A로 진행 권장 (본선 데모용)

---

## 15. 다음 단계 — 시작 가능

### 즉시 시작 가능한 첫 작업
```bash
# 1. requirements.txt 갱신 + 설치
cd ajin-ai-assistant-react
pip install google-genai sse-starlette

# 2. Gemini API 키 발급 + .env 갱신
# https://aistudio.google.com/app/apikey

# 3. Phase 1 구현 시작 (~1h)
```

### 사용자 결정 필요
| # | 결정 | 옵션 |
|:--:|---|---|
| 1 | **Gemini API 키 발급** | Google AI Studio (무료 권장) vs Vertex AI |
| 2 | **LM Studio 사용 여부** | 본선 데모만 vs 운영도 / Phase 2에 포함 |
| 3 | **임베딩 모델 추가 옵션** | bge-m3만 (현재) vs Gemini text-embedding-004 추가 |
| 4 | **로깅 라이브러리** | 표준 logging vs structlog (구조화) |
| 5 | **SSE 라이브러리** | sse-starlette vs FastAPI 직접 (현재 backend/sse.py 활용) |

권장 디폴트: AI Studio 무료 / LM Studio 포함 / bge-m3만 / 표준 logging / sse-starlette

---

## 16. 시간 분배표 (총 2~2.5h)

| 시간대 | 작업 |
|:--:|---|
| 00:00 ~ 00:15 | 의존성 설치 + Gemini API 키 발급 |
| 00:15 ~ 00:35 | Phase 1-1 — `llm_types.py` + `providers/base.py` |
| 00:35 ~ 01:00 | Phase 1-2 — `ollama_provider.py` + `gemini_provider.py` |
| 01:00 ~ 01:15 | Phase 1-3 — `llm_router.py` 기본 라우팅 |
| 01:15 ~ 01:30 | 휴식 + 1차 검증 (Ollama + Gemini 정상 호출) |
| 01:30 ~ 01:50 | Phase 2-1 — `llm_health.py` Circuit breaker |
| 01:50 ~ 02:05 | Phase 2-2 — `lm_studio_provider.py` + `llm_metrics.py` |
| 02:05 ~ 02:15 | Phase 2-3 — FastAPI 통합 |
| 02:15 ~ 02:30 | Phase 3 — 통합 테스트 + 검증 체크리스트 |

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — 16 섹션 / 8 신규 파일 / 3 페이즈 / 10 테스트 시나리오 |

---

**관련 문서**:
- [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md) — 17일 통합 일정
- [DAY3_PLAN.md](DAY3_PLAN.md) — Day 3 (어제) — useSSE 훅 작성
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — 디자인 사양
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — 기능 C 사양
