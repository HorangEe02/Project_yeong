# 환자 페이지 신규 기능 3건 — 가능성 평가 + 상세 계획

> 작성일: 2026-04-26 (QR 자가 발급 본 배포 직후)
> 사용자 요청 기능: ① 탭 가운데 정렬, ② 외래 내역 날짜/월/년 드롭다운 필터, ③ 안내 탭 응급 호출 (119+위치)
> 본 문서는 **가능성 평가 + 위험 분석 + 단계별 commit 계획**. 실제 구현은 사용자 승인 후 step-by-step.

---

## 0. 한 줄 평가

| # | 기능 | 가능? | 난이도 | 1회용 / 영구 가치 | 권장 |
|---|------|-------|--------|------------------|------|
| 1 | 탭 가운데 배치 | ✅ 즉시 | 매우 낮음 (CSS 1줄) | 영구 UX | ★★★ |
| 2 | 외래 날짜/월/년 드롭다운 필터 | ✅ 즉시 | 중 (~80줄 + 테스트) | 영구 — 누적 데이터 많아질수록 가치↑ | ★★★ |
| 3 | 응급 호출 (119 + 위치 공유) | ✅ 가능 (제한 사항 있음) | 중 (~120줄 + 윤리 검토) | 영구 — 그러나 책임/오용 위험 | ★★ |

세 기능 모두 **기술적으로 100% 구현 가능**. 다만 **기능 ③** 은 윤리·법적 검토 필요 (실제 119 통화 트리거).

---

## 1. 기능 ① — 탭 가운데 배치

### 1.1 현재
`src/pages/HospitalHomePage.tsx:81` — 탭 `<nav role="tablist">` 의 className:
```tsx
className="sticky top-[60px] z-10 flex gap-1 overflow-x-auto border-b border-outline-variant bg-surface py-2"
```
→ 기본 `flex` 의 `justify-start` 가 좌측 정렬.

### 1.2 변경
`flex` → `flex justify-center` 추가. (또는 데스크톱 width 가 좁을 때 좌측 유지를 위해 `sm:justify-center` 도 가능)

```tsx
className="... flex justify-center gap-1 overflow-x-auto ..."
```

### 1.3 위험
- 모바일 좁은 화면에서 탭이 화면 폭 초과 시 — `overflow-x-auto` 와 `justify-center` 조합 시 스크롤 시작점이 첫 탭이 되어 약간 어색할 수 있음
  - 완화: `justify-center` 만 적용하면 컨테이너가 충분히 넓을 땐 가운데, 좁을 땐 자동으로 left 시작 (브라우저 default behavior)

### 1.4 결과
시각적으로 정렬만 변경. 단위 테스트 없음 (스타일 only).

---

## 2. 기능 ② — 외래 내역 날짜/월/년 드롭다운 필터

### 2.1 현재
`AppointmentsTab.tsx`:
- `subscribeMyAppointments` 가 모든 예약을 scheduledAt 순으로 반환
- 카드 list 에서 평면 list 로 표시 (그룹화·필터 없음)
- 카드: 부서명 / 상태 뱃지 / 일시 / [접수]·[취소] 버튼

### 2.2 목표
드롭다운 + 그룹화:
- 드롭다운 「일별」 / 「월별」 / 「년별」 (default: 일별)
- 그룹 헤더 (예: "2026-04-26 (일)" / "2026-04 (4월)" / "2026")
- 각 그룹 안에 카드 list

추가 보너스 (제안):
- 「과거 / 오늘 / 미래」 toggle — 흔한 UX 패턴
- 검색 box (부서명 부분 매치)

### 2.3 데이터 흐름
```ts
type Granularity = 'day' | 'month' | 'year';

// scheduledAt (epoch ms) → KST 기준 그룹 키
function groupKey(scheduledAt: number, gran: Granularity): string {
  const kst = new Date(scheduledAt + 9 * 60 * 60 * 1000);
  const yyyy = kst.getUTCFullYear();
  const mm = String(kst.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(kst.getUTCDate()).padStart(2, '0');
  if (gran === 'year') return `${yyyy}`;
  if (gran === 'month') return `${yyyy}-${mm}`;
  return `${yyyy}-${mm}-${dd}`;
}

// 그룹화 (ordered Map 으로 정렬 보존)
function groupAppointments(
  list: AppointmentPatientIndex[],
  gran: Granularity,
): Map<string, AppointmentPatientIndex[]>;
```

### 2.4 UI 변경
- 드롭다운 `<select>` 또는 button group (선호: button group — 모바일 친화적)
- 그룹 헤더: `<h3 className="sticky top-N">` — 스크롤 시 보이게
- 빈 그룹은 표시 안 함

### 2.5 위험
- 예약 0건 사용자에게는 드롭다운이 무의미하므로 0건일 땐 드롭다운 숨김
- 데이터 양이 작을 때 (예: 1건) 드롭다운 noise — 5건 이상일 때만 노출 등 정책 결정 필요

### 2.6 비범위
- 사용자 정의 날짜 범위 (date range picker) — 별도 sprint
- 부서별 필터 — 별도 sprint
- 서버측 페이지네이션 (현재 RTDB 전체 fetch)

---

## 3. 기능 ③ — 응급 호출 (119 + 위치 공유)

### 3.1 기술 스택
- **`tel:119` 링크** — `<a href="tel:119">` — 모든 모던 브라우저 + 모바일 OS 지원. 클릭 시 OS 전화 앱 자동 시작.
- **`navigator.geolocation.getCurrentPosition()`** — 표준 Web API. HTTPS 필수 (LIVE OK).
- **권한 prompt** — 첫 호출 시 브라우저가 위치 권한 요청. 거부 시 fallback 필요.
- **지도 링크** — Google Maps `https://maps.google.com/?q=lat,lng` 또는 Kakao `https://map.kakao.com/?q=...`.

### 3.2 UX 설계
```
┌─────────────────────────────────────┐
│  🚨 응급 호출                        │
│                                     │
│  지금 도움이 필요하세요?             │
│  119 통화 + 현재 위치 공유합니다     │
│                                     │
│   [ 🆘 119 신고 ]                   │
│                                     │
│   현재 위치 (대기 중...)             │
│   위도: 37.xxxxx                    │
│   경도: 127.xxxxx                   │
│   [ 🗺️ 지도에서 보기 ] (Google Maps)│
│                                     │
│   ※ 119 통화 중 위치를 직접 알려    │
│   주세요. 자동 전송 기능은 없습니다.│
└─────────────────────────────────────┘
```

### 3.3 동작 시퀀스
1. 사용자가 안내 탭 → 「응급 호출」 모드 진입 (또는 별도 탭/카드)
2. 위치 권한이 없으면 자동으로 prompt 요청 (또는 명시적 「위치 가져오기」 버튼)
3. 위치가 도착하면 위도/경도 + 지도 링크 표시
4. 「🆘 119 신고」 클릭 → `tel:119` → OS 전화 앱
5. 사용자가 통화 중 화면에 표시된 위치를 119 상담사에게 직접 안내

### 3.4 윤리 / 법적 검토 (중요)
- ❗ **데모 환경에서 실수로 119 통화 트리거 위험** — 한국 119 는 허위 신고 시 과태료 가능
- 완화 옵션:
  - **(A) 확인 dialog** — "정말 119 에 전화하시겠습니까?" → 명시적 두 번째 클릭
  - **(B) "데모 모드" 표시** — 위 confirm 후에도 진짜 통화 트리거. 책임 면제 X
  - **(C) Hospital features.emergencyCall flag** — admin 가 토글한 hospital 만 활성. demo 는 default off.
  - **(D) localhost / preview 채널에서는 tel: 차단** — `firebase deploy preview` 일 때 특수 처리

권장 조합: **A + C** (확인 dialog + features 가드).

### 3.5 위치 공유 — 병원 RTDB 전송 (옵션, 별도 sprint)
- `/hospitals/{hid}/emergency_calls/{pushId}` 신규 path:
  ```ts
  { uid, lat, lng, accuracy, timestamp, status: 'active' | 'resolved' }
  ```
- staff console 에 "응급 호출" 알림 패널 추가 (별도 sprint)
- 본 sprint 비범위 — 본 sprint 는 119 통화 + 화면 위치 표시만

### 3.6 위험
| 위험 | 가능성 | 영향 | 완화 |
|------|--------|------|------|
| 실수 클릭 → 119 허위 신고 | 중 | 법적 책임 + 119 자원 낭비 | 확인 dialog (A) + features 가드 (C) |
| 위치 권한 거부 → 정보 표시 안 됨 | 중 | 위치 안내 불가, 119 통화는 가능 | 거부 시 fallback "수동 안내" 메시지 |
| HTTPS 필요 | 낮음 | LIVE OK / dev local 은 HTTPS X 시 동작 안 함 | dev 환경에서 stub geolocation 또는 `localhost` HTTPS 우회 |
| 정확도 낮음 (실내 GPS) | 중 | 위치 ±100m 오차 | 정확도 표시 + 사용자가 119 와 통화 중 보정 |
| iOS Safari 권한 정책 | 중 | 권한 prompt 시점 차이 | 명시적 버튼 클릭 후 요청 (Safari 정책 준수) |

---

## 4. 구현 우선순위 + Commit 단위 계획

세 기능을 **단일 sprint** 로 묶어서 진행하는 것이 효율적 (변경 영역이 patient page 안에 모두 있고 회귀 위험 분리 명확).

### Phase A — 기능 ① + ② (회귀 0)
| # | Commit | 변경 |
|---|--------|------|
| 1 | `feat(ui.center-tabs)` | HospitalHomePage 탭 nav 에 `justify-center` 추가 (~3줄, 시각만) |
| 2 | `feat(appointments.filter)` | AppointmentsTab — 일/월/년 드롭다운 + 그룹화 helper + 그룹 헤더 UI |
| 3 | `test(appointments.filter)` | 그룹화 helper 단위 테스트 (KST 경계 / 빈 그룹 / 다중 entries) + 드롭다운 토글 |

### Phase B — 기능 ③
| # | Commit | 변경 |
|---|--------|------|
| 4 | `feat(emergency.1)` | EmergencyCallCard 컴포넌트 (위치 hook + tel:119 + 지도 링크 + 확인 dialog) |
| 5 | `feat(emergency.2)` | GuideTab 에 응급 호출 모드 추가 (또는 separate panel/tab — 결정 필요) + features.emergencyCall 가드 |
| 6 | `test(emergency)` | EmergencyCallCard 단위 테스트 (geolocation mock / 권한 거부 / dialog 흐름 / features off) |

### Phase C — 마무리
| # | Commit | 변경 |
|---|--------|------|
| 7 | `docs(patient-features)` | 본 문서 진행 추적 + LOCAL_SYNC_GAPS / HANDOFF 갱신 |

### (옵션) Phase D — Deploy
| # | Commit | 변경 |
|---|--------|------|
| 8 | (deploy) | `npx vite build && firebase deploy --only hosting` + HOSTING_DEPLOY_LOG entry |

총 **7 commit + 1 옵션** = 7~8 commits.

### Phase B 의 "응급 호출" 진입점 결정 옵션
- **B-1**: GuideTab 안에 3rd 모드 추가 (지도 보기 / QR 안내 / **응급 호출**)
- **B-2**: 새 6번째 탭 「응급」 추가 — 항상 노출, prominent
- **B-3**: HomeTab 상단에 항상 노출되는 빨간 카드

권장: **B-1** (안내 컨텍스트 안에 있는 것이 자연스러움 + 신규 탭 추가 부담 X).

---

## 5. 리스크 종합

| 카테고리 | 리스크 | 본 sprint 처리 |
|----------|--------|--------------|
| 기술 | tel:119 가 desktop 에서 동작 안 함 | OK (모바일 응급 시나리오만 의도됨) |
| 기술 | iOS Safari geolocation 권한 prompt | 명시적 버튼 후 요청 (Safari 정책) |
| 윤리 | 실수 클릭 → 119 허위 신고 | 확인 dialog 강제 + 데모 banner |
| 정책 | features.emergencyCall 미정의 | FEATURE_DEFAULTS 에 false 추가, admin 가 명시 enable 후 노출 |
| UX | 데이터 0건 사용자에게 필터 noise | 필터 UI 는 entries.length >= 5 일 때만 |
| 회귀 | 탭 가운데 → 좁은 화면 스크롤 어색 | sm:justify-center 만 적용 |

---

## 6. 합의 요청 항목

사용자 승인 필요:

### 일반
1. **세 기능 일괄 진행**: Phase A + B + C OK? (또는 일부만)
2. **단일 sprint vs 분리**: 7-8 commit 한 번에 OK?
3. **commit 8 (deploy)**: 별도 승인 단계 OK?

### 기능 ① 탭 가운데
4. `justify-center` 적용 OK? (모든 화면 폭 vs `sm:justify-center` 만)

### 기능 ② 필터
5. 필터 UI: button group OK? (또는 `<select>`)
6. 그룹 헤더 sticky? OK
7. 데이터 0~4건일 때 필터 자동 숨김 OK?
8. 보너스: 「과거/오늘/미래」 toggle 추가 OK? (또는 비범위)

### 기능 ③ 응급
9. 응급 호출 진입점: B-1 (GuideTab 3rd 모드) OK? (또는 B-2/B-3)
10. 확인 dialog 강제 OK? ("정말 119 에 전화하시겠습니까?")
11. `features.emergencyCall` 가드 OK? (default false, admin 명시 enable)
12. 위치 공유 — 본 sprint 에선 화면 표시만, 병원 RTDB 전송은 별도 sprint OK?

승인되면 commit 1 부터 순차 진행.

---

## 7. 진행 추적

| # | Commit | 상태 | 결과 요약 |
|---|--------|------|-----------|
| 1 | `1da6ccf` | ✅ 완료 | HospitalHomePage 탭 nav `justify-center` (1줄 변경) |
| 2 | `4d28991` | ✅ 완료 | AppointmentsTab 그룹화 helper + 「일별/월별/년별」 button group + sticky 헤더 + 5건 미만 시 자동 숨김 |
| 3 | `810cf18` | ✅ 완료 | 그룹화 helper 단위 테스트 (18 케이스 — KST 자정 경계 포함) |
| 4 | `49b70cb` | ✅ 완료 | EmergencyCallCard — 119 통화 + 위치 표시 + 확인 dialog (LocationState 머신) |
| 5 | `2da2aeb` | ✅ 완료 | GuideTab 'emergency' 3rd 모드 + FEATURE_DEFAULTS.emergencyCall=false 가드 |
| 6 | `2a7bc2c` | ✅ 완료 | EmergencyCallCard 단위 테스트 (15 케이스) + tel: 링크 정리 (button 안 a 중첩 제거) |
| 7 | (이 commit) | ✅ 완료 | docs |

### 최종 메트릭
- **6 feat/test commit + 1 docs commit = 7 커밋**
- vitest: 297 → **330 passed** (+33: 18 grouping + 15 emergency)
- tsc 0 errors, vite build 성공
- LIVE 영향 0 — hosting 재배포 별도 승인

### 사용자 영향 (배포 후)

| 흐름 | 변화 |
|------|------|
| 모든 환자 페이지 | 6-tab nav 가운데 정렬 |
| 외래 탭 (5건 이상) | 「일별/월별/년별」 button group + 그룹 헤더 + 카운트 |
| 안내 탭 — features.emergencyCall=true 한 hospital | 「응급 호출」 3rd 모드 추가 (빨간 강조) → 119 + 위치 + 확인 dialog |
| 안내 탭 — features.emergencyCall=false (default) | 변동 없음 (지도 보기 / QR 안내 두 탭만) |

### 후속 (별도 승인)

#### 7.1 Hosting 재배포
- `npx vite build && firebase deploy --only hosting`
- HOSTING_DEPLOY_LOG.md 추가 entry
- 시각 검증:
  1. `/h/demo/patient/home` → 탭 가운데 정렬 확인
  2. AppointmentsTab → 5건 이상 시 button group 표시 + 그룹화 동작
  3. (admin 가 features.emergencyCall=true 토글 후) 안내 탭 → 「응급 호출」 모드 추가 / 119 + 위치 + 확인 dialog

#### 7.2 별도 sprint 가능
- 「과거/오늘/미래」 toggle (보너스, 본 sprint 비범위)
- 부서별 / 사용자 정의 날짜 범위 필터
- 응급 호출 시 병원 RTDB 자동 전송 + staff 콘솔 알림 패널
- 응급실 수용 가능 인원 표시
- 보호자 자동 알림 (FCM/SMS)
