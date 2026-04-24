# Commit 7 설계안 — Custom Claims Cloud Function

> **상태**: 설계 검토 (사용자 승인 후 착수)
> **대상 브랜치**: `mediway/plusultra/p1`
> **선행 조건**: Commits 1-6 완료 (✅)

## 1. 목표

Firebase ID 토큰에 `role`, `hospitalId`, `hospitalIds`를 주입하여 **RTDB 보안 규칙(Commit 8)이 `auth.token.*`로 데이터 격리를 강제**할 수 있게 한다.

## 2. Non-Goals

- Identity Platform 업그레이드 (유료 · P1 범위 밖)
- 다양한 role hierarchy 설계 (P1은 `platformAdmin`만 추가됨)
- 토큰 생명주기 관리 UI (P2+)

## 3. 주요 설계 선택 (Q 3개 답변 필요)

### Q1: Claim 설정 트리거 방식

| 옵션 | 설명 | 장단점 |
|---|---|---|
| **(A) Callable 중심 (권장)** | 유저가 가입·로그인 완료 후 클라이언트가 `refreshMyClaims` 호출 → Function이 RTDB user 프로필 읽어 claim 설정 | ✅ Identity Platform 불필요 · ✅ 기존 v2 onCall 패턴 재사용 · ⚠️ 클라이언트 레이스 조건 주의 |
| (B) `onCreate` 1st-gen trigger | `functions.auth.user().onCreate()` — 유저 생성 시 자동 | ⚠️ 2024년 deprecated(지원은 유지) · 마이그레이션 시점 불확실 |
| (C) `beforeUserCreated` (Identity Platform) | GCIP 유료 기능 | ❌ 비용 이슈 |

→ **(A) Callable 중심 권장**

### Q2: Claim 갱신 권한 경계

| 함수 | 호출 주체 | 대상 | 설명 |
|---|---|---|---|
| `refreshMyClaims` | 로그인된 모든 유저 | 자기 자신 | 본인 RTDB 프로필 기반 claim 최신화 — 가입 직후·병원 변경 직후 호출 |
| `setUserClaims` | **platformAdmin만** | 임의 uid | 운영자 개입 (역할 승격, 긴급 권한 조정) — audit log 기록 |

### Q3: 토큰 즉시 갱신 UX

Firebase ID 토큰 **최대 1시간 캐시**. claim 변경 후 즉시 반영하려면 `user.getIdToken(true)` 강제 갱신 필요.

**제안 패턴**:
- 클라이언트 훅 `useRefreshToken()`이 `refreshMyClaims` 호출 → Function 성공 → 즉시 `getIdToken(true)`
- AuthStore에 `claimsVersion` 필드 추가, 토큰 갱신 후 증가 → 하위 컴포넌트 invalidate
- **가입 플로우**: 프로필 생성 직후 자동 호출 (유저가 병원 선택 화면에 도달하기 전)

## 4. 파일 구성

### 4.1 `functions/src/setClaims.ts` (신규)

```typescript
import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';

const region = 'asia-northeast3';

/**
 * 본인 RTDB 프로필 기반으로 Custom Claims 최신화.
 * 가입 직후, 병원 전환 직후 클라이언트에서 호출.
 */
export const refreshMyClaims = onCall({ region, cors: true }, async (req) => {
  if (!req.auth?.uid) throw new HttpsError('unauthenticated', '로그인 필요');
  const uid = req.auth.uid;

  const snap = await admin.database().ref(`users/${uid}`).get();
  if (!snap.exists()) throw new HttpsError('not-found', '유저 프로필 없음');

  const profile = snap.val();
  const claims = {
    role: profile.role ?? 'patient',
    hospitalId: profile.primaryHospitalId ?? profile.hospitalId ?? null,
    hospitalIds: profile.hospitalIds ?? [],
    claimsSetAt: Date.now(),
  };
  await admin.auth().setCustomUserClaims(uid, claims);
  return { claims, forceRefresh: true };
});

/**
 * 플랫폼 관리자가 임의 유저의 claim을 직접 조작.
 * 역할 승격·긴급 권한 조정 시 사용.
 */
export const setUserClaims = onCall({ region, cors: true }, async (req) => {
  if (!req.auth?.uid) throw new HttpsError('unauthenticated', '로그인 필요');
  if (req.auth.token.role !== 'platformAdmin') {
    throw new HttpsError('permission-denied', '플랫폼 관리자만 가능');
  }
  // zod 검증 후 setCustomUserClaims + audit log 작성
  // ...
});
```

### 4.2 `functions/src/index.ts` (수정)
- `export { refreshMyClaims, setUserClaims } from './setClaims';`

### 4.3 `functions/src/userLink.ts` (수정)
- `ensureUserRecord` 완료 시 자동으로 `setCustomUserClaims` 호출하도록 확장 → **Kakao/Naver 소셜 로그인 후 claim 즉시 주입**

### 4.4 `functions/src/adminCreateStaff.ts` (수정)
- 스태프 계정 생성 시 `hospitalId`·role claim 즉시 주입

### 4.5 `src/hooks/useRefreshToken.ts` (신규 · 클라이언트)

```typescript
import { useCallback } from 'react';
import { getAuth } from 'firebase/auth';
import { httpsCallable } from 'firebase/functions';
import { functions } from '@/config/firebase';

export function useRefreshToken() {
  return useCallback(async () => {
    const auth = getAuth();
    if (!auth.currentUser) throw new Error('로그인 필요');
    const fn = httpsCallable(functions, 'refreshMyClaims');
    await fn();
    // 토큰 강제 갱신 — 새 claim이 즉시 페이로드에 반영
    await auth.currentUser.getIdToken(true);
  }, []);
}
```

### 4.6 `src/stores/authStore.ts` (수정 · 기존 파일)
- `init()` 시점에 `getIdTokenResult().claims.role`이 없으면 `refreshMyClaims` 1회 호출
- 로그인 직후 자동 claim 최신화

### 4.7 Tests

- `functions/src/__tests__/setClaims.test.ts` — mock `admin.auth().setCustomUserClaims` + `admin.database().ref().get()` 검증
- `src/hooks/__tests__/useRefreshToken.test.ts` — mock callable + getIdToken(true) 호출 확인

## 5. 데이터 흐름

### 5.1 신규 환자 가입 시
```
1. Email 가입 → Firebase Auth 유저 생성
2. 클라이언트: RTDB /users/{uid} 프로필 작성 (role=patient, primaryHospitalId=선택한 병원)
3. 클라이언트: refreshMyClaims 호출
4. Function: RTDB 프로필 읽어 setCustomUserClaims
5. 클라이언트: getIdToken(true)로 토큰 갱신
6. 이후 RTDB 보안 규칙이 auth.token.hospitalId로 격리 작동
```

### 5.2 소셜 로그인 (Kakao/Naver)
```
1. OAuth 코드 → Cloud Function (kakaoAuth/naverAuth)
2. ensureUserRecord가 /users/{uid} 생성 또는 갱신
3. ✨ v2 변경: ensureUserRecord 끝에 setCustomUserClaims 호출
4. Custom token 반환 → 클라이언트 signInWithCustomToken
5. 클라이언트 signIn 직후 getIdToken(true)
```

### 5.3 Admin이 역할 변경
```
1. 관리자 콘솔에서 유저 역할 수정
2. RTDB /users/{uid} 업데이트
3. setUserClaims(uid, newClaims) 호출
4. 대상 유저가 다음 로그인 or refreshMyClaims 호출 시 즉시 반영
5. audit_logs 기록
```

## 6. 보안

- **Function 외부에서 claim 쓰기 불가** — Admin SDK만 권한 있음
- **`setUserClaims`는 platformAdmin만** — `req.auth.token.role` 확인
- **audit log 모든 claim 변경 기록** — actorUid·대상uid·before·after·timestamp
- **Service Account 노출 금지** — Functions runtime 환경에서만 Admin SDK 초기화
- **`refreshMyClaims`는 본인 uid만** — 다른 유저 claim 조작 불가 (함수 내부에서 `req.auth.uid`만 사용)

## 7. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 가입 직후 claim 아직 없어 RTDB 접근 401 | AuthStore init에서 claim 없으면 즉시 `refreshMyClaims` + 로딩 스피너 |
| 토큰 1h 캐시 때문에 역할 변경 안 반영 | 관리자 변경 후 "유저에게 재로그인 요청" UX / 클라이언트 주기적 `getIdToken(true)` |
| `refreshMyClaims` 스팸 호출 | Functions rate limiting (분당 10회 등) + 클라이언트 debounce |
| 가입 중단 시 orphan 프로필 + no claim | 프로필 작성 이전에 Firebase Auth 유저만 있으면 정상, 프로필 생성 후에만 claim 필요 |
| RTDB 프로필에 `role` 없음 | 기본값 `'patient'` + warn 로그 |

## 8. 구현 단계 (세부)

1. **functions/src/setClaims.ts 작성** (`refreshMyClaims` + `setUserClaims`)
2. **functions/src/index.ts export 추가**
3. **functions/src/userLink.ts 수정** — `ensureUserRecord`에 claim 설정 훅
4. **functions/src/adminCreateStaff.ts 수정** — 스태프 생성 시 claim 설정
5. **`src/hooks/useRefreshToken.ts` 신규**
6. **`src/stores/authStore.ts` 수정** — init 시 claim 체크 + refreshMyClaims 호출
7. **Tests** — functions + hooks
8. **TypeScript + ESLint 검증**
9. **(배포는 Commit 7에서 제외)** — Commit 9 마이그레이션 후 일괄 배포

## 9. 롤백

- `functions/src/index.ts`에서 export만 주석 처리 → Function 자동 비활성
- 기존 유저는 claim 없어도 앱 동작 (RTDB 규칙 아직 hospitalId 기반 아니므로 P1·P2 기간 안전)
- Commit 8(RTDB Rules) 배포 전까지는 claim 실패 시 **앱 전체 중단 X**

## 10. 검토 포인트 (사용자 승인 필요)

- [ ] **Q1**: Callable 중심 (A) 채택? ✅ 권장
- [ ] **Q2**: `refreshMyClaims` (본인) + `setUserClaims` (platformAdmin) 분리 OK?
- [ ] **Q3**: AuthStore init에서 자동 `refreshMyClaims` OK? 아니면 명시적 트리거만?
- [ ] ensureUserRecord에 claim 주입 훅 추가 OK? (Kakao/Naver 기존 플로우 변경)
- [ ] audit_logs 구조 확장 필요 여부 (setUserClaims 기록용 신규 action 타입)
- [ ] **배포 전략**: P1에서는 코드만 머지, 실제 배포는 Commit 8·9 이후 일괄? → 제안

---

_작성일: 2026-04-22_
