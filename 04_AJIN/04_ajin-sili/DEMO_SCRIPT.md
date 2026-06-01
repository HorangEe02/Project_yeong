# AJIN AI Assistant — 데모 시연 스크립트

> 제3회 실리 AX 기술전 (DX 부문) 출품작 시연 가이드.
> 작성일: 2026-05-11

---

## 0. 데모 환경 사전 점검 (시연 30분 전)

- [ ] 백엔드: `uvicorn backend.main:app --reload --port 8000`
- [ ] 프론트엔드: `npm run dev` (port 5173)
- [ ] LLM 라우터 상태: `/onboarding/health` 응답 `200 OK`
- [ ] ChromaDB 인덱스: `vectorstore/chroma.sqlite3` 존재 (~5.8MB)
- [ ] 9개 크롤러 캐시: `data/crawled/` 최근 24시간 내 갱신
- [ ] XGBoost 금형 모델 캐시: `data/mold_ml/xgb_mold_life.pkl` 존재
- [ ] **F**: `/equipment/headline` 응답 200, 데일리 헤드라인 카드 동작
- [ ] **F PWA**: `/equipment/field` 라우트 접근 가능, `manifest.webmanifest` 로드
- [ ] 데모 계정 5개 로그인 테스트:
  - L1 신입사원: `kim.intern@ajin.co.kr`
  - L3 품질팀장: `park.qm@ajin.co.kr`
  - L4 해외영업팀장: `lee.intl@ajin.co.kr`
  - L4 생산기술팀장: `jung.eng@ajin.co.kr` (F+D 시연용)
  - L5 HR 관리자: `choi.hr@ajin.co.kr`
- [ ] **OverviewGuideModal localStorage 초기화**: 평가자 자리에서 첫 진입 시 가이드 5장이 정확히 표시되도록 `localStorage.removeItem('ajin-equipment-guide-shown')` 실행
- [ ] **알람 ack 초기화**: `localStorage.removeItem('ajin-equipment-acked-alerts')` — 알람 3건 노출되도록

---

## 1. 시연 흐름 (총 30~32분, 6개 페르소나 × 6개 기능)

### Persona 1 — 신입사원 (L1): 기능 C 신입 가이드 (6분)

**진입**: `/onboarding` (대시보드 C 카드 또는 사이드바 "C2 · 신입 가이드")

**시연 멘트**:
> "신입사원이 첫 출근일에 가장 막막한 것은 '내 사수가 누구인가', '오늘 뭘 읽어야 하는가'입니다. AJIN AI Assistant는 부서를 자동 추론해 사수를 추천하고, SOP 자동 퀴즈·협업 시나리오 매칭·도면 Vision Q&A 를 한 페이지에서 제공합니다."

**클릭 흐름**:
1. **우측 사이드 패널** — MentorCard: 부서 자동 인식 → 사수 후보 3명 표시 → 체크리스트 5개 항목 → "SOP 읽음" 체크
2. **SOP 학습 그리드** — 8종 카드 중 "8D Report 작성 절차" 클릭 → 4지선다 3문제 자동 출제(LLM) → 제출 → 정답 + 해설 표시
3. **부서별 빠른 질문** — 6개 칩 중 "EWP가 뭔가요?" 클릭 → `/chat` 라우트로 prefill 이동 → SSE 답변
4. **협업 시나리오 매칭** — "고객사가 PPAP 요청했어요" 입력 → 절차 카드 즉시 응답(LLM 호출 0회) — 내가 할 일 + 이관 대상 + 데드라인
5. **도면 Vision Q&A** — 부품 사진 드래그앤드롭 → "이게 뭐죠?" → Gemini Vision SSE 스트리밍 → 응답 하단 "**도면 인덱스에 저장**" 버튼 클릭 → "/search → 도면" 탭에서 즉시 재검색 가능

**강조 포인트**:
- 미사용 백엔드 6개 API(`/sop/*`, `/quick-questions`, `/scenarios/match`, `/chat/vision`, `/upload`)가 모두 활성화됨
- 부서별 RBAC가 자동 적용되어 신입은 본인 부서 정보만 노출
- 글로서리 50+ 용어가 답변에 자연스럽게 인용됨

---

### Persona 2 — 품질팀장 (L3): 기능 A 검색 + 도면 + 조직도 (6분)

**진입**: `/search`

**시연 멘트**:
> "품질팀장은 매일 8D, PPAP, FMEA 문서와 도면을 다룹니다. AJIN AI Assistant는 BM25+벡터 하이브리드 RAG와 함께, 도면 메타·Vision 캡션 인덱스까지 통합 검색합니다."

**탭 구성** (Tabs: 통합 / 인사 / 문서 / **도면**):
1. **통합 탭**: 검색창 "EWP 8D Report" → 하이브리드 검색 결과 5건 + 본문 미리보기 + 출처
2. **인사 탭**: 17개 부서 조직도(Treemap), 19개 사업장 MapView — JOON INC(조지아) 마커 → 부품 EWP/CCH 표시
3. **문서 탭**: doc_type 필터로 PPAP만 보기
4. **도면 탭 (P2 신규)**: "EWP" 검색 → 도면 메타 카드 3장(DWG-EWP-001 하우징 상부 / DWG-EWP-002 하우징 하부 / DWG-EWP-003 임펠러) 노출. 자산 타입 셀렉트로 "Vision 캡션"만 보기 → 신입사원이 업로드한 도면 캡션이 함께 검색됨

**강조 포인트**:
- BM25 + ChromaDB + RRF 결합으로 키워드+의미 검색 동시 지원
- role_level 기반 마스킹 (L3 이상만 인사 정보 풀 조회)
- **자산 타입 통합**: 텍스트 문서, 도면 메타, Vision 캡션이 한 검색창에서 모두 노출 (정식 CAD 파싱은 v2.0 로드맵으로 솔직히 명시)

---

### Persona 3 — 해외영업팀장 (L4): 기능 B 초안 작성 (6분)

**진입**: `/draft`

**시연 멘트**:
> "해외영업팀은 HMGMA(현대차 조지아 메타플랜트)와 영문 커뮤니케이션이 일상입니다. PPAP 제출 안내 이메일을 IATF 16949 용어로 5초 안에 초안 작성하고, 5축 품질 점수로 검증합니다."

**클릭 흐름**:
1. 문서 유형: "HMGMA PPAP 제출 안내" 선택
2. 수신처: "HMGMA (미국, 영문)" 선택
3. 입력: "EWP-2026-001 부품 PPAP Level 3 제출 안내, 검토 미팅 요청"
4. "초안 생성" → SSE 스트리밍 (Gemini)
5. 품질 점수: 구조 92 / 길이 88 / 용어 95 / 완성도 90 / 톤 94
6. "부분 수정" → 한 단락만 LLM 재작성
7. "내보내기" → DOCX 다운로드

**강조 포인트**:
- ko / en / ko_en 3개 언어 라우팅
- 수신처별 톤·시그니처 자동 분기 (HMGMA: Best regards / 사내: 감사합니다)
- 버전 관리: draft → under_review → approved 승인 워크플로우

---

### Persona 4 — 생산기술팀장 (L4): 기능 F 설비 AI + 기능 D 컴플라이언스 (8분) ⭐ 차별화

**진입**: `/equipment` → 흐름 중간에 `/compliance`로 자동 라우팅

**시연 멘트**:
> "여기가 본 출품작의 차별화 무기 둘 — F 설비 AI와 D 컴플라이언스입니다. 7종 ML 엔진과 Nelson 8 Rules, XGBoost 금형 예측이 실제 동작하고, F에서 발견된 위험은 자동으로 D 컴플라이언스·B 문서작성과 한 흐름으로 이어집니다. 그리고 D는 HMGMA 1호 협력사 맥락의 미국 통상 규제(관세 25%·IRA·USMCA)를 9개 크롤러가 실시간 추적합니다."

#### 4-A. 기능 F 설비 AI (4분)

**클릭 흐름**:
1. `/equipment` 첫 진입 → **OverviewGuideModal** 자동 표시 (1분 가이드 5장: 5공정·Nelson 8·Cpk·7 ML·알람 워크플로우) → "건너뛰기" 또는 다음
2. **데일리 헤드라인 카드** 상단에 한 줄 요약: "OBC 평탄도 · Cpk 1.21 · 위반 3건 (Rule 1,2) · 금형 critical 2대" — 시그널 칩 클릭으로 SPC 탭 자동 점프
3. **SPC · Nelson 8** 서브탭 → OBC 공정 선택 → 관리도 차트 + 위반점 빨강 표시 + 한국어 권장 조치문
4. **ML 엔진** 서브탭 → ⓘ 아이콘 클릭 → "XGBoost 회귀 — 금형 잔여수명 예측. 사용률·불량률·추세·보전횟수 등 10개 특성을 학습…" 한국어 설명 노출
5. **예측 정비** 서브탭 → 위험 금형 카드 (MD-014 OBC) → 📅 **예측 교체일 2026-05-18** + 🎯 **95% CI: 14k~18k shots** 표시
6. 같은 카드에서 **컴플라이언스 영향** 액션 클릭 → `/compliance`로 자동 라우팅 (state 전달)

#### 4-B. 기능 D 컴플라이언스 (4분)

**클릭 흐름**:
7. Updates 탭: IRA 시나리오 카드 → severity HIGH 클릭
8. 영향도 네트워크 그래프: JOON INC → 영향받는 부품 EWP/CCH/OBC 노출
9. 관세 시뮬레이션 모달: 한국→미국 수입액 1,800만 USD × 25% = **63억 KRW** 예상 영향
10. mitigation 액션 카드 3개: ① 현지 생산 확대 ② USMCA 원산지 ③ HMGMA SQ 협의
11. **긴급 조치 탭** (F로 복귀하여) → 알람 카드 → **8D Report 작성** 클릭 → `/draft`로 prefill 라우팅 → 위반 정보 자동 입력된 textarea 노출

**강조 포인트**:
- F → D → B 한 흐름으로 자동 라우팅 (위반 발견 → 컴플라이언스 영향 → 8D 초안)
- Nelson 8 Rules + XGBoost + 95% CI + 한국어 권장 조치 = IATF 16949 산업 표준 완전 부합
- 9개 실 크롤러 (ISO/MSDS/EU/Domestic/OEM/APQP/Carbon ESG/EV Battery/Global Trade)
- HMGMA 1호 협력사 맥락의 미국 통상 규제 5건 시나리오
- VIEW/ANALYZE/OPERATE 3단계 RBAC

---

### Persona 5 — HR 관리자 (L5): 기능 E 인사 (3분)

**진입**: `/hr`

**시연 멘트**:
> "마지막으로 인사 도메인입니다. 1,024 LOC의 단일 페이지에 6개 탭이 모두 들어있어, 권한이 있는 HR 담당자라면 셀프서비스부터 채용 AI까지 한 곳에서 처리합니다."

**시연 필수 (25분 데모 기준)**:

#### Tab 1: Create User (60초)
- 3-step 위저드: 기본정보 → 권한 설정 → 인증 발급
- EmployeeIDPreview: 자동 사번 생성 (EMP-XXXX)
- 마지막 Step에서 "인증서 발급 마크다운 다운로드"

#### Tab 2: HR Stats (60초)
- 7개 서브탭 중 "본부 × 직급 매트릭스" 히트맵 시연
- 30개 부서 × 8개 직급 시각화
- "DownloadActions" → CSV/JSON 내보내기

#### Tab 3: Vacation (45초)
- 잔여 연차 카드(15일 / 사용 7일 / 부여 22일)
- "신청 모달" → 사유 입력 → 제출
- L3+ 매니저 화면: 팀원 신청 대기 1건 → 승인/반려

#### Tab 4: Certificate (15초)
- 증명서 종류: "재직증명서" 선택 → 영문 옵션 → 5초 발급 → PDF 다운로드

**시연 선택 (시간 남으면, 10분 데모 기준)**:

#### Tab 5: Recruiting AI (60초)
- JD + 면접질문 10개 + 평가 루브릭 5초 동시 생성

**시연 제외 (로드맵 슬라이드만)**:

- Delegation (위임 룰) — 백엔드 안정화 후 v2.0

---

### Persona 6 — 라인 작업자 (L1): 기능 F 현장 모드 PWA (3분) 🆕

**진입**: `/equipment/field` (대시보드 → 설비 모듈 → hero 영역의 "📱 현장 모드 (PWA)" 링크)

**시연 멘트**:
> "마지막 페르소나는 라인 작업자입니다. 책상이 아닌 라인에서 태블릿·스마트폰을 사용하는 작업자를 위한 풀스크린 PWA 모드입니다. 폰트 1.2배, 터치 48px 이상, 5초 자동 새로고침, critical 알람 발생 시 기기 vibration까지 — 책상 화면을 그대로 축소한 게 아니라 현장 시나리오에서 다시 설계했습니다."

**클릭 흐름**:
1. `/equipment/field` 진입 → 사이드바 없는 풀스크린, 진한 색상 헤드라인
2. **데일리 헤드라인**: 동일 백엔드 데이터가 색상 강조된 큰 박스로 표시 (Cpk 0.89 → 빨강 / 1.21 → 주황)
3. **5공정 큰 카드**: 좌측 색상 굵은 라인 + 우측 22px Cpk 숫자 + "즉시 정지 검토 / 점검 필요 / 정상" 한국어 상태
4. 우상단 **새로고침 버튼** 회전 애니메이션 + 5초 자동 폴링 (실시간성 강조)
5. critical 알람 발생 시 `navigator.vibrate([100, 60, 100])` — 시연 시 휴대폰 진동 발생
6. **하단 안내**: "Chrome 메뉴 → 홈 화면에 추가" → standalone PWA install 시연

**강조 포인트**:
- 사이드바 제거 + 폰트 16px(데스크톱 14px의 1.14x) + 터치 영역 ≥48px
- 자동 5초 폴링 + vibration → 라인 작업자가 화면을 들여다보지 않아도 알람 감지
- `manifest.webmanifest`로 PWA 등록 (Android/iOS 모두 standalone 가능)
- 같은 백엔드 `/equipment/headline` + `/equipment/dashboard/overview` 재사용 (별도 인프라 X)

---

## 2. 백업 시나리오 (시연 중 장애 대응)

### Case A: LLM 응답 지연 / 실패
- 증상: SSE 스트리밍이 10초 이상 대기
- 대응: 우상단 상태 인디케이터 확인 → "Gemini 차단됨, Ollama 폴백 중" 노출되면 그대로 시연 지속
- 최악: "Mock 모드" 토글 (각 페이지에 `LIVE/MOCK` 배지 존재) → 사전 캐시된 응답으로 시연

### Case B: 백엔드 다운
- 증상: 401/500 에러
- 대응: 우상단 토스트 "백엔드 재연결 중" → API client.ts의 3-tier auto-recovery가 자동 처리
- 최악: 페이지 새로고침 (Firebase 세션 유지) → 재진입

### Case C: 데이터 누락
- 증상: 검색 결과 0건
- 대응: 검색어를 "EWP" → "전자식 워터펌프"로 한글 동의어 변경 (글로서리에서 매핑)

---

## 3. Q&A 예상 질문 + 답변

| 질문 | 답변 |
|------|------|
| "도면이나 CAD 검색은 되나요?" | "`/search → 도면` 탭에서 도면 메타 15건(EWP/CCH/OBC/BMS 등)을 실시간 검색할 수 있고, 신입 가이드의 Vision Q&A로 도면 사진을 업로드하면 캡션이 자동 인덱싱돼 같은 탭에서 함께 검색됩니다. 정식 CAD 파일(DWG/STEP/DXF) 파싱은 v2.0 로드맵입니다." |
| "ML 엔진은 정말 동작하나요? 가짜 아닌가요?" | "7종 ML 모두 실제 학습된 모델입니다. XGBoost 금형 예측은 200 트리, 10개 특성으로 학습돼 `data/mold_ml/xgb_mold_life.pkl`에 캐시됩니다. 예측 결과에 95% CI와 예측 교체일이 함께 표시됩니다. 학습 데이터는 합성(Weibull bathtub curve)이며 실 공정 데이터 연동은 v2.0 — 정직하게 표기합니다." |
| "현장 모드 PWA는 어떻게 설치하나요?" | "데모 중 시연합니다. Chrome 메뉴 → '홈 화면에 추가' 또는 Safari 공유 → '홈 화면에 추가' — manifest.webmanifest 가 등록되어 standalone 앱처럼 실행됩니다. 같은 백엔드 API를 재사용하므로 별도 모바일 앱 빌드가 필요 없습니다." |
| "SPC Nelson Rule 위반 시 누가 대응하나요?" | "긴급 조치 탭에서 각 알람 카드의 'Acknowledge / 8D Report 작성 / 관련 SOP 보기' 3개 액션으로 처리합니다. 8D Report는 자동으로 `/draft`에 위반 정보가 prefill되어 LLM이 D1~D8 8단계 초안을 생성합니다. SOP는 `/chat`에서 부서별 가이드를 조회합니다." |
| "온보딩 페이지가 따로 있나요?" | "예, `/onboarding` 라우트에 신입사원 전용 대시보드가 있습니다. SOP 자동 퀴즈, 부서별 빠른 질문, 협업 시나리오 매칭, 도면 Vision Q&A 등 5개 섹션을 한 화면에 통합했습니다." |
| "위임 룰(Delegation)은 왜 시연 안 하나요?" | "결재권 위임은 백엔드 안정화 후 v2.0에 풀 출시 예정입니다. 현재는 UI 시연만 가능합니다." |
| "관세 시뮬레이션은 실데이터인가요?" | "관세율(25%, IRA 7,500달러)은 실 규제값입니다. 수입 금액은 데모용 시뮬레이션이며, 운영 환경에서는 ERP 연동으로 실데이터 적용합니다." |
| "RBAC는 어떻게 동작하나요?" | "role_level(1~5) + department 조합으로 5단계 권한. compliance는 VIEW/ANALYZE/OPERATE 3단계, admin은 L4+ 진입 가능합니다." |
| "LLM은 어떤 모델을 쓰나요?" | "Gemini 1.5 Pro (메인) → Ollama (로컬 폴백) → LM Studio (오프라인) 3-tier 서킷 브레이커입니다." |

---

## 4. 시연 마무리 멘트

> "오늘 시연한 6개 기능 — 신입 온보딩, 사내 검색, 영문 초안, **설비 AI + 통상 규제 연계**, 인사 셀프서비스, 현장 PWA — 는 모두 아진산업이 HMGMA 1호 협력사로 글로벌화하면서 현장에서 마주친 실제 페인 포인트에 대응합니다. 백엔드 LLM 라우터·RAG 인덱싱·9개 크롤러·7종 ML 엔진·Nelson 8 Rules·XGBoost 금형 예측이 모두 실제 동작하며, 책상의 부서장부터 라인의 작업자까지 한 시스템으로 이어집니다. 감사합니다."

---

## 5. 시연 후 자료 배포

- README.md (한 페이지 요약본)
- 본 DEMO_SCRIPT.md
- 백엔드 API 카탈로그 (FastAPI `/docs` Swagger UI)
- v2.0 로드맵 슬라이드 (P0 온보딩 라우트 + P2 도면 검색 PoC)

---

## 부록: 라우트 → 페르소나 매핑

| 라우트 | 주 페르소나 | 부 페르소나 | 권한 |
|--------|-----------|-----------|------|
| `/onboarding` | 신입사원 L1 | 전 직급 | All |
| `/search` | 품질팀장 L3 | 모든 실무자 | All (마스킹) |
| `/draft` | 해외영업 L4 | 품질팀 L3+ (F 알람 prefill) | All |
| `/compliance` | 생산기술 L4 | 부서장 (F 금형 위험 prefill) | L2+ |
| `/equipment` | 생산기술 L4 | 품질팀 L3+ | 14개 부서 화이트리스트 |
| **`/equipment/field`** | **라인 작업자 L1** | 전 직급 (현장 PWA) | All (Shell 외부) |
| `/hr` | HR 관리자 L5 | 본인 셀프서비스 | All (탭별 분기) |
| `/admin` | IT 관리자 L4+ | 보안 담당 | L3+ |
| `/chat` | 신입사원 L1 | 전 직급 | All |
