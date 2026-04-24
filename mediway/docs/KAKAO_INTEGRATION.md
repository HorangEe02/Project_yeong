# Kakao 통합 전략 (MediWay)

> **작성일**: 2026-04-24
> **범위**: 보유한 Kakao 개발자 키 기반 실현 가능성 평가 + Phase별 도입 설계
> **상태**: 설계 문서 (구현은 Phase 별로 분할)

---

## 1. 보유 키 인벤토리

경로: `data/kakao_api/` (🔥 **Git 추적 금지 대상** — `.gitignore` 및 Secret 이관 필요)

| 키 종류 | 용도 | 보관 원칙 |
|---|---|---|
| **JavaScript 키** | 웹 SDK (Kakao Maps, Kakao 로그인 팝업, 공유) | 프론트엔드 번들 포함 OK — 단, Kakao 콘솔 도메인 화이트리스트로 보호 |
| **REST API 키** | 서버 OAuth 토큰 교환, Local/Mobility API | Firebase Functions Secret (`KAKAO_CLIENT_ID`) |
| **Client Secret (로그인)** | REST API 로그인 추가 보안 | 🔥 Firebase Functions Secret (`KAKAO_CLIENT_SECRET`) |
| **Client Secret (비즈)** | 비즈메시지 인증 추가 보안 | 🔥 Firebase Functions Secret (P3 알림톡 시점 등록) |
| **네이티브 앱 키** | Android/iOS SDK | Capacitor 래퍼 리소스 |
| **Admin 키** | 알림톡 발송, 사용자 unlink, 관리 API | 🔥🔥 Firebase Functions Secret (`KAKAO_ADMIN_KEY`) |

> 🔒 **실제 키 값은 이 문서에 기록하지 않는다.** 개별 값은 Kakao Developers 콘솔 또는 로컬 `../data/kakao_api/` (outer `.gitignore` 적용됨)에서 수동 확인. 과거 이 문서에 평문/truncated 키가 있었다면 **재발급 권고**.

### Secret 이관 — **Commit 7.5에서 완료**

구체 실행 매뉴얼은 [SECRETS_SETUP.md](./SECRETS_SETUP.md) 참고.

핵심 요약:
- 코드 변경: `functions/src/secrets.ts` 추가, `kakaoAuth`/`naverAuth`가 `defineSecret(...).value()` 사용
- 환경 분리: 프론트 public 키는 `.env.local`, 서버 private 키는 `functions/.secret.local` + Firebase Secret Manager
- gitignore: `../data/kakao_api/`, `.env.local`, `functions/.secret.local` 등 추적 금지
- 배포 담당자 수동 액션: `firebase functions:secrets:set <KEY>` 실행 + Kakao/Naver 콘솔 Redirect URI 등록

---

## 2. 현재 Kakao 통합 상태

### 2.1 이미 구현됨 ✅
- `functions/src/providers/kakao.ts` — Authorization Code Flow 토큰 교환
- `functions/src/index.ts :: kakaoAuth` — Callable Function
- `src/services/socialAuth.ts :: startKakaoLogin` — OAuth 인가 시작
- `src/pages/auth/SocialCallbackPage.tsx` — 콜백 처리
- `src/components/auth/KakaoButton.tsx` — UI 진입점

### 2.2 부족한 부분 ⚠️
- 환경변수 미등록 (Secret 이관 대기)
- Redirect URI 미등록 (Kakao 콘솔 작업 대기)
- JS SDK 팝업 방식 미지원 (현재 전체 리다이렉트만) — UX 개선 여지
- 계정 연결 해제 (unlink) 미구현 — 탈퇴 시 Admin 키로 호출 필요
- 세션 키(`kakao_account`)에서 `phone_number`, `birthday` 미수집 → 비즈니스 인증 후 확장

---

## 3. Kakao 제품별 도입 시나리오

### 3.1 Kakao Map (실외) — Leaflet 실내와 공존

**전제**: MediWay는 [Leaflet 실내 평면도](../src/components/map/leaflet-renderer)를 병원 내부 네비게이션에 씀. Kakao Map은 실외 전용이라 **교체가 아니라 보완**.

| 시나리오 | 설명 | 복잡도 | 우선순위 |
|---|---|---|---|
| **A. 오시는 길** | Landing + 병원 상세에 카카오맵 정적 iframe 또는 SDK static view | 1일 | 🟢 P2 |
| **B. 집→병원 외부 길찾기** | Kakao Mobility API (자동차) + 대중교통은 Naver/외부 API 대체 | 3일 | 🟡 P3 |
| **C. 실외→실내 seamless 전환** | Geofence (GPS 50m 임계) → Leaflet indoor로 자동 전환 | 5일+ | 🟠 P4 (Capacitor 필요) |
| **D. 인근 병원 검색** | Kakao Local API `/v2/local/search/keyword.json?category_group_code=HP8` | 2일 | 🟡 플랫폼 확장 |

#### 구현 포인트 — 시나리오 A (즉시 가능)

```tsx
// src/components/common/KakaoMapStatic.tsx (신규 예상)
interface Props {
  lat: number;
  lng: number;
  name: string;
  width?: number;
  height?: number;
}

export function KakaoMapStatic({ lat, lng, name, width = 640, height = 360 }: Props) {
  const key = import.meta.env.VITE_KAKAO_MAP_KEY;
  // 로드 후 kakao.maps.load() 호출
  useEffect(() => {
    if (!window.kakao?.maps) {
      const script = document.createElement('script');
      script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${key}&autoload=false`;
      script.onload = () => window.kakao.maps.load(init);
      document.head.appendChild(script);
    } else {
      window.kakao.maps.load(init);
    }
    // ...
  }, [lat, lng]);
  // ...
}
```

#### 구현 포인트 — 시나리오 B (Mobility API)

```ts
// functions/src/providers/kakaoMobility.ts (신규 예상)
// 자동차 길찾기: https://apis-navi.kakaomobility.com/v1/directions
// 인증: REST API 키 사용 ("Authorization: KakaoAK <REST_KEY>")
// 주의: 호출 무료 티어 일 1,000건 한도
```

---

### 3.2 Kakao 로그인 고도화

| 현재 | 개선안 | Phase |
|---|---|---|
| 전체 리다이렉트 | JS SDK `Kakao.Auth.authorize` 팝업 | P2 |
| `email` only | Kakao Sync 동의 후 `phone_number`·`birthday`·`gender` 자동 수집 | P4 |
| unlink 미구현 | 계정 삭제 시 Admin 키로 `/v1/user/unlink` 호출 | P2 |
| 동일 이메일 중복 | Firebase 멀티 provider 연결 (`linkWithCredential`) 고려 | P4 |
| refresh token 미사용 | 장기간 미로그인 사용자 재인증 UX 개선 | P5 |

---

### 3.3 Kakao 알림톡 (P3 F5)

**사전 작업**:
1. Kakao 비즈니스 채널 개설 (MediWay 공용 vs 병원별 선택 필요)
2. 알림톡 템플릿 5종 심사 (3~5영업일)
   - `APPOINTMENT_CONFIRMED` — 예약 확정
   - `PATIENT_CALL` — 진료실 호출
   - `PAYMENT_REQUEST` — 결제 요청
   - `PROXY_PAYMENT_REQUEST` — 보호자 대리결제 링크
   - `RESULT_AVAILABLE` — 검사결과 도착
3. Fallback 체인: **알림톡 → FCM → SMS** (plusultra_v2 §3.4 준수)

**서버 구현 예상**:
```ts
// functions/src/notifications/sendAlimtalk.ts (P3)
// POST https://kakaoapi.aligo.in/akv10/alimtalk/send/
// 또는 카카오 비즈메시지 직접 API
// Admin 키 + 비즈 Client Secret 둘 다 필요
```

---

### 3.4 카카오톡 공유 (P3 F8·F9 연계)

- **대리결제 링크** 카카오톡 공유가 핵심 UX — `Kakao.Share.sendDefault` (JS SDK)
- Feed/List/Location/Commerce 템플릿 4종 중 Commerce 적합
- 공유 메시지에 `?pay_token=xxx` 포함 → 보호자가 탭 → PaymentPage

---

## 4. Phase 매핑 — 제품별 일정

```
P1 (현재)         P2              P3               P4               P5
─────────────────────────────────────────────────────────────────────
[Commit 7.5]      시나리오 A       시나리오 B        시나리오 C        인근병원 D
Secret 이관       (오시는길)        (외부 길찾기)     (Geofence)       (플랫폼 확장)
                  JS SDK 팝업       알림톡 심사       Kakao Sync 확장  unlink on 탈퇴
                                   알림톡 발송       Capacitor 네이티브
                  카카오톡 공유      결제 공유 링크
```

---

## 5. 리스크·법무

| 리스크 | 완화 |
|---|---|
| Admin 키 유출 시 알림톡 무단 발송 | Secret Manager + IP 화이트리스트 (콘솔 설정) |
| JS 키 유출 시 지도 호출 쿼터 고갈 | 도메인 화이트리스트 엄격 관리, 쿼터 모니터링 |
| Kakao Sync 개인정보 확장 동의 | PIPA 준수 — 수집 목적·보유기간 약관 명시 |
| 비즈메시지 오발송 (잘못된 템플릿) | 5종 모두 샌드박스 테스트 후 배포, idempotent 키 |
| Kakao API 장애 | 동일 알림을 FCM/SMS로 이중 발송 (멱등 키) |

---

## 6. 다음 체크포인트

- [ ] **Commit 7.5**: Secret Manager 이관 + `.gitignore` + README 갱신
- [ ] **P2**: 시나리오 A (LandingPage 카카오맵 정적 뷰) PR
- [ ] **P2**: JS SDK 팝업 기반 KakaoButton 업그레이드
- [ ] **P3 F5 사전**: 알림톡 템플릿 5종 초안 + 비즈니스 채널 개설 주체 결정 (MediWay vs 병원별)
- [ ] **P3 F5**: Kakao Admin 키 발송 Function + FCM fallback 래퍼
- [ ] **P3 F8·F9**: 카카오톡 공유 Commerce 템플릿 설계
- [ ] **P4 탈퇴 플로우**: `/v1/user/unlink` 연동
