# AJIN AI Assistant — React 마이그레이션 종합 계획서

> **버전**: 1.0
> **작성일**: 2026-04-27
> **컨텍스트**: 제3회 KNU SILLI 경진대회 본선 진출 — Streamlit (v3.5) → React 전환
> **목적**: `uiux/AJIN AI Assistant Design System` 분석 결과를 바탕으로, [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) 의 6대 기능 구현 가능성을 평가하고, 본선 데모까지의 우선순위·로드맵·위험 요소를 정리

---

## 목차

1. [디자인 시스템 분석 결과](#1-디자인-시스템-분석-결과)
2. [기능별 갭 분석 (6대 기능)](#2-기능별-갭-분석-6대-기능)
3. [구현 가능성 종합 평가](#3-구현-가능성-종합-평가)
4. [React 기술 스택 제안](#4-react-기술-스택-제안)
5. [백엔드 API 갭 분석](#5-백엔드-api-갭-분석)
6. [Phase별 마이그레이션 로드맵](#6-phase별-마이그레이션-로드맵)
7. [우선순위 큐 (본선 데모 기준)](#7-우선순위-큐-본선-데모-기준)
8. [위험 요소 + 완화 방안](#8-위험-요소--완화-방안)
9. [다음 단계 지시](#9-다음-단계-지시)

---

## 1. 디자인 시스템 분석 결과

### 1-1. 디자인 시스템 자산 인벤토리

| 항목 | 위치 | 규모 | 상태 |
|---|---|:--:|:--:|
| **디자인 가이드** | [README.md](../../uiux/AJIN AI Assistant Design System/README.md) | ~200줄 | ✅ 완성 |
| **에이전트 스킬** | [SKILL.md](../../uiux/AJIN AI Assistant Design System/SKILL.md) | ~25줄 | ✅ 완성 |
| **디자인 토큰** | [colors_and_type.css](../../uiux/AJIN AI Assistant Design System/colors_and_type.css) | 246줄 | ✅ 완성 |
| **Web 앱 테마** | [ui_kits/web_app/theme.css](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/theme.css) | **1,844줄** | ✅ 완성 |
| **React 컴포넌트** | `ui_kits/web_app/*.jsx` | **2,132줄** (12개) | ✅ 완성 |
| **모바일 UI 키트** | `ui_kits/mobile/` | 다수 | ✅ 완성 |
| **로고 자산** | `assets/` | 5종 SVG/PNG | ✅ 완성 |
| **AJIN Sans 폰트** | `fonts/` | **8 weights** OTF/TTF | ✅ 완성 |
| **미리보기 페이지** | `preview/` | **17개 HTML** | ✅ 완성 |
| **스크린샷** | `screenshots/` | **15+ PNG** (light/dark/mobile) | ✅ 완성 |

### 1-2. 주요 디자인 변경점 (vs 기존 Streamlit v3.5)

| 영역 | Streamlit v3.5 | 새 디자인 시스템 | 영향 |
|---|---|---|:--:|
| **Primary Gold (Light)** | `#C88A00` | **`#D89400`** | 🟡 톤 미세 조정 |
| **Primary Gold (Dark)** | `#F9A70D` | **`#FCB132`** | 🟡 톤 미세 조정 |
| **베이스 폰트** | Pretendard | **AJIN Sans** (자체 폰트, 8 weights) | 🟢 대폭 개선 |
| **매테리얼** | 플랫 | **Apple Liquid Glass** (top bar, right panel, modals, chat composer) | 🟢 신규 |
| **Tahoe 라디우스** | 2px 일률 | 2px (HUD) **+ 10/14/20/24px** (chrome/cards/window/shell) | 🟢 신규 |
| **Glass 토큰** | 없음 | `--glass-bg/border/highlight/shadow/blur/saturate` | 🟢 신규 |
| **로고** | 임시 SVG 2종 | **공식 5종** (light/dark/official/symbol/mark) | 🟢 신규 |
| **상태 글리프** | `●` `○` | `●` `○` `▣` `▢` `─ ─ ─` (확장) | 🟢 강화 |

### 1-3. 디자인 시스템 핵심 규칙 (Hard Rules from SKILL.md)

| # | 규칙 | 의미 |
|:--:|---|---|
| 1 | **이모지 금지** | 상태는 `●` `○` 글리프 + 색상으로만 |
| 2 | **영문 대문자 + 한글 부제** 모든 주요 섹션에 짝 | `CORE MODULES (핵심 모듈)` |
| 3 | **모서리 2px** | 8px/12px round 절대 금지 |
| 4 | **골드는 CTA·활성·핵심 메트릭에만** | 장식용 절대 금지 |
| 5 | **Liquid Glass 4영역 한정** | top bar / right panel / modals / chat composer |
| 6 | **한국어 우선, 영어는 구조적 라벨** | 본문은 한국어, 영문은 컨텍스트 |

### 1-4. UI 키트 컴포넌트 매트릭스

| 파일 | 역할 | 라인 | 기능 매핑 |
|---|---|:--:|:--:|
| [Login.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Login.jsx) | 로그인 + 비번 정책 체크리스트 | 39 | 인증 |
| [TopBar.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/TopBar.jsx) | 52px sticky Liquid Glass 상태바 | 19 | 공통 |
| [LeftSidebar.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/LeftSidebar.jsx) | 로고/유저/모듈/등록/보안 로그 | 83 | 공통 |
| [RightPanel.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/RightPanel.jsx) | GPU 게이지/지연/QPS/수집 | 37 | 공통 |
| [Dashboard.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Dashboard.jsx) | 4 메트릭 + 6 모듈 카드 | 47 | 대시보드 |
| [Search.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Search.jsx) | 6 본부 + 19 팀 + 24명 + 6필터 | **249** | **A** |
| [Draft.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Draft.jsx) | 3탭 + 어조/유형 + diff + CC | **188** | **B** |
| [Chat.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Chat.jsx) | 듀얼 모드 + SOP 단계 + 부서 자동 | **261** | **C** |
| [Compliance.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Compliance.jsx) | 4탭 + 관세 슬라이더 + 시나리오 | **332** | **D** |
| [Admin.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Admin.jsx) | 6탭 + 보안/분석/통계 | **377** | **E** |
| [Equipment.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Equipment.jsx) | OVERVIEW 5하위탭 + ML + SPC | **460** | **F** |
| [Icons.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Icons.jsx) | 인라인 아이콘 (Lucide CDN 대체) | 40 | 공통 |
| **합계** | **12 컴포넌트** | **2,132** | |

### 1-5. 디자인 시스템 종합 평가

**강점**:
- ✅ **완성도 높은 React 컴포넌트** — 6대 기능 모두 페이지 골격 존재 (Streamlit 12,679줄을 React 2,132줄로 압축한 우수한 추상화)
- ✅ **자체 폰트 패밀리** "AJIN Sans" 100~800 8 weights — 브랜드 정체성 확립
- ✅ **Apple Liquid Glass 매테리얼** 적용 영역 명시 — 최신 디자인 트렌드 반영
- ✅ **이중 라이트/다크 + 글래스 토큰** — 모든 디자인 변수가 CSS 변수로 깔끔
- ✅ **영문 + 한글 병기 패턴** 일관 적용
- ✅ **Hard Rules** 명시 — 디자이너 의도 흐트러짐 방지

**한계**:
- ⚠️ **Babel standalone 기반 데모 코드** — 프로덕션 React가 아닌 브라우저 즉시 컴파일 (성능·번들·TS 미지원)
- ⚠️ **차트 라이브러리 미통합** — Plotly/Chart.js/Recharts 어느 것도 import 없음
- ⚠️ **API/네트워크 코드 없음** — 모든 데이터가 컴포넌트 내부 mock
- ⚠️ **상태관리 없음** — props drilling만 (`active`, `theme`, `streaming`)
- ⚠️ **라우팅 없음** — `active === 'dashboard'` switch 패턴 (URL 동기화 X)
- ⚠️ **국제화/i18n 없음** — 한국어 하드코딩
- ⚠️ **폼 검증 없음** — react-hook-form 등 미적용

> **결론**: 디자인 시스템은 **시각적 사양으로는 95% 완성**되어 있으며, React 프로덕션 앱으로 만들기 위한 **인프라(빌드/라우팅/상태/통신)는 0%**.

---

## 2. 기능별 갭 분석 (6대 기능)

각 기능을 **[FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md)** 사양 vs **UI 키트 구현** 으로 대조한 매트릭스입니다.

### 2-1. 기능 A: 인원 검색

| Spec 항목 | UI 키트 (Search.jsx) | 갭 |
|---|:--:|---|
| 시맨틱 하이브리드 검색 (FTS5+ChromaDB+RRF) | ❌ 단순 substring | API 연결 |
| ML 의도 분류 5ms (TF-IDF+LR) | ❌ | 응답 메타 표시 |
| 검색 이력 + 5종 정렬 | ❌ | 칩 + Select 추가 |
| FTS5 전문 검색 | ❌ | API 연결 |
| Text-to-SQL | ❌ | 입력 패널 추가 |
| 가시성 3-Tier 마스킹 | ❌ | 이메일 `***@***` 렌더링 |
| HTML 카드형 조직도 | ✅ **인터랙티브 6 본부 + 19 팀** | — |
| 사업장 지도 (Folium) | ❌ Plant 텍스트만 | react-leaflet 통합 |
| 교차 네비 (이메일/문서) | ❌ | 카드 액션 버튼 추가 |
| 부서 별칭 48종 매칭 | ❌ | API 연결 |

**완성도**: **40% (UI) / 0% (API)** → 종합 **20%**
**핵심 추가 작업**: API 연결, 5종 정렬, 검색 이력 칩, 가시성 마스킹, react-leaflet 지도, 교차 네비

---

### 2-2. 기능 B: 문서 작성

| Spec 항목 | UI 키트 (Draft.jsx) | 갭 |
|---|:--:|---|
| 3탭 (내부/외부/이력) | ✅ `tab: internal` | 이력 탭 콘텐츠 |
| 어조 + 문서유형 셀렉터 | ✅ | — |
| Few-shot RAG (ChromaDB) | ❌ | API 연결 |
| 문서 유형 13종 | 🟡 PPAP만 표시 | 셀렉트 옵션 추가 |
| 가중치 BM25 검색 | ❌ | API 연결 |
| 품질 평가 5기준 100점 | 🟡 `lg-conf` 카드 | 5기준 분해 표시 |
| 버전 비교 diff (HTML 하이라이트) | ✅ `lg-diff-line add/del` | — |
| CC 자동 추천 (필수/권장/선택) | ✅ `lg-cc-chips` 3색 | — |
| 양식 카탈로그 11종 | ❌ | 새 탭 또는 모달 |
| 7포맷 다운로드 | 🟡 일부 | 7개 버튼 모두 + 핸들러 |
| 마크다운 → CSV/XLSX 변환 | ❌ | 백엔드 호출 |
| Jinja2 매핑 (8D/ECN/회의록) | ❌ | API 연결 |
| SSE 스트리밍 (실시간 토큰) | 🟡 시뮬레이션 | 실제 SSE |

**완성도**: **70% (UI) / 0% (API)** → 종합 **35%**
**핵심 추가 작업**: SSE 클라이언트, 7포맷 핸들러, 13종 문서유형, 양식 카탈로그, 이력 탭

---

### 2-3. 기능 C: AI 업무 도우미

| Spec 항목 | UI 키트 (Chat.jsx) | 갭 |
|---|:--:|---|
| SSE 실시간 스트리밍 | 🟡 `streaming` 상태 | 실제 EventSource |
| 듀얼 모드 (교육/업무) | ✅ `mode: 교육/업무` | — |
| 부서 자동 선택 | ✅ `dept: 생산기술팀` | 토큰 기반 자동 |
| SOP 8종 단계별 | ✅ `view: sop, sopStep` | API + 콘텐츠 |
| 협업 시나리오 5종 | ❌ | 트리거 + UI |
| 업무 액션 라우터 | ❌ | 의도 분류 + 액션 |
| 컨텍스트 최적화 (모드별 토큰 예산) | ❌ | API 측 |
| 대화 요약 메모리 | ❌ | 메모리 박스 |
| 비전 모델 (Gemma 4 이미지) | ❌ | 이미지 업로드 |
| 파일 업로드 20+ 확장자 | ❌ | 📎 버튼 + 파서 |
| 다운로드 영구화 (4포맷) | ❌ | 버튼 + 영구 저장 |
| 피드백 이모지 (👍/👎) | ❌ | 버튼 + DB |
| 용어집 297항목 자동 주입 | ❌ | API 측 |
| 빠른 질문 데모 6개 | ✅ `quick-card` | — |
| ML 의도 분류 5ms | ❌ | API 측 |

**완성도**: **55% (UI) / 0% (API)** → 종합 **27%**
**핵심 추가 작업**: 실제 SSE, 비전·파일·다운로드, 협업 시나리오, 메모리 박스, 피드백

---

### 2-4. 기능 D: 법규 모니터링

| Spec 항목 | UI 키트 (Compliance.jsx) | 갭 |
|---|:--:|---|
| 4탭 구조 (모니터/업데이트/사업장/문서) | ✅ `tab: updates` | — |
| 9종 크롤러 | ❌ | 크롤러 테이블 + 실행 버튼 |
| 리스크 스코어링 (40+30+30=100) | 🟡 점수 표시 | 분해 차트 |
| 데모 시나리오 3종 | 🟡 카드 표시 | 시뮬레이션 액션 |
| 데드라인 타임라인 (Plotly Gantt) | ❌ | Plotly 통합 |
| 관세 시뮬레이터 슬라이더 | ✅ `tariff: 25` | 6품목 차트 |
| 변경 자동 감지 + CSV 내보내기 | ❌ | 백엔드 + 다운로드 |
| 영향 네트워크 (Plotly Network) | ❌ | Plotly 통합 |
| AI 리스크 분류 (TF-IDF+RF) | ❌ | API |
| 사업장 지도 (Folium 19개소) | ❌ | react-leaflet |
| 부서 기반 접근 제어 (7개) | ❌ | RBAC 가드 |

**완성도**: **40% (UI) / 0% (API)** → 종합 **20%**
**핵심 추가 작업**: Plotly Gantt/Network, 슬라이더 → Plotly Bar, react-leaflet, 9 크롤러 패널

---

### 2-5. 기능 E: 인사 관리

| Spec 항목 | UI 키트 (Admin.jsx) | 갭 |
|---|:--:|---|
| 6탭 구조 (Tier 4) / 4탭 (Tier 3) | ✅ `tab: security` | RBAC 분기 |
| RBAC 6단계 + 28권한 | ❌ | 권한 매트릭스 UI |
| JWT + bcrypt 인증 | ❌ | 토큰 갱신 로직 |
| 비밀번호 정책 6조건 | 🟡 Login에 일부 | 실시간 강도 표시 |
| 보안 감사 3종 (무차별/야간/비활성) | 🟡 보안 탭 카드 | 감지 로직 + 알람 |
| AI 활용 분석 + ROI | 🟡 막대 차트 | 부서×기능 히트맵 |
| 인력 통계 7차트 (Plotly) | 🟡 막대 차트 (CSS) | Plotly 7종 |
| 로그인 이력 다운로드 (CSV/XLSX) | ✅ 다운로드 버튼 | API 연결 |
| 인라인 편집 7항목 | ❌ | 더블클릭 → 편집 |
| 3단계 사용자 생성 위저드 | ❌ | Stepper |
| 감사 로그 (audit.db) | ❌ | API |
| 부서 매핑 30개 + 사번 자동 갱신 | ❌ | 폼 로직 |

**완성도**: **45% (UI) / 0% (API)** → 종합 **22%**
**핵심 추가 작업**: Plotly 7차트, 인라인 편집, 위저드, RBAC 매트릭스, 감사 로그 테이블

---

### 2-6. 기능 F: 설비/공정 AI

| Spec 항목 | UI 키트 (Equipment.jsx) | 갭 |
|---|:--:|---|
| 3탭 + 5하위탭 (OVERVIEW) | ✅ `tab/sub` 구조 | — |
| 에러코드 DB 201건 + 7장비 | ❌ | API + 테이블 |
| ML 에러 검색 (TF-IDF + 동의어 79개) | ✅ `errQuery, equipFilter, symptom` | API 연결 |
| 에러 인과 25 카테고리 + 70 규칙 | ❌ | API |
| Markov 25상태 + DFS 3단계 | ❌ | 트리 시각화 |
| SPC Nelson 8 Rules + 차트 | 🟡 5공정 카드 | Plotly + Annotation |
| ML SPC Isolation Forest | ❌ | API |
| SPC 데이터 생성기 + CSV 업로드 | ❌ | 폼 + 업로더 |
| XGBoost 금형 수명 | ❌ | API + 게이지 |
| MTBF 예측 정비 (15대×240건) | ❌ | API + 차트 |
| 에러 발생 이력 685건 | ❌ | 테이블 |
| 점검 9 템플릿 (3장비×3주기) | ❌ | 체크리스트 폼 |
| 매뉴얼 RAG 3하위탭 | ❌ | RAG 검색 패널 |
| 부서 기반 접근 제어 (14개) | ❌ | RBAC 가드 |

**완성도**: **50% (UI) / 0% (API)** → 종합 **25%**
**핵심 추가 작업**: Plotly Nelson SPC, 금형 게이지, Markov 트리, MTBF 차트, CSV 업로더, 매뉴얼 RAG

---

## 3. 구현 가능성 종합 평가

### 3-1. 평가 매트릭스

| 기능 | 디자인 완성도 | API 백엔드 | 차트 | 지도 | 파일 IO | 종합 가능성 |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **A** | 40% | 100% (FastAPI 라우터 존재) | — | react-leaflet 필요 | 일부 | **🟢 90%** |
| **B** | 70% | 100% | — | — | 7포맷 핸들러 | **🟢 95%** |
| **C** | 55% | 100% | — | — | 비전·다운로드 | **🟡 85%** |
| **D** | 40% | 100% | Plotly 다수 | react-leaflet | CSV | **🟡 80%** |
| **E** | 45% | 60% (Auth만) | Plotly 7종 | — | CSV/XLSX | **🟡 75%** |
| **F** | 50% | 80% | Plotly 다수 | — | CSV 업로드 | **🟢 90%** |

### 3-2. 결론: **전 6대 기능 모두 구현 가능**

> 디자인 시스템과 백엔드 비즈니스 로직(`features/`) 이 이미 잘 갖춰져 있어, **프론트엔드 React 앱 + 차트/지도 라이브러리 통합 + 백엔드 API 보강**만 하면 모든 기능을 구현할 수 있습니다.

**가장 중요한 인사이트**:
- 백엔드 `features/` 비즈니스 로직 (~33MB) 은 그대로 활용 가능
- UI 키트는 골격이지만 **모든 페이지 구조는 이미 존재**
- 추가로 필요한 것은 **인프라(빌드·라우팅·상태·통신)** 와 **차트/지도 라이브러리**

---

## 4. React 기술 스택 제안

### 4-1. 권장 스택

| 카테고리 | 라이브러리 | 사유 |
|---|---|---|
| **빌드 도구** | **Vite** 5+ | 빠른 HMR, ESBuild, TypeScript 즉시 지원 |
| **UI 프레임워크** | **React 18** | 디자인 시스템과 일치, Suspense·Concurrent |
| **언어** | **TypeScript** | 타입 안정성, FastAPI 스키마와 매칭 |
| **스타일** | **CSS 변수 + 모듈** (또는 Tailwind) | 디자인 시스템 colors_and_type.css 직접 활용 |
| **라우팅** | **React Router 6** | 표준, RBAC 가드 친화 |
| **상태 관리** | **Zustand** (글로벌) + React Query (서버) | 가볍고 직관적 |
| **HTTP 클라이언트** | **axios** + interceptors | JWT auto-refresh |
| **SSE 클라이언트** | `@microsoft/fetch-event-source` | POST 지원 (EventSource는 GET만) |
| **차트** | **Plotly.js** (`react-plotly.js`) | 기존 Streamlit 차트 그대로 재사용 가능 |
| **지도** | **react-leaflet** + OpenStreetMap | Folium 대체, 무료 |
| **폼** | **react-hook-form** + Zod | 검증·성능 우수 |
| **테이블** | **TanStack Table v8** | 정렬·필터·페이지네이션 |
| **마크다운** | **react-markdown** + remark-gfm | LLM 응답 렌더링 |
| **아이콘** | **Lucide React** | 1.5 stroke 디자인 시스템 일치 |
| **유틸** | **date-fns**, **clsx** | 표준 |
| **테스트** | Vitest + Testing Library | Vite 친화 |

### 4-2. 폴더 구조 제안

```
ajin-ai-assistant-react/
├── frontend/                          ← 새로 생성
│   ├── public/
│   │   └── fonts/                     ← AJIN Sans 복사
│   ├── src/
│   │   ├── main.tsx                   ← 진입점
│   │   ├── App.tsx                    ← 라우터 + 테마 + 인증
│   │   ├── routes/
│   │   │   ├── _shell.tsx             ← 3-Column HUD 레이아웃
│   │   │   ├── login.tsx
│   │   │   ├── dashboard.tsx
│   │   │   ├── search.tsx
│   │   │   ├── draft.tsx
│   │   │   ├── chat.tsx
│   │   │   ├── compliance.tsx
│   │   │   ├── admin.tsx
│   │   │   └── equipment.tsx
│   │   ├── components/                ← 디자인 시스템 컴포넌트
│   │   │   ├── shell/                 ← TopBar, LeftSidebar, RightPanel
│   │   │   ├── ui/                    ← Button, Card, Badge, Input, Select
│   │   │   ├── chart/                 ← PlotlyChart, NelsonSPC, OrgChart
│   │   │   └── form/                  ← TextField, Stepper
│   │   ├── api/                       ← API 클라이언트
│   │   │   ├── client.ts              ← axios 인스턴스 + interceptors
│   │   │   ├── sse.ts                 ← SSE 헬퍼
│   │   │   ├── auth.ts                ← /api/auth/*
│   │   │   ├── employee.ts            ← /api/employee/*
│   │   │   ├── draft.ts               ← /api/draft/*
│   │   │   ├── onboarding.ts          ← /api/onboarding/*
│   │   │   ├── compliance.ts          ← /api/compliance/*
│   │   │   ├── admin.ts               ← /api/admin/* (확장)
│   │   │   └── equipment.ts           ← /api/equipment/* (확장)
│   │   ├── store/                     ← Zustand
│   │   │   ├── auth.ts                ← JWT 상태
│   │   │   ├── theme.ts               ← light/dark/auto
│   │   │   └── ui.ts                  ← 우측 패널 토글 등
│   │   ├── hooks/                     ← 커스텀 훅
│   │   │   ├── useTheme.ts
│   │   │   ├── useStream.ts           ← SSE 훅
│   │   │   └── useRBAC.ts             ← 권한 체크
│   │   ├── types/                     ← TypeScript 타입
│   │   │   └── api.ts                 ← FastAPI Pydantic 미러
│   │   ├── styles/
│   │   │   ├── tokens.css             ← uiux/colors_and_type.css 복사
│   │   │   └── theme.css              ← uiux/ui_kits/web_app/theme.css 복사 + 정리
│   │   └── lib/                       ← 유틸
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── .env.example                   ← VITE_API_URL=http://localhost:8000
│
├── backend/                           ← 기존 FastAPI (그대로)
├── core/, features/, data/, vectorstore/, scripts/, tests/
├── docs/                              ← 정리된 문서
└── uiux/                              ← 디자인 시스템 (참조용)
```

### 4-3. 디자인 토큰 → React 매핑

```ts
// src/styles/tokens.ts (TypeScript 미러)
export const tokens = {
  color: {
    light: { bg:'#FAF8F5', surface:'#FFFFFF', primary:'#D89400', /* ... */ },
    dark:  { bg:'#0A0E14', surface:'#111820', primary:'#FCB132', /* ... */ },
  },
  font: {
    family: '"AJIN Sans", "Pretendard", "Noto Sans KR", sans-serif',
    size: { xs:12, sm:13, base:15, md:16, lg:18, xl:20, '2xl':28, '3xl':36 },
  },
  layout: {
    topBarHeight: 52,
    leftPanelWidth: 240,
    rightPanelWidth: 280,
  },
  glass: {
    blur: 24,
    saturate: 140,
  },
} as const;
```

CSS 변수는 그대로 사용 — `var(--hud-primary)`, `var(--glass-bg)` 등.

---

## 5. 백엔드 API 갭 분석

### 5-1. 현재 FastAPI 라우터 (8개)

| 라우터 | 엔드포인트 | 사용 기능 |
|---|---|---|
| `auth` | `/login`, `/change-password`, `/refresh` | E (인증) |
| `health` | `/health` | 공통 |
| `models` | `/installed`, `/available`, `/auto-select` | C (LLM 선택) |
| `search` | `/documents`, `/summarize` | B (문서 검색) |
| `employee` | `/search` | A (인원 검색) |
| `onboarding` | `/chat` (SSE), `/chat/vision`, `/upload` | C |
| `draft` | `/generate` (SSE), `/generate-pipeline`, `/export`, `/templates` | B |
| `compliance` | `/scenarios`, `/facilities`, `/check` | D |

### 5-2. 추가 필요 라우터

#### 기능 A 보강
- `GET /api/employee/recent-searches` — 검색 이력
- `GET /api/employee/sort-options` — 정렬 메타
- `GET /api/employee/org-chart` — 조직도 트리

#### 기능 D 보강
- `GET /api/compliance/crawlers` — 9 크롤러 status
- `POST /api/compliance/crawlers/run` — 크롤러 실행
- `GET /api/compliance/changes` — 변경 이력
- `GET /api/compliance/scenarios/{id}/simulate` — 시나리오 시뮬레이션
- `GET /api/compliance/tariff/simulate` — 관세 시뮬레이션
- `GET /api/compliance/impact-network/{scenario_id}` — 영향 네트워크 데이터

#### 기능 E 신규 (아직 라우터 없음)
- `GET /api/admin/users` — 사용자 목록
- `POST /api/admin/users` — 신규 생성 (3단계)
- `PATCH /api/admin/users/{id}` — 인라인 편집
- `GET /api/admin/security/audit` — 보안 감사 결과
- `GET /api/admin/login-history` — 로그인 이력
- `GET /api/admin/login-history/export?format=csv|xlsx` — 다운로드
- `GET /api/admin/analytics/usage` — AI 활용 분석
- `GET /api/admin/analytics/roi` — ROI 산출
- `GET /api/admin/stats/headcount` — 인력 통계 7종

#### 기능 F 신규 (아직 라우터 없음)
- `GET /api/equipment/dashboard` — OVERVIEW 메트릭
- `POST /api/equipment/error-search` — TF-IDF 에러 검색
- `GET /api/equipment/errors/{code}/causality` — 인과 규칙
- `GET /api/equipment/spc/{process}` — Nelson Rule 분석
- `POST /api/equipment/spc/upload` — CSV 업로드
- `POST /api/equipment/spc/regenerate` — 샘플 재생성
- `GET /api/equipment/molds` — 25개 금형
- `GET /api/equipment/molds/{id}/lifespan` — XGBoost 예측
- `GET /api/equipment/markov/{error_code}` — 연쇄 고장 예측
- `GET /api/equipment/maintenance/mtbf` — MTBF 분석
- `GET /api/equipment/maintenance/cost-top5` — 비용 TOP 5
- `GET /api/equipment/inspection/templates` — 9 템플릿
- `POST /api/equipment/manual/search` — 매뉴얼 RAG

### 5-3. 추정 작업량

| 라우터 | 신규 엔드포인트 수 | 예상 시간 |
|:--:|:--:|:--:|
| A 보강 | 3 | 0.5 일 |
| B 보강 | 0 (기존 충분) | — |
| C 보강 | 1~2 (피드백) | 0.5 일 |
| D 보강 | 6 | 1.5 일 |
| **E 신규** | **9** | **2 일** |
| **F 신규** | **13** | **3 일** |
| **합계** | **31~33 신규/보강** | **~7 일** |

> 비즈니스 로직은 `features/` 에 이미 존재 — FastAPI 래퍼만 작성하면 됨.

---

## 6. Phase별 마이그레이션 로드맵

### 본선 일정 가정 (2026-04-27 기준 ~본선 제출일까지)

본선 일정에 따라 4~6주 안에 완성해야 한다고 가정 (~6주 = 약 30 작업일).

### Phase 1: **인프라 부트스트랩** (3일)
**목표**: 빌드 + 라우팅 + 인증 + 테마 + 통신 기반 완성

- [ ] `frontend/` 디렉토리 + Vite + React 18 + TS 초기 설정
- [ ] uiux 디자인 토큰을 `src/styles/tokens.css` 로 복사 + 정리
- [ ] AJIN Sans 폰트 `public/fonts/` 복사 + `@font-face`
- [ ] React Router 6 라우트 트리 구성 (8 페이지)
- [ ] 3-Column HUD 셸 (`_shell.tsx`) — TopBar / LeftSidebar / RightPanel
- [ ] axios 클라이언트 + JWT interceptor + auto-refresh
- [ ] Zustand auth/theme/ui store
- [ ] 라이트/다크/AUTO 테마 토글
- [ ] Login 페이지 (FastAPI `/api/auth/login` 연결)
- [ ] RBAC 가드 (`<RequireAuth>`, `<RequireRole>`)
- [ ] 환경변수 (`VITE_API_URL`)

**산출물**: 로그인 → 대시보드 빈 셸까지 동작

### Phase 2: **공통 컴포넌트 라이브러리** (3일)
**목표**: 디자인 시스템을 재사용 가능한 React 컴포넌트로 정착

- [ ] **Button** (primary/secondary/tertiary/ghost) + 스트리밍 disabled
- [ ] **Card** (`.hud-panel-box`)
- [ ] **MetricCard** (3xl 값 + 영문 라벨 + 한글 부제 + sub)
- [ ] **Badge** (ok/warn/fail/info/off — `●`/`○` 글리프)
- [ ] **PanelHeader** (영문 + 한글 + 우측 배지)
- [ ] **StatusDot** + **StatusText**
- [ ] **DottedSeparator**
- [ ] **Input** (text/search) + **Select** + **Slider**
- [ ] **Tabs** (메인 + 서브)
- [ ] **Stepper** (3단계 위저드용)
- [ ] **DataTable** (TanStack Table 래퍼)
- [ ] **GlassPanel** (Liquid Glass 매테리얼)
- [ ] **PlotlyChart** (react-plotly.js + 테마 자동 적용)
- [ ] **MapView** (react-leaflet + 19개소)
- [ ] **MarkdownRenderer** (LLM 응답)

### Phase 3: **기능 A 인원 검색** (3일)
- [ ] 조직도 인터랙티브 (uiux Search.jsx 포팅)
- [ ] 6 필터 + 5종 정렬 + 검색 이력 칩
- [ ] 가시성 마스킹 (3-Tier)
- [ ] 사업장 지도 (react-leaflet)
- [ ] 교차 네비 (이메일/문서 작성 → B 페이지)
- [ ] 백엔드 `/api/employee/search` 연결

### Phase 4: **기능 C AI 도우미** (4일)
**(대회 데모 가장 핵심)**
- [ ] 듀얼 모드 + 부서 자동
- [ ] SSE 실시간 스트리밍 (`@microsoft/fetch-event-source`)
- [ ] 메시지 리스트 + 마크다운 렌더링
- [ ] SOP 8종 단계별 가이드 (체크리스트 + 진행률 바)
- [ ] 협업 시나리오 5종 트리거
- [ ] 빠른 질문 6개
- [ ] 파일 업로드 (📎, 20+ 확장자)
- [ ] 비전 모델 (이미지 업로드)
- [ ] 다운로드 영구화 (DOCX/XLSX/CSV/TXT)
- [ ] 피드백 이모지 + DB
- [ ] 네비 차단 (스트리밍 중)
- [ ] 메모리 요약 박스 (점선)

### Phase 5: **기능 B 문서 작성** (3일)
- [ ] 3탭 + 어조/유형 셀렉터
- [ ] SSE 스트리밍 생성
- [ ] 품질 평가 5기준 분해 카드
- [ ] CC 추천 칩
- [ ] 버전 diff (HTML 하이라이트)
- [ ] 7포맷 다운로드 핸들러
- [ ] 양식 카탈로그 11종

### Phase 6: **기능 F 설비/공정** (4일)
**(SILLI 데모 가장 강력 기능)**
- [ ] OVERVIEW 5하위탭
- [ ] 5공정 건강 카드
- [ ] **Plotly Nelson Rule SPC 차트** (위반 음영 + 풍선)
- [ ] ML SPC Cpk 예측
- [ ] 에러 검색 (입력 + 카테고리 + 결과 카드)
- [ ] 에러 이력 685건 테이블
- [ ] Markov 연쇄 트리 시각화
- [ ] XGBoost 금형 25개 게이지
- [ ] MTBF 차트 (15대 × 240건)
- [ ] CSV 업로드 + 데이터 생성기
- [ ] 매뉴얼 RAG 3하위탭
- [ ] 점검 9 템플릿 체크리스트

### Phase 7: **기능 D 법규 모니터링** (3일)
- [ ] 4탭 구조
- [ ] 시나리오 TOP-3 카드 + 시뮬레이션
- [ ] **Plotly Gantt** (데드라인 타임라인)
- [ ] 관세 슬라이더 → **Plotly Bar** (6품목 원가)
- [ ] 변경 감지 메트릭 + CSV 내보내기
- [ ] 9 크롤러 패널 + 실행 버튼
- [ ] **Plotly Network** (영향 네트워크)
- [ ] 사업장 지도 (재사용)

### Phase 8: **기능 E 인사 관리** (3일)
- [ ] 6탭 구조 (RBAC 분기)
- [ ] 사용자 인라인 편집 7항목
- [ ] 3단계 사용자 생성 위저드
- [ ] 보안 감사 3종 카드
- [ ] **Plotly 7차트** (인력 통계)
- [ ] 부서 × 기능 히트맵 (AI 활용 분석)
- [ ] 로그인 이력 다운로드 (CSV/XLSX)
- [ ] 비밀번호 정책 6조건 실시간

### Phase 9: **백엔드 API 보강 + 통합 테스트** (3일)
- [ ] E·F 라우터 22개 신규 엔드포인트 작성
- [ ] D 라우터 6개 보강
- [ ] CORS 설정 (Firebase 도메인)
- [ ] E2E 테스트 (Cypress 또는 Playwright)
- [ ] 본선 데모 시나리오 리허설

### Phase 10: **Firebase 배포 + 최종 폴리싱** (1일)
- [ ] Vite 빌드 → Firebase Hosting
- [ ] FastAPI Cloud Run 또는 사내 GPU 서버 배포
- [ ] HTTPS + 도메인 + 환경변수
- [ ] 본선 데모 영상 캡처

**총 예상 작업량**: **30 작업일 (4~6주)**

---

## 7. 우선순위 큐 (본선 데모 기준)

### 🔥 우선순위 1 — 데모 시연 핵심 (반드시 완성)

| # | 항목 | 데모 임팩트 |
|:--:|---|---|
| **1** | 인프라 부트스트랩 (Phase 1) | 모든 기반 |
| **2** | 공통 컴포넌트 (Phase 2) | 디자인 일관성 |
| **3** | **기능 C AI 도우미** (Phase 4) | SILLI 핵심 — 생산성 향상 |
| **4** | **기능 F 설비 AI** (Phase 6) | SILLI 핵심 — 품질·안전 (실동작 ML) |
| **5** | **기능 B 문서 작성** (Phase 5) | SILLI 핵심 — 업무 효율화 |
| **6** | **기능 D 법규 모니터링** (Phase 7) | SILLI 핵심 — 안전·투자비 절감 |
| **7** | Firebase 배포 (Phase 10) | 외부 시연 가능 |

### 🟡 우선순위 2 — 완성도 보강

| # | 항목 |
|:--:|---|
| **8** | **기능 A 인원 검색** (Phase 3) — 조직도 인터랙티브가 시각적 임팩트 큼 |
| **9** | **기능 E 인사 관리** (Phase 8) — RBAC + 보안 감사 |
| **10** | 백엔드 API 보강 (Phase 9) |

### 🟢 우선순위 3 — 시간 여유 시

| # | 항목 |
|:--:|---|
| **11** | 모바일 반응형 (Phase 2 일부 + 추가) |
| **12** | E2E 테스트 |
| **13** | 다국어 (영문 데모 가능) |

---

## 8. 위험 요소 + 완화 방안

### 8-1. 기술 위험

| 위험 | 영향 | 확률 | 완화 |
|---|:--:|:--:|---|
| **Ollama 외부 호스팅** | 🔴 | 중 | 사내 GPU 서버 + Cloudflare Tunnel (현재 ngrok 대체) — 또는 Cloud Run with GPU (비용 ↑) |
| **ChromaDB 크기 (15MB)** | 🟡 | 낮 | Cloud Run + Persistent Volume 또는 사내 호스팅 |
| **CORS 정책** | 🟡 | 중 | `backend/config.py` 에 Firebase 도메인 추가 + `samesite=none; secure` 쿠키 |
| **SSE 프록시 끊김** | 🟡 | 중 | Cloud Run gen2 또는 사내 nginx + `proxy_read_timeout 600s` |
| **Plotly 번들 크기 (3MB+)** | 🟢 | 높 | 코드 스플리팅 (`React.lazy(() => import('react-plotly.js'))`) |
| **AJIN Sans 폰트 크기** | 🟢 | 낮 | `font-display: swap` + 본문은 Pretendard fallback |
| **TS 타입 동기화** (FastAPI ↔ React) | 🟡 | 중 | `pydantic-to-typescript` 또는 OpenAPI codegen |

### 8-2. 일정 위험

| 위험 | 영향 | 확률 | 완화 |
|---|:--:|:--:|---|
| **30 작업일은 4~6주 분량** | 🔴 | 높 | 우선순위 1 (7항목)에 집중, 나머지는 Phase 10 후 |
| **개인 1인 작업 시 백엔드+프론트 동시** | 🟡 | 높 | UI는 mock 데이터로 먼저 진행, 백엔드 보강은 통합 시점에 일괄 |
| **본선 일정 압박** | 🔴 | 중 | 기능 우선순위 1 (B/C/D/F) 4개를 우선 완성 → 1차 데모 가능, 이후 A/E 보강 |

### 8-3. 디자인 위험

| 위험 | 영향 | 확률 | 완화 |
|---|:--:|:--:|---|
| **Liquid Glass 브라우저 호환성** | 🟢 | 낮 | `backdrop-filter` + `-webkit-` prefix (Chrome/Safari OK, Firefox 제한) |
| **OKLCH 색공간** | 🟢 | 낮 | `color-mix()` 폴백 (대부분 모던 브라우저 지원) |
| **AJIN Sans 라이선스** | 🟡 | 중 | 사용 확인 필요 — 사용자가 폰트 권리 보유 여부 확인 |

---

## 9. 다음 단계 지시

### 즉시 시작 가능한 작업 (사용자 승인 후)

#### Step 1: Vite + React + TS 부트스트랩 (다음 작업)
```bash
cd <REPO_ROOT>
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom@6 zustand axios @microsoft/fetch-event-source \
  react-plotly.js plotly.js react-leaflet leaflet \
  react-hook-form zod @tanstack/react-table \
  react-markdown remark-gfm lucide-react \
  date-fns clsx
npm install -D @types/leaflet @types/react-plotly.js
```

#### Step 2: 디자인 토큰 + 폰트 이식
```bash
mkdir -p frontend/src/styles frontend/public/fonts
cp uiux/AJIN\ AI\ Assistant\ Design\ System/colors_and_type.css frontend/src/styles/tokens.css
cp uiux/AJIN\ AI\ Assistant\ Design\ System/ui_kits/web_app/theme.css frontend/src/styles/theme.css
cp uiux/AJIN\ AI\ Assistant\ Design\ System/fonts/* frontend/public/fonts/
cp uiux/AJIN\ AI\ Assistant\ Design\ System/assets/*.svg frontend/public/
```

#### Step 3: 셸 컴포넌트 + 라우터 (uiux 컴포넌트 → TSX 포팅)
- `App.tsx`, `routes/_shell.tsx`, `routes/login.tsx`, `routes/dashboard.tsx`
- TopBar / LeftSidebar / RightPanel을 babel JSX → TSX로 변환

### 의사 결정 필요 항목

다음 중 사용자 결정이 필요합니다:

| # | 결정 항목 | 옵션 |
|:--:|---|---|
| **1** | 본선 일정 (4주 vs 6주) | 일정에 따라 우선순위 큐 조정 |
| **2** | 백엔드 호스팅 | Cloud Run vs 사내 GPU + Cloudflare Tunnel vs 그대로 ngrok |
| **3** | 스타일 전략 | CSS 변수 + 모듈 vs Tailwind CSS + CSS 변수 |
| **4** | TS 엄격도 | strict 모드 vs 점진적 |
| **5** | 모바일 데이터 데모 | 본선에 모바일 시연 포함? |
| **6** | AI Sans 폰트 라이선스 | 사용 권리 확인 필요 |
| **7** | i18n 영문 데모 | 한국어만 vs 한·영 |

---

## 부록 A. uiux UI 키트 ↔ React TSX 매핑 표

| UI 키트 (Babel JSX) | 신규 React TSX | 변환 작업 |
|---|---|---|
| `Login.jsx` (39줄) | `routes/login.tsx` + `components/auth/LoginForm.tsx` | TS 타입 + react-hook-form |
| `TopBar.jsx` (19줄) | `components/shell/TopBar.tsx` | props 타입화 |
| `LeftSidebar.jsx` (83줄) | `components/shell/LeftSidebar.tsx` | router Link |
| `RightPanel.jsx` (37줄) | `components/shell/RightPanel.tsx` | live data hook |
| `Dashboard.jsx` (47줄) | `routes/dashboard.tsx` | 메트릭 카드 분리 |
| `Search.jsx` (249줄) | `routes/search.tsx` + `OrgChart.tsx` + `EmployeeTable.tsx` | 분리 + API 연결 |
| `Draft.jsx` (188줄) | `routes/draft.tsx` + `DraftEditor.tsx` + `QualityCard.tsx` | SSE 통합 |
| `Chat.jsx` (261줄) | `routes/chat.tsx` + `ChatStream.tsx` + `ChatComposer.tsx` | SSE + 파일 + 비전 |
| `Compliance.jsx` (332줄) | `routes/compliance.tsx` + 4개 탭 컴포넌트 | Plotly + Map |
| `Admin.jsx` (377줄) | `routes/admin.tsx` + 6개 탭 컴포넌트 | RBAC + Plotly |
| `Equipment.jsx` (460줄) | `routes/equipment.tsx` + 5하위탭 + ML 컴포넌트 | Plotly + 게이지 |
| `Icons.jsx` (40줄) | `components/ui/Icon.tsx` (Lucide 매핑) | Lucide React |

---

## 부록 B. 본선 데모 15분 시나리오 (UI 키트 적용)

| 분 | 페이지 | 데모 포인트 |
|:--:|:--:|---|
| 0~1 | Login | 비밀번호 정책 6조건 실시간 |
| 1~2 | Dashboard | 4 메트릭 + 6 모듈 카드 + 시스템 정보 |
| 2~4 | A Search | **인터랙티브 조직도** + 시맨틱 검색 + 가시성 마스킹 |
| 4~7 | B Draft | "PPAP 제출 안내" → 스트리밍 + 품질 87점 + 7포맷 |
| 7~10 | C Chat | "프레스 트라이 SOP" → 8단계 + 퀴즈 → 오답 재학습 |
| 10~12 | D Compliance | 산안법 시뮬 + 관세 슬라이더 25% → 400억 원 |
| 12~14 | F Equipment | **Nelson SPC 위반** + 에러 "이상한 소리" → 베어링 + Markov 연쇄 |
| 14~15 | E Admin | 보안 감사 + ROI 950만 원/월 |

---

---

## 10. 사용자 확정 결정사항 (2026-04-27)

| # | 항목 | 결정 |
|:--:|---|---|
| 1 | **본선 일정** | **2주 (14일)** — 매우 압축됨, 우선순위 1 항목 위주 |
| 2 | **백엔드 호스팅** | **Firebase Web Hosting** (React 정적) + **Gemini API** + **Ollama** + **LM Studio** (3-tier LLM 폴백) |
| 3 | **스타일 전략** | **CSS 변수 + 모듈** (디자인 토큰 직결) |
| 4 | **TypeScript** | **strict 모드** |
| 5 | **모바일 데모** | **본선 포함** (uiux/mobile 키트 활용) |
| 6 | **AJIN Sans 폰트** | **uiux 폰트 그대로 사용 가능** |
| 7 | **i18n** | **한국어 + 영어 둘 다 지원** |

### 10-1. LLM 다중 프로바이더 아키텍처

```
┌──────────────────┐
│  React Frontend  │
│  (Firebase Host) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   API Gateway    │ ← FastAPI 백엔드 (Cloudflare Tunnel 경유)
│   (LLM Router)   │
└─┬────┬─────┬─────┘
  │    │     │
  ▼    ▼     ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Gemini API   │  │ Ollama       │  │ LM Studio    │
│ (Cloud)      │  │ (Local GPU)  │  │ (Local CPU)  │
│ 1순위·고품질 │  │ 2순위·온프레 │  │ 3순위·폴백   │
└──────────────┘  └──────────────┘  └──────────────┘
```

**프로바이더 라우팅 정책**:
| 작업 | 1순위 | 2순위 | 3순위 |
|---|:--:|:--:|:--:|
| **C 챗봇 일반 질의** | Gemini 1.5 Pro | Ollama qwen3.5:9b | LM Studio |
| **C 비전 (이미지)** | Gemini 1.5 Pro Vision | Ollama gemma4 | — |
| **B 문서 작성** | Ollama qwen3.5:9b (한국어) | Gemini 1.5 Pro | LM Studio |
| **B 임베딩 (RAG)** | Ollama bge-m3 | — | — |
| **A/F 의도 분류** | 로컬 TF-IDF 모델 | — | — |

**환경변수**:
```
VITE_API_URL=https://ajin-api.your-tunnel.com
GEMINI_API_KEY=AIza...        # 백엔드 .env
OLLAMA_URL=http://localhost:11434
LM_STUDIO_URL=http://localhost:1234/v1
```

### 10-2. Firebase Web Hosting 배포 전략

| 컴포넌트 | 배포 위치 |
|---|---|
| **React SPA (Vite 빌드)** | Firebase Hosting (`*.web.app`) |
| **FastAPI 백엔드** | 사내 GPU 서버 + **Cloudflare Tunnel** (HTTPS, ngrok 대체) |
| **Ollama LLM** | 사내 GPU 서버 (FastAPI와 동일 호스트) |
| **LM Studio** | 사내 호스트 (CPU/GPU 폴백) |
| **Gemini API** | Google Cloud (외부 API) |
| **ChromaDB** | 사내 (FastAPI와 동일 호스트) |
| **SQLite DB** | 사내 (FastAPI와 동일 호스트) |

**CORS 설정 갱신** ([backend/config.py](../../backend/config.py)):
```python
CORS_ORIGINS = [
    "https://ajin-ai-assistant.web.app",
    "https://ajin-ai-assistant.firebaseapp.com",
    "http://localhost:5173",  # Vite dev
]
```

### 10-3. 모바일 반응형 전략

**브레이크포인트**:
| 폭 | 동작 |
|---|---|
| `> 1024px` | 3-Column HUD (full) |
| `768~1024px` | 우측 패널 자동 숨김, 좌측 사이드바 유지 |
| `< 768px` | 좌측 사이드바 햄버거, 단일 컬럼, uiux/mobile 키트 활용 |

**모바일 우선 페이지**:
- 대시보드 (메트릭 카드 1열 스택)
- C 챗봇 (sticky composer + 메시지 풀스크린)
- F SPC 차트 (가로 스크롤)
- 그 외 페이지: 데스크톱 우선, 모바일은 시연 가능 수준

### 10-4. i18n 한·영 전략

| 라이브러리 | **react-i18next** + i18next-browser-languagedetector |
|---|---|
| 기본 언어 | 한국어 (ko) |
| 보조 언어 | 영어 (en) |
| 토글 위치 | TopBar 우측 (`KO` ↔ `EN`) |
| 자동 감지 | localStorage → navigator.language |
| 번역 파일 | `src/i18n/{ko,en}/{common,A,B,C,D,E,F}.json` |

**번역 우선순위** (시간 부족 시):
1. **공통 (TopBar/Sidebar/Login/Dashboard)** — 데모 직격
2. **C 챗봇 + B 문서 + F 설비** — 핵심 평가 기능
3. D/E/A — 후순위

### 10-5. 압축 14일 로드맵

| Day | Phase | 작업 | 비고 |
|:--:|:--:|---|---|
| **1** | 1 | Vite + TS + 라우터 + 토큰 + 폰트 + 셸 골격 | 오늘 시작 |
| **2** | 1 cont. | TopBar/LeftSidebar/RightPanel TSX + 인증 + Login | |
| **3** | 2 | 공통 컴포넌트 (Button/Card/Badge/Input/Tabs/PlotlyChart/MapView) | |
| **4** | 4 | **C AI 도우미** — SSE + 챗 레이아웃 + LLM 멀티 프로바이더 라우터 | ⭐ |
| **5** | 4 cont. | C — SOP 8종 + 협업 시나리오 + 비전 + 파일 + 다운로드 + 피드백 | ⭐ |
| **6** | 6 | **F 설비** — OVERVIEW + 5하위탭 + Plotly Nelson SPC | ⭐ |
| **7** | 6 cont. | F — 에러 검색 + Markov + 금형 + MTBF + CSV 업로드 + 매뉴얼 | ⭐ |
| **8** | 5 | **B 문서 작성** — 3탭 + SSE + 7포맷 + 품질 평가 + CC | ⭐ |
| **9** | 7 | **D 법규** — 4탭 + Plotly Gantt + 관세 슬라이더 + 영향 네트워크 | ⭐ |
| **10** | 3 | A 인원 검색 — 조직도 + 6 필터 + 가시성 + react-leaflet | |
| **11** | 8 | E 인사 — 6탭 + Plotly 7차트 + 위저드 + 인라인 편집 | |
| **12** | — | **i18n 한·영** + **모바일 반응형** | |
| **13** | 9 | 백엔드 API 22개 신규 + LLM 멀티 프로바이더 통합 | |
| **14** | 10 | Firebase 배포 + Cloudflare Tunnel + 데모 리허설 | |

**위험**: 12·13일 작업이 다음 날로 밀릴 수 있음 → A/E 페이지를 mock-only 데모 수준으로 유지하고 B/C/D/F만 풀 통합.

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — uiux 디자인 시스템 분석 + 6대 기능 갭 + 9 Phase 로드맵 |
| **1.1** | 2026-04-27 | 사용자 결정 7항목 반영 — 2주 일정 / Firebase + Gemini+Ollama+LM Studio / strict TS / 모바일 / 한·영 |

---

**관련 문서**:
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — 기존 Streamlit 디자인 사양
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — 6대 기능 상세
- [uiux/AJIN AI Assistant Design System/README.md](../../uiux/AJIN AI Assistant Design System/README.md) — 디자인 시스템 가이드
- [uiux/AJIN AI Assistant Design System/SKILL.md](../../uiux/AJIN AI Assistant Design System/SKILL.md) — Hard Rules
