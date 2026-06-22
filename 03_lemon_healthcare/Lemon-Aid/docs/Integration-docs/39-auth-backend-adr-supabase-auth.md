# 39 — ADR: 인증 백엔드로 Supabase Auth 채택 (가이드 01 3단계)

> 2026-06-12: PR#4 임포트로 팀원 문서 36(medical-wiki-rag-execution-plan)과 번호가 겹쳐 36→39로 리네임.

- 상태: **채택** (2026-06-12, 제품 오너 확인)
- 결정 범위: 모바일 로그인/가입(소셜 3종 + 이메일)과 백엔드 토큰 검증 방식
- 근거 문서: `mobile/uiux/implementation-guides/01-auth-onboarding-signup.md` §3단계 결정표 (Supabase Auth 권고 검토), `mobile/uiux/handoff/02_FRONTEND_GUIDE.md` §7 (`/auth/*` 계획 표)

## 컨텍스트

- 백엔드 `/auth/*` 라우트는 **공백**이다 — 계획 표만 존재하고 구현이 없다.
- 모바일은 가이드 01의 3단계 점진 도입 중 1·2단계(동의 게이트 UI, auth 없는 가입 위저드)가 진행 가능한 상태로 설계되어 있고, 3단계가 본 결정에 게이트되어 있었다.
- 현행 dev 스택은 `AUTH_MODE=disabled`로 동작하며, 백엔드 보호 라우트는 issuer-qualified subject(`build_owner_subject`) + FORCE RLS로 소유자 격리를 이미 강제한다.

## 결정

**Supabase Auth를 채택한다.** 소셜(카카오/Apple/Google)·이메일 인증 플로우는 Supabase SDK가 담당하고, 백엔드는 Supabase 발급 JWT의 **검증만** 담당한다(`AUTH_MODE` 활성 + issuer/audience/JWKS 설정). 자체 OIDC 풀스택 신규 개발은 기각.

## 근거

- 가이드 01 결정표의 권고 검토안 — `/auth/*` 표 대부분이 Supabase SDK 호출로 대체되어 백엔드 신규 개발량이 JWT 검증 설정 수준으로 줄어든다.
- 백엔드 소유자 격리 모델(issuer-qualified subject)이 외부 IdP 발급 토큰과 자연스럽게 합치된다 — `iss`가 Supabase 프로젝트로 고정되고 `sub`가 안정적 사용자 키.
- 이메일 인증/복구/소셜 연동·계정 충돌 처리 등 보안 민감 플로우를 자체 구현하지 않는다 (의료 인접 서비스의 보안 부담 축소).

## 영향 / 후속 작업 (P2 착수 시)

1. Supabase 프로젝트 생성·소셜 프로바이더(카카오/Apple/Google) 설정 — 팀 계정·키 발급 필요 (사용자/팀 액션).
2. 백엔드: `AUTH_MODE` 활성 경로에 Supabase issuer/JWKS 검증 설정 추가 + `build_owner_subject` 매핑 회귀 테스트. **신규 `/auth/*` 라우트는 만들지 않는다.**
3. 모바일: `supabase_flutter` 도입, 가이드 01 3단계 화면(소셜 3종+이메일 로그인/가입/복구/계정 충돌)을 시안 프레임에 맞춰 구현. dev 토큰 화면은 dev flavor 전용 유지.
4. 기존 dev 우회(`AUTH_MODE=disabled`)는 dev/CI 전용으로 보존.

## 미결

- Supabase 프로젝트 리전·요금제, 카카오 비즈앱 심사 일정 — 팀 결정.
- 기존 익명(disabled 모드) 데이터의 신규 subject 이전 정책 — 마이그레이션 설계 별건.
