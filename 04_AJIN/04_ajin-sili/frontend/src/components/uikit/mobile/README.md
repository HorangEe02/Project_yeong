# AJIN Mobile UI Kit — Reference Components

> **출처**: `uiux/AJIN AI Assistant Design System/ui_kits/mobile/` (v3.5, 2026-04-26)
> **상태**: Reference only — 본 디렉토리의 컴포넌트는 frontend 의 실 페이지에서 직접 import 되지 않음.
> 디자인 패턴 인용 + 점진 적용용 보존.

## 파일 인벤토리 (9 files, 약 4,030 lines)

| 파일 | 줄수 | 역할 |
|---|---|---|
| `MobScreens.jsx` | 594 | iPhone 모바일 화면 reference (login splash, dashboard greet, search, chat) |
| `MobNeuralScreens.jsx` | 236 | Neural Expressive 모바일 변형 (ne-greet ombre / ne-card / ne-pill 적용) |
| `PadScreens.jsx` | 314 | iPad 태블릿 화면 reference |
| `PadModules.jsx` | 583 | 태블릿 모듈별 컴포넌트 (Dashboard / Chat / Search) |
| `AjinTweaks.jsx` | 92 | Tweaks 패널 — Style/Glow/Liquid Glass/Gold accent/Device frame 조정 |
| `tweaks-panel.jsx` | 530 | Tweaks 패널 본체 — slider/radio/segmented 컨트롤 + edit mode 프로토콜 |
| `ios-frame.jsx` | 460 | iPhone bezel + Dynamic Island frame (titanium/space-black/silver) |
| `design-canvas.jsx` | 622 | 디자인 canvas — 다중 device frame 동시 preview |
| `Icons.jsx` | 19 | 공용 SVG 아이콘 모음 |

## 사용 가이드

### 1. 디자인 패턴 인용 (현재 권장)

본 디렉토리의 컴포넌트는 **vanilla JSX prototype** (React + Babel inline) 으로
작성됨. ES module / TypeScript 변환 없이는 frontend 페이지에서 직접 import 불가.

대신 **CSS class + 구조 패턴** 만 인용:

- **Liquid Glass v3**: `.aj-glass`, `.aj-divlist`, `.aj-toast`
  → `frontend/src/styles/mobile-theme.css` + `mobile-theme-v3.css` 이미 통합
- **App Store pattern**: `.aj-as-sect`, `.aj-as-card`, `.aj-as-eyebrow`
- **Pill composer**: `.aj-pill`, `.aj-pill .send`
- **Daily Brief card**: `.aj-brief-card`, `.aj-brief-stat`
- **Suggested list**: `.aj-suggest-list`, `.aj-suggest-row`
- **Bottom Nav (5탭)**: `.aj-bottom-nav` — 이미 `BottomTabBar.tsx` 로 구현됨
- **iOS Dynamic Island**: `.aj-island.pill` / `.wide` / `.minimal`

### 2. Tweaks 패널 통합 (별도 PR 권장)

`AjinTweaks.jsx` + `tweaks-panel.jsx` 를 frontend 의 settings 페이지 또는 floating
dev button 으로 노출하면 시연 시 강력한 demo:

```jsx
const TWEAK_DEFAULTS = {
  style: 'neural',
  lgBlur: 36,
  lgSat: 1.8,
  lgEdge: 1,
  lgTintA: 0.08,
  goldH: 1,
  bezelTone: 'titanium',
  island: 'pill',
};

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  useEffect(() => {
    document.documentElement.style.setProperty('--lg-blur', `${tweaks.lgBlur}px`);
    document.documentElement.style.setProperty('--lg-sat', tweaks.lgSat);
    // ...
  }, [tweaks]);

  return (
    <>
      <Shell />
      <AjinTweaks tweaks={tweaks} setTweak={setTweak} />
    </>
  );
}
```

→ 향후 `frontend/src/routes/profile-design-tweaks.tsx` 또는 dev panel 로 통합.

### 3. 페이지별 reference 활용

`MobScreens.jsx` / `MobNeuralScreens.jsx` 의 컴포넌트 → frontend 페이지 마이그레이션
참조:

- **Login splash** → `MobScreens.jsx :: LoginScreen` 의 brand 위치 / button gradient
- **Dashboard greet** → `MobNeuralScreens.jsx :: DashboardScreen` 의 `ne-greet` ombre
- **Daily Brief card** → `MobScreens.jsx :: BriefCard` 의 lens tint + headline
- **Search module 카드** → 노란 (SOP) / 녹색 (QM) / 빨간 (REG) gold tint variants
- **Pill composer** → `MobScreens.jsx :: PillComposer` 의 send 버튼 amber

각 패턴을 frontend 의 해당 페이지에 점진 적용 (`feat/ui-page-*` 후속 PR).

## CSS Knobs (사용자 노출 가능)

`mobile-theme-v3.css` 가 노출하는 CSS variables (이미 frontend 통합):

| 변수 | 기본값 | 효과 |
|---|---|---|
| `--lg-blur` | 36px | Liquid Glass blur 반경 |
| `--lg-sat` | 1.8 | backdrop saturation |
| `--lg-bright` | 1.06 | backdrop brightness |
| `--lg-edge` | 1 | specular edge intensity (0~1) |
| `--lg-tint-a` | 0.08 | primary tint amount (0~0.3) |
| `--aj-gold-h` | 1 | gold accent hue intensity (0~1) |
| `--aj-radius` | 22px | card corner radius |

→ DevTools 또는 향후 Tweaks 패널에서 동적 조정 가능.

## 향후 통합 로드맵

| 단계 | 작업 | PR (예정) |
|---|---|---|
| 1 | Tweaks 패널 React 컴포넌트 변환 + Settings 라우트 추가 | `feat/ui-tweaks-panel` |
| 2 | MobScreens 의 Daily Brief 카드 → dashboard.tsx 마이그레이션 | `feat/ui-dashboard-brief` |
| 3 | MobNeuralScreens 의 ne-greet → dashboard / chat 적용 | `feat/ui-greet-ombre` |
| 4 | iOS Dynamic Island pill → TopBar 모바일 변형 | `feat/ui-dynamic-island` |
| 5 | PadScreens / PadModules → 태블릿 페이지 reference 적용 | `feat/ui-tablet-pages` |

## 라이센스

본 reference 컴포넌트는 AJIN AI Assistant Design System v3.5 의 산출물.
폰트 (A2Z): SIL OFL 1.1 (`frontend/public/fonts/LICENSE.txt`).
컴포넌트 코드: 내부 사용 — AJIN 산업 SILLI 2026 본선 시연 한정.
