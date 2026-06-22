# 2026-06-21 Supplement Analysis Quality Fixes

## 기준

- Repo: `Lemon-Aid` / 작성일: `2026-06-21 KST`
- 주제: 영양제 OCR 분석 품질 수정 (성분명 한글화 · 멀티이미지 융합 · 파서 2버그 · 섭취 주의사항 번역)
- 사용자 실측 케이스: 삼대오백 멀티이미지, Doctor's Best Ubiquinol(단일성분), ZMA(Men/Women 멀티컬럼표)

## 오늘 완료한 작업

- [x] 성분명 한글(영문) 현지화 — 신규 `nutrient_display_name_localizer`(결정적 EN→KO 사전, KDRIs+영양제 동의어) (`fa7862e8`)
- [x] 멀티이미지 단일제품 융합 — async 멀티경로가 융합 분기 미도달 → `merge_strategy=single_product`를 sync 융합경로로 라우팅 + 모바일 uploadTimeout 240 (`a21b691b`)
- [x] OCR 비성분 노이즈 필터 — 신규 `supplement_candidate_filter`(영양성분/기준치에/단위 드롭, 실영양소 보존) (`a21b691b`)
- [x] declaration 멀티라인 원재료명 파서 (`486250f5`)
- [x] 파서 2버그 수정 (`9dc85387`, 적대리뷰 APPROVE)
- [x] 섭취 주의사항 한국어 번역 안정화 (`3cacded1`, 라이브 검증)
- [x] raw OCR 텍스트 저장 게이트 + 전용 동의 (`c99fcf3b`, `b97ce1a4`)
- [x] 백엔드 재빌드 + recreate + 라이브 검증

## 근본 원인 + 수정

### 1) Ubiquinol(첫 영양제) 항상 빈 결과 — `9dc85387`
- OCR은 성공(conf=high)했으나 gemma LLM 파싱이 깨진 JSON 반환 → `OllamaStructuredOutputError`
- 🔴 `supplement_parser.py:411` LLM 호출에 try/except 부재 → 예외가 결정적 패턴-fallback(413~)을 건너뜀 → 후보 0개(ZMA는 LLM 성공이라 fallback 작동=비대칭)
- 수정: LLM 호출을 try/except로 감싸 실패 시 빈 결과 + `LLM_PARSE_FALLBACK_WARNING` + fallback 계속 실행 → "Ubiquinol 200 mg" 정규식 구제

### 2) 아연 중복(함량 O/X) — `9dc85387`
- ZMA는 Men/Women 2열 표 → OCR 선형화로 숫자 뒤섞임. LLM은 전체 괄호명(함량 None), 패턴-fallback은 단순명+함량
- 🔴 이름-키 불일치(`Zinc (zinc mono-L-methionine, aspartate)` ≠ `Zinc`)로 enrich·dedup 실패 → 중복
- 수정: base-name 키(`_ingredient_base_name_key`, 후행 괄호 제거)로 enrich, **1:1 unambiguous일 때만 + consume-once**(`_build_fallback_amount_index`/`_select_fallback_for_candidate`); add-new dedup은 full키 유지
- ⚠️ 리뷰서 잡은 2 MEDIUM(동일 base 2폼에 amount broadcast / distinct same-base amount suppress)을 가드로 닫음

### 3) 섭취 주의사항 영문 잔존 — `3cacded1`
- CLOVA 워드박스 → 주의사항이 단어 5조각(`["Consult","pregnant",...]`)으로 저장 → 번역기가 정확한 개수 echo 요구, 조각서 miscount → 무성(無聲) 실패(로깅 0)
- 수정: 단일토큰 English 조각 coalesce → 1문장 후 번역 + per-item fallback + 실패 logging + budget 12→40s
- 라이브 검증(실 gemma): 5조각 → "임신, 수유 중이거나 약을 복용하는 경우, 또는 어린이에게는 전문가와 상담하십시오."

## 검증

- 파서 단위 146 통과(신규 11 포함), 라이브: 주의사항 한국어 / Ubiquinol 성분 구제 / 아연 단일행+함량
- 적대 리뷰(opus) APPROVE — 2 MEDIUM 수정 후

## 잔여

- "함량 확인 필요" 일부 = 한국어 원재료 함량 미표기(정상)
- OCR garbage 파편(Men/Vitamin/asmagnesium aspartate 등 3+자) = conservative filter 미포착(별개, 멀티컬럼 표 파싱 근본 이슈)
