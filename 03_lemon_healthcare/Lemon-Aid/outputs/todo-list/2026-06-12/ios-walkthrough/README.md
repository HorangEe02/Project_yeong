# iOS 26.5 인터랙티브 워크스루 증거 (2026-06-12)

- 기기: iPhone 17 Pro 시뮬레이터, iOS 26.5 (UDID `7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB`)
- 빌드: `flutter build ios --simulator --debug` — iOS 는 Xcode 커스텀 스킴이
  없어 `--flavor` 불가 (Android 와 다름). 기본 baseUrl `http://127.0.0.1:8000/api/v1`
  → docker compose backend 로 직결.
- 백엔드: compose dev 스택 (AUTH_MODE=disabled, alembic 0042)

## 검증 항목 (직전 세션 우선순위 2 + 가이드 06 b/c/d 실화면)

| 파일 | 확인 내용 |
|---|---|
| `01-home-render.png` | 홈 대시보드 렌더 (날짜 캡슐·매크로 칩·마스코트·하단 네비) |
| (대화 중 캡처) | 챗: 상시 면책 라인 "레몬봇 안내는 일반 참고용이에요…" 입력창 위 상시 노출. "비타민 D 얼마나 먹어야 해?" → 개인 복용량 boundary 응답 + 근거 칩 kdris-2025 + 주의 라인 — iOS→백엔드 왕복 확인 |
| `03-score-screen-practice-added-checked.png` | 오늘의 분석: 추이 잠금 카드(7일 미만), '오늘 실천 추가하기' CTA→다이얼로그→추가→체크 토글(취소선) |
| `04-score-screen-past-day-readonly.png` | (신규 구현) 날짜 칩 → ko 데이트 피커(미래 비활성) → 과거일(6/11): '오늘' 복귀 칩 + "지난 날짜의 점수는 준비 중이에요…" 안내 + 추가 CTA 숨김(읽기 전용). '오늘' 칩 복귀 정상 |
| `05-home-ready-target-kcal.png` | (가이드 10 ⑤ ready 재검, 2026-06-13) 프로필+식사 310kcal+영양제 API 생성 후: 점수 80 '양호'(초록 캡션 — 공유 매핑), **0 / 2000 kcal 목표 모드**(KDRIs EER 백엔드 값), 소모 추정치 미노출, 풀폭 옐로 '영양소 상세 보기' CTA |
| `06-score-ready-grade-colors.png` | 오늘의 분석 ready: **success 초록 링(80/100) + '양호' successSoft 칩** — 가이드 06 (d) 라이브 검증. 관찰: 결정론 코칭 항목 영어 출력(서버 소유 문구 — 백엔드 보고) |
| `07-home-supplement-category-chip.png` | (가이드 10 P2 7 후속, 2026-06-13) 홈 영양제 관리 카드: **"비타민B 컴플렉스" 행 옆 노란 "비타민B" 분류 칩** 라이브 렌더. 분류 미선택 영양제(분류없음·비타민D 2000IU·ZMA 등)는 칩 없음 — 백엔드 category_key 라운드트립 실화면 검증 |

## 관찰 (수정하지 않음 — 후속 검토 후보)

1. 챗 액션 칩이 raw snake_case 로 노출 (`complete_missing_record`,
   `run_or_refresh_analysis`) — 한글 라벨 매핑 검토 후보 (가이드 05/10 소관).
2. 시뮬레이터에 합성 키 입력으로 한글 타이핑 시 조합이 깨져 첫 자모만
   입력됨 — 앱 버그 아님 (테스트 입력 경로 한계). 실기기/실키보드 무관.
