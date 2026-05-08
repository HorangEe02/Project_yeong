# Changelog

## [v3.5] — 2026-04-03 (UX 개선 + 다운로드 확장 + 모델 정리 + 인코딩 수정)

### 문서 다운로드 확장
- **CSV/XLSX 내보내기**: 기능 B 문서 작성(7열), 검색 패널(5열), 양식 다운로드(5열) 전체 적용
- **`tabular_exporter.py`** (신규): 마크다운 테이블/Key-Value 자동 파싱 → CSV(BOM)/XLSX 변환
- **시트명 금지문자 치환**: openpyxl `/\*?:[]` → `_` 자동 처리

### AI 도우미 다운로드 영구화
- **근본 수정**: `st.write_stream()` 1회성 렌더링 문제 해결 — session_state `_downloads`에 바이트 저장
- **4포맷 지원**: DOCX/XLSX/CSV/TXT 동시 다운로드, rerun 후에도 버튼 유지
- **메모리 관리**: 최근 20개 메시지만 다운로드 바이트 유지

### 인사관리 탭 통합 + 이력 다운로드
- **이력 탭 → 보안 탭 통합**: Tier 4(7→6탭), Tier 3(5→4탭), 접이식 expander로 상세 이력 배치
- **CSV/XLSX 다운로드**: 날짜 필터 + 전체 컬럼(타임스탬프/사번/부서/IP/User-Agent)
- **sqlite3.Row 호환성 수정**: tuple 변환 추가

### Light 모드 로고 수정
- **`ajin_logo_light.svg`** (신규): 텍스트 `fill:#fff` → `fill:#2C241A` (다크 브라운)
- **테마별 자동 전환**: `get_current_theme()` 기반 로고 SVG 동적 선택 (로그인 + 사이드바)

### 법규 모니터링 구조 개선
- **4탭 구조**: 법규 모니터 / **법규 업데이트** / 사업장 / 법규 문서 (메인 탭 승격)
- **법규 업데이트 탭 통합**: 시나리오 TOP-3 대시보드 + 변경 감지 메트릭 + 필터 + CSV 내보내기 + 전후 비교
- **크롤링 관리**: 실행 버튼 상단 이동 + 빠른 현황 요약 라인
- **한글 깨짐 복원**: U+FFFD 19개 수정 (리스크 점수, 돌아가기, 필요 조치 사항 등)

### 인코딩 안정성 강화
- **`_safe_truncate()`**: 멀티바이트 한글 안전 잘림 함수 (change_detector.py 4곳 적용)
- **UTF-8 PRAGMA**: compliance_changes.db, compliance.db 초기화 시 명시
- **ISO 크롤러**: HTTP 응답 인코딩 `charset_encoding or "utf-8"` 명시

### SPC 데이터 관리
- **`spc_data_generator.py`** (신규): 정규분포 시뮬레이션 + Nelson Rules 시나리오 주입
- **CSV 업로드 UI**: 공정 선택 → 업로드 → 미리보기 → 적용
- **샘플 재생성**: 전체 5공정 일괄 재생성 (샘플 수/시드 설정)

### Ollama 모델 정리
- **모델 프로필 재구성**: 5개 패밀리 10개 모델 (Qwen3.5/EXAONE/Gemma4/GPT-OSS/Nemotron)
- **비전 모델 교체**: qwen3-vl/llama3.2-vision/gemma3 → Gemma 4 멀티모달
- **불필요 모델 삭제**: 15개 삭제 (68.3GB 절약, 161.5GB → 93.2GB)
- **fallback 목록 갱신**: gemma3 → gemma4 교체

### 대시보드 갱신
- **6개 모듈 카드**: A~F 전체 표시 (E. 인사관리, F. 설비/SPC 신규 추가)
- **시스템 정보**: LLM 4패밀리, 비전 Gemma4, ML/DL 7모델, XLSX/CSV 출력, SPC DB
- **버전 표기**: v3.4 → v3.5 전체 갱신

---

## [v3.4] — 2026-04-03 (v3.2 가이드 전면 구현 + UI 고도화 + Dark 모드 개선)

### Dark 모드 가독성 강화
- **전체 UI**: `--hud-text-dim` 색상 `#B0A898` → `#D5CFC5` (명암비 5.2:1 → 8.5:1, WCAG AAA)
- **17개 파일 ~90개소** var() 폴백 색상 일괄 교체 (라이트 모드 영향 없음)
- **Plotly 차트/조직도**: 서브 텍스트 색상 동기화

### 한글 글씨 크기 +2px 증가
- **17개 UI 파일 172줄** font-size 일괄 증가 (10px→12px, 11px→13px, 12px→14px, 13px→15px, 14px→16px)
- `hud_tokens.py` FONT_SIZES 토큰 동기화

### Feature C — AI 업무 도우미
- **부서 selectbox 고정** (v3.4): SYS_ADMIN/HR_ADMIN 외 사용자는 소속 부서 변경 불가 (`disabled=True`)
- **SOP 5종 추가**: PPAP(5단계), 8D Report(5단계), ECN(3단계), 프레스 트라이(4단계), 금형 입고(3단계) → 총 8종
- **`collaboration_guide.py`** (신규, 200줄): 부서 간 협업 시나리오 5종 (8D/ECN/SPC/PPAP/안전점검), 키워드 매칭 즉시 응답
- **퀴즈 재학습 경로**: `related_step` 필드 추가, 오답 시 "Step N 다시 보기" 버튼 + 정답 시 "다음 퀴즈"/"학습 완료" 분기
- **온보딩 진행률 바**: `st.progress()` → HUD 스타일 HTML 바 (Day N/5, 색상 코딩)
- **데모 빠른 질문**: 생산기술팀 질문 6개 교체 (SOP/협업 시나리오 트리거)
- **스트리밍 중 네비게이션 차단**: `is_streaming` 플래그 → 사이드바 버튼 `disabled` + "(응답 생성 중...)" 표시

### Feature D — 법규 모니터링
- **`demo_scenario_engine.py`** (신규, 260줄): 데모 시나리오 3종 (산안법 85점/관세 78점/REACH 52점) + Before/After JSON 자동 생성
- **원 페이지 대시보드**: 4개 메트릭 카드 + TOP-3 시나리오 카드 + "시뮬레이션 실행" 버튼
- **시나리오 시뮬레이션 결과**: 변경 비교 (취소선/강조) + 리스크/시행일/영향시설/필요조치 + 관세 시뮬레이터 연동
- **챗봇 연동**: `regulation_status` 액션 (키워드→시나리오 매칭 + 전체 요약)

### Feature E — 인사 관리
- **본부/부서 selectbox 오류 수정**: `_on_div_change()` 레이스 컨디션 해소 — `_on_dept_change()` 직접 호출 제거, 세션 기반 부서 리스트 동기화

### Feature F — 설비/공정 AI
- **SPC 분석 탭 신설** (4탭 구조): 5공정 건강 신호등 그리드 + 공정 선택 + Nelson 관리도 + Cpk 통합 요약
- **`spc_dashboard.py`** (신규, 130줄): `ProcessHealth` + `SPCDashboard.get_all_process_health()`
- **`NELSON_RULE_GUIDE`** (spc_realtime.py): 8규칙 × 원인/조치/심각도/차트 주석 + `enrich_violations()`
- **Nelson 차트 Annotation**: Plotly `add_vrect()` 음영 + `add_annotation()` 텍스트 풍선
- **데모 합성 데이터 강화**: 공정별 Nelson 패턴 주입 (EWP: R2+R3, CCH: R1, 범퍼: R5, 시트레일: R3)
- **에러 검색 고도화**:
  - 동의어 39→79개 (`EQUIPMENT_SYMPTOM_SYNONYMS` 7장비 40카테고리)
  - `error_history_db.py` (신규): 에러 발생 이력 DB + 시딩 685건
  - `search_with_context()`: 검색 + 이력 요약 + Markov 연쇄 경고 통합
  - 카드 UI: 이력 메트릭(3개월 N회/평균 M분/추세/주원인) + 👍/👎 피드백 + Markov 인라인
- **증상 카테고리 드롭박스**: `EQUIPMENT_SYMPTOM_CATEGORIES` (7장비 40증상) + 2단계 selectbox + 전체 가이드 Expander
- **개요 탭 5개 하위 탭 분리**: 설비개요 / 긴급조치 / 장비유형별 / 예측정비 / ML엔진
- **매뉴얼 AI 3개 하위 탭 분리**: 에러코드 조회 / 증상별 검색 가이드 / 매뉴얼 AI 질의
- **챗봇 ML 검색 연동**: 자연어 증상 → `ml_search_with_context()` (기존 `lookup_error()` 대체), 키워드 16개 확장
- **SPC 챗봇 연동**: `_action_spc_status()` 실제 데이터 반환 (bridge redirect → 공정 건강 요약)
- **피드백 수집**: `save_feedback()` + `search_feedback.db`

### 버그 수정
- Markov 연쇄 예측 UI 속성명 수정 (`chain.path` → `chain.steps`)
- `page_onboarding.py` 협업 시나리오 로컬 import `UnboundLocalError` 수정
- `page_compliance.py` 시뮬레이션 오류 시 세션 키 미삭제 stuck state 수정
- `page_onboarding.py` 퀴즈 radio key 재사용 → 동적 key로 변경
- `generate_spc_ml_data.py` Nelson Rule 5 사이드 교대 → 같은 방향 고정
- `error_history_db.py` `makedirs("")` 빈 경로 가드
- `work_actions.py` `"컴플라이언스"` 유니코드 깨짐 수정
- `page_equipment.py` SPC 탭 `hud_panel_title()` 반환값 미사용 수정, Cpk 0.0 falsy 체크 수정

### 파일 통계
- 신규 Python 모듈: **6개** (spc_dashboard, error_history_db, collaboration_guide, demo_scenario_engine, seed_error_history, seed_error_history)
- 수정 Python 파일: **~20개** (UI 6 + 백엔드 8 + 스크립트 2 + 스타일 4)
- 신규 데이터: error_history.db (685건), demo_scenarios/ (6 JSON), SPC 재생성 (10,000건)
- 총 추가/수정 코드: **~3,000줄**

---

## [v3.3] — 2026-04-01 (보안 강화 + UX 개선 + 접근 제어 고도화 + 예측 정비)

### 보안 수정
- **`core/auth/session_store.py`**: 세션 폴백 자동 로그인 취약점 제거 — 쿠키 없으면 로그인 페이지로 이동 (admin 세션 탈취 방지)

### 비밀번호 정책 강화
- **`ui/page_login.py`**: 비밀번호 조건 안내 HUD 스타일 박스 + `_render_password_strength_indicator()` 실시간 강도 표시 함수 추가 (6개 조건 ✓/✗ + 진행 바)
- **`ui/page_profile.py`**: 비밀번호 조건 안내 동일 스타일로 통일 + 실시간 강도 표시 연동
- 3곳 모두 `validate_password_strength()` 서버 사이드 검증 적용 (기존 "6자 이상" → "8자+대소문자+숫자+특수문자+연속3회 금지")

### Feature C — AI 업무 도우미
- **`ui/page_onboarding.py`**: 소속 부서 selectbox 기본값 자동 선택 (`user_department` 세션 기반)
- **`features/onboarding/department_router.py`**: `DEPARTMENT_ALIASES` public export (레거시 부서명 매핑)
- **`ui/page_onboarding.py`**: 바로가기 버튼 + AI bridge 버튼에 `is_menu_visible()` 부서 권한 체크 추가

### Feature B — 문서 작성
- **`features/draft/template_exporter.py`**: Jinja2 변수 매핑 불일치 12건 해소 (8D/ECN/회의록 등), 발신자 파싱 오류 수정 (부서 접미사 감지), `.hwpx` → `.odt` 확장자 변경
- **`ui/doc_search_panel.py`**: HWPX → ODT MIME 타입/라벨 변경
- **`ui/page_draft.py`**: HWPX → ODT 라벨/확장자/MIME + 메트릭 표시 변경

### Feature E — 인사 관리
- **`core/auth/department_config.py`**: 17 → 30개 부서 접두어 매핑 확장 (config.py 29개 부서 + 독립부서 1개 전체 커버)
- **`ui/page_admin.py`**: 부서 selectbox `on_change` 콜백 — 부서/본부 변경 시 사원번호 접두어 자동 갱신

### Feature D, F — 부서 기반 접근 제어
- **`core/auth/permissions.py`**: `COMPLIANCE_MENU_DEPARTMENTS` (7개), `EQUIPMENT_MENU_DEPARTMENTS` (14개), `is_menu_visible()` 함수 신규
- **`ui/hud_left_panel.py`**: `_get_allowed_modules()` 에 부서 기반 메뉴 필터 추가
- **`ui/page_equipment.py`**: 페이지 진입 시 부서 접근 제어 방어 코드 추가
- **`ui/page_compliance.py`**: 페이지 진입 시 부서 접근 제어 방어 코드 추가

### Feature F — 설비/공정 AI
- **`ui/page_equipment.py`**: 4탭 → 3탭 (도면 탭 삭제), 예측 정비 대시보드 섹션 추가, ML 엔진 목록에 Maintenance MTBF 추가
- **`features/equipment/maintenance_predictor.py`** (신규, 359줄): 수리 이력 기반 MTBF 분석 엔진 — 15대 기계, 2년치 가상 데이터 240건, 계절별/주기별 패턴, 다음 정비 예측, 위험도 분류, 비용 TOP 5

### Dark 모드 가독성
- **`ui/hud_style.py`**: `--hud-text-dim: #8A7E6E` → `#B0A898` (명암비 3.5:1 → 5.2:1, WCAG AA 충족)
- **`ui/hud_tokens.py`**: `COLORS["dark_text_dim"]` 동기화
- **`app.py`**: AUTO 테마 모드일 때 현재 적용 테마 캡션 표시

---

## [v3.1] — 2026-03-30 (ML/DL 확장 + 6대 기능 심화)

### 기능 A — 인원 검색 고도화 (3개 모듈 신규)
- **`features/search/employee/semantic_search.py`** (신규, 282줄): FTS5 + ChromaDB 하이브리드 검색, RRF(Reciprocal Rank Fusion) 점수 통합, BGE-M3 임베딩
- **`features/search/employee/search_history.py`** (신규, 65줄): 세션 기반 검색 이력 (최근 10건) + 클릭 시 재검색 + 5종 정렬 옵션 (이름/부서/직급/입사일/관련도)
- **`features/search/employee/analytics.py`** (신규, 192줄): 인사 분석 대시보드 — 본부별/직급별/공장별/근속연수 통계 + Plotly 시각화 6종
- **`features/search/ml_intent_classifier.py`** (신규, 313줄): TF-IDF + LogisticRegression 의도 분류기 (5개 인텐트, 1,500건 학습 데이터, cross-validation)
- **`ui/page_search.py`**: 검색 이력 pill 버튼 + 정렬 드롭다운 + 인사 분석 대시보드 탭 (185줄 추가)

### 기능 B — 문서 작성 고도화 (5개 모듈 신규)
- **`features/draft/fewshot_rag.py`** (신규, 274줄): ChromaDB 기반 Few-shot RAG — 유사 문서 자동 검색 → LLM 프롬프트 주입 (문서 품질 향상)
- **`features/draft/doc_quality_scorer.py`** (신규, 231줄): 문서 품질 자동 채점 (A~F 등급) — 구조/분량/용어/완성도/톤 5축 평가 + TF-IDF 유사도
- **`features/draft/cc_recommender.py`** (신규, 121줄): 문서 유형 + 작성자 부서 기반 CC 수신자 자동 추천
- **`features/draft/doc_diff.py`** (신규, 58줄): difflib 기반 문서 버전 비교 — 추가/삭제/유지 라인 수 + HTML diff 하이라이팅
- **`features/draft/template_exporter.py`** (신규, 272줄): Jinja2 템플릿 렌더링 → DOCX/PDF/HWPX 내보내기 통합
- **`ui/page_draft.py`**: Few-shot RAG 주입 + 품질 등급 카드 + 버전 diff 비교 탭 (300줄 추가)

### 기능 C — AI 업무 도우미 고도화 (5개 모듈 신규)
- **`features/onboarding/sop_guide.py`** (신규, 163줄): SOP 가이드 엔진 — 질문→SOP 자동 매칭 + 단계별 절차 렌더링
- **`features/onboarding/quiz_engine.py`** (신규, 146줄): SOP/용어집 기반 퀴즈 자동 생성 (4지선다 + 체크리스트 유형)
- **`features/onboarding/work_actions.py`** (신규, 169줄): 업무 모드 액션 라우터 — 에러코드 조회, SPC 분석, 문서 작성 등 교차 기능 실행
- **`features/onboarding/context_optimizer.py`** (신규, 205줄): RAG 컨텍스트 리랭킹 + 중복 제거 + 토큰 버짓 관리 (LLM 효율 최적화)
- **`features/onboarding/stream_response.py`** (신규, 118줄): Ollama 실시간 스트리밍 응답 + 토큰 필터링
- **`ui/page_onboarding.py`**: ML 의도 분류 통합 + SOP 자동 가이드 + 퀴즈 렌더링 + 업무 액션 실행 (240줄 추가)

### 기능 D — 법규 모니터링 고도화 (8개 모듈 신규)
- **`features/compliance/risk_scorer.py`** (신규, 185줄): 정량 리스크 스코어링 (0~100) — 영향도 × 가능성 × 긴급도 가중 평균
- **`features/compliance/timeline_builder.py`** (신규, 143줄): 규제 기한 타임라인 (Plotly Gantt) + 리스크 레이더 차트
- **`features/compliance/tariff_simulator.py`** (신규, 99줄): 관세 영향 시뮬레이터 — 세율/환율 슬라이더 + 제품별 영향 테이블
- **`features/compliance/regulation_classifier.py`** (신규, 216줄): TF-IDF + RandomForest 규제 위험 자동 분류 (HIGH/MEDIUM/LOW + 신뢰도)
- **`features/compliance/impact_network.py`** (신규, 171줄): 규제→시설→부서/제품 영향 네트워크 그래프 (Plotly)
- **`features/compliance/impact_analyzer.py`** (신규, 263줄): LLM 기반 영향 분석 + 룰 기반 스코어링 하이브리드
- **`features/compliance/text_change_detector.py`** (신규, 185줄): 규제 텍스트 변경 감지 (difflib) + 수치 변경 자동 추출
- **`features/compliance/change_detector.py`** (신규, 179줄): JSON diff 규제 변경 감지 + SQLite 이력 관리
- **`ui/page_compliance.py`**: 리스크 대시보드 + 기한 타임라인 + 관세 시뮬레이터 + AI 위험 분류기 (380줄 추가)

### 기능 E — 관리 고도화 (2개 모듈 신규)
- **`features/admin/usage_analytics.py`** (신규, 316줄): AI 시스템 사용 분석 — 기능별/부서별/시간대별 사용량 + DAU + 피드백 통계 + ROI 추정
- **`features/admin/security_monitor.py`** (신규, 244줄): 보안 이상 탐지 — 브루트포스/비정상 시간대/비활성 계정 접근 감지
- **`ui/page_admin.py`**: 7탭 구조 확장 (ANALYTICS + SECURITY + HR STATS 추가) + ROI 대시보드 + 히트맵 (550줄 추가)

### 기능 F — 설비/공정 AI 고도화 (7개 모듈 신규)
- **`features/equipment/spc_ml_predictor.py`** (신규, 650줄): Isolation Forest 이상 탐지 + 이동 윈도우 Cpk 예측 (LinearRegression)
- **`features/equipment/spc_realtime.py`** (신규, 369줄): **Nelson 8 Rules** 실시간 SPC 이상 감지 (8가지 통계적 패턴 규칙)
- **`features/equipment/markov_predictor.py`** (신규, 428줄): Markov Chain 연쇄 고장 예측 — 70+ 인과 규칙 + 캐스케이드 체인 추적
- **`features/equipment/mold_ml_predictor.py`** (신규, 554줄): **XGBoost** 금형 수명 예측 + 배스터브 곡선 + 교체 시기 경고
- **`features/equipment/ml_error_search.py`** (신규, 403줄): TF-IDF 에러코드 ML 검색 (201건 + 한국어 동의어 확장)
- **`features/equipment/error_causality.py`** (신규, 282줄): 70+ 인과관계 규칙 정의 + Markov용 합성 이벤트 시퀀스 생성
- **`features/equipment/dashboard_data.py`** (신규, 199줄): 설비 대시보드 데이터 집계 (ML 모델 상태 + 경고 수준)
- **`ui/page_equipment.py`**: OVERVIEW 탭 신설 + ML 에러 검색 + Nelson Rules + Cpk 예측 + 금형 수명 예측 (450줄 추가)

### ML 모델 6종 — 학습 데이터 + 모델 파일
- **ML_01 SPC 이상 탐지**: `data/spc_ml/` 5공정 CSV + Isolation Forest (`spc_ml_predictor.py`)
- **ML_02 에러코드 TF-IDF**: TF-IDF + cosine similarity 201건 인덱싱 (`ml_error_search.py`)
- **ML_03 금형 XGBoost**: `data/mold_ml/mold_training_data.csv` + `xgb_mold_life.pkl` (`mold_ml_predictor.py`)
- **ML_04/07 문서품질+규제위험**: `data/regulation_ml/` + TF-IDF+RF 분류기 (`doc_quality_scorer.py`, `regulation_classifier.py`)
- **ML_05 의도 분류기**: `data/intent_ml/intent_training_data.csv` + TF-IDF+LR `.pkl` (`ml_intent_classifier.py`)
- **ML_06 Markov 고장**: `data/markov_ml/event_sequences.json` + `markov_model.pkl` (`markov_predictor.py`)

### 데이터 생성 스크립트 (4개 신규)
- **`scripts/generate_spc_ml_data.py`**: SPC ML 학습용 합성 측정 데이터 생성
- **`scripts/generate_mold_ml_data.py`**: 금형 수명 ML 학습용 합성 데이터 생성
- **`scripts/generate_intent_data.py`**: 의도 분류기 학습용 1,500건 합성 데이터 + 텍스트 증강
- **`scripts/generate_regulation_data.py`**: 규제 위험 분류기 학습용 합성 데이터 생성

### UI 공통 개선
- **`ui/doc_search_panel.py`** (신규, 550줄): 통합 문서 검색/템플릿 다운로드 패널
- **`ui/plotly_theme.py`** (신규, 45줄): 다크/라이트 테마 연동 Plotly 차트 통합 테마
- **`ui/hud_style.py`**: v3.1 컴포넌트 CSS 스타일 보강
- **`ui/hud_top_bar.py`**: 상단 바 v3.1 표기 반영
- **`ui/hud_right_panel.py`**: ML 모델 상태 게이지 연동

### 파일 통계
- 신규 Python 모듈: **35개** (features 30 + scripts 4 + ui 1)
- 수정 Python 파일: **18개** (UI 페이지 10 + 기존 모듈 8)
- 신규 ML 모델 파일: **6종** (.pkl + .csv)
- 총 추가 코드: **~7,500줄** (백엔드) + **~2,100줄** (UI) = **~9,600줄**
- 총 프로젝트 규모: 174 → **~210개** Python 파일, **~55,000줄**

---

## [v3.0.1] — 2026-03-28 (HUD 대시보드 UI 전면 개편)

### HUD 커맨드 센터 대시보드 (Phase 0~7)
- **`ui/hud_tokens.py`** (신규): 디자인 토큰 — 60-30-10 컬러, A2Z 폰트, 레이아웃 상수
- **`ui/hud_top_bar.py`** (신규): 상단 고정 상태 바 (ENV/AUTH/LLM ENGINE/VECTOR DB/RBAC LEVEL)
- **`ui/hud_layout.py`** (신규): 3컬럼 레이아웃 — 사이드바 240px + 중앙:우측 4:0.8 비율
- **`ui/hud_left_panel.py`** (신규): CORE MODULES 네비 (SVG 아이콘 + 영문/한글) + SYSTEM REGISTRY + SECURITY LOG
- **`ui/hud_center_panel.py`** (신규): SQL 입력 바 + 결과 카드 + AI SESSION MEMORY
- **`ui/hud_right_panel.py`** (신규): 콤팩트 GPU 게이지(80px SVG) + 레이턴시 + DATA INGESTION 프로그레스

### 폰트 시스템 교체
- JetBrains Mono → **에이투지체(A2Z)** 로컬 폰트 (base64 @font-face, 4 weight: 400/500/600/700)
- Noto Sans KR 한글 fallback 유지
- Material Icons 보호 CSS 추가 (아이콘 폰트 깨짐 방지)

### UI 전면 재구성
- **`ui/hud_style.py`** 전면 교체: CSS 변수 기반, 다크/라이트 지원, `safe_html()` 유틸리티 추가
- **`app.py`** 전면 재구성: 상태 바 + 3컬럼 + CORE MODULES 네비 + 페이지 라우팅
- **`ui/icons.py`**: `equipment`, `analytics`, `toggle_panel` SVG 아이콘 추가 + `get_svg_data_uri()` 함수
- 모든 페이지(10개 파일): `st.markdown(unsafe_allow_html)` → `safe_html()` 교체
- 모든 하드코딩 색상/폰트 → CSS 변수(`var(--hud-*)`) 일괄 전환

### 기능 C 리브랜딩
- "온보딩 챗봇" → **"AI 업무 도우미 (AI WORK ASSISTANT)"** 전면 명칭 변경
- 사이드바, 페이지 헤더, 대시보드, RBAC 메뉴, LLM 프롬프트 모두 반영
- 모드 라벨: "🎓 온보딩 / 💼 업무" → "교육 모드 / 업무 모드"

### 업무 모드 2단 구조 응답
- LLM 출력을 `[요약]` + `[상세]` 2단 구조로 생성
- 요약: 3문장 이내 핵심 답변 (바로 표시)
- 상세: 500자 이내 용어 설명 + 실무 맥락 (`st.expander`로 접기/펼치기)
- 시스템 프롬프트에 플레이스홀더(`{user_query}`, `{glossary_info}` 등) 추가 — 질문 컨텍스트 주입 수정

### 우측 패널 콤팩트 + 토글
- GPU 게이지: 160px → 80px (50% 축소)
- 프로그레스 바: 높이 4px→3px, 간격 14px→8px
- `HIDE`/`SYS` 토글 버튼으로 우측 패널 표시/숨김 전환
- 숨김 시 메인 콘텐츠 전체 폭 사용

### 사이드바 개선
- 배치 순서: DASHBOARD → 테마 → CORE MODULES → SYSTEM REGISTRY → SECURITY LOG
- CORE MODULES: SVG 아이콘 + 영문 (한글) 라벨 1행 통합
- 사이드바 접힘 시 빈 공간 제거 (`aria-expanded="false"` → width: 0)

### 모바일 반응형 CSS
- `@media (max-width: 768px)`: 상단 바 압축, 사이드바 0px, 메트릭 2열 wrapping, 폰트/패딩 축소
- `@media (max-width: 480px)`: ENV/AUTH 숨김, 메트릭 1열, 탭 8px

### 탭 이모지 → 텍스트 전환
- 5개 페이지(equipment/admin/profile/onboarding/draft)의 24개 탭 라벨에서 이모지 제거
- HUD 대문자 텍스트만 유지

### 교차 기능 네비게이션 수정
- **`core/feature_bridge.py`** 전면 재작성: `_nav_override` → `active_module` 키 직접 설정
- 바로가기 버튼(인원 검색/문서 양식/설비 에러코드) 정상 동작 복원

### 외부 접속 지원
- ngrok 터널링 설정 (`ngrok http 8502`)
- 5G/LTE 모바일에서 외부 URL로 접속 가능

### 버그 수정
- `page_compliance.py` SyntaxError: f-string 내 `'A2Z'` 따옴표 중첩 충돌 수정
- Streamlit `st.markdown` HTML 주석(`<!-- -->`) 파싱 깨짐 → 주석 제거
- Streamlit 4칸 들여쓰기 HTML이 코드블록으로 렌더링 → `safe_html()` + `textwrap.dedent` 적용
- Material Icons 아이콘 폰트가 A2Z로 덮어씌워짐 → 보호 CSS 셀렉터 추가
- 로그인 페이지 버전 표기: v2.2 → v3.0

---

## [v3.0] — 2026-03-28

### 공통 인프라 — Phase 0: 부서 컨텍스트 시스템
- **`core/auth/user_context.py`**: UserContext dataclass (12필드 + 5프로퍼티 + 27부서→본부 매핑)
- **`core/auth/visibility.py`**: 3-Tier 가시성 (FULL/PARTIAL/HIDDEN) + email 마스킹 + phone 숨김
- **`core/department_config.py`**: 29개 부서 레지스트리 (doc_priority, cc_targets, glossary_focus, quick_questions, onboarding_essentials)
- **`core/auth/context_middleware.py`**: 문서유형 스마트 정렬 + 직급 기반 톤 자동설정 + LLM 컨텍스트 빌드
- **`core/auth/permissions.py`**: 28개 세부 권한 (Compliance 12 + Admin 16) + Tier 판정
- **`core/feature_bridge.py`**: 교차 기능 내비게이션 6개 함수 (navigate_to, go_to_email_compose 등)

### 기능 A — 검색 고도화
- **`features/search/employee/fts_index.py`**: FTS5 전문 검색 (unicode61 토크나이저, 329건 인덱싱)
- **`features/search/employee/text_to_sql.py`**: 자연어→SQL 변환 + 위험 SQL 차단 (DROP/DELETE/UPDATE)
- **`ui/page_search.py`**: 가시성 필터 적용 + 교차 네비게이션 버튼 ("이메일 작성" / "문서 작성")

### 기능 B — 문서 작성 고도화
- **`features/draft/search_engine.py`**: 가중치 BM25 검색 (title 3.0, doc_type 2.5) + 9종 문서유형 자동 감지
- **`features/draft/version_db.py`**: 문서 버전 영구 저장 (SQLite) + 이력 조회 + 롤백 지원
- **`ui/page_draft.py`**: 3탭 구조 (내부용/외부용/🕘 문서 이력) + 자동 버전 저장 + bridge_params 수신

### 기능 C — 온보딩 챗봇 고도화
- **`features/search/intent_router.py`**: 하이브리드 의도분류 (키워드 점수 + LLM 폴백, SCORE_GAP_THRESHOLD=2)
- **`features/onboarding/feedback_db.py`**: 👍👎 만족도 수집 + 인텐트별/부서별 통계
- **`features/onboarding/conversation_memory.py`**: 대화 요약 메모리 (10턴 초과 시 자동 요약, LLM 실패 시 키워드 폴백)
- **`features/onboarding/proactive_engine.py`**: 선제적 가이드 (미탐색 필수 항목 자동 추천 + 온보딩 진행률)
- **`features/onboarding/curriculum.py`**: 학습 커리큘럼 (기초→핵심→심화 3단계 + SQLite 진행 추적)
- **`ui/page_onboarding.py`**: 듀얼 모드 전환 (🎓 온보딩 / 💼 업무) + 모드별 시스템프롬프트 분기 + 진행률 바 + QUICK NAV 3버튼

### 기능 D — 접근 제어 적용
- **`ui/page_compliance.py`**: 3-Tier 권한 분기 (VIEW/ANALYZE/OPERATE) + 7건 disabled 패턴 + Tier 배지

### 기능 E — 접근 제어 적용
- **`ui/page_admin.py`**: 4-Tier 권한 분기 (SELF/TEAM/DEPT/SYSTEM) + 팀 조회 자기팀/타팀 분기

### 기능 F — 설비/공정 AI 대폭 확장
- **`features/equipment/drawing_search.py`**: 도면 검색 DB (15건 시딩, 번호/키워드 검색, BOM 정보)
- **`features/equipment/inspection_db.py`**: 설비 점검 이력 (6종 템플릿 46항목, 점검 기록 저장/조회)
- **`ui/page_equipment.py`**: 5탭 UI (매뉴얼/SPC/금형/도면검색/점검이력) — 도면+점검 2탭 신규
- **`scripts/seed_synthetic_data.py`**: 합성 데이터 시딩 (에러코드 201건 + 금형 25건 + SPC 5공정×50측정값)

### 백엔드 보안 계층
- **`backend/auth_middleware.py`**: JWT→UserContext 복원 + 감사 로그 DB (audit.db)
- **`backend/dependencies.py`**: `get_current_user()` + `get_optional_user()` + `require_permission()` 의존성
- **`backend/main.py`**: CORS Authorization 헤더 허용
- **`backend/routers/compliance.py`**: 3개 엔드포인트 인증 필수 + `compliance.run_analysis` 권한 체크
- **`backend/routers/employee.py`**: 인증 필수 + 가시성 필터 (PARTIAL→마스킹, HIDDEN→제외) + 감사 로깅
- **`backend/routers/draft.py`**: 감사 로깅 (문서 생성/내보내기 추적)
- **`backend/routers/onboarding.py`**: 토큰에서 부서 자동 주입

### 라이트 테마 — 60-30-10 컬러 시스템
- **`ui/hud_style.py`**: 안 B "웜 크림 + 앰버 브라운 + 아진 골드" 적용
  - 60% 기본: `#FAF8F5` 배경, `#FFFFFF` 카드, `#2C241A` 텍스트
  - 30% 보조: `#F0EBE3` 사이드바, `#D6CFC3` 보더, `#7A6E5E` 보조텍스트
  - 10% 강조: `#C88A00` CTA 버튼, `#F9A70D` 활성 탭 밑줄
- 다크 CSS 하드코딩 → CSS 변수 기반 전환 (var(--hud-surface2) 등)
- 3단계 specificity 방어: CSS 변수 → `.stApp` 접두어 → `html body .stApp` 최종 보장

### 데이터 시딩
- 에러코드: 8건 → **201건** (프레스 47, 용접기 30, 로봇 31, 사출기 40, 공통 33, CNC 10, 레이저 10)
- 금형: 3건 → **25건** (EWP/CCH/OBC/범퍼/서브프레임/시트/도어/브레이크 + 보전 이력)
- SPC: 0건 → **5공정 × 50측정값** (EWP 내경, CCH 두께, OBC 평탄도, 범퍼 너겟, 시트레일 홀)
- 도면: 0건 → **15건** (EWP/CCH/OBC/BMS/범퍼/서브프레임/시트/연료탱크/도어/브레이크)
- 점검 템플릿: 0건 → **6종 46항목** (프레스/용접기/로봇 일상+정기)

---

## [v2.7] — 2026-03-27

### 기능 E — 사용자 관리 고도화

#### 사용자 목록 — 부서/직급/이메일/연락처/입사일/퇴사일 인라인 변경
- **`ui/page_admin.py`**: 사용자 expander 내 편집 영역 3행 확장
  - **행 1**: 부서 변경 / 직급 변경 / 역할 변경 (selectbox + 적용)
  - **행 2**: 이메일 / 연락처 / 입사일 / 퇴사일 (text_input + date_input + 📝 저장)
  - **행 3**: 🔑 PW 초기화 / 🔴🟢 상태 변경
  - `sqlite3.Row` `.get()` 에러 수정 → `dict(user).get()` 또는 `user["key"]` 사용
  - 모든 UPDATE에 `updated_at=datetime('now')` 타임스탬프 추가

#### 사용자 생성 — 상태/입사일/퇴사일 필드 추가
- **`ui/page_admin.py`**: 생성 폼 3단계로 확장 (1️⃣ 부서 → 2️⃣ 사원 정보 → 3️⃣ 인사 정보)
  - **상태**: 활성/비활성 선택 (기존: 항상 활성)
  - **입사일**: `st.date_input()` — 기본값 오늘 날짜
  - **퇴사일**: `st.date_input()` — 재직 중이면 비워둠
  - INSERT SQL에 `hire_date`, `resign_date` 포함

#### DB 마이그레이션
- **`core/auth/database.py`**: `_migrate_columns`에 `hire_date TEXT`, `resign_date TEXT` 추가
  - 기존 사용자 데이터 유지 (ALTER TABLE ADD COLUMN)
  - 앱 재시작 시 자동 마이그레이션

#### 사용자 목록 표시 개선
- expander 내 사용자 상세에 **입사일** / **퇴사일(재직 중)** 표시 추가

#### 테스트 계정 데이터 정비
- 기존 13명 테스트 계정에 부서/직급/이메일/연락처/입사일 일괄 입력
- 19개 부서별 1명씩 신규 테스트 계정 생성 (총 33명)
  - 직급 분포: 부장 1, 차장 1, 과장 3, 대리 4, 주임 3, 사원 7
  - 역할 자동 배정: 부장·차장 → TEAM_LEAD, 과장 → MANAGER, 나머지 → EMPLOYEE

#### 버그 수정
- `sqlite3.Row` `.get()` AttributeError 수정 (필터링 + 표시 3곳)
- 기능 B `download_button` DuplicateElementKey 수정 (`key_prefix` 매개변수 추가)
- 기능 C 파일 업로드 후 LLM 참조 안 되는 버그 수정 (`uploaded_file_text` 세션 변수 확인)
- 기능 C 파일 업로드 확장자 추가 (`.xlsx`, `.xls`, `.pptx`, `.doc`)

---

## [v2.6] — 2026-03-27

### 기능 A — 조직도 시각화 개선

#### 전체 조직도 간소화
- **`features/search/employee/org_chart.py`**: `create_org_tree_html()` — 팀(부서) 노드 제거
  - 기존: 대표이사 → 7본부 → **27팀** → 해외법인 (가로 ~3,240px, 스크롤 필수)
  - 변경: 대표이사 → **7본부만** → 해외법인 (가로 ~900px, 스크롤 불필요)
  - 본부 카드에 "N팀 · N명" 요약 표시
  - 본부 카드 호버 시 소속 팀 이름 목록 툴팁 표시
  - 팀 단위 상세는 아래 부서별 조직도에서 확인

#### 부서별 조직도 — 직급별 행 그리드 레이아웃
- **`features/search/employee/org_chart.py`**: `create_dept_org_chart_html()` 완전 재작성
  - 기존: CSS 트리 수직 체이닝 (직급 노드 + 개인 카드 혼합) → 가독성 저하
  - 변경: **직급별 행(Row) 배치** — 같은 직급의 카드들이 한 행에 나란히 표시
  - 팀장 행: 최상단 골드 보더 강조 카드
  - 직급별 색상: 임원(레드) / 부장·차장(골드) / 과장·대리(그린) / 주임·사원(블루)
  - 각 카드: 이름(볼드) + 직급 + 내선번호, 호버 시 전화/이메일 상세 표시
  - `flex-wrap` 적용 — 인원 많은 직급에서 자동 줄바꿈
- **신규 함수**: `_dept_chart_css()`, `_pos_level_class()` — 직급별 행 그리드 CSS 및 스타일 매핑

#### 부서 프로필 전면 업데이트 (공식 직무 소개 기반)
- **`features/onboarding/department_router.py`**: `DEPARTMENT_PROFILES` 11 → **31개** 부서
  - **데이터 출처**: [아진산업 공식 직무소개](https://www.wamc.co.kr/bbs/content.php?co_id=jobIntro)
  - 20개 부서 신규 추가: 내부감사팀, 재무팀, 회계팀, 원가기획팀, 총무인사팀, ESG경영팀, 해외지원팀, 상생협력팀, 자재관리팀, 기술영업팀, 금형생산팀, 자동화기술팀, FA사업팀, 플랜트사업팀, 제품설계팀, 공법계획팀, 용기운영팀, 비전연구팀, 바디선행개발팀, 전장선행개발팀
  - 기술연구소: 통합 프로필 유지 + 바디선행/전장선행 개별 프로필 분리 추가
  - 각 프로필: 공식 홈페이지 직무 설명 기반 `core_responsibilities` 작성
- **`ui/page_onboarding.py`**: 부서 드롭다운 하드코딩 12개 → `DEPARTMENT_PROFILES`에서 동적 생성 (31개)

#### 시설 지도 좌표 누락 수정
- **`data/facility_db/plants.json`**: 신규 추가된 10개 시설의 lat/lng 좌표 추가
  - **근본 원인**: v2.6에서 추가된 시설에 좌표 미입력 → Folium 지도 렌더링 조건 `if lat is not None and lng is not None` 미충족 → 지도 안 보임
  - 자사 공장 2개: 경주 입실(35.7895, 129.3142), 경산 하양(35.9072, 128.8183)
  - 국내 계열사 5개: 카인텍 건천/모화, 우신산업, AJ아진, 준텍
  - 해외법인 3개: 소주A&T, WOOSHIN USA, AJECC USA, 베트남
  - **결과**: 19개 전 시설 좌표 보유 → 지도 정상 표시

#### 시설 마스터 데이터 전면 업데이트 (plants.json v4.0)
- **`data/facility_db/plants.json`**: 공식 홈페이지(wamc.co.kr) 기반 전면 업데이트
  - **자사 공장**: 3 → **5개** (경주 입실공장, 경산 하양공장 추가)
  - **국내 계열사**: 3 → **7개** (우신산업, AJ아진, 준텍 추가, 아진카인텍 건천/모화 분리)
  - **해외법인**: 6 → **7개** (WOOSHIN USA, 소주A&T, AJECC USA 추가, 기존 아진실업 유한공사 제거)
  - **총 시설**: 12 → **19개**
  - 전 시설 전화번호/팩스번호 추가
  - 홈페이지 URL 수정 (`ajin.co.kr` → `wamc.co.kr`)
  - 주소 정확도 향상 (공식 홈페이지 기준)

#### 기능 B — 보고서 양식 4건 추가 (v2.0_update 반영)
- **v2.0_update/보고서 기본 양식** 13개 파일 분석 → 프로젝트 미존재 양식 4건 추가
  - `data/templates/report/quality_improvement.j2` — **품질문제 개선대책서** (품질보증팀)
  - `data/templates/report/incident_report.j2` — **안전 인시던트 리포트** (안전보건팀, 산안법 제57조)
  - `data/templates/report/container_spec.j2` — **납입용기 규격 설정서** (생산관리팀/자재팀)
  - `data/templates/report/supply_dispatch.j2` — **사급 반출 요청서** (구매팀/자재팀)
- **`features/draft/template_catalog.py`**: "품질/안전 문서" + "생산/자재 문서" 2개 카테고리 추가 (기존 7→11 양식)
- **`features/draft/doc_type_config.py`**: 4건 입력 필드 + LLM 프롬프트 템플릿 추가 (기존 9→13 문서유형)
- **`data/templates/reference/`**: 원본 xls/pdf 6건 보관 (실제 양식 참고용)
- 재무/금융 양식 4건(대금수령계좌, 이용약정서 등)은 AI 시스템 범위 밖으로 제외

#### 조직도 가로 스크롤 컨트롤 + iframe 스크롤 최종 수정
- **`features/search/employee/org_chart.py`**: `_scroll_control_js()` 헬퍼 함수
  - 전체 조직도 + 부서별 조직도 하단에 ◀▶ 버튼 + 드래그 가능 스크롤바 추가
  - **3가지 스크롤 방식**: ① ◀▶ 버튼 클릭 ② thumb 마우스 드래그 (실시간 반영) ③ 콘텐츠 영역 grab & drag
  - **iframe 타이밍 버그 수정**: IIFE 즉시 실행 → `DOMContentLoaded` + 재시도 로직(최대 20회, 100ms 간격)으로 변경 — `st.html()` iframe 내 DOM 구성 전 스크립트 실행되어 이벤트 바인딩 실패하던 문제 해결
  - `addEventListener` → `onclick`/`onmousedown` 직접 바인딩으로 안정성 향상
  - 기능 A + 기능 C 양쪽 모두 적용

#### 기능 C — 라이트 모드 레터박스 수정
- **`ui/page_onboarding.py`**: ACTIVE MODEL 박스 라이트 모드 대응
  - **근본 원인**: `st.html()` + 하드코딩 다크 색상 (`#10161f` 배경, `#f9a70d` 텍스트)
  - 라이트 모드에서 검은 배경에 검은 글자 → 내용 불가시
  - **수정**: `st.html()` → `st.markdown(unsafe_allow_html=True)` + CSS 변수(`var(--hud-*)`) 적용
  - KNOWLEDGE BASE / DEPARTMENTS 카드도 동일하게 CSS 변수 대응

#### 기능 D — 규제 문서 관리 탭 3건 버그 수정
- **`ui/page_compliance.py`**: 규제 문서 관리 탭 3건 수정
  - **RESET 버튼 라이트 모드**: `type="secondary"` 명시 + 파일 존재 시에만 표시
  - **RESET → 실제 파일 삭제**: 세션 기반 숨김 → **2단계 확인 후 실제 파일 삭제** (되돌릴 수 없음 경고 → 삭제 확인/취소)
  - **규제 변경 비교 DuplicateElementKey 에러**: `_render_version_comparison()`이 규제 모니터링 탭(L937)과 문서 관리 탭(L1486)에서 **같은 json_filename으로 2번 호출** → 동일 key 생성. `key_prefix` 매개변수 추가하여 `"monitor"` / `"docs"` 구분 (예: `ver_cmp_monitor_iso_standards_json` vs `ver_cmp_docs_iso_standards_json`)

#### 기능 D — 규제 변경 비교 "이전 이력 없음" 수정
- **`ui/page_compliance.py`**: `_render_version_comparison()` 첫 스냅샷 자동 생성
  - **근본 원인**: 비교 기능이 `data/crawled/history/` 디렉토리의 백업 파일을 검색하지만, 최초 크롤링 시 백업 없이 직접 저장 → history 비어있음 → "이전 크롤링 이력이 없습니다" 항상 표시
  - **수정 1**: history가 비어있으면 현재 JSON을 첫 스냅샷으로 자동 복사 + "1개 버전만 있습니다" 안내
  - **수정 2**: 전체 크롤링(`run_all`) 시에도 `backup_before_crawl()` 호출 추가 (기존에는 개별 REFRESH만 백업)
  - **결과**: REFRESH 1회 실행 후 Before/After 비교 정상 동작

#### 기능 D — 저장된 규제 문서 RESET 버튼
- **`ui/page_compliance.py`**: `_render_regulation_docs()` 내 RESET 기능 추가
  - 저장된 문서 목록 상단에 🔄 RESET 버튼 배치
  - 클릭 시 `compliance_docs_hidden_ts` 세션 타임스탬프 저장 → 이전 파일 목록에서 숨김
  - **파일 삭제가 아닌 세션 기반 숨김** — 파일은 보존되며 앱 재시작 시 복원
  - RESET 후 새로 생성한 문서만 표시

#### 기능 D — 보고서 "적용 시설 상세" 섹션 추가
- **`features/compliance/regulation_exporter.py`**: `_build_plant_detail_section()` 함수 신규
  - `plant_regulation_mapper.get_applicable_plants(doc_type)`를 활용하여 규제 유형별 적용 시설을 자동 매핑
  - 카테고리별(자사/국내 계열사/해외법인) 테이블 생성: 시설명 · 보유 인증 · 주요 생산품
  - 모든 보고서(ISO, 국내법, EU, APQP, MSDS 등) 상단에 자동 삽입
  - 개별 항목의 `affected_plants`/`affected_processes` 배열 표시 추가 (국내법규 등)
  - **결과**: "아진산업 3개 공장 전체 인증 보유" → 각 공장의 인증/제품/역할 구체적 표시
  - EV 보고서: JOON INC(Georgia)만 표시 / 국내법: 국내 6개소 / ISO: 자사 3개소

#### 기능 D — APQP/MSDS 크롤러 + 보고서 수정 (3건)
- **`features/compliance/apqp_crawler.py`**: `APQPCrawlResult`에 `total_count` 프로퍼티 추가
  - **근본 원인**: UI가 `getattr(result, "total_count", 0)`으로 수집 건수를 추출하지만, `APQPCrawlResult`는 `total_phases`/`total_checklist_items`/`total_updates`로 분리 저장 → 항상 0
  - **수정**: `total_count` 계산 프로퍼티 추가 (`5 + 12 + 4 = 21건`)
- **`features/compliance/msds_crawler.py`**: `MSDSCrawlResult`에 `total_count` 프로퍼티 추가 (동일 패턴)
  - `total_records + len(svhc_updates)` = 10건
- **`features/compliance/regulation_exporter.py`**: APQP/MSDS 전용 마크다운 포매터 추가
  - **근본 원인**: 범용 변환기가 `key_requirements`/`compliance_status` 등 범용 필드명을 기대하지만, APQP(`key_activities`/`deliverables_ko`/`oem_requirements`)와 MSDS(`substance_name_ko`/`ghs_classification`/`hazard_statements`)는 고유 필드명 사용 → 보고서에 ID만 출력되고 내용 비어있음
  - **수정**: `_apqp_item_to_md()` — 5단계 프로세스 전용 (핵심 활동, 산출물, 게이트 리뷰, OEM 요구사항)
  - **수정**: `_msds_item_to_md()` — 화학물질 전용 (CAS No., GHS 분류, 위험 문구, CMR/SVHC, 노출 기준, 국내/국제 규제)
  - **결과**: APQP 보고서 508자 → 3,920자, MSDS 보고서 → 4,436자 (내용 풍부)

#### 기능 C — 파일 업로드 후 LLM 참조 안 되는 버그 수정
- **`ui/page_onboarding.py`**: 텍스트 파일 업로드 시 LLM이 내용을 읽지 못하는 버그 수정
  - **근본 원인**: 업로드 시 텍스트 파일은 `uploaded_file_text`에 추출 텍스트 저장 + `uploaded_file_bytes` 삭제되지만, 응답 생성 코드에서 `uploaded_file_bytes`만 확인 → 항상 None → 파일 컨텍스트 비어있음
  - **수정 1**: `uploaded_file_text` 세션 변수를 우선 확인 → 텍스트 파일(PDF/DOCX/TXT 등) 정상 참조
  - **수정 2**: 파일 첨부 상태에서 의도 분류 스킵 → 파일 컨텍스트 + LLM 직접 응답 우선 (파일 무시 방지)
  - **영향**: 이미지 파일은 기존대로 비전 모델로 분석, 텍스트 파일은 LLM 프롬프트에 내용 주입

#### 용어집 DB 로딩 오류 수정 (2건)
- **`features/onboarding/glossary_matcher.py`**: `self.glossary_dir` 저장 누락 수정 + **Type D JSON 구조 파서 추가**
  - **근본 원인 1**: `file_count` 프로퍼티에서 `self.glossary_dir` 미저장 → `AttributeError`
  - **근본 원인 2**: v2.0 추가 6개 JSON 파일이 `{"terms": {"용어": "설명문자열"}}` 구조(Type D)인데, `_extract_terms()`가 이를 처리하지 못해 `TypeError` → 전체 로딩 실패 → `(0, 0)` 반환
  - **영향**: 대시보드 "0 GLOSSARY TERMS", 기능 C "0 Terms (0 Files)" 표시
  - **수정**: `_extract_terms()`에 Type D 분기 추가 (dict의 str 값 → `{"term": key, "definition": val}` 변환), 개별 항목 실패 시 `continue`로 전체 중단 방지
  - **결과**: 21개 파일 297개 용어 정상 로드

#### 기능 C — 조직도 시각화 (챗봇 내 표시)
- **`ui/page_onboarding.py`**: `_handle_org_chart_query()` + `_build_division_summary()` 신규
  - "조직도 보여줘" → 기능 A의 `create_org_tree_html()` HTML 시각화를 챗봇 내 렌더링
  - "품보팀 조직도" → `create_dept_org_chart_html()` 부서별 조직도 표시
  - 시각화 아래에 7개 본부별 부서 인원 현황 + 팀장 정보 마크다운 요약 출력
  - `_handle_employee_query()`에 `_ORG_CHART_KEYWORDS` 감지 분기 추가
  - 채팅 히스토리에는 텍스트 요약만 저장 (HTML은 1회성 렌더링)

#### 기능 C — 부서 별칭(약어) 인원 조회 기능
- **`features/search/intent_router.py`**: 부서 별칭 인식 + 의도 분류 부스트
  - **문제**: "품보팀", "생기팀", "안보팀", "QA" 등 약어로 인원 조회 시 `document_search`로 분류되어 인원 검색 미실행
  - **수정**: `DEPARTMENT_ALIASES`(48개) / `DIVISION_ALIASES`(8개)를 `search.py`에서 import하여 쿼리 매칭 시 `emp_score +2` 부스트
  - 문서/규정 키워드(`절차`, `규정` 등)와 동시 출현 시 부스트 억제 — "안전 교육 절차"는 `document_search` 유지
  - `EMPLOYEE_KEYWORDS`에 "팀원들", "구성원", "멤버", "소속", "현황" 5개 키워드 추가

#### 대시보드 시스템 구성 재편
- **`ui/page_dashboard.py`**: 하단 시스템 아키텍처를 **4개 분야별 그룹 카드**로 재편
  - 기존: 1행 4열 (LLM/Embedding/VectorDB/Export)
  - 변경: 2x2 그리드 — AI/NLP 엔진 | 데이터 | 인프라 | 출력
  - 각 그룹 4항목씩 16개 시스템 컴포넌트 표시

---

## [v2.5] — 2026-03-26

### 기능 C 통합 확장 + 기능 D 재구조화 + 규제 문서 연동 + LLM 응답 개선

#### 기능 C 온보딩 챗봇 — 기능 B/D 통합 (5분기 의도 분류)
- **`features/search/intent_router.py`**: 3분기→**5분기** 확장
  - 기존: `employee_lookup` / `company_info` / `document_search`
  - 추가: **`document_compose`** (문서 작성 요청) + **`regulation_query`** (규제 조회)
  - `COMPOSE_KEYWORDS` 28개, `REGULATION_KEYWORDS` 27개 추가
- **`ui/page_onboarding.py`**: 핸들러 2개 신규
  - `_handle_compose_query()`: 채팅에서 이메일/보고서 작성 → LLM 생성 → DOCX/TXT 다운로드 버튼 제공
  - `_handle_regulation_query()`: 채팅에서 규제 질의 → `regulation_context.py` 데이터 로드 → 공장-규제 매핑 포함 분석 답변
  - `_quick_docx()`: 채팅 내 즉석 DOCX 변환 유틸리티

#### LLM 응답 길이 대폭 확장
- **`config.py`**: `OLLAMA_NUM_PREDICT` 전면 확장
  - 기본값: 512→**2048** (4배)
  - 온보딩: 300→**1024** (3.4배)
  - 문서 작성: 800→**4096** (5.1배)
  - 규제 분석: 500→**2048** (4.1배)
  - `OLLAMA_NUM_CTX`: 4096→**8192** (2배)
  - 신규: `onboarding_compose` **3072**, `onboarding_regulation` **2048**
- **`features/onboarding/prompts/onboarding_system.txt`**: "400자 이내 간결하게" → **"500자 이상 상세하게"**, 답변 구조 6단계로 확장

#### 기능 B — 규제 문서 5종 추가 + 하위 탭 분할
- **`features/draft/doc_type_config.py`**: EXTERNAL_DOC_TYPES에 규제 문서 5종 추가
  - 규제 변경 영향 보고서, OEM 규제 대응 통보문, 협력사 준수 요청서, 규제 시행 계획서, 규제 대비 체크리스트
  - `build_prompt()`에 규제 전용 선택적 라인 5개 추가
- **`ui/page_draft.py`**: 내부용/외부용 각각 **하위 2탭** (📃 양식 다운로드 / ✏️ 문서 작성) 분할
  - 결과 표시(내보내기/편집/수정)가 "문서 작성" 하위 탭 안으로 이동
  - 규제 문서 유형 감지 시 기능 D 크롤링 데이터 자동 주입

#### 기능 D — 3탭 + 하위 5탭 + 규제 문서 관리
- **`ui/page_compliance.py`**: 6탭→**3탭** 통합
  - 탭 1: 규제 모니터링 → **하위 5탭** (시나리오/미국규제/규제DB/크롤링/규정확인)
  - 탭 2: 시설/공장 관리 → 공장별 적용 규제 자동 매핑 표시
  - 탭 3: 규제 문서 관리 (신규) → 문서 생성/저장/조회/다운로드/Before-After 비교
- **`_CRAWLER_META`**: 함수 내부 → 모듈 레벨로 이동 (다중 함수 공유)

#### 신규 모듈 (기능 D 확장)
- **`features/compliance/regulation_context.py`**: 규제 데이터 참조 모듈
  - `get_regulation_context()`, `inject_regulation_context()`, `get_available_regulations()`, `get_regulation_items()`
- **`features/compliance/plant_regulation_mapper.py`**: 공장-규제 자동 매핑
  - 9개 규제 유형별 적용 규칙 정의 (ISO, EU, 국내법, 미국규제, OEM, MSDS, ESG, EV, Trade)
  - `get_applicable_plants()`, `get_plant_regulations()`, `get_regulation_mapping_summary()`

#### 기능 B — 문서 검색 패널 확장
- **`ui/doc_search_panel.py`**: 외부용 문서 유형에 "규제 보고서" 카테고리 추가, REG DOCS 메트릭 카드 추가

---

## [v2.2] — 2026-03-26

### 주간/야간 테마 + Liquid Glass 이모지 + 로그인 개선 + 보안 강화

#### 주간/야간 모드 (라이트/다크 테마)
- **`ui/hud_style.py`**: CSS 변수 기반 라이트/다크 테마 전환 시스템
  - `--hud-bg`, `--hud-text`, `--hud-border`, `--hud-accent` 등 CSS 변수 정의
  - `get_current_theme()` 함수 — 사용자 설정 / 시간 기반 자동 전환
- **`app.py`**: 사이드바 테마 셀렉트박스 (🔮 자동 / 🌤️ 라이트 / 🌑 다크)
- **`features/search/employee/org_chart.py`**: `_get_layout_defaults()`, `_get_hover_style()` — Plotly 차트 테마 동적 대응

#### Liquid Glass 스타일 이모지 전면 교체 (94개)
- 10개 UI 파일에 걸쳐 전체 이모지를 Liquid Glass 스타일로 통일
  - 주요 변경: 🔒→🪪, 🚀→✨, 🌐→🌍, 📡→🔮, 📚→📖, 🏭→🏗️, 👤→🪪, 📞→☎️, ✉→📧

#### 로그인 페이지 개선
- 회원가입 탭 삭제 (로그인 + 비밀번호 변경만 유지)
- 테스트 계정 목록 expander 삭제

#### 기능 E (Admin) 개선
- 사용자 목록 부서/직급 필터링 추가
- 사용자 생성 시 부서 카테고리 설명 추가

#### 보안 강화
- JWT 기반 인증 시스템 (`core/auth/jwt_handler.py`)
- 세션 파일 기반 서버 사이드 세션 (`core/auth/session_store.py`)
- 쿠키 기반 새로고침 세션 유지

---

## [v2.1] — 2026-03-26

### 인증/RBAC + 인사관리 시스템 (기능 E 신규)

#### 인증 시스템
- **`core/auth/auth_db.py`**: auth.db SQLite — users/login_history 테이블
- **`core/auth/jwt_handler.py`**: JWT 토큰 생성/검증 (PyJWT)
- **`core/auth/session_store.py`**: 파일 기반 서버 사이드 세션
- **`ui/page_login.py`**: 로그인 페이지 (아진 로고 + 사원번호/비밀번호)
- bcrypt 비밀번호 해싱, 5회 실패 시 30분 잠금

#### RBAC 권한 관리
- 5단계 역할: SYS_ADMIN, HR_ADMIN, TEAM_LEAD, MANAGER, EMPLOYEE
- 기능별 접근 제어 — Admin 페이지는 SYS_ADMIN/HR_ADMIN만 접근

#### 기능 E: 인사 관리 (page_admin.py)
- 4탭 구조: 사용자 목록 / 사용자 생성 / 로그인 이력 / 관리 도구
- 테스트 계정 12개 일괄 생성 기능 (부서별/직급별)
- 사용자 생성 시 이메일/연락처/부서 필드 추가

#### 프로필 페이지
- **`ui/page_profile.py`**: 내 정보 조회/수정 + 비밀번호 변경
- 사이드바 사용자 카드 클릭 시 프로필 페이지 이동

---

## [v2.0] — 2026-03-26

### 대개편 — 기능 A/B 재구조화 + 조직도 계층 수정 + 시각화 오류 해결

#### 기능 A 대개편 — "인원 검색 및 조직도" 전용 페이지
- **`ui/page_search.py`** 완전 재작성 (~1100줄 → ~200줄)
- 문서 검색 기능 전부 제거 → 기능 B로 이전
- DOC SEARCH / ORG CHART 2탭 → 직원 검색 + 조직도 단일 페이지
- 헤더: "DOC SEARCH ENGINE" → "EMPLOYEE DIRECTORY 인원 검색"
- 네비게이션: "A. DOC SEARCH 문서 검색" → "A. EMPLOYEE 인원 검색"

#### 조직도 계층 구조 수정
- **`features/search/employee/org_chart.py`**: `POSITION_HIERARCHY` 임포트
- **`create_treemap()`**: 직급 노드 동일 레벨(형제) → 상무→부장→과장 **수직 체이닝**, 누적값(`cumulative`) 계산으로 `branchvalues="total"` 호환
- **`create_sunburst()`**: 동일한 계층 체이닝 적용
- **`create_dept_org_chart()`**: 직급 수평 배열(y=0.72 고정) → **수직 계층 배치** (y 좌표 분산), 개인 노드 우측 팬아웃

#### 시각화 렌더링 오류 해결
- **근본 원인**: `_render_org_panel()`에서 모든 차트가 하나의 `try/except ImportError` 블록 안에 있어, `ImportError`가 아닌 예외 발생 시 이후 전체 차트 스킵
- **수정**: import문만 별도 `try/except ImportError`로 분리, 각 차트를 **개별 `try/except Exception`**으로 격리
- Treemap/Sunburst/Plant Bar/Position Pie 중 하나가 실패해도 나머지 정상 렌더링
- 에러 발생 시 `st.warning(f"차트 생성 실패: {e}")` 표시

#### 기능 B 대개편 — "문서 검색/작성" 내부용/외부용 분할
- **`ui/page_draft.py`** 완전 재작성
- 기존 "✉ 이메일 / 📄 공식 문서" 2탭 → **"🏢 내부용(Internal) / 🌐 외부용(External)" 2탭** 구조
- 각 탭 내부: 문서 검색 + 양식 다운로드 + 이메일/문서 작성 + 내보내기(DOCX/PDF/HWPX)
- 네비게이션: "B. DOC WRITER 문서 작성" → "B. DOCUMENTS 문서 검색/작성"
- 헤더: "DOCUMENT WRITER" → "DOCUMENTS / 문서 검색 및 작성"

##### 내부용 탭
- 수신처: 사내 (고정, 선택 불필요)
- 문서 유형: 사내 이메일, 회의록
- 톤: semi_formal / 한국어
- 양식 다운로드: `to_internal.j2`, `meeting_note.j2`

##### 외부용 탭
- 수신처 5종: 현대/기아, HMGMA(영문), HMGMA(국영문), 2차 협력사, 해외법인
- 문서 유형: 이메일, 8D 보고서, ECN 변경통보
- 톤/언어: 수신처에 따라 자동 (`tone_config.py`)
- 양식 다운로드: `to_oem.j2`, `to_supplier.j2`, `to_overseas.j2`, `8d_report.j2`, `ecn_notice.j2`

#### 신규 모듈
- **`ui/doc_search_panel.py`**: 문서 검색 + 양식 다운로드 재사용 패널 (`context="internal"/"external"` 파라미터)
  - 내부용: SOP, 부서 가이드, 사내 이메일, 회의록, 협업 가이드
  - 외부용: 8D, ECN, PPAP, OEM 이메일, 협력사 이메일, 해외 이메일, 규제 문서
  - Jinja2 템플릿 양식 다운로드 UI

#### 백엔드
- **`backend/schemas/draft.py`**: `DraftGenerateRequest`에 `context` 필드 추가 ("internal"/"external")
- **`backend/routers/draft.py`**: context 기반 프롬프트 분기 (사내→간결 존댓말 / 외부→수신처+언어)

#### UI
- **`ui/components.py`**: 사이드바 메뉴 라벨 변경 — A: "EMPLOYEE 인원 검색", B: "DOCUMENTS 문서 검색/작성"

---

## [v1.7] — 2026-03-25

### 아키텍처 개선 — FastAPI 백엔드 + 보안 강화 + UI/UX 개선

#### FastAPI 백엔드 도입
- Streamlit ↔ FastAPI REST API 아키텍처 분리
- `backend/main.py`: FastAPI 서버 (127.0.0.1:8000)
- `backend/routers/`: onboarding, draft, search, employee API
- `backend/schemas/`: Pydantic 요청/응답 스키마
- Streamlit(프론트엔드) → FastAPI(백엔드) → Ollama(LLM) 3티어 구조

#### 보안 강화 (19건 취약점 감사 및 수정)
- **XSS 방어**: 파일명, 검색 쿼리, 모델 배지에 `escape_html()` 적용
- **API 보안**: `0.0.0.0` → `127.0.0.1` 바인딩, CORS 메서드/헤더 최소화
- **파일 업로드**: 백엔드에서 크기(20MB)/확장자 검증, `validate_path()` 적용
- **프롬프트 인젝션**: 백엔드 모든 LLM 입력에 `sanitize_llm_input()` 적용
- **Jinja2 보안**: `SandboxedEnvironment` 적용
- **에러 정보 누출 방지**: 내부 에러 메시지 제거 + 로깅
- **세션 보안**: 채팅 히스토리 100건, 리비전 10건 제한
- **의존성**: PyPDF2→pypdf, 누락 패키지 추가

#### 기능 A 개선
- Treemap/Sunburst: 변수명 충돌 수정, key 명시, height=650 명시
- 부서별 조직도(트리형) 시각화 추가

#### 기능 B 개선 — 초안→완성 문서
- "DRAFT GENERATOR" → "DOCUMENT WRITER" 명칭 완전 변경
- DraftPipeline asyncio 이벤트 루프 충돌 수정
- 문서 생성 프롬프트 강화: placeholder 금지 7개 규칙
- Jinja2 템플릿 기반 완성 이메일 생성 파이프라인 정상화

#### 기능 C 개선
- Ollama 모델 선택 (채팅/비전) UI 추가
- 파일 첨부 기능 (텍스트+이미지)
- 스트리밍 응답 구현
- 채팅 컨테이너 고정 높이 + 스크롤
- Employee DB 연동 — 부서/직급/이름 검색 자연어 대응
- 빠른 질문 9개로 확장 (자동차 품질 중심)

#### 기능 D 개선
- Folium + OpenStreetMap 지도 (Mapbox 대체)
- 시설 DB: 국내 6개소 + 해외 6개소 전체 표시
- 사업장별 규제 필터링 기능
- HTML 렌더링: `st.html()` / `st.markdown()` 사용 분리

#### UI/UX
- Streamlit v1.51.0 호환: 복잡한 HTML → `st.html()` 변환
- CSS 클래스 의존 블록은 `st.markdown(unsafe_allow_html=True)` 유지
- 메트릭 카드 박스 크기 통일
- Ollama 스트리밍 응답 (thinking 모드 비활성화)

---

## [v1.6] — 2026-03-24

### 글로벌 확장 — JOON INC / HMGMA / 미국 규제 대응

#### Phase 1: 데이터 레이어
- **`config.py`**: CEO 서정호, 매출 1조886억, 직원 649명, `HMGMA_INFO` / `OVERSEAS_SUBSIDIARIES` 딕셔너리 추가, JOON INC(Georgia) 해외법인 추가
- **`plants.json`**: JOON INC(Statesboro, GA) 신규 등록 ($312M 투자, 630명 목표, EWP/CCH), AJIN USA(Alabama) 상세화, 메타데이터 v3.0
- **용어사전 4파일 23항목 신규**: `ev_parts_terms.json` (EWP/CCH/PTC/OBC/BMS), `lightweight_terms.json` (CFRP/Prepreg/핫스탬핑/위상최적화/Metal 3D), `global_terms.json` (HMGMA/JOON/IRA/KMMG/HMMA/SDF/USMCA/AEO), `advanced_quality_terms.json` (RPN/Cpk/PSW/MSA/IATF16949)
- **기업 지식베이스 3파일 신규**: `company_info/history.md` (1976~2025 연혁), `culture_welfare.md` (복지/급여/ESG), `global_network.md` (12개 사업장 + HMGMA)
- **미국 규제 시나리오 5건**: `us_trade_regulations.json` (관세25%/IRA/USMCA/OSHA/EPA)

#### Phase 2-A: 기능 A — 조직도 해외법인 노드
- **`org_chart.py`**: `create_org_tree()` — 대표이사 아래 y=0.05에 해외법인 6개 노드 추가 (시안색 구분)
- `create_treemap()` / `create_sunburst()` — "해외법인" 상위 노드 + 6개 법인 하위 노드

#### Phase 2-B: 기능 B — 영문 이메일 + 다국어 생성
- **`page_draft.py`**: 이메일 탭에 수신처(6종) 선택 추가 — HMGMA(영문), HMGMA(국영문), 해외법인 등
- 수신처에 따라 언어 자동 추론 (ko/en/ko_en)
- 이메일 프롬프트: 영문 전용 지시(`formal business English, IATF terminology`), 국영문(`Korean + English Version`), 한국어별 분기
- HMGMA 수신 시 톤 힌트(`조지아 전기차 공장, JOON INC EWP/CCH 공급`) 자동 주입

#### Phase 2-C: 기능 C — 온보딩봇 회사정보 라우팅
- **`intent_router.py`**: `COMPANY_INFO_KEYWORDS` 30+ 키워드 추가, `classify_intent()` 3분기 (employee_lookup / company_info / document_search)
- **`page_onboarding.py`**: `_handle_company_info_query()` 신규 — company_info/*.md 3파일을 LLM 컨텍스트로 주입하여 연혁/복지/해외사업 질문 자연어 답변
- 빠른 질문 **3탭 구조**: 부서별 질문 / 회사정보·해외 (9문항) / 공통 질문

#### Phase 2-D: 기능 D — 미국 규제 모니터링
- **`us_trade_crawler.py`** 신규: `USTradeRegulationCrawler` — 5개 시나리오 로드, `estimate_tariff_impact()` 관세 시뮬레이션
- **`page_compliance.py`**: "🇺🇸 US TRADE 미국규제" 탭 신규 (기존 5탭 → 6탭)
  - 요약 메트릭: 관세율 25% / IRA $7,500 / 규제 5건
  - 시나리오 카드: 심각도 색상, 영향 사업장/제품, 대응 방안, 모니터링 URL
  - 관세 영향 시뮬레이션: 3개 품목별 25% 관세 추정 테이블 + 연간 총액

#### Phase 3: UI/UX 확장
- **`page_search.py`**: ADVANCED FILTERS에 사업장(Site) 필터 추가 (국내 6 + 해외 6), "해외 연락처 포함 검색" 체크박스, 문서 유형에 미국 규제(IRA/관세/OSHA/EPA/USMCA) 추가
- **`page_search.py`**: 조직도 탭에 "🌐 해외법인 포함 표시" 토글 추가
- **`page_dashboard.py`**: 상단 메트릭 용어집 85→108, 크롤러 9→10
- **`page_dashboard.py`**: 기능 B 카드 — "DOCUMENT WRITER" + 다국어/수신처 6종 반영
- **`page_dashboard.py`**: 기능 C 카드 — 용어 108개, 3-Tab FAQ, 3분기 의도 분류
- **`page_dashboard.py`**: 기능 D 카드 — 크롤러 10개, 미국 IRA, 시설 12개소

#### Phase 4: 미구현 항목 보완 (22/22 태스크 완료)

**즉시 효과 (하 난이도)**:
- **A-5**: 조지아 공장 샘플 문서 3종 — `8D-2026-JOON-001.md` (EWP 조립 불량 8D), `EMAIL-2026-HMGMA-001.md` (2026 Q1 납기 영문 이메일), `PPAP-2026-HMGMA-CCH.md` (CCH PPAP 18항목 체크리스트)
- **B-6**: `features/draft/tone_config.py` — 수신처 6종별 formality/language/honorifics/closing/signature/guidelines 설정
- **D-6**: `page_compliance.py` — `_count_regulations_for_plant()` 함수 + 시설 카드에 "규제 N건 적용" 골드 배지
- **C-4 보완**: `page_onboarding.py` — 해외영업팀(6문항) DEPT_QUESTIONS 추가 + selectbox 반영

**핵심 기능 (중 난이도)**:
- **A-2**: `database.py` — `overseas_assignment`/`language_skills` 컬럼 추가 (마이그레이션 안전 처리), `seed_data.py` — `seed_overseas_assignments()` 15명 해외파견 시드
- **B-1**: 영문 이메일 Jinja2 템플릿 3종 — `email_en_delivery_delay.j2`, `email_en_quality_report.j2`, `email_en_ppap_submission.j2`
- **B-2**: 품질 문서 Jinja2 템플릿 3종 — `8d_report_template.j2`, `ppap_checklist_template.j2`, `fmea_process_template.j2`
- **D-3**: `impact_analyzer.py` — `estimate_tariff_impact()` (25% 관세 3품목 시뮬레이션), `check_origin_compliance()` (USMCA RVC 75% 판정), `generate_us_timeline()` (시행일 기준 마일스톤)
- **C-3**: `glossary_matcher.py` — `TERM_ALIASES` 25+항목 (워터펌프→EWP, 조지아→JOON INC, 탄소섬유→CFRP 등), `_load_all()`에서 alias 자동 등록
- **D-2**: 기존 4개 시나리오 JSON (`scenario_safety_distance/chemical_reach/ev_battery/noise_regulation`) 전부에 `applicable_plants` 배열 추가

**인프라 (중 난이도)**:
- **B-5**: `schemas/draft.py` — `DraftGenerateRequest`에 `language`/`recipient` 필드, `routers/draft.py` — `GET /draft/templates` 엔드포인트 (Jinja2 파일 목록 반환)
- **C-5**: `scripts/reindex_v16.py` — 용어집 108항목 + 기업정보 3파일 ChromaDB 인덱싱 스크립트 (glossary/company_info 컬렉션)

#### 기타
- `app.py`: 사이드바 버전 `v1.5` → `v1.6`
- `README.md`: v1.6 전면 재작성 — 회사 현황, 프로젝트 구조, 기능 상세, 실행 방법 업데이트

---

## [v1.5] — 2026-03-24

### 기능 B: 이메일 및 공식 문서 작성 (전면 개편)

#### "초안 작성" → "문서 작성"으로 명칭 변경 + 2탭 모드 분리
- **변경 파일**: `ui/page_draft.py`, `ui/components.py`
- 헤더: "DRAFT GENERATOR / 초안 작성" → "DOCUMENT WRITER / 이메일 및 공식 문서 작성"
- 사이드바 메뉴: "B. DRAFT GEN 초안 작성" → "B. DOC WRITER 문서 작성"
- **`st.tabs()` 2탭 구조 도입**:
  - **탭 1 — ✉ 이메일 작성**: 이메일 유형 선택, 수신자/제목/발신자/CC 필드, 이메일 전용 프롬프트
  - **탭 2 — 📄 공식 문서 작성**: 8D/ECN/회의록 유형 선택, 참조 문서 검색 포함
- 이메일 프롬프트에 CC 필드 반영
- 결과 표시/내보내기/수정은 양쪽 탭 공통 사용

### 기능 C: 온보딩 챗봇 대화 연속성 수정

#### 대화 이력 LLM 프롬프트 주입
- **변경 파일**: `ui/page_onboarding.py`
- **근본 원인**: `_build_prompt()`에서 `{conversation_history}`가 항상 `"(첫 번째 질문입니다)"`로 고정
- **수정**: `st.session_state["onboarding_messages"]`에서 최근 3턴(6메시지)을 추출하여 프롬프트에 실제 주입
- 각 메시지 300자 제한으로 토큰 오버플로우 방지
- `_handle_employee_query()`에도 최근 2턴(4메시지) 대화 이력 주입
- "우리 회사 조직도 보여줘" → "기술영업팀" 같은 후속 질문이 맥락 유지됨

### 기능 D: 시설 DB 지도 표시 수정

#### 지도 렌더링 개선 + 외부 지도 링크 폴백
- **변경 파일**: `ui/page_compliance.py`
- `st.map()` height를 350px로 명시 (expander 내 높이 계산 문제 해소)
- 지도 타일 로드 실패 시에도 **네이버 지도 / 카카오맵 외부 링크** 제공
- 경산 본사, 경산 제2공장 등 모든 사업장에서 지도 또는 링크로 위치 확인 가능

### 기타

- `app.py`: 사이드바 버전 표시 `v1.4` → `v1.5`

---

## [v1.4] — 2026-03-24

### 공통

#### 1. 로고 클릭 시 대시보드 이동
- **변경 파일**: `app.py`, `ui/components.py`
- 사이드바 아진 로고 영역 전체를 클릭 가능한 컨테이너로 변경
- CSS 오버레이 투명 버튼 방식으로 구현
- `st.session_state["_nav_override"]`로 네비게이션 오버라이드
- `render_feature_selector()`에서 `_nav_override` 인식하여 `st.radio` index 변경
- 사이드바 버전 표시 `v1.2` → `v1.4`

### 기능 A: 사내 문서 검색 및 조직 정보

#### 2. 조직도 호버 말풍선 수정 (이름/연락처/이메일 표시)
- **변경 파일**: `features/search/employee/org_chart.py`
- **근본 원인**: hover 문자열에 `\n` 사용 → Plotly에서 줄바꿈 무시됨
- **수정**: `_hover()` 헬퍼 함수 도입 — 모든 `\n`을 `<br>`로 변환
- 적용 범위: `create_org_tree()`, `create_treemap()`, `create_sunburst()`, `create_dept_org_chart()` 전체
- 부서 노드에 팀장 이메일 정보도 추가 (기존: 전화번호만)
- 부서별 조직도 개인 노드에 전화번호 추가 (기존: 이메일/내선만)
- `hoverlabel` 스타일 통일 (HUD 테마: 다크 배경 + 골드 테두리)

### 기능 B: 이메일 및 공식 문서 초안 작성

#### 3. 이메일 작성+수정 UX 업그레이드
- **변경 파일**: `ui/page_draft.py`
- **직접 편집**: `st.text_area()`로 초안을 직접 수정 가능 + "편집 내용 저장" 버튼
- **AI 수정**: REVISE 버튼 → Pipeline 의존 제거, `_revise_fallback()` LLM 직접 호출로 단일화
- **수정 이력**: `st.session_state["draft_revision_history"]`에 모든 수정 기록 저장
  - 직접 편집 / AI 수정 구분 표시
  - `st.expander()`로 이력 조회 가능

### 기능 C: 신입사원 온보딩 챗봇

#### 4. 부서별 맞춤 빠른 질문
- **변경 파일**: `ui/page_onboarding.py`
- 기존 `SAMPLE_QUESTIONS` (9개 고정) → `DEPT_QUESTIONS` 부서별 딕셔너리로 교체
- 11개 부서 각 6개 맞춤 질문 정의 (품질보증팀, 안전보건팀, 생산관리팀, 영업팀, 생산기술팀, 부품개발팀, 품질경영팀, 기술교육원, IT전략팀, 구매팀, 기술연구소)
- 공통 질문 3개 (`_COMMON_QUESTIONS`) 모든 부서에 추가 표시
- 부서 selectbox 변경 시 빠른 질문이 자동으로 해당 부서 맞춤으로 전환

### 기능 D: 법규/규정 모니터링

#### 5. 경산 공장 지도 미표시 수정
- **변경 파일**: `ui/page_compliance.py`
- **근본 원인**: `st.map()` 호출 시 `latitude`/`longitude` 파라미터 명시 누락 + 타입 안전성
- **수정**: `float()` 명시적 변환 + `latitude="lat"`, `longitude="lon"` 파라미터 명시
- `try/except`로 지도 로드 실패 시 에러 메시지 표시 (기존: silent 실패)

---

## [v1.2] — 2026-03-24

### 기능 A: 사내 문서 검색 및 조직 정보

#### 1-1. 문서 검색 결과 페이지네이션
- **변경 파일**: `ui/page_search.py`
- 검색 결과를 10건씩 페이지 분할하여 표시
- `st.session_state`에 `search_page` 키로 현재 페이지 번호 관리
- 검색 k값을 100으로 확대하여 충분한 결과 확보 후 UI 레이어에서 슬라이싱
- 상단에 "총 X건 중 Y-Z건 표시" 정보 표시
- 하단에 "이전 / 다음" 페이지 네비게이션 버튼 추가
- 브라우즈 모드에서도 동일한 페이지네이션 적용

#### 1-2. 조직도 노드 호버 시 말풍선 (이름/직급/연락처)
- **변경 파일**: `features/search/org_chart.py`
- `create_org_tree()`에서 팀장 노드에 `phone`, `email`, `extension` 정보 추가 조회
- Plotly `hovertemplate` 활용하여 호버 시 이름/직급/연락처/이메일 표시
- 부서 노드에도 팀장 연락처 포함
- `hoverlabel` 스타일링 (HUD 테마에 맞는 배경색/폰트)

#### 1-3. Treemap: 부서 → 직급 → 개인 드릴다운
- **변경 파일**: `features/search/org_chart.py`
- `create_treemap()`을 3레벨(루트→본부→부서)에서 5레벨(루트→본부→부서→직급→개인)로 확장
- 개인 노드의 `customdata`에 이름/연락처/이메일 포함
- `hovertemplate`로 개인 정보 호버 표시
- `pathbar`(상단 경로바)를 활용한 드릴다운 UX

#### 1-4. Sunburst: 부서 → 직급 → 개인 계층 시각화
- **변경 파일**: `features/search/org_chart.py`
- `create_sunburst()`를 5레벨(루트→본부→부서→직급→개인)로 확장
- `maxdepth` 파라미터로 초기 표시 깊이 제한, 클릭 시 드릴다운
- 개인 노드 hover에 이름/직급/연락처/이메일 표시

---

### 기능 B: 이메일 및 공식 문서 초안 작성

#### 2-2. HWPX 파일 깨짐 수정
- **변경 파일**: `features/draft/exporters/hwpx_exporter.py`
- `mimetype` 파일을 비압축(STORED) + ZIP 내 첫 번째 엔트리로 강제 배치
- XML 인코딩 `<?xml version="1.0" encoding="UTF-8"?>` 선언 명시
- 필수 파일 구조 보완 (`version.xml` 등)
- `_write_content_hpf()` 네임스페이스 정리

#### 2-3. 수정 요청(REVISE) 미반영 수정
- **변경 파일**: `ui/page_draft.py`, `features/draft/session.py`
- 초안 생성 시 모든 경로(Pipeline/stream_generate 폴백)에서 `DraftSession` 생성 보장
- `session_id`와 `draft_text`를 `st.session_state`에 확실히 저장
- revise 결과를 `st.session_state["draft_text"]`에 즉시 반영
- LLM JSON 파싱 실패 시 "전체 텍스트 기반 수정" 폴백 추가
- `st.rerun()`으로 화면 갱신 보장

---

### 기능 C: 신입사원 온보딩 챗봇

#### 3-1. 사원 조회 DB + LLM 하이브리드 답변
- **변경 파일**: `ui/page_onboarding.py`
- `_handle_employee_query()` 전면 재작성
- **기존**: DB 조회 → `format_search_result()` 마크다운 직접 출력 (LLM 미사용)
- **변경**: DB 조회 → 마크다운 결과를 LLM 프롬프트 컨텍스트로 주입 → LLM이 자연어 답변 스트리밍 생성
- 프롬프트에 규칙 포함: 여러 명이면 "어느 분을 찾으시나요?", 결과 없으면 재검색 안내
- LLM 실패 시 기존 DB 마크다운 직접 출력 폴백 유지
- 소스 뱃지: `Employee DB (SQLite)` → `Employee DB + LLM`

---

### 기능 D: 법규/규정 모니터링

#### 4-1. 시나리오 사업장별 영향 분석 필터
- **변경 파일**: `ui/page_compliance.py`
- 시나리오 선택 드롭박스 아래에 **사업장/공장 필터 selectbox** 추가
- `plants.json`에서 자사 공장 + 국내 계열사 + 해외법인 전체 목록 로드
- `_run_impact_analysis()`, `_render_impact_result()`, `_render_simulated_impact()` 함수에 `plant_filter` 파라미터 추가
- 선택된 사업장이 영향 범위에 없으면 "포함되지 않습니다" 안내 표시

#### 4-2. 크롤러 실행 결과 상세 보고
- **변경 파일**: `ui/page_compliance.py`
- **Run All Crawlers**:
  - `crawler.crawl()` 반환값에서 `total_count`/`total_records` 및 `errors` 추출
  - 성공 시: `"✅ ISO 국제규격: 15건 수집"` 형태로 건별 상세 표시
  - 실패 시: `"❌ 크롤러명: 크롤링 실패"` + `st.expander()`로 오류 메시지(`str(e)`) 표시
  - 경고가 있는 경우: `st.expander()`로 경고 내역 상세 표시
- **Run Selected**:
  - 동일하게 수집 건수 + 오류 상세 표시

#### 4-3. 시설 클릭 시 지도/주소/주력제품/홈페이지 표시
- **변경 파일**: `ui/page_compliance.py`, `data/facility_db/plants.json`
- `plants.json` 데이터 확장:
  - 자사 공장 3곳: `lat`, `lng` 위경도, `homepage` URL, `main_business` 배열 추가
  - 국내 계열사 3곳: `lat`, `lng`, `main_business` 추가
  - 해외법인 6곳: `lat`, `lng`(가능한 곳), `main_business` 추가
- `_render_facility_db()` UI 확장:
  - 각 사업장 카드 아래 `st.expander()` 상세 패널 추가
  - `st.map()` (Streamlit 내장)으로 위치 지도 표시 (위경도 있는 경우)
  - 2컬럼 레이아웃: 주소/설립일/인원 | 홈페이지/주력사업/인증
  - 주력 생산 물품 목록 표시

---

### 기타 변경

- `app.py`: 사이드바 버전 표시 `v1.0` → `v1.2`
- `README.md`: 프로젝트 문서 신규 작성 (v1.2 기준)
- `CHANGELOG.md`: 변경 이력 문서 신규 작성

---

## [v1.0] — 2026-03 (최초 릴리스)

### 기능 A: 사내 문서 검색
- BM25 + Semantic 하이브리드 검색 엔진
- 문서 카테고리별 브라우징 (8D, ECN, PPAP, 회의록, 이메일)
- Plotly 조직도 (3레벨: 루트→본부→부서)
- Treemap / Sunburst 조직 시각화 (3레벨)
- SQLite 기반 사원 검색 엔진

### 기능 B: 이메일/공문 초안 작성
- Ollama LLM 기반 초안 자동 생성
- RAG 참조 문서 기반 맥락 반영
- DOCX, PDF, TXT, HWPX 내보내기
- DraftSession 기반 수정(revise) 기능

### 기능 C: 신입사원 온보딩 챗봇
- 부서별 맞춤 답변 (14개 부서)
- 용어집 자동 매칭 + RAG 지식베이스 검색
- 사원 DB 직접 조회 (마크다운 테이블 출력)
- 비전 모델 이미지 분석, 파일 업로드 지원

### 기능 D: 법규/규정 모니터링
- 시나리오 모니터링 + 영향 분석 (rule-based + LLM)
- 9종 규제 크롤러 (ISO, MSDS, EU, 국내법규 등)
- 시설/공장 DB (자사 3곳 + 국내 계열사 3곳 + 해외법인 6곳)
- 화학물질 레지스트리 (SVHC 후보 표시)
- 규정 준수 확인 (자연어 질의)
