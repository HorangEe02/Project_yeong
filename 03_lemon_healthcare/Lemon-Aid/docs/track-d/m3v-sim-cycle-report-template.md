# M-3-V.B — sim cycle 결과 보고 (template)

> 사용 방법: 이 파일을 `m3v-sim-cycle-results-YYYY-MM-DD.md` 로 복사 후
> 각 row 의 `✓ / ✗ / —` 와 캡처 파일명, elapsed_ms, 비고를 채워넣는다.
> 가이드: [m3v-sim-cycle-guide.md](./m3v-sim-cycle-guide.md)

---

## 0. 실행 환경

| 항목 | 값 |
|---|---|
| 실행 일자 | YYYY-MM-DD |
| 실행자 | (이름) |
| backend commit | `git rev-parse --short HEAD` |
| mobile flutter | `flutter --version` 첫 줄 |
| iOS sim | iPhone 15 Pro, iOS 17.x |
| Android emu | Pixel 7, API 34 |
| Ollama 모델 | qwen3.5:9b |
| OLLAMA_READ_TIMEOUT_SEC | 120 (M-3-V.A default 확인) |
| 영양제 라벨 fixture | 5종 (A-E) 명시 |

---

## 1. 회원가입 + 동의 cycle (한 번만)

| step | 동작 | iOS ✓/✗ | iOS 캡처 | Android ✓/✗ | Android 캡처 | 비고 |
|---|---|---|---|---|---|---|
| 2.1.1 | Splash → Login | | `ios-signup-01.png` | | `and-signup-01.png` | |
| 2.1.2 | 회원가입 폼 진입 | | `ios-signup-02.png` | | `and-signup-02.png` | |
| 2.1.3 | 이메일/비번 입력 | | — | | — | validation 통과 여부 |
| 2.1.4 | 프로필 입력 | | `ios-signup-03.png` | | `and-signup-03.png` | |
| 2.1.5 | 동의 매트릭스 3 toggle | | `ios-signup-04.png` | | `and-signup-04.png` | |
| 2.1.6 | 가입 완료 → 홈 redirect | | `ios-signup-05.png` | | `and-signup-05.png` | 토큰 저장 확인 |

---

## 2. 시나리오 A — 종합비타민 (갤러리, 일반 케이스)

| step | iOS ✓/✗ | iOS 캡처 | iOS elapsed | Android ✓/✗ | Android 캡처 | Android elapsed | 비고 |
|---|---|---|---|---|---|---|---|
| 캡처 화면 진입 | | — | — | | — | — | |
| 권한 다이얼로그 + 허용 | | `ios-A-permission.png` | — | | `and-A-permission.png` | — | |
| 갤러리 사진 선택 | | — | — | | — | — | |
| Crop (`image_cropper` / UCropActivity) | | — | — | | `and-A-crop-ucrop.png` | — | |
| Upload progress | | `ios-A-upload.png` | — | | `and-A-upload.png` | — | |
| 결과 화면 + ingredient list | | `ios-A-result.png` | __s | | `and-A-result.png` | __s | 성분 개수 기재 |
| 안전 위젯 3종 가시 | | (위 캡처 포함) | — | | (위 캡처 포함) | — | Disclaimer + Emergency + Consult |

**판정**: iOS [PASS/FAIL] / Android [PASS/FAIL]
**비고**:

---

## 3. 시나리오 B — 오메가3 (영문/한글 혼합)

| step | iOS ✓/✗ | iOS 캡처 | iOS elapsed | Android ✓/✗ | Android 캡처 | Android elapsed | 비고 |
|---|---|---|---|---|---|---|---|
| 갤러리 / 카메라 선택 | | — | — | | — | — | |
| Crop | | — | — | | — | — | |
| Upload + 결과 | | `ios-B-result.png` | __s | | `and-B-result.png` | __s | `name_ko` + `name_en` 둘 다 채워졌는지 |

**판정**: iOS [PASS/FAIL] / Android [PASS/FAIL]
**비고**:

---

## 4. 시나리오 C — 프로바이오틱스 (긴 OCR — **M-3-V.A 핵심 회귀**)

| step | iOS ✓/✗ | iOS 캡처 | iOS elapsed | Android ✓/✗ | Android 캡처 | Android elapsed | 비고 |
|---|---|---|---|---|---|---|---|
| 갤러리 사진 선택 | | — | — | | — | — | |
| Crop | | — | — | | — | — | |
| Upload progress (장시간) | | `ios-C-upload-progress.png` | — | | `and-C-upload-progress.png` | — | progress UI 안정성 |
| **결과 (60-120s 예상)** | | `ios-C-result.png` | __s | | `and-C-result.png` | __s | **timeout 안 걸리고 성공해야 함** |

**판정**: iOS [PASS/FAIL] / Android [PASS/FAIL]
**M-3-V.A 회귀 결론**:
- read_timeout 120s 적용 효과: [확인 / 미확인 / 부족]
- 만약 FAIL (timeout): read_timeout 추가 상향 검토 (예: 180s)
**비고**:

---

## 5. 시나리오 D — 비타민D (작은 라벨, 낮은 OCR 신뢰도)

| step | iOS ✓/✗ | iOS 캡처 | iOS elapsed | Android ✓/✗ | Android 캡처 | Android elapsed | 비고 |
|---|---|---|---|---|---|---|---|
| Upload + 결과 | | `ios-D-low-conf.png` | __s | | `and-D-low-conf.png` | __s | confidence < 0.85 표기 확인 |
| Manual review 진입 가능 | | `ios-D-manual-review.png` | — | | `and-D-manual-review.png` | — | OCR text 편집 가능 |

**판정**: iOS [PASS/FAIL] / Android [PASS/FAIL]
**비고**:

---

## 6. 시나리오 E — 칼슘 (영문 비중)

| step | iOS ✓/✗ | iOS 캡처 | iOS elapsed | Android ✓/✗ | Android 캡처 | Android elapsed | 비고 |
|---|---|---|---|---|---|---|---|
| Upload + 결과 | | `ios-E-result.png` | __s | | `and-E-result.png` | __s | 영문 ingredient name 비율 |

**판정**: iOS [PASS/FAIL] / Android [PASS/FAIL]
**비고**:

---

## 7. 안전 위젯 폴백 (M-4 회귀 대비)

| step | iOS ✓/✗ | iOS 캡처 | Android ✓/✗ | Android 캡처 | 비고 |
|---|---|---|---|---|---|
| EmergencyResources 전화 탭 | | `ios-emergency-tap.png` | | `and-emergency-tap.png` | 현재 빈 알림 / M-4 적용 후 Clipboard SnackBar |
| Disclaimer 가시 + 한국어 표기 정확 | | (위 캡처) | | (위 캡처) | 금지 표현 0건 |
| ConsultProfessional 링크 동작 | | — | | — | 외부 브라우저 진입 / 또는 fallback |

---

## 8. 발견 이슈

> 회귀 / 신규 UX / 컴플라이언스 위반으로 분류. 각 이슈는 별도 GitHub issue
> 생성 권장.

### 8.1 회귀 (이전 M-3 통과 → 깨짐)
| # | 시나리오 | step | 증상 | 후속 |
|---|---|---|---|---|
| | | | | |

### 8.2 신규 UX 이슈
| # | 시나리오 | step | 증상 | 우선순위 (P0/P1/P2) | 후속 |
|---|---|---|---|---|---|
| | | | | | |

### 8.3 컴플라이언스 위반
| # | 위치 | 위반 표현 / 누락 위젯 | 즉시 fix 여부 |
|---|---|---|---|
| | | | |

---

## 9. 결론

| 영역 | 결과 |
|---|---|
| 회원가입 + 동의 cycle | [PASS/FAIL] |
| 시나리오 A (종합비타민) | iOS [P/F] / Android [P/F] |
| 시나리오 B (오메가3) | iOS [P/F] / Android [P/F] |
| 시나리오 C (긴 OCR, M-3-V.A) | iOS [P/F] / Android [P/F] |
| 시나리오 D (낮은 신뢰도) | iOS [P/F] / Android [P/F] |
| 시나리오 E (영문) | iOS [P/F] / Android [P/F] |
| **종합 판정** | [PASS / CONDITIONAL PASS / FAIL] |

**다음 단계**:
- (예시) M-3-V.C 자동 오류 시나리오 script 실행
- (예시) M-4 안전 위젯 polish 우선순위 조정
- (예시) read_timeout 추가 상향 (180s) 검토
