# Lemon-note — 로컬 우선 AI 회의록 (녹음 · 화자구분 전사 · 요약 · 공유)

> 회의를 녹음하거나 업로드하면 **화자별 전사 → 구조화 요약(결정·할 일·일정 후보) → 검토·수정 → 내보내기·Slack 공유**까지 한 흐름으로 처리하는 회의록 도구.
> **비용 0 로컬 우선**으로 설계 — 스마트폰/웹은 녹음·UI만, AI 처리는 사용자의 Mac 로컬 Worker에서 실행하고, 서버 준비 시 API·스키마를 유지한 채 서버로 이전한다.

![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)
![ASR](https://img.shields.io/badge/ASR-faster--whisper%20(medium%2Flarge--v3)-FF6B6B)
![Diarization](https://img.shields.io/badge/Diarization-sherpa--onnx%20(open)-6BA539)
![LLM](https://img.shields.io/badge/LLM-Ollama%20gemma4%3Ae4b%20%7C%20qwen3.5-7C3AED)
![DB](https://img.shields.io/badge/DB-SQLite%20%7C%20Supabase%20Postgres-3ECF8E)
![Frontend](https://img.shields.io/badge/Frontend-Vanilla%20JS%20(no%20build)-F7DF1E)
![Cost](https://img.shields.io/badge/Runtime%20Cost-%240-000000)

> 📦 **성격** — 자기주도 설계·구현. 요구사항 분석 → 설계 문서화 → 다차원 설계 리뷰 → 데모 MVP → 실제 로컬 모델 전환까지 단독으로 진행.

---

## 한 줄 요약

**"금전 비용 0으로, 어떤 Mac에서도 즉시 도는 화자구분 AI 회의록 — 녹음 완료 후 로컬에서 전사·요약하고, 발화를 클릭하면 그 지점부터 재생되며, 요약·일정은 사람이 검토·수정한다."**

핵심은 **Provider 추상화**다. 전사·요약·저장·화자구분을 인터페이스 뒤로 숨겨, `stub ↔ 실제 모델`과 `로컬(Mac) ↔ 서버(GPU)`를 **API·DB 스키마 변경 없이** 교체한다.

---

## 시스템 개요

```
 Web / 모바일 녹음 클라이언트 (Vanilla JS, MediaRecorder)
        │  POST /v1/jobs (multipart: audio + 메타 + 녹음동의)
        ▼
 ┌─────────────────────────── Mac 로컬 Worker (FastAPI) ───────────────────────────┐
 │  Job Pipeline:  uploaded → normalizing → transcribing → summarizing → ready     │
 │                                                                                 │
 │   TranscriptionProvider   ── stub | faster-whisper(+sherpa/pyannote 화자구분)    │
 │   SummaryProvider         ── stub | Ollama(gemma4:e4b / qwen3.5 / qwen2.5)      │
 │   StorageProvider         ── LocalFiles | (Supabase Storage)                    │
 │   Diarization             ── sherpa-onnx(오픈) | pyannote(HF 토큰)               │
 └─────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
 DB: SQLite(로컬 기본) │ Supabase Postgres(서버, DB_BACKEND=postgres)  +  로컬/Storage 파일
        │
        ▼
 앱: 회의 목록 · 상세(오디오 플레이어) · 발화 클릭 재생 · 화자별 말풍선 전사 ·
     요약/결정/할일/일정 편집 · MD/TXT 내보내기 · Slack Webhook 공유
```

상태값은 API·DB·UI가 동일 문자열을 공유한다: `uploaded → normalizing_audio → transcribing → summarizing → ready_for_review` (실패 시 `failed`).

---

## 핵심 기능

- **녹음/업로드** — 브라우저 `MediaRecorder`(시작/일시정지/재개/정지·레벨미터) + 파일 업로드 fallback, 녹음 동의 저장, ASR 힌트(hotwords).
- **화자구분 전사** — faster-whisper 전사 + sherpa-onnx(오픈 모델, HF 토큰 불필요) 화자 분리. 발화를 클릭하면 오디오가 해당 `start_ms`부터 재생되고 현재 발화가 하이라이트된다(Range 스트리밍).
- **구조화 요약** — 로컬 LLM이 `요약 / 결정사항 / 할 일(담당·마감) / 일정 후보(신뢰도·근거 발화)`를 JSON으로 생성. 원본 전사·음성은 보존하고 사용자가 요약본만 별도 버전으로 수정.
- **내보내기·공유** — Markdown/TXT 내보내기, Slack Incoming Webhook 공유(전송 전 미리보기·로그).
- **원본 불변성 / 감사 로그 / soft-delete / 녹음 동의** 등 보안·보존 정책 반영.

---

## 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| Worker | Python · **FastAPI** · Uvicorn | 단일 프로세스 background task 파이프라인 |
| ASR | **faster-whisper** (small/medium/large-v3) | PyAV 디코딩 → ffmpeg 불필요. Mac CPU int8 |
| 화자구분 | **sherpa-onnx**(오픈) / pyannote(옵션) | 토큰 없이 동작하는 오픈 모델 기본 |
| 요약 LLM | **Ollama** gemma4:e4b(기본) / qwen3.5 / qwen2.5 | 추론모델 `<think>` 제거 + JSON 추출 견고화 |
| DB | **SQLite**(로컬 기본) / **Supabase Postgres**(서버) | `DB_BACKEND` 듀얼 백엔드, native 타입 |
| 저장 | 로컬 파일 / Supabase Storage | `/users/{id}/meetings/{id}/...` |
| Frontend | **Vanilla HTML/CSS/JS** (빌드·CDN 없음) | 오프라인 동작, Figma 디자인 기반 |

**검증(Apple M4 Pro / 24GB):** 48초 한국어 음성 → 전사 medium ≈19s(오탈자 거의 없음) + gemma4:e4b 요약 ≈10s(담당자 추출 정확). 전체 파이프라인 ≈31s.

---

## 미리보기 · 배포 (Vercel, 무료)

프론트엔드(`local-worker/web/`)는 **빌드 없는 정적 파일 + 해시 라우팅**이라 Vercel Hobby(무료)로 그대로 배포된다.

- Vercel → Add New Project → 이 레포 Import → **Root Directory = `05_lemon-note/local-worker/web`**, Framework Preset = **Other**(빌드/설치 명령 없음) → Deploy
- 첫 화면(녹음 UI)은 브라우저에서 바로 동작한다. 목록/달력 등 백엔드 호출은 정적 배포엔 서버가 없어 비활성이다(04_AJIN 정적 화면과 동일 방식).
- **AI 전사·요약은 로컬 모델(faster-whisper·Ollama)** 이라 Vercel에서 돌리지 않는다 → 요금이 발생하지 않는다. 완전 동작은 로컬 `./run.sh`.

## 실행

```bash
cd local-worker
./run.sh                        # ① stub 모드 — 즉시, 모델 다운로드 0

# ② 실제 로컬 모델 (여전히 무료)
#   pip install faster-whisper ; ollama pull gemma4:e4b
ASR_PROVIDER=faster_whisper SUMMARY_PROVIDER=ollama STUB_STAGE_DELAY=0 ./run.sh
```
→ 브라우저 <http://localhost:8710>. 자세한 설정·모델·화자구분·Supabase 연결은 [`local-worker/README.md`](local-worker/README.md) 참고.

---

## 설계 산출물

- [`meeting-recorder-implementation-plan.md`](meeting-recorder-implementation-plan.md) — 마스터 기획서
- [`docs/`](docs/) — 기능별 구현 문서 · API 스펙 · DB 스키마 · MVP 작업분해 · 로컬 Worker 구조
- [`docs/design-review-findings.md`](docs/design-review-findings.md) — 다차원 설계 리뷰(20개 이슈, 스키마-API 불일치·설계 결함·누락) 및 반영 결과

---

## 보안 · 비밀값 관리

API 키·토큰·DB 비밀번호 등 **비밀값은 절대 커밋하지 않는다.** 실제 값은 로컬 `local-worker/.env`(`.gitignore` 처리)에만 두고, 저장소에는 값이 없는 `local-worker/.env.example` 템플릿만 커밋한다. Supabase publishable(anon) 키·URL은 공개용이라 예시에 포함될 수 있으나, `service_role` 키와 `DATABASE_URL`(비밀번호 포함)은 본인만 로컬 `.env`에 입력한다.
