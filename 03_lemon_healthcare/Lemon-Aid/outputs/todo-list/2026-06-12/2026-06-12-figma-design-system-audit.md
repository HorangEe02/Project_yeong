# Figma 디자인 시스템 ↔ 코드 대조 감사 (2026-06-12)

- 출처: Figma `LemonAid` 파일 `01_Design_System` 페이지 (node `5:4` → `DesignSystem_v2.0` frame `37:2`), Figma Dev Mode MCP로 추출
- 대조 대상: `mobile/lib/utils/design_tokens_v2.dart` + `mobile/lib/utils/brand_palette.dart` (Figma 페이지 헤더가 명시한 "코드 단일 출처")

## ✅ 일치 (변경 불요)

| 영역 | 결과 |
|---|---|
| Semantic 20변수 (bg/surface/sunken/section, border/borderStrong, ink 4종, success·warning·danger·review·info 쌍 10종) | **전부 hex 일치** |
| Brand yellow 모드 5단계 (brand #FFC700 / pressed #E5B300 / deep #C99100 / soft #FFF6CC / tint #FFF0A8) | **전부 일치** |
| 타이포 7스타일 크기/굵기/행간 (display 32 Bold 120% ~ micro 11 SemiBold 130%) | 일치 |
| 시니어 본문 최소 15px (AppText.body) | 일치 |
| AppSpace 스케일 (8/12/16/24) | 일치 |

## ⚠️ 불일치 (결정 필요)

### 1. brand_palette.dart 비-yellow 모드 — Figma 4모드×5단계 vs 코드 4모드×3단계

| 모드·단계 | Figma | 코드 | 상태 |
|---|---|---|---|
| purple pressed | #7164DB | #7B6ED4 | ≠ |
| purple soft | #EEEBFD | #F0EEFF | ≠ |
| green pressed | #4AA663 | #4FA869 | ≠ |
| green soft | #E4F4E8 | #E8F7ED | ≠ |
| blue pressed | #3884E5 | #3A88EE | ≠ |
| blue soft | #E3F0FF | #E3F0FF | ✓ |
| brandDeep ×4모드 | 정의됨 (#4F44A6/#2F7C44/#1F5BB8/#C99100) | **코드 미구현** | 누락 |
| brandTint ×4모드 | 정의됨 (#E2DDFB/#D4EDDA/#CEE3FF/#FFF0A8) | **코드 미구현** | 누락 |

- 영향 범위: `app.dart`·`brand_theme_controller.dart`·`settings_screen.dart`·`local_prefs.dart` (사용자가 설정에서 비-yellow 테마 선택 시에만 가시 차이)
- ✅ **해결 (2026-06-12)**: 사용자 결정으로 코드를 Figma에 정렬 — pressed/soft hex 5건 교정 + `deepColor`/`tintColor` 단계 추가 (`brand_palette.dart`)

### 2. 타이포 letterSpacing — Figma 음수 자간 vs 코드 0

| 스타일 | Figma | 코드 |
|---|---|---|
| display | -1.2 | 0 |
| title | -0.8 | 0 |
| subtitle | -0.5 | 0 |
| bodyLg~micro | 0 | 0 ✓ |

- ✅ **결정 (2026-06-12)**: 현행 0 유지 (코드가 단일 출처 + 시니어 가독성). **Figma 측 작업**: display/title/subtitle Text Style의 자간을 0으로 수정

### 3. (해결 완료) design_tokens_v3 잔존 import

- `medical_disclaimer.dart`가 마지막 v3 import였음 → **v2로 마이그레이션 완료 (2026-06-12)**
  - 매핑: AppSpacing s8/s12/s16/s24→AppSpace sm/md/lg/xl(값 동일) · review/reviewSoft 동명 동치 · ink100→border · ink700→inkSecondary · ink500→caption 기본 · label→caption 변형 · 면책 문구 상수는 위젯 내부로 이동(유일 사용처)
  - 의도된 시각 변화: v3 웜 톤(브라운 텍스트·크림 보더) → v2 쿨 그레이 — 전 화면 v2 전환에 따른 정합화
- v3 파일은 이제 **import 0건** → 헤더 명시대로 별도 PR에서 삭제 가능

## 📌 Figma 측 작업 항목 (코드 무관)

- Typography가 Pretendard 미설치로 Inter 폴백 중 — Figma 환경에 Pretendard 설치 후 Text Style family 일괄 교체 (페이지 내 자체 메모 확인)
