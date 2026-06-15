# 외부 IdP 설정 가이드 (v4.7 Feature E)

AJIN AI Assistant 는 외부 OIDC IdP 와의 SSO 통합을 지원합니다. 이 문서는 4개
대표 IdP 의 설정 절차를 cheatsheet 형식으로 정리합니다.

> 기본 상태: `IDP_PROVIDER=disabled` — 외부 IdP 가 비활성이며 기존 사번/비밀번호
> 로그인만 사용 가능. SSO 활성화는 환경변수 변경만으로 가능하며 코드 변경
> 불필요.

## 1. 공통 환경변수

| 변수 | 설명 | 예시 |
|---|---|---|
| `IDP_PROVIDER` | `disabled` / `oidc` / `saml`(Phase 4) | `oidc` |
| `OIDC_DISCOVERY_URL` | OIDC `.well-known/openid-configuration` URL | (아래 IdP 별 표 참조) |
| `OIDC_CLIENT_ID` | IdP 에 등록된 클라이언트 ID | `ajin-ai-assistant` |
| `OIDC_CLIENT_SECRET` | IdP 에 등록된 시크릿 | (난수) |
| `SESSION_STORE` | `memory` / `redis` (Cloud Run 멀티 인스턴스 시 redis 필수) | `redis` |
| `REDIS_URL` | `SESSION_STORE=redis` 시 필요 | `redis://10.0.0.5:6379/0` |

## 2. Callback URL (Redirect URI)

모든 IdP 의 클라이언트 등록 시 다음 redirect URI 를 화이트리스트에 추가해야
합니다.

```
https://<your-host>/api/auth/idp/oidc/callback
```

로컬 dev:

```
http://localhost:8000/api/auth/idp/oidc/callback
```

## 3. IdP 별 설정 cheatsheet

### 3.1 Keycloak (자체 호스팅)

1. Keycloak admin console → Realm 선택 → Clients → **Create client**
2. Client type: `OpenID Connect`, Client ID: `ajin-ai-assistant`
3. **Client authentication: ON** (confidential client)
4. Valid redirect URIs: `https://<host>/api/auth/idp/oidc/callback`
5. **Credentials** 탭 → Client secret 복사 → `OIDC_CLIENT_SECRET`
6. Discovery URL:

   ```
   https://<keycloak-host>/realms/<realm-name>/.well-known/openid-configuration
   ```

### 3.2 Okta

1. Okta admin → Applications → **Create App Integration**
2. Sign-in method: **OIDC - OpenID Connect**, Application type: **Web Application**
3. Sign-in redirect URIs: `https://<host>/api/auth/idp/oidc/callback`
4. Grant type: `Authorization Code`
5. Assignments: 사내 IdP 사용자 그룹 선택
6. Client Credentials 페이지에서 Client ID / Secret 복사
7. Discovery URL:

   ```
   https://<your-okta-domain>/.well-known/openid-configuration
   ```

   또는 custom auth server:

   ```
   https://<your-okta-domain>/oauth2/<auth-server-id>/.well-known/openid-configuration
   ```

### 3.3 Azure AD (Microsoft Entra ID)

1. Azure portal → Microsoft Entra ID → **App registrations** → **New registration**
2. Name: `AJIN AI Assistant`, Supported account types: 회사 정책에 맞춰 선택
3. Redirect URI: Platform=Web, `https://<host>/api/auth/idp/oidc/callback`
4. 등록 후 **Application (client) ID** 복사 → `OIDC_CLIENT_ID`
5. **Certificates & secrets** → New client secret → 값 복사 → `OIDC_CLIENT_SECRET`
6. **Token configuration** → Optional claims → `email`, `preferred_username` 추가 권장
7. Discovery URL:

   ```
   https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
   ```

### 3.4 Google Workspace

1. GCP Console → APIs & Services → **Credentials** → **Create Credentials** → **OAuth client ID**
2. Application type: **Web application**
3. Authorized redirect URIs: `https://<host>/api/auth/idp/oidc/callback`
4. Client ID / Secret 복사
5. Discovery URL (고정):

   ```
   https://accounts.google.com/.well-known/openid-configuration
   ```

> Workspace 도메인 제한이 필요하면 IdP 측 정책 또는 `map_to_internal_user` 에서
> `info.email` 도메인 화이트리스트 검증을 추가하세요.

## 4. 도메인 매핑 정책 (권장)

회사 정책상 사내 이메일은 IdP, 외부 사용자는 사번/비밀번호로 분리 운영하는
경우 다음 패턴을 권장합니다.

- `@ajin.co.kr` 도메인 이메일 → IdP SSO 로그인
- 그 외 (외주/임시) → 기존 사번/비밀번호 로그인

코드 변경 없이 IdP 측 사용자 풀에서 도메인을 제한하면 자연스럽게 구현됩니다.
프론트엔드의 `IdPLoginButtons` 는 활성 IdP 만 표시하므로 무영향 회귀 보장.

## 5. JIT Provisioning 매핑 룰

OIDC 콜백에서 IdP 사용자를 내부 사용자로 매핑하는 우선순위:

1. `employees.db.employees.email` 에서 IdP 이메일 매칭 → `employee_id` 결정
2. `auth.db.users.email` 매칭 → `employee_id` 결정
3. 이메일 local part 가 사번 형식(`PFX-DDDD`)이면 그대로 사용

매핑 성공 시 `auth.db.users` 에 없으면 `EMPLOYEE` 권한으로 자동 생성됩니다
(password_hash = `!OIDC!` placeholder — 사번/비번 로그인 차단). 매핑 실패 시
403 — 사내 직원이 아닌 외부 IdP 계정 차단.

## 6. 시연용 Keycloak (docker-compose, 선택)

로컬 데모용 Keycloak 1대.

```yaml
# docker-compose.keycloak.yml
services:
  keycloak:
    image: quay.io/keycloak/keycloak:24.0
    command: start-dev
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: admin
    ports:
      - "8180:8080"
```

1. `docker compose -f docker-compose.keycloak.yml up -d`
2. http://localhost:8180 → admin/admin 로그인
3. Realm 생성 → Client 등록 (위 3.1 참고)
4. Realm `master` 또는 신규 realm 의 discovery URL:

   ```
   http://localhost:8180/realms/<realm>/.well-known/openid-configuration
   ```

5. AJIN 백엔드 환경변수:

   ```bash
   export IDP_PROVIDER=oidc
   export OIDC_DISCOVERY_URL=http://localhost:8180/realms/master/.well-known/openid-configuration
   export OIDC_CLIENT_ID=ajin-ai-assistant
   export OIDC_CLIENT_SECRET=<keycloak-client-secret>
   ```

## 7. 운영 체크리스트

- [ ] redirect URI 가 HTTPS (Cloud Run 도메인) 인가
- [ ] `OIDC_CLIENT_SECRET` 이 Secret Manager 에 저장되어 있는가 (env 직접 X)
- [ ] `SESSION_STORE=redis` + Memorystore VPC 연결 완료 (멀티 인스턴스)
- [ ] IdP 측 JIT provisioning 매핑 검증 (이메일 → employee_id)
- [ ] IdP 로그인 감사 로그(`audit_logs.idp_login`) 가 Firestore 에 기록되는가
- [ ] 비상시 `IDP_PROVIDER=disabled` 로 즉시 롤백 가능한가 (env 변경만)

## 8. SAML (Phase 4 예정 stub)

`core/auth/idp_saml.py` 는 현재 `NotImplementedError` 만 raise 하는 stub
입니다. 활성화 시 약 4 인시간 추가 작업 필요:

- SP metadata XML 생성/노출 (`GET /api/auth/idp/saml/metadata`)
- IdP metadata XML 파싱 + 인증서 검증
- AuthnRequest 생성 (HTTP-Redirect binding)
- SAMLResponse XML 서명 검증 (signed assertion)
- NameID → employee_id 매핑 (OIDC 와 동일한 JIT provisioning 재사용)

Phase 4 활성화 결정 시 별도 PR 로 진행.
