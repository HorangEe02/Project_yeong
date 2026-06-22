# 2026-06-11 일일 건강 점수 — 산정 방식 확정분 + 보류 결정 10건

> 구현: `b43b9bfd` (`src/services/daily_health_score.py`, `GET /dashboard/summary`의 `health_score` 블록, `daily-health-score-v1.0.0`)
> 근거 문서: `docs/Nutrition-docs/core-algorithm/` 00·02·03·05·07·09 + LLM-WIKI(`/Volumes/Corsair EX400U Media/LLM-WIKI`)

## 확정 산식 (P0 출시분)

```
final = round(0.6 × activity + 0.4 × nutrition), 0~100 clamp
activity  = calculate_activity_score(...).v4_score (cap 100)   # 기존 algorithms/activity.py 재사용
            v1 걸음수 기본점수(02 §1.1) → v2 Tanaka HR 보정(§1.2, 분 데이터 없으면 0.7 고정·무감점)
            → v4 만성질환·흡연 max() 가중(§4.4, '활동 동기 점수' 프레임) · 코호트 없음 → v3 보너스 0
nutrition = 100 − kcal 감점 − 나트륨 감점                        # 당일 확정 식사 totals만
            kcal: r=섭취/TDEE(Mifflin-St Jeor+걸음수 PAL, 03문서) — 0.8~1.2 무감점 / ±밴드 −10 / 그 외 −20
            나트륨: 2000mg 초과 1000mg당 −10 (최대 −30)
결손: 한 축 None → 가중치 재정규화 / 둘 다 None → data_status not_ready·score null (날조 금지)
라벨: ≥90 좋아요 / ≥75 양호 / ≥55 보통 / ≥35 주의 / <35 참고 (+만성질환 시 전문가 상담 병기)
근거 인용: 감점 driver → category key → retrieve_llm_wiki_context_db → source_citations (fail-open [])
```

## 보류 결정 (Phase 2/3 · 제품/운영)

| # | 항목 | 내용 / 조건 |
|---|---|---|
| 1 | [P2] v3 백분위 보너스 | 코호트 집계(n≥100) 서버 구축 후. winsorization·자기비교 옵션 포함 (02 §4.3) |
| 2 | [P2] 미량영양소 영양 점수 | meal totals가 kcal/거시영양소+Na뿐 — KDRIs 13종 점수는 food_records nutrient_estimates 통합 또는 totals 확장 후 |
| 3 | [P2] HR 보정 실연동 | health_daily_summaries에 target_hr_minutes 동기화 추가 시 v2 실활성화 (현 0.7 고정) |
| 4 | [정책] cap 정합화 | 신규 health_score는 le=100. 기존 activity 카드 le=120 vs 문서 의사코드 130 불일치 별건 정리 |
| 5 | [제품] **가중치 0.6/0.4 확정** | 활동 우선 휴리스틱(evidence C). figma 78점/84링 동일값 vs 활동 서브점수 링 분리도 함께 결정 |
| 6 | [P2] 컨텍스트 반영 깊이 | 영양 REFERRAL_REQUIRED 게이트(05 §5), 음주 회복 점수(09)는 일일 점수 밖 별도 트랙 |
| 7 | [영속] 점수 이력 저장 | ✅ **채택 (2026-06-12)** — `PERSIST_DAILY_HEALTH_SCORE=true` (docker-compose 기본), 목록 응답에 score/measured_date/label 요약 필드 추가, 모바일 `_TrendChartCard`(CustomPainter) 구현으로 4주 추이 잠금 해제. 7일치 미만은 잠금 유지 |
| 8 | [운영] wiki vector RAG | enable_wiki_vector_rag=True + ingest_llm_wiki_embeddings.py + seed_entity_wiki_links.py --apply 3단계. 미실행 시 lexical 폴백(동작함, 정밀도만 낮음) |
| 9 | [운영] DASHBOARD_ALGORITHM_VERSION bump | 카드 추가는 하위호환 — 회귀추적 관례상 bump 검토 |
| 10 | [P3] 한국인 BMR 0.95 보정·Hall 체중모델·약물DB | evidence C / 임상 자문 필요 (03·07 말미) — 일일 점수 무관 |

## 프론트 소비 규칙 (재확인)
- 홈 점수 카드·오늘의 분석 링 = 같은 `health_score.score` (분리 시 결정 #5)
- `message`/`label_text`는 서버가 금칙어 처리 완료 — 프론트 가공 금지
- `source_citations[].source_path`(wiki 내부 경로) 사용자 노출 금지 — title만
- not_ready → 기록 유도 placeholder (점수 표시 금지)
