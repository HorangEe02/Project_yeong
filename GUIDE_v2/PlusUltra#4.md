# PlusUltra #4 — 고령자·접근성·OAuth·가족 대리 상세 구현 가이드

> **Phase 4 기능 설명서 + 구현 가이드라인**
> 범위: 고령자 모드 · TTS 음성 안내 · OAuth 확장(카카오/Apple/네이버) · 홈 응급 버튼 · 가족 계정 연동
> 예상 기간: 3주 (1인 풀타임, UIUX·심사 포함 ≈ 15~17일)
> 선행 요건: **Phase 1·2·3 완료** — 대시보드·탭·알림 인프라가 작동해야 하며, 더보기 탭에 설정 스켈레톤이 있어야 함

---

## 목차

- [起 — 왜 지금 접근성·가족인가](#起--왜-지금-접근성가족인가)
- [承 — 설계 원칙과 기술 선택](#承--설계-원칙과-기술-선택)
- [轉 — 세부 구현 설계](#轉--세부-구현-설계)
  - [1. 고령자 모드 (F16)](#1-고령자-모드-f16)
  - [2. 음성 길안내 / TTS (F17)](#2-음성-길안내--tts-f17)
  - [3. OAuth 로그인 확장 (F15)](#3-oauth-로그인-확장-f15)
  - [4. 응급 버튼 (F10)](#4-응급-버튼-f10)
  - [5. 가족 계정 연동 (F7)](#5-가족-계정-연동-f7)
  - [6. 데이터 스키마 확장](#6-데이터-스키마-확장)
  - [7. 보안 규칙 확장](#7-보안-규칙-확장)
  - [8. 규제·법률 대응](#8-규제법률-대응)
- [結 — 완료 기준·검증 전략·Next](#結--완료-기준검증-전략next)
- [UIUX 가이드라인](#uiux-가이드라인)
- [부록](#부록)

---

## 📌 v2 업데이트 (2026-04-22)

> **이 파일은 PlusUltra v1 상세 가이드입니다.** v2 기준 문서 `GUIDE_v2/plusultra_v2.md` §Phase 4가 최종 실행 기준이며, 충돌 시 **v2가 우선**합니다.

### Phase 4 v2 조정사항

| # | 조정 | v1 대비 | 영향 섹션 |
|---|---|---|---|
| 1 | 🔥 **가족 대리 (F7) MOAT 1순위 격상** | v1은 P4 일반 기능 | §5. 가족 계정 연동 — **영업 Top 3 셀링 포인트 1순위**. MyChart · 똑닥 · 세브란스 · 아산 모두 미지원이 MediWay의 가장 큰 경쟁 우위 |
| 2 | 🔻 **F17 TTS 핵심 경로만** | v1은 전역 TTS + Cloud TTS 서버 백업 포함 | §2. TTS — **지도 길찾기 음성 안내만** 구현. 앱 전역 TTS(홈 위젯 읽기 등) · Cloud TTS 서버 백업은 P5 이후 |
| 3 | ⏸ **네이버 OAuth 연기** | v1은 정식 구현 | §3. OAuth 확장 — **카카오 + Apple Sign-In만**. 네이버는 P5 이후. 커버리지 95%+ 확보됨 |
| 4 | 🆕 **F20 Apple Watch / 삼성헬스 바이탈 연동 신규** (v1에 없음) | — | **신규 §5.5** 개념: HealthKit(iOS) · Samsung Health SDK → 심박 · 걸음 · 수면 **읽기만**. 공유는 가족 대리 · 의료진 메시지(P5). Capacitor 래퍼 필요 여부 P4 후반 결정 |
| 5 | 🔸 **고령자 모드는 P2 인프라 위에 "완성" 단계** | v1은 P4에서 처음 빌드 | §1. 고령자 모드 — P2에서 이미 토글 · CSS custom property · `.ui-senior` root class가 깔려 있음을 전제로, font scale · 위젯 축소 · 단어 치환만 담당 |
| 6 | 🔸 **응급 버튼 (F10) 위치 확정** | v1은 P4에서 배치 | P2에서 이미 홈 위젯 3개 중 하나로 확보. P4에서는 확인 모달 1단계(119 오발신 방지) + tel:119 연결만 마무리 |

### 신규 §5.5 — Apple Watch / 삼성헬스 연동 (F20) 핵심

- **iOS**: HealthKit (Capacitor 래퍼 필요)
- **Android**: Samsung Health SDK 또는 Google Fit fallback
- **P4 범위**: 읽기만 — 심박 · 걸음 · 수면 · 활동
- **표시**: 홈 위젯 선택 슬롯 "최근 심박 72bpm · 걸음 3,450"
- **공유**: 가족 대리(이 파일 F7) · 의료진 메시지(PlusUltra#5)
- **Privacy**: 명시 동의 · Firebase Storage 암호화 · 즉시 삭제 지원
- **P5 확장**: 실시간 구독 · 이상치 알림 · 의료진 자동 공유

상세는 `plusultra_v2.md` §4.6 및 §부록 C.F20 참조.

### MOAT 강조 (가족 대리)

v1은 F7을 P4 내 일반 기능으로 취급. v2는 **MOAT 랭킹 #1**로 격상:
- MyChart: 가족 계정 지원 미흡
- 똑닥: 제한적
- 세브란스 · 서울아산: 미지원
- **한국 가족 문화와 최고 궁합** — 자녀가 부모 앱 대리 관리, 재방문률·충성도 상승

영업 자료·랜딩 페이지에서 **대표 MOAT로 노출**.

### 적용 원칙

- 고령자 모드 상세 UI · TTS 기술 · OAuth 통합 · JWT 초대 토큰 · 권한 2단계(읽기/대리) · audit: **v1 원안 준수**
- TTS 스코프 · 네이버 연기 · Apple Watch 신규 · 가족 대리 격상 · 응급 버튼 P2 위치: **v2 기준**
- 의심 시 `GUIDE_v2/plusultra_v2.md` §"Phase 4" 및 §"부록 A. MOAT 랭킹" 확인

---

## 起 — 왜 지금 접근성·가족인가

### 사용자 구성의 현실

한국 의료앱의 실제 사용자는 두 극단으로 나뉜다:
- **디지털 네이티브**: 20~40대. 예약·결제·길찾기를 빠르게 소화
- **디지털 이민자**: 60대 이상. 앱이 "한 화면이 여러 개로 바뀌고 글자가 작은" 지점에서 탈락

사용자 연구(DBpia 고령자 UI 평가 연구)에 따르면 고령자 UI 실패 영역은 4가지: **디자인·콘텐츠·프로세스·시스템**. P1-P3를 구축하며 첫 3가지에 집중했지만, **"사용성"이라는 관점에서 본격적인 고령자 친화**는 P4가 첫 번째 기회다.

또한 MyChart 리뷰에서 가장 많이 언급되는 불만은:
- "기능이 너무 많다"
- "디지털 친숙도가 요구된다"
- "연결된 가족 계정이 없어 부모 대신 관리가 어렵다"

P4는 이 세 가지를 **"간단 모드 + OAuth 로그인 간소화 + 가족 대리"**로 동시에 해결한다.

### 응급 버튼의 존재 이유

병원 앱은 본질상 **사람이 아프거나 불안한 순간**에 사용된다. 홈 화면에 진료 예약이 있어도, **"응급실에 가야 할 때"** 바로 인도할 수 있는 경로가 별도로 있어야 한다. 이것은 기능이라기보다 **브랜드 신뢰의 기초**다.

### OAuth의 비용 대비 효용

이메일·비밀번호 입력은 고령자에게 **첫 번째 이탈 지점**이다. 카카오·Apple·네이버는 한국 사용자에게 이미 보편. 로그인 완료율을 10~20%p 올릴 수 있다는 것이 업계 경험.

### Phase 4의 4대 가치

1. **포용성(Inclusivity)** — 60대+ 환자가 보호자 도움 없이 앱을 쓸 수 있어야 MediWay가 "병원의 공식 앱"이 된다
2. **가족 효과(Proxy)** — 자녀가 부모 앱을 대신 관리 → 재방문률·충성도 상승
3. **안전감(Safety)** — 응급 버튼이 주는 심리적 안정
4. **전환율(Conversion)** — OAuth로 로그인 마찰 감소, 재로그인 시 이메일·비번 기억 스트레스 제거

---

## 承 — 설계 원칙과 기술 선택

### 원칙 9계명

1. **접근성은 옵션이 아니라 기본** — 고령자 모드는 토글이지만, 모든 컴포넌트는 토글 꺼진 상태에서도 WCAG 2.1 AA 통과
2. **한 화면 = 한 행동** (고령자 모드) — 주요 액션 1~2개로 축소
3. **TTS는 사용자 허락 + 명시적 트리거** — 자동 재생 금지 (iOS Safari 정책과도 일치)
4. **OAuth는 보조, 이메일은 유지** — 플랫폼 벤더 종속 방지
5. **가족 권한은 "읽기"와 "대리"로만 분리** — 세밀한 RBAC 남용 금지
6. **민감 정보 접근은 이벤트 로깅** — 가족 대리가 진단명을 읽어도 audit에 기록
7. **응급 버튼은 어디서든 도달** — 홈 고정 + 더보기·헤더에도 중복 배치
8. **동의는 철회 가능하고 타임스탬프 보관** — PIPA 기본
9. **실패 모드 명확화** — TTS 미지원 브라우저·OAuth 취소·가족 초대 만료 시 명시적 UI

### 기술 스택 선택 근거

| 영역 | 선택 | 대안 | 이유 |
|---|---|---|---|
| 고령자 모드 스케일링 | **CSS class `.ui-senior` on `<html>` + var 조정** | Tailwind config 분기 | 런타임 즉시 전환, 빌드 영향 없음 |
| 큰 글자 방식 | **`font-size` root 조정 + `em` 기반 컴포넌트** | 개별 클래스 scale-up | 정돈·일관성. Tailwind `rem`이 이미 root 기반 |
| TTS | **Web Speech API `SpeechSynthesis`** | 서버 TTS(Google Cloud Text-to-Speech) | 클라 내장 무료. 한국어 음성 품질 iOS 우수 |
| TTS 백업 | Cloud TTS 녹음 후 Storage 캐싱 | 즉시 재생만 | 긴 안내(1분+)는 서버 TTS 품질 우위. P4 옵션 |
| 카카오 로그인 | **카카오 JS SDK + Firebase Custom Token** | GCIP 멀티테넌시 | Firebase가 카카오 직접 지원 X. Custom Token flow가 표준 |
| Apple Sign-In | **Firebase Auth OAuthProvider('apple.com')** | 순수 구현 | Firebase가 1급 지원, 심사 요건 자동 충족 |
| 네이버 로그인 | Naver JS SDK + Custom Token (카카오와 동일 패턴) | 미지원 | 선택 (필수는 카카오+Apple) |
| 응급 번호 전화 | `tel:119` | WebRTC VoIP | 표준, 권한 필요 없음 |
| 가족 초대 링크 | JWT 단일 토큰 + 카카오톡 공유 | 별도 앱간 초대 | 재사용 가능, 로그인 전 사용자도 처리 |
| 권한 체크 | **Custom claim + RTDB 규칙 2중** | 단일 | claim은 1시간 캐시라 RTDB가 최종 방어선 |

### 필요 선행 지식

| 분야 | 깊이 | 핵심 |
|---|---|---|
| Phase 1-3 산출물 | 완전 이해 | HospitalContext, 알림 인프라, custom claim 회로 |
| CSS custom properties + em/rem | 실무 | 스케일링 기본 |
| Web Speech API (SpeechSynthesis·Utterance) | 실무 | 한국어 voice 선택, rate·pitch, 이벤트 |
| Firebase Auth OAuthProvider + Custom Token | 실무 | Apple·카카오 통합 |
| Kakao JS SDK 초기화·인증 | 기본 | `Kakao.Auth.loginForm` |
| WCAG 2.1 AA + prefers-reduced-motion | 기본 | 접근성 기본 원칙 |
| JWT 서명·만료·일회용 | 기본 | 가족 초대 토큰 |

### 위험 조기 식별

| 위험 | 영향 | 완화 |
|---|---|---|
| Apple 심사 반려 (Apple Sign-In 없음) | iOS 앱 배포 차단 | P4 **초반**에 Apple Sign-In 착수, 웹 우선은 나중 |
| 카카오 앱 심사 (Biz 채널) | 로그인 승인 지연 | Dev 승인만 먼저, Prod 병행 |
| TTS 한국어 음성 부재 | 안내 기능 무력화 | iOS 기본 `Yuna`, Android `ko-KR` fallback. 미지원 시 시각 알림만 |
| 가족 초대 토큰 유출 | 무단 접근 | 10분 만료·일회용 + 로그 |
| 고령자 모드가 오히려 불편 | 사용률 저조 | 사용자 연구 결과 반영, 간단 모드 + "표준 모드" 쉬운 복귀 |
| 응급 버튼 오탭 | 119 오발신 | 확인 모달 1단계 |

---

## 轉 — 세부 구현 설계

### 1. 고령자 모드 (F16)

#### 1.1 토글 경로
- 더보기 탭 → 화면 설정 → "고령자 모드"
- 실수 탭 방지: 토글 아래 설명 "글자와 버튼이 커지고, 홈 화면이 단순해집니다."

#### 1.2 저장 위치
- `/users/{uid}/preferences/largeUi: boolean`
- custom claim에도 반영 → SSR/초기 렌더 플래시 방지 (`auth.token.ui` 참조)

#### 1.3 스케일링 구조

```css
/* src/styles/senior.css */
html.ui-senior {
  font-size: 18px;                 /* 기본 16 → 18 */
}
html.ui-senior .senior-hero {
  font-size: 2.25rem;               /* 40.5px */
  line-height: 1.3;
}
html.ui-senior button,
html.ui-senior a {
  min-height: 56px;                 /* 터치 타겟 확대 */
}
html.ui-senior .text-sm {
  font-size: 1rem;                  /* 작은 텍스트는 body 크기로 승격 */
}
@media (prefers-reduced-motion: reduce) {
  html.ui-senior * { transition: none !important; animation: none !important; }
}
```

- 이유: root `font-size` 조정만으로 `rem` 기반 Tailwind 전체가 자연 확대. `em` 기반 컴포넌트는 컨텍스트별 확대
- 복잡도 최소. Tailwind config 수정 없음

#### 1.4 간소 홈 (Senior Home)

고령자 모드에서 홈 탭 렌더를 변경:

```tsx
function HomeTab() {
  const { largeUi } = usePreferences();
  return largeUi ? <SeniorHome /> : <StandardHome />;
}
```

SeniorHome:
- 위젯 **4개만**: 오늘 일정 · 대기 순번(있으면) · 길찾기 · 전화걸기
- 각 카드는 고대비·아이콘 크게·한 줄 설명
- 언어 단순화: "비대면 진료" → "집에서 진료", "결제" → "돈 내기"

#### 1.5 적용 범위 매트릭스

| 영역 | 고령자 모드 적용 |
|---|---|
| 홈 탭 | SeniorHome으로 완전 교체 |
| 외래/입원/검진 | 기본 UI 유지, 내부 타이포만 확대 |
| 안내 | 지도 UI 유지, 하단 POI 카드·CTA만 확대 |
| 더보기 | 리스트 간격·터치 타겟 확대 |
| 결제 | 금액·CTA 확대, 단계 수 변화 없음 |
| 로그인 | OAuth 버튼 더 크게 노출 (F15와 시너지) |

#### 1.6 언어 단순화 정책

- 한자어 줄이기: "예약 변경" → "다시 잡기"
- 영문 지양: "OK", "Skip" 없음
- 부정문 대신 긍정문: "이메일 없음" → "이메일이 비어있어요"
- 고령자 모드에서만 교체 사전(`i18n.senior.json`) 적용

### 2. 음성 길안내 / TTS (F17)

#### 2.1 트리거 상황
- **안내 탭**에서 길찾기 시작 시 사용자 선택
- 세션 중 다음 경유지 전환 시 자동 TTS (허락 범위 내)
- 접근성 목적: 저시력·운전 중

#### 2.2 훅 설계

```ts
// src/hooks/useTextToSpeech.ts
interface UseTTSOptions {
  rate?: number;    // 0.5~2 (기본 1)
  pitch?: number;
  lang?: string;    // 'ko-KR'
}

export function useTextToSpeech(opts?: UseTTSOptions) {
  const voices = useSpeechVoices();  // 한국어 voice 필터
  const speak = useCallback((text: string) => { /* ... */ }, [voices]);
  const stop = useCallback(() => speechSynthesis.cancel(), []);
  const supported = 'speechSynthesis' in window;
  return { supported, speak, stop, voices };
}
```

#### 2.3 한국어 음성 선택

```ts
function pickKoreanVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  return (
    voices.find(v => v.lang === 'ko-KR' && v.name.includes('Yuna')) ||
    voices.find(v => v.lang === 'ko-KR' && v.localService) ||
    voices.find(v => v.lang.startsWith('ko')) ||
    null
  );
}
```

#### 2.4 안내 문구 생성

- 경유지 진행 시: "다음 목적지는 3층 내과입니다. 엘리베이터에서 좌회전하세요."
- 거리 포함: "10미터 앞 오른쪽으로 이동합니다."
- **짧게·명령형·단위 명시** — 고령자 청취 친화

#### 2.5 실패 대응
- `supported === false` → TTS 버튼 비활성, "이 기기에서는 음성 안내가 지원되지 않습니다."
- voices.length === 0 → 일부 브라우저는 첫 `getVoices()` 빈 배열 → `voiceschanged` 이벤트 구독 재시도

#### 2.6 설정 항목

더보기 → 음성 안내
- 음성 안내 on/off
- 속도 (느리게·보통·빠르게)
- 테스트 재생 ("MediWay가 안내를 시작합니다.")

### 3. OAuth 로그인 확장 (F15)

#### 3.1 Apple Sign-In

```ts
// src/services/auth/apple.ts
import { OAuthProvider, signInWithPopup } from 'firebase/auth';
import { auth } from '@/config/firebase';

export async function signInWithApple() {
  const provider = new OAuthProvider('apple.com');
  provider.addScope('email');
  provider.addScope('name');
  return signInWithPopup(auth, provider);
}
```

- Firebase Console → Auth → Providers → Apple 활성화
- Apple Developer 콘솔에서 **Services ID + Key** 생성
- iOS Safari 외 PWA·모바일 앱 컨텍스트에서는 `signInWithRedirect` 사용 권장
- **Apple App Store 심사 요건**: 타 OAuth 있으면 Apple Sign-In도 제공

#### 3.2 카카오 로그인 (Firebase Custom Token)

```ts
// 1) 클라: Kakao JS SDK로 로그인 → access_token
Kakao.Auth.login({
  success: async ({ access_token }) => {
    // 2) Functions 호출 → access_token으로 사용자 정보 조회 + custom token 발급
    const result = await kakaoAuth({ accessToken: access_token });
    // 3) Firebase로 로그인
    await signInWithCustomToken(auth, result.firebaseToken);
  },
});
```

Functions 측:
```ts
// functions/src/auth/kakaoToken.ts
export const kakaoAuth = onCall({ region: 'asia-northeast3' }, async (req) => {
  const { accessToken } = req.data;
  const profile = await fetch('https://kapi.kakao.com/v2/user/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  }).then(r => r.json());
  const uid = `kakao:${profile.id}`;
  // 사용자 레코드 생성/갱신
  await getAuth().setCustomUserClaims(uid, { provider: 'kakao' });
  const firebaseToken = await getAuth().createCustomToken(uid);
  return { firebaseToken };
});
```

- `kakao:{id}` prefix로 네임스페이스 충돌 방지
- 사용자 최초 로그인 시 `/users/{uid}` 레코드 생성 + P1 플로우(hospital 선택)에 합류

#### 3.3 네이버 로그인 (카카오와 동일 패턴, 선택)

#### 3.4 계정 연결

- 한 사용자가 카카오·이메일 병행 가능하도록 **Firebase Auth linking**
- `linkWithPopup(auth.currentUser, provider)` API
- 사용자 UX: 설정 → 계정 연결

#### 3.5 탈퇴·연결 해제

- 카카오 탈퇴 시 Firebase Auth 사용자는 유지되지만 `providerData`에서 카카오 제거
- OAuth 제공자 연결 해제 옵션 UI 필요 (개인정보 보호법 권리)

### 4. 응급 버튼 (F10)

#### 4.1 노출 위치

1. **홈 탭 고정 하단 버튼** (`fixed bottom-0` 아님, `sticky` 또는 홈 카드 최상단 빨강 배지)
2. 더보기 탭 상단 크게
3. 헤더의 작은 SOS 아이콘 (선택)

#### 4.2 동작 흐름

1. 탭 → 확인 모달 "응급실로 바로 안내하고 119 전화를 드릴까요?"
2. 2개 CTA: "응급실 안내" / "119 전화"
3. **응급실 안내**: 자동으로 안내 탭 전환 + 경로 "응급실"로 설정
4. **119 전화**: `window.location.href = 'tel:119'`

#### 4.3 시각 코드

- 빨강 `bg-error` 배경 + 흰색 텍스트 + 아이콘 `PhoneAlert`
- 주변 여백 확보하여 오탭 방지
- 장시간 눌러야 반응하는 long-press 옵션 고려 (P5)

#### 4.4 데이터

- 병원별로 응급실 POI 필수: `/hospitals/{id}/emergencyPoiId`
- 응급 번호는 한국 기본 119, 병원별 오버라이드 가능

### 5. 가족 계정 연동 (F7)

#### 5.1 권한 모델

- **읽기(reader)** — 일정·대기 순번 조회만
- **대리(delegate)** — 예약·결제·알림 수신까지

민감 정보(진단명·처방 약품 상세)는 "reader"는 접근 불가, "delegate"는 가능 + 접근 로그 남김.

#### 5.2 데이터 모델

```
/users/{uid}/family/
  grantees/            # 내가 권한을 준 사람들
    {granteeUid}: { role: "reader" | "delegate", grantedAt, acceptedAt }
  granters/            # 내게 권한을 준 사람들 (역인덱스)
    {granterUid}: { role, grantedAt, acceptedAt }
/family_invites/{token}
  inviterUid
  role
  createdAt
  expiresAt
  inviteeEmail? / inviteePhone?
  status: "pending" | "accepted" | "expired" | "revoked"
```

#### 5.3 초대 플로우

1. 더보기 → 가족 연결 → "초대 보내기"
2. 역할 선택 (읽기/대리) + 이메일 or 전화번호
3. 서버: JWT 토큰 생성, 10일 만료
4. 초대 링크를 카카오톡·SMS로 공유 (사용자가 수동 공유)
5. 수락자가 링크 탭 → MediWay 로그인 → 수락 확인 → 상호 연결

#### 5.4 관리 UI

- 내가 권한을 준 사람 / 내게 권한을 준 사람 2개 섹션
- 각 항목에 "권한 변경" (reader ↔ delegate), "연결 해제" 버튼
- 감사 로그 탭 (누가 내 정보를 언제 조회했나)

#### 5.5 접근 감사

- 대리 권한자가 pmnt·처방 읽기 시 `/audit_logs/{hospitalId}/family_access`에 기록:
  ```json
  { actorUid, targetUid, resource, timestamp }
  ```
- 사용자에게 가끔 요약 알림 ("지난 주 김철수님이 내 정보 3회 조회")

#### 5.6 철회

- 언제든지 연결 해제 가능. 해제 즉시 access denied
- 1차 심사·계약한 병원·PIPA 준수 문서에 포함

### 6. 데이터 스키마 확장

```
/users/{uid}/
  preferences/
    largeUi: boolean
    tts: { enabled, rate }
    emergencyNumber: string    # 사용자별 커스텀 (기본 "119")
  family/
    grantees/{uid}: {...}
    granters/{uid}: {...}
  linkedProviders/
    apple: true
    kakao: true
    naver: false
/family_invites/{token}: {...}
/audit_logs/{hospitalId}/family_access/{id}: {...}
/hospitals/{id}/emergencyPoiId: string
```

### 7. 보안 규칙 확장

핵심:
- `/users/{uid}/family/granters/{granterUid}`가 존재해야 다른 사용자 데이터 접근 가능
- 리더는 `/visit_plans/{granterUid}/waypoints` 정도까지. `prescriptions`는 delegate만
- `/family_invites/{token}` 읽기는 토큰 소유자(초대 수락자)에 한정

```jsonc
{
  "visit_plans": {
    "$uid": {
      ".read": "auth.uid === $uid 
                || auth.token.hospitalRoles[data.child('hospitalId').val()] in ['staff','admin']
                || root.child('users').child($uid).child('family/grantees').child(auth.uid).exists()"
    }
  },
  "hospitals": {
    "$hospitalId": {
      "prescriptions": {
        "$uid": {
          ".read": "auth.uid === $uid 
                    || auth.token.hospitalRoles[$hospitalId] in ['staff','admin']
                    || root.child('users').child($uid).child('family/grantees').child(auth.uid).child('role').val() === 'delegate'"
        }
      }
    }
  }
}
```

### 8. 규제·법률 대응

#### 8.1 접근성
- 한국 장애인차별금지법에 따라 공공성 높은 앱은 WCAG 대응 권장
- 의료앱은 명시 의무는 아직 없으나 공공 파트너십 시 필요

#### 8.2 가족 대리 동의
- **미성년자/피후견인** 특수 케이스: 법정대리인 확인 필요. P4는 성인 간 대리만 허용, 미성년자는 P5 이후
- 가족 연결 시 수락자의 명시 동의 UI 필수

#### 8.3 OAuth
- 카카오·Apple 약관 준수 의무
- 개인정보처리 위탁 동의 업데이트 필요

#### 8.4 응급 연락
- 119 자동 발신 아님 (사용자 확인). 오탭 시 사회적 비용 발생 방지

---

## 結 — 완료 기준·검증 전략·Next

### 완료 기준 (세부화)

#### 기능
- [ ] 더보기 → 고령자 모드 토글 → 앱 전체 글자·버튼 크기 즉시 확대
- [ ] 고령자 모드에서 홈 탭이 SeniorHome으로 교체 (4개 위젯만)
- [ ] 안내 탭에서 TTS 음성 안내 on/off 가능
- [ ] TTS 재생 시 한국어 voice 사용 (확인: voice.lang === 'ko-KR')
- [ ] Apple Sign-In 로그인 성공 (Safari·Chrome)
- [ ] 카카오 로그인: 샌드박스에서 로그인 → 사용자 레코드 생성 → 병원 선택 단계로
- [ ] 계정 연결 UI에서 카카오·Apple 연결/해제 가능
- [ ] 응급 버튼 탭 → 확인 모달 → "응급실 안내" 선택 시 안내 탭 진입 + 경로 자동
- [ ] 응급 버튼 "119 전화" 탭 시 `tel:119` 다이얼러 트리거
- [ ] 가족 초대 링크 발송 → 수락자 로그인 → 상호 연결
- [ ] 읽기 권한자는 진료 일정 조회 가능, 처방 상세 접근 시 401
- [ ] 대리 권한자는 예약·결제·처방 접근 가능 + audit log 기록
- [ ] 가족 연결 해제 즉시 접근 차단

#### 접근성
- [ ] Lighthouse Accessibility 100 (주요 페이지)
- [ ] 키보드 단독 네비로 주요 플로우 완주 가능
- [ ] prefers-reduced-motion 존중
- [ ] 색 대비 WCAG 2.1 AA (고령자 모드는 AAA 목표)

#### 품질
- [ ] tsc·eslint 통과
- [ ] E2E Playwright 시나리오 통과 (고령자 모드·가족 초대)
- [ ] Apple·카카오 로그인 로컬에뮬·샌드박스 성공

### 검증 전략

1. **자동**
   - Vitest 유닛: TTS voice pick 알고리즘, 가족 권한 체크 유틸
   - E2E: OAuth popup 차단을 피해 emulator 기반 가짜 provider 테스트
   - 규칙 E2E: `public/e2e-family-access.html` 신규 (reader/delegate 시나리오)
2. **수동**
   - **사용자 연구**: 60대+ 3명에게 1회 세션 관찰. 고령자 모드로 예약 완주 관찰
   - Apple 심사 사전 리뷰: iOS Safari + TestFlight(만약 네이티브 래퍼 시점)
3. **규제**
   - 가족 연결 동의 텍스트 법무 검토
   - PIPA 처리방침 업데이트

### 롤백 계획
- 기능별 flag: `VITE_P4_SENIOR_MODE`, `VITE_P4_TTS`, `VITE_P4_KAKAO_LOGIN`, `VITE_P4_FAMILY`
- Apple 로그인만 먼저 배포 (심사 요건) → 나머지는 단계적

### Next (Phase 5 진입 조건)
1. 완료 기준 100% 통과
2. 파일럿 병원 1곳에서 고령자 실사용자 피드백 수집
3. P5 시작 시 `PlusUltra#5.md`로 이어받아 **검사결과 무기한·디지털 문진·의료진 메시지·PHR 연동·다국어**

---

## UIUX 가이드라인

### U1. 참조 자산 매핑 (P4 대상)

| 경로 | 대응 P4 화면 |
|---|---|
| `mobile_uiux/mediway_user_main/` | SeniorHome 단순화 대상 |
| `mobile_uiux/mediway/`, `mediway_1~4/` | 다양한 홈 변형 — 고령자 모드 inspiration |
| `uiux/*/mediway_clinical/DESIGN.md` | 접근성 원칙 (48×48 터치 타겟) 재참조 |
| `mobile_uiux/mediway_admin/` | 가족 관리 UI 패턴 참고 (관리자 리스트 스타일) |

목업에 명시적 "고령자 모드" 화면은 없으므로, **기존 mediway 시리즈의 여백·카드·버튼 크기를 기반으로 1.25~1.5배 확대**한 버전을 설계한다.

### U2. 고령자 모드 레이아웃

#### U2.1 SeniorHome (모바일)

```
┌──────────────────────────────────────┐
│  {병원명}                      [👤]  │  h-20, 고대비 로고 큼
├──────────────────────────────────────┤
│                                      │
│  김철수님                            │  text-3xl
│  안녕하세요                          │
│                                      │
│  ┌──────────────────────────────────┐│
│  │ 📅 오늘 진료                     ││  카드 p-6
│  │                                  ││
│  │ 오후 2시 내과                    ││  text-2xl
│  │ 3층 진료실                       ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌──────────────────────────────────┐│
│  │ 🗺️ 길찾기                         ││
│  │ 진료실로 바로 안내                ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌──────────────────────────────────┐│
│  │ 🔴 응급실                         ││  error color bg
│  │ 응급실로 가거나 전화하기          ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌──────────────────────────────────┐│
│  │ ⚙️ 설정                          ││
│  │ 글자 크기·음성·계정               ││
│  └──────────────────────────────────┘│
└──────────────────────────────────────┘
```

- 버튼 **최소 높이 80px**
- 글자 `text-xl~2xl`, 카드 `text-3xl` 헤드라인
- 아이콘 40~48px
- 컬러는 대비 최대 (primary on white, error on white)
- 탭 네비는 숨기고 전체를 홈 단일 페이지로 운영 (단순화)

#### U2.2 SeniorHome (웹)

- 2컬럼 대신 **단일 컬럼 `max-w-2xl mx-auto`** — 고령자 데스크탑도 집중도 우선
- 각 카드가 거의 화면 폭 가득, 스크롤 리스트
- 마우스 포인터 크게 + 고대비 focus ring

### U3. TTS UI

#### U3.1 길찾기 화면 TTS 컨트롤

- 안내 탭 지도 우상단에 **🔊 아이콘 버튼** (36×36, 활성 시 primary)
- 탭 시 토글 (on ↔ off)
- 현재 재생 중이면 **파동 애니메이션** (reduce-motion 시 static icon)

#### U3.2 설정 (더보기)

- 음성 안내 on/off 큰 토글
- 속도 슬라이더 3단계 (느리게·보통·빠르게) with 미리듣기 버튼
- "테스트 재생" 버튼 → "MediWay가 안내를 시작합니다" 발화

### U4. OAuth 로그인 UI

#### U4.1 로그인 페이지 배치

```
┌──────────────────────────────────────┐
│ MediWay                              │
│                                      │
│ [노란 카카오 로그인] ←  가장 크게      │
│ [검정 Apple 로그인]                  │
│ [녹색 네이버 로그인] (선택)           │
│                                      │
│ ── 또는 ──                            │
│                                      │
│ [이메일 입력]                         │
│ [비밀번호]                            │
│ [로그인]                              │
└──────────────────────────────────────┘
```

- **한국 사용자 문화에 맞춰 OAuth가 먼저, 이메일은 fallback**
- OAuth 버튼 공식 브랜드 컬러·아이콘 준수 (카카오 가이드라인·Apple HIG)
- **카카오 버튼 노란색 #FEE500**
- **Apple 버튼 검정/흰색** (심사 요건)
- 접근성: 각 버튼 `aria-label="카카오로 로그인"` 등

#### U4.2 계정 연결 UI (더보기)

- 연결된 제공자 리스트 (체크·해제 버튼)
- 마지막 로그인 제공자 표시

### U5. 응급 버튼 UI

#### U5.1 홈 고정 배너 (일반 모드)

- 홈 탭 상단 또는 하단에 `bg-error text-on-error rounded-xl p-4` 배너
- 아이콘 `PhoneAlert` + "응급실 바로 가기"
- 탭 면적 충분

#### U5.2 고령자 모드

- 홈의 4개 CTA 중 하나로 확대 노출

#### U5.3 확인 모달

- `glassmorphism` 배경
- 제목: "응급 상황인가요?"
- 두 개 primary 크기 버튼: "응급실 안내" / "📞 119 전화"
- 취소 버튼은 tertiary 스타일

### U6. 가족 연결 UI

#### U6.1 진입점

- 더보기 → "가족 연결" (아이콘 Users)
- 2개 섹션 탭: "내가 초대한 사람" / "나를 초대한 사람"

#### U6.2 초대 보내기 플로우

1. "+ 초대 보내기" 큰 CTA
2. 단계 1: 역할 선택 (카드 2개 — 읽기 권한 / 대리 권한, 각 설명 포함)
3. 단계 2: 이메일 or 전화번호 입력
4. 단계 3: 카카오톡으로 공유 / SMS로 보내기 / 링크 복사
5. 완료 화면

#### U6.3 권한 관리

- 각 가족원 카드: 아바타 + 이름 + 역할 뱃지 + 마지막 접근 일시
- 탭 시 상세: 권한 변경 (reader ↔ delegate), 감사 로그 보기, 연결 해제
- 연결 해제는 **빨강 confirmation**

#### U6.4 감사 로그 뷰

- 시간 순 리스트: "{date} 김영희님이 내 진료 일정을 열람했습니다."
- 필터: 기간·조회자

### U7. 접근성 통합 체크리스트 (P4 QA)

- [ ] WCAG 2.1 AA 전역 통과, 고령자 모드 주요 페이지 AAA
- [ ] 색대비 ≥ 7:1 (고령자 모드에서 primary on white)
- [ ] 모든 폼 필드 `<label>` 연결
- [ ] `aria-live="polite"` — TTS 상태·대기 순번 업데이트
- [ ] 키보드 포커스 ring 시각적 명확
- [ ] prefers-reduced-motion 존중
- [ ] prefers-color-scheme 기초 대응 (다크는 P5로)
- [ ] 터치 타겟 모바일 ≥ 44px, 고령자 모드 ≥ 64px
- [ ] 스크린 리더 테스트: iOS VoiceOver + Android TalkBack 주요 흐름

### U8. 애니메이션·모션 정책 업데이트

P3까지의 펄스·shake·체크 애니메이션은 `reduce-motion`에서 전부 off. 고령자 모드에서는 **기본적으로 transition 100ms 이하로 제한** — 감각 과부하 방지.

### U9. 피해야 할 함정

1. **고령자 모드를 "다크 모드"처럼 별도 theme로 취급** — 유지보수 비용 폭발. 반드시 **font-size 기반 스케일링**
2. **TTS 자동 재생** — iOS Safari에서 차단됨. 사용자 트리거 필요
3. **OAuth를 팝업만 지원** — 모바일 Safari에서 팝업 차단률 높음. `signInWithRedirect` 병행
4. **가족 권한을 세밀하게 분리(3개 이상)** — 사용자 혼란. 2개만 유지
5. **응급 버튼 오탭 방치** — 확인 모달 필수
6. **고령자 모드의 자동 활성화** — 사용자 선택권 존중. 연령 추정 기반 자동 on 금지
7. **초대 링크 만료 없음** — 반드시 10분~10일 범위
8. **감사 로그 미통보** — 대리 권한이 민감정보 접근 시 알림 없는 것은 신뢰 훼손

### U10. 구현 체크리스트 — UIUX

- [ ] SeniorHome 모바일/웹 레이아웃 구현
- [ ] 설정 화면에서 고령자 모드 토글 + 미리보기
- [ ] TTS 재생 아이콘·애니메이션·reduce-motion fallback
- [ ] 로그인 페이지에 OAuth 버튼 3종 (카카오·Apple·네이버)
- [ ] Apple 버튼 HIG 디자인 준수
- [ ] 카카오 버튼 브랜드 가이드 준수
- [ ] 응급 배너 홈 노출 + 확인 모달 + 119 전화
- [ ] 가족 연결 리스트·초대 플로우·권한 관리·감사 로그
- [ ] Lighthouse Accessibility 스코어 95~100

### U11. 작업 견적 (UIUX 포함)

| 작업 | 소요 |
|---|---|
| 고령자 모드 CSS·토글·SeniorHome 구현 | 2.5일 |
| TTS 훅·UI·설정 | 1.5일 |
| Apple Sign-In 통합 + 콘솔 구성 | 1.0일 |
| 카카오 로그인 (Functions·클라) | 2.0일 |
| 네이버 로그인 (선택, 공수별 보수) | 1.0일 |
| 계정 연결·해제 UI | 1.0일 |
| 응급 버튼 UI + 홈 배치 + 확인 모달 | 1.0일 |
| 가족 연결 데이터·Functions·권한 규칙 | 2.5일 |
| 가족 UI (초대·관리·감사 로그) | 2.0일 |
| 규칙 E2E + 심사 문서 업데이트 | 1.0일 |
| 사용자 연구 세션·피드백 반영 | 1.5일 |
| 회귀·UIUX QA·Lighthouse | 1.0일 |
| **합계** | **17.0일 (≈ 3.5주)** |

---

## 부록

### 부록 A. 의사결정 레지스터 (P4)

| ID | 결정 | 대안 | 근거 |
|---|---|---|---|
| D1 | 고령자 모드는 root `font-size`로 스케일 | 별도 theme | 유지보수·일관성 |
| D2 | TTS는 Web Speech API 기본 | 서버 TTS | 비용·지연 |
| D3 | Apple·카카오만 필수, 네이버는 선택 | 3개 모두 동급 | 공수 대비 효용 |
| D4 | 가족 권한 2단계 (reader/delegate) | 4단계 세분화 | 복잡도 폭발 방지 |
| D5 | 응급 버튼은 탭 네비 밖 | 탭 내부 배치 | 안전·즉시성 |
| D6 | 초대 링크 10일 만료 | 영구 | 보안 |
| D7 | 가족 접근 감사 로그 보관 1년 | 영구 | 저장 비용 + PIPA 최소 수집 |

### 부록 B. 파일 생성·수정 체크리스트

**신규**
- `src/styles/senior.css`
- `src/hooks/usePreferences.ts`, `useTextToSpeech.ts`, `useSpeechVoices.ts`
- `src/components/senior/SeniorHome.tsx`, `SeniorActionCard.tsx`
- `src/components/common/EmergencyBanner.tsx`, `EmergencyModal.tsx`
- `src/services/auth/apple.ts`, `kakao.ts`, `naver.ts`
- `src/services/family.ts`
- `src/components/more/AccountLinkingPage.tsx`, `FamilyPage.tsx`, `InviteFlow.tsx`, `FamilyAuditLog.tsx`
- `src/pages/AcceptFamilyInvitePage.tsx` (`/family-invite/:token`)
- `functions/src/auth/kakaoToken.ts`, `naverToken.ts`
- `functions/src/family/createInvite.ts`, `acceptInvite.ts`, `revokeAccess.ts`
- `public/e2e-family-access.html`

**수정**
- `src/pages/LoginPage.tsx` — OAuth 버튼 3종 노출
- `src/pages/hospital/HospitalShell.tsx` — SeniorHome 분기
- `src/components/hospital/HomeTab.tsx` — senior mode 분기
- `src/components/hospital/MoreTab.tsx` — 설정·계정 연결·가족 연결 항목 추가
- `database.rules.json` — family·linkedProviders·audit_logs 확장
- 개인정보 처리방침·이용약관 업데이트

### 부록 C. Phase 관계 다이어그램

```
 Phase 3 (완료)                Phase 4 (본 문서)                Phase 5
 ───────────                   ───────────────                 ────────
 WaitQueue · 결제 · 알림톡      + SeniorMode · SeniorHome       검사결과 무기한
 InpatientTab · CheckupTab     + TTS 음성 안내                 의료진 메시지
 주차 어댑터                    + Apple/카카오 OAuth             문진·PHR 연동
                               + Emergency button               다국어
                               + Family (reader/delegate)
                               + Audit logs for family access
```

### 부록 D. OAuth 통합 체크리스트

**Apple Sign-In**
- [ ] Apple Developer → Services ID 생성
- [ ] Key 파일(.p8) 다운로드
- [ ] Firebase Console → Auth → Apple 활성화, Services ID/Key 입력
- [ ] `OAuthProvider('apple.com')` 클라 구현
- [ ] Safari·Chrome 로그인 성공
- [ ] 첫 로그인 시 이메일·이름 수신 확인 (두 번째부터는 이메일만)

**카카오 로그인**
- [ ] Kakao Developers → 앱 등록
- [ ] JavaScript 키 발급 + 도메인 등록
- [ ] 동의 항목: 닉네임·이메일·프로필 이미지
- [ ] 비즈 채널 연결 (Biz 용 필요 시)
- [ ] Kakao JS SDK 초기화 → 로그인 팝업 → access_token
- [ ] Firebase Function `kakaoAuth` → 사용자 확인 + custom token 발급
- [ ] `signInWithCustomToken(auth, firebaseToken)` → 사용자 레코드 생성
- [ ] 테스트 계정으로 로그인 샌드박스 → 프로덕션

### 부록 E. 학습 리소스

- Web Speech API: https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis
- Firebase Apple Sign-In: https://firebase.google.com/docs/auth/web/apple
- Kakao JS SDK: https://developers.kakao.com/docs/latest/ko/kakaologin/js
- Firebase Custom Tokens: https://firebase.google.com/docs/auth/admin/create-custom-tokens
- WCAG 2.1 AA 지침: https://www.w3.org/WAI/WCAG21/quickref/
- 고령자 모바일 헬스케어 UI 연구 (DBpia): `plusultra.md` 참조
- Apple HIG Sign In with Apple: https://developer.apple.com/design/human-interface-guidelines/sign-in-with-apple
- 카카오 로고 가이드라인: https://developers.kakao.com/design-guide

---

_작성일: 2026-04-22_
_대상 Phase: #4 — 고령자·접근성·OAuth·가족 대리_
_선행: `PlusUltra#1.md`, `PlusUltra#2.md`, `PlusUltra#3.md`_
_이어지는 문서: `PlusUltra#5.md` (검사결과·메시지·PHR·다국어)_
_UIUX 참조: `uiux/mobile_uiux/mediway/`, `mediway_user_main/`, `uiux/*/mediway_clinical/DESIGN.md`_
