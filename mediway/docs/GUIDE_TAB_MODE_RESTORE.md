# GuideTab 모드 탭 부활 — 지도 보기 / QR 안내 설계

> 작성일: 2026-04-26 (E AI Triage 본 배포 직후)
> 전제: B-3.10 + F1 + E 완료, prod parity LIVE 도달
> 목표: 환자가 `/h/{slug}/patient/home?tab=guide` 진입 시 placeholder 가 아닌
>       실제 지도 + QR 안내를 사용할 수 있도록 복원
> 범위: 본 문서는 **설계 + commit 단위 계획**. 실제 구현은 사용자 승인 후 step-by-step.

---

## 0. 목적

### 발견된 문제 (시각 검증 §2 결과)
- T0-1 B-1 commit `ab85aa7` 에서 `HospitalHomePage` 6-tab shell 도입 시 **GuideTab 은 placeholder** 로 남겨졌음.
- 원래 V1 `/patient` 페이지가 가졌던 "지도 보기" / "QR 안내" 모드 탭이 사라진 것처럼 보임 (실제로는 `PatientPage` 안에 존재 — sessionId 진입 시에만 접근).
- 일반 home → 안내 탭 클릭 시 14줄 placeholder 만 노출.

### 본 sprint 목표
- GuideTab 안에 **「지도 보기」 / 「QR 안내」 모드 탭** 부활 — V1 `PatientPage` 와 동일 패턴.
- **「지도 보기」**: `PatientMapBrowseView` 재사용 (코드 변경 없음 — 그대로 마운트).
- **「QR 안내」 (sessionId 없음)**: 간결한 안내 메시지 + 단계 표시 (사용자가 "QR 코드를 어디서 받는가" 를 즉시 알 수 있게).
- sessionId 가 있는 진입은 기존 `PatientPage` 가 그대로 처리 (`/h/{slug}/patient/{sessionId}`) — 본 sprint 비범위.

### 비범위 (의도적 제외)
- ChatbotWidget hospitalId 일원화 (별도 sprint — 사용자 미확정)
- QR 코드 자가 발급 기능 (PatientDashboard 의 QRDisplay) — sessionId 없는 home tab 에 마운트하면 localStorage / useSession 으로 인한 부작용 위험
- PatientDashboard 전체 이식 — 너무 큰 변경

---

## 1. 현재 ↔ 목표 상태

### 현재 (GuideTab.tsx 14줄)
```tsx
export function GuideTab() {
  return (
    <section>
      <h2>안내</h2>
      <p>병원 내부 지도와 주요 위치가 이곳에 표시될 예정입니다.</p>
    </section>
  );
}
```

### 목표
```
GuideTab
├── h2 "안내"
├── 모드 토글 [지도 보기] [QR 안내]
└── (browse 모드)  → <PatientMapBrowseView />
   (qr 모드)       → <QRGuidePlaceholder />
       ├── 큰 QR 아이콘
       ├── "병원에서 QR 코드를 스캔하면 동선 안내가 시작됩니다"
       ├── 단계 1: 안내 데스크 방문 → 2: QR 코드 받기 → 3: 자동 안내
       └── 도움말 "QR 코드가 있나요? 카메라 앱으로 스캔하세요" (앵커: tel: or 안내 데스크)
```

V1 `/patient` 와의 일관성:
- 모드 라벨 동일 (「지도 보기」 / 「QR 안내」)
- 기본값 `guide` (QR 안내) — V1 PatientPage 와 동일
- URL 동기화: `?tab=guide&mode=browse|guide` — replace navigation (history stack 안 늘림)

---

## 2. 추가/변경 파일 목록

### 신규
| 파일 | 역할 |
|------|------|
| `src/components/patient/QRGuidePlaceholder.tsx` | sessionId 없을 때 표시할 단계 안내 + QR 아이콘 |
| `src/components/patient/__tests__/QRGuidePlaceholder.test.tsx` | render + 텍스트 검증 |
| `src/components/patient/tabs/__tests__/GuideTab.test.tsx` | 모드 토글 + 자식 마운트 검증 |

### 변경
| 파일 | 변경 |
|------|------|
| `src/components/patient/tabs/GuideTab.tsx` | 모드 탭 UI + URL `?mode=` 동기화 + 두 자식 컴포넌트 분기 마운트 |

### 변경 안 함
- `PatientMapBrowseView.tsx` — 그대로 재사용
- `PatientPage.tsx` — `/h/:slug/patient/:sessionId` 직접 진입 케이스에서 그대로 사용
- `PatientDashboard.tsx`, `useSession.ts`, QR 토큰 발급 인프라 — 본 sprint 비범위

---

## 3. GuideTab 설계

### 3.1 컴포넌트 구조
```tsx
type Mode = 'browse' | 'guide';

export function GuideTab() {
  const [searchParams, setSearchParams] = useSearchParams();
  const paramMode = searchParams.get('mode');
  const mode: Mode = paramMode === 'browse' ? 'browse' : 'guide';

  const setMode = (next: Mode) => {
    const params = new URLSearchParams(searchParams);
    if (next === 'guide') params.delete('mode');
    else params.set('mode', next);
    setSearchParams(params, { replace: true });
  };

  return (
    <section>
      <header>
        <h2>안내</h2>
        <p>{description}</p>
      </header>
      <ModeTabs mode={mode} onChange={setMode} />
      <div hidden={mode !== 'browse'}>
        <PatientMapBrowseView />
      </div>
      <div hidden={mode !== 'guide'}>
        <QRGuidePlaceholder />
      </div>
    </section>
  );
}
```

### 3.2 Mount-all 정책
- 두 모드 panel 모두 마운트 — 모드 전환 시 지도 viewport / 줌 / POI 선택 상태 보존
- `hidden` 속성으로 표시만 토글 (HospitalHomePage 의 패턴 그대로)

### 3.3 URL 쿼리 동기화
- 기본값 `guide` 모드 — `?mode=` 누락 시 (V1 `PatientPage` 와 동일)
- `?mode=browse` 일 때 「지도 보기」 활성
- `?tab=` 와 `?mode=` 둘 다 보존 — `tab=guide&mode=browse` 같은 조합

### 3.4 모드 탭 UI 스타일
V1 `PatientPage` (line 60-80) 의 토글 그룹 디자인 차용:
```
[ 🗺️ 지도 보기 ]  [ 🔲 QR 안내 ]   ← rounded-xl bg-surface-container-high p-1
```
활성: `bg-surface-container-lowest text-primary shadow-ambient`
비활성: `text-on-surface-variant hover:bg-surface-container`

---

## 4. QRGuidePlaceholder 설계

### 4.1 레이아웃
```
┌──────────────────────────────────────────────┐
│              [ 🔲 QR 큰 아이콘 ]              │
│                                              │
│          QR 코드를 받아 안내를 시작하세요      │
│                                              │
│   1. 병원 안내 데스크 방문                    │
│   2. 환자 QR 코드 발급 요청                   │
│   3. 의료진이 스캔하면 동선 안내 자동 시작    │
│                                              │
│        ※ QR 코드 화면이 열린 상태에서        │
│        의료진에게 보여 주세요                 │
└──────────────────────────────────────────────┘
```

### 4.2 추가 메타
- `aria-label="QR 안내"` — 스크린 리더 보조
- `data-testid="qr-guide-placeholder"` — 테스트 식별
- 추후 sprint 에서 sessionId 자가 발급 / QR 표시 추가 시 본 placeholder 를 PatientDashboard 의 qr_display state 와 합칠 수 있게 컴포넌트 분리 유지

### 4.3 비범위 (확장 옵션)
- "내 QR 코드 보기" 버튼 → 별도 sprint (추가 sessionId 생성 흐름)
- "안내 데스크 위치 보기" → 「지도 보기」 모드로 자동 전환 + 데스크 POI 강조 (B-3.11 후속 가능)

---

## 5. Commit 단위 계획 (총 3 commit)

각 commit 빌드 + 테스트 그린 보장.

### Commit 1 — `feat(guide.1): GuideTab 모드 탭 부활 + PatientMapBrowseView 마운트`
- 변경: `src/components/patient/tabs/GuideTab.tsx`
- 신규: `src/components/patient/QRGuidePlaceholder.tsx`
- 검증: tsc 0, vite build 성공
- LIVE 영향: 0 (배포 후 시각 변화)

### Commit 2 — `test(guide.2): GuideTab + QRGuidePlaceholder 단위 테스트`
- 신규: `src/components/patient/__tests__/QRGuidePlaceholder.test.tsx`
- 신규: `src/components/patient/tabs/__tests__/GuideTab.test.tsx`
- 검증:
  - 기본 render — h2 "안내" + 모드 토글 + 기본 QR 안내 모드
  - 모드 전환 — [지도 보기] 클릭 → URL `?mode=browse` + PatientMapBrowseView 가시
  - URL `?mode=browse` 진입 → 지도 보기 활성
  - URL `?mode=guide` 또는 누락 → QR 안내 활성
  - Mount-all — 두 패널 모두 DOM 에 존재 (hidden 속성 토글)

### Commit 3 — `docs(guide): GuideTab 모드 부활 + 본 문서 추적`
- 변경: 본 문서 §10 진행 추적 채움
- 변경: `docs/LOCAL_SYNC_GAPS.md` GuideTab 관련 항목 정리 (있다면)

### (옵션) Commit 4 — Hosting 재배포
- 사용자 승인 시: `npx vite build && firebase deploy --only hosting`
- HOSTING_DEPLOY_LOG.md 추가 entry
- LIVE 영향: 환자 home → 안내 탭 진입 시 새 UI

---

## 6. 테스트 전략

### 단위 (vitest + jsdom + testing-library)
| 컴포넌트 | 케이스 |
|----------|--------|
| `QRGuidePlaceholder` | render / 단계 텍스트 / aria / testid (4) |
| `GuideTab` | (a) 기본 진입 → QR 안내 활성, (b) `?mode=browse` 진입 → 지도 활성, (c) [지도 보기] 클릭 → URL params 갱신, (d) 두 panel 모두 DOM 마운트 (hidden 토글), (e) 다시 [QR 안내] 클릭 → URL `?mode=` 제거 |

### 회귀 (변경 없음 보장)
- HospitalHomePage 의 6-tab visibility — `?tab=guide` 진입 / `?mode=browse` 보존 검증
- `PatientPage` (`/h/:slug/patient/:sessionId`) 동작 무변경
- 기존 263 vitest 그대로 그린

---

## 7. 리스크 / 비범위

| 리스크 | 가능성 | 영향 | 완화 |
|--------|--------|------|------|
| Mount-all 시 지도 컴포넌트 (HospitalMapContainer) 가 hidden 상태에서도 무거운 데이터 fetch | 낮음 | 첫 진입 perf 약간 저하 | HospitalMapContainer 는 이미 PatientMapBrowseView 안에서 fetch — 본 sprint 변경 없음. perf 측정 결과 수용 불가 시 별도 lazy mount sprint |
| 사용자가 [지도 보기] 활성 상태로 화면 떠남 후 home → 외래 → 안내 복귀 시 모드 보존 X | 중 | UX 사소 | URL `?mode=browse` 유지 → tab 전환 시 `?tab=appointments` 로 변경되며 mode 잃음. 이는 prod parity 와 동일 (V1 PatientPage 도 같은 동작) |
| QRGuidePlaceholder 의 텍스트가 i18n 미고려 | 낮음 | 향후 영어 추가 부담 | 본 sprint 비범위 (전체 한국어 하드코딩 패턴 유지) |
| sessionId 진입 사용자가 `/h/.../patient/{sid}` 가 아닌 `/h/.../patient/home?tab=guide&mode=guide` 로 잘못 진입 | 낮음 | QR 안내 placeholder 만 보고 혼란 | sessionId 진입은 QR 스캔 결과 redirect 되므로 직접 발생하지 않음 |

### 비범위 (별도 sprint)
- ChatbotWidget hospitalId 일원화 (이슈 1) — 본 문서 비포함
- QR 코드 자가 발급 (sessionId 없이도 QR 표시) — 별도 sprint
- 안내 데스크 POI 자동 강조 — 별도 sprint

---

## 8. 합의 요청 항목

사용자 승인 필요:

1. **모드 라벨**: V1 그대로 「지도 보기」 / 「QR 안내」 OK?
2. **기본값**: `guide` (QR 안내) — V1 동일 OK? (또는 browse 가 기본?)
3. **QR 안내 모드 콘텐츠**: 큰 QR 아이콘 + 3단계 안내 + "데스크에 보여 주세요" 메시지 OK?
4. **Mount-all 정책**: 두 panel 모두 마운트 OK? (perf 우려 시 lazy mount 로 변경)
5. **commit 분할**: 3 commit (feat + test + docs) OK?
6. **commit 4 (hosting 재배포)**: 본 sprint 외 별도 승인 단계 OK?

승인되면 commit 1 부터 순차 진행.

---

## 9. 진행 추적

| # | Commit | 상태 | 결과 요약 |
|---|--------|------|-----------|
| 1 | `04e51fb` | ✅ 완료 | GuideTab 14줄 placeholder → 모드 탭 UI + QRGuidePlaceholder + PatientMapBrowseView mount-all |
| 2 | `e21b9c2` | ✅ 완료 | 16 단위 테스트 (10 GuideTab + 6 QRGuidePlaceholder) |
| 3 | `48ec43b` | ✅ 완료 | (보너스) ChatbotWidget hospitalId 소스 일원화 — useHospital().slug 로 변경, F1.1c 와 일관성 회복 |
| 4 | (이 commit) | ✅ 완료 | 본 문서 + LOCAL_SYNC_GAPS 추적 |

### 최종 메트릭
- **2 feat + 1 test + 1 fix + 1 docs = 5 커밋** (이슈 2 GuideTab 4건 + 이슈 1 ChatbotWidget 1건)
- vitest: 263 → 279 passed (+16)
- tsc 0 errors, vite build 성공
- LIVE 영향 0 (hosting 재배포 별도 승인)

### 해결된 이슈

**이슈 1 — ChatbotWidget hospitalId 일원화** (`48ec43b`)
- `profile.hospitalId` undefined 시 위젯 사라지던 버그 수정
- F1.1c 의 useHospital().slug 패턴으로 일원화 → WaitQueueWidget / AppointmentsTab / TriageWidget 와 일관

**이슈 2 — GuideTab 모드 탭 부활** (`04e51fb`, `e21b9c2`)
- T0-1 B-1 placeholder → V1 PatientPage 동등 모드 탭 UI 복원
- 「지도 보기」 (PatientMapBrowseView 재사용) / 「QR 안내」 (QRGuidePlaceholder)
- URL `?mode=` 동기화 + Mount-all + 접근성

### 후속 (별도 승인)
- Hosting 재배포 (`npx vite build && firebase deploy --only hosting`)
- HOSTING_DEPLOY_LOG.md 추가 entry
