# Lemon-Aid (레몬에이드) — 만성질환자 중심 AI 헬스케어 플랫폼

> 영양제 라벨 OCR·음식 사진 분석·의료 지식 RAG 챗봇을 한 서비스로 묶어, 만성질환자의 **일상 영양·복약 관리**를 돕는 AI 헬스케어 플랫폼입니다.
> 전체 소스는 [`Lemon-Aid/`](./Lemon-Aid) 에 있습니다 (FastAPI 백엔드 · Flutter 모바일 · 학습/평가 파이프라인).

---

## 프로젝트 개요

- **목표**: 영양제·식단 사진 한 장으로 성분/영양을 자동 분석하고, 사용자의 만성질환·복약 맥락을 반영해 **안전한** 영양 정보를 제공.
- **대상**: 당뇨·고혈압·이상지질혈증 등 만성질환을 관리하는 일반 사용자.
- **핵심 원칙**: 의료법 준수(진단·처방 대체 금지), 개인정보 최소수집, 모든 AI 응답에 안전 고지·전문가 상담 권유.

---

## 핵심 결과

### 1. 영양제 OCR · AI 분석
- CLOVA / PaddleOCR + Gemma 레이아웃 파싱으로 영양제 라벨에서 **성분·함량**을 추출.
- 멀티이미지(앞·뒤·성분표)를 **단일 제품으로 융합**해 한 번의 분석 결과 제공.
- 성분명 영문→한국어 현지화, 섭취/주의사항 번역, 노이즈(기준치·단위 등) 필터링.

### 2. 음식 / 식단 분석
- YOLO 음식 게이트 → **CLIP 비음식 필터**(사람·식기·소품 컷, 프로덕션 ON·startup warm-up) → DINOv3 40종 분류 → 100g 기준 영양 매핑.
- 동기 추론을 이벤트 루프에서 분리(`anyio.to_thread`)하고 분류기를 프로세스 단위로 공유해 요청당 모델 재로드를 제거.

### 3. AI 챗봇 (LLM-WIKI RAG)
- 검수된 의료 위키를 **pgvector RAG**(bge-m3 임베딩 + Gemma 합성)로 검색해 **출처를 인용**하는 답변 생성.
- 오케스트레이션: 민감정보 동의 게이트 → 검수 출처 governance 게이트(미준비 시 fail-closed) → 사용자 건강 맥락 로딩 → 1차 에이전트 → 미해결 시 위키 RAG 폴백.
- **안전 스크린**: 약물 변경 지시·응급 신호는 LLM을 호출하지 않고 전문가/응급 안내로 우회. 건강과 무관한 질문은 최소 응답으로 거절.

### 4. 영양 계산 (KDRIs 2025)
- 보건복지부 **2025 한국인 영양섭취기준** 적용. 연령·성별·임신 상태별 권장량/상한 조회.
- 5-card 종합 분석(부족·과다·주의·목적별·점수)과 만성질환 기반 영양소 우선순위 추천.

### 5. 프라이버시 · 보안
- PostgreSQL **Row-Level Security** 요청롤 전환, 요청 단위 GUC 트랜잭션, 권한 분리된 감사/학습 엔진.
- 민감 건강정보 동의 게이트, 원문 OCR 텍스트 저장의 별도 동의 게이팅, 비밀정보 스캔(detect-secrets) CI.

---

## 아키텍처 · 기술 스택

| 영역 | 기술 |
|---|---|
| 백엔드 | FastAPI, SQLAlchemy, Alembic, Pydantic v2 |
| 데이터 | PostgreSQL(pgvector), Redis |
| 비전/OCR | CLOVA OCR, PaddleOCR, YOLO, DINOv3, CLIP (HuggingFace transformers) |
| LLM | Ollama / Gemma (+ SGLang 호환) |
| 모바일 | Flutter (Riverpod, go_router, Dio) |
| 인프라 | Docker Compose, GitHub Actions CI (lint · test · security · docker build) |

---

## 엔지니어링 하이라이트

- **RLS 멀티스테이지 마이그레이션**: 전 owner 라우트를 요청롤 RLS seam으로 전환하고 `lemon_app` 비특권 롤로 안전하게 컷오버. 라우트-시밍 회귀 가드 테스트로 고정.
- **결정적 CI**: black/ruff·fastapi 버전 핀으로 환경 드리프트 제거, detect-secrets baseline 정비. 전체 백엔드 단위 테스트 2,400+ 통과.
- **안전 우선 챗봇**: governance fail-closed + tiered RAG + 약물변경 안전 스크린을 통합 테스트로 검증.
- **운영 안정화**: 모델 startup warm-up, gemma keep-alive, per-stage 타임아웃 예산으로 모바일 타임아웃 대응.

---

## 면책 고지

본 프로젝트가 제공하는 정보는 일반적인 건강 관리를 위한 **참고 자료**이며, 의사·약사·영양사의 전문적 진단이나 처방을 대체하지 않습니다. 복약·치료 판단은 반드시 의료진과 상담하세요.
