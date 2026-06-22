# ✅ 코드 리뷰 체크리스트

> 리뷰어와 작성자 모두 이 체크리스트를 사용합니다. 작성자는 PR 올리기 전 자체 점검, 리뷰어는 리뷰 시 참조.

---

## 1. 작성자 자체 점검 (PR 올리기 직전)

### 형식
- [ ] PR 제목이 Conventional Commits 형식 (`<type>(<scope>): <subject>`)
- [ ] 브런치 이름이 `<type>/<scope>-<주제>` 형식
- [ ] PR 본문에 요약(Why) / 변경(What) / 검증(How) 작성
- [ ] 관련 이슈 링크 (`Closes #N` / `Refs #N`)
- [ ] 스크린샷·로그 (UI·OCR·모바일 변경 시)

### 코드
- [ ] `develop` 최신을 rebase로 동기화
- [ ] 모든 pre-commit hook 통과 (`pre-commit run --all-files`)
- [ ] 모든 테스트 green (`pytest`, `flutter test`)
- [ ] CI 모든 체크 green
- [ ] 디버그 코드(`print`, `console.log`, `breakpoint()`) 제거
- [ ] 주석 처리된 코드 블록 제거 (의도가 없으면)
- [ ] TODO/FIXME는 이슈 번호 인용 (`# TODO(#N): ...`)

### 보안
- [ ] `.env` / 비밀키 / 토큰 미포함
- [ ] 대용량 파일(2MB+) 미포함 — 필요 시 LFS
- [ ] API 키·DB 비밀번호 하드코딩 없음
- [ ] SQL/Shell injection 위험 없음 (파라미터 바인딩 사용)

### 문서
- [ ] 새 기능·API는 `PROJECT_GUIDE.md` 또는 `docs/`에 반영
- [ ] `.env.example` 갱신 (새 환경변수 추가 시)
- [ ] 의존성 변경 시 `requirements.txt` / `pubspec.yaml` 동기화

---

## 2. 리뷰어 체크리스트

### A. 의도 이해
- [ ] PR 본문을 읽고 **무엇을 / 왜** 이해함
- [ ] 의도와 코드가 일치함
- [ ] 관련 이슈/디자인 문서 확인

### B. 정확성 (가장 중요)
- [ ] 로직이 의도대로 동작 — 엣지 케이스 고려됨
- [ ] 에러 처리 / 예외가 합리적 (과하지도, 부족하지도)
- [ ] 동시성·경합 가능성 없음 (해당 시)
- [ ] 외부 입력 검증 (API, 사용자 입력)
- [ ] 시간/지역(timezone, locale) 처리 OK

### C. 테스트
- [ ] 핵심 동작에 대한 테스트 존재
- [ ] 엣지 케이스 / 실패 경로 테스트
- [ ] 픽스처/모킹이 과하지 않음 (mock보다 실제 통합 우선)
- [ ] 테스트가 결정적(deterministic) — 시간/네트워크 의존성 격리

### D. 가독성
- [ ] 함수/변수 이름이 의도를 드러냄
- [ ] 함수가 너무 길지 않음 (한 화면 안에 보이는 것이 이상적)
- [ ] 들여쓰기 깊이가 깊지 않음 (가능하면 early return)
- [ ] 주석은 "왜"를 설명 (코드가 이미 "무엇"을 말함)
- [ ] 중복 코드(DRY 위반) 없음 — 단, **3번 반복부터** 추상화

### E. 아키텍처
- [ ] 변경이 기존 계층 구조를 존중 (model/service/api 분리)
- [ ] 모듈 간 의존성 방향이 올바름 (UI → service → repository)
- [ ] 부수 효과(side effect)가 명확히 분리됨
- [ ] 인터페이스가 안정적 (자주 깨질 가능성 낮음)

### F. 성능
- [ ] N+1 쿼리 없음 (DB 접근)
- [ ] 불필요한 동기 I/O 없음 (async 활용)
- [ ] 큰 데이터 처리 시 스트리밍/페이징
- [ ] 캐시가 필요한 곳에는 캐시, 없어야 할 곳엔 없음

### G. 보안
- [ ] 인증/인가가 올바른 위치에 적용
- [ ] 사용자 입력 sanitize / validate
- [ ] 비밀값이 로그에 노출되지 않음
- [ ] OWASP Top 10 (XSS, CSRF, IDOR, SSRF, ...) 점검

### H. 문서·UX
- [ ] API 변경은 OpenAPI / 가이드에 반영
- [ ] 에러 메시지가 사용자 친화적 (특히 모바일)
- [ ] 의료/법적 표현 검증 (Lemon Aid 특성)

---

## 3. 영역별 추가 체크

### 📱 mobile (Flutter)
- [ ] 위젯 트리가 너무 깊지 않음 (state 분리, hooks/riverpod 활용)
- [ ] async에서 `BuildContext` 사용 시 `mounted` 체크
- [ ] 색상·spacing은 디자인 토큰 사용 (하드코딩 X)
- [ ] iOS/Android 모두 빌드 검증
- [ ] 빌드 후 화면 스크린샷 첨부

### 🔧 backend (FastAPI)
- [ ] Pydantic 스키마로 입/출력 명시
- [ ] 비동기 라우트는 `async def` 일관성
- [ ] DB 세션 의존성 주입 (`Depends(get_db)`)
- [ ] 에러 응답이 표준 형식 (`HTTPException` + detail)
- [ ] OpenAPI tags / summary 작성

### 🤖 ai (Claude/LLM)
- [ ] 시스템 프롬프트가 컨벤션 준수 (`PROJECT_GUIDE.md`)
- [ ] 비용 추적 가능 (input/output 토큰 로깅)
- [ ] 의료 표현 검증 (compliance 테스트)
- [ ] Tool use 결과 검증

### 🖼️ ocr
- [ ] 픽스처(snapshot) 업데이트 시 변경 이유 PR 본문에 명시
- [ ] CER/WER 변동이 평가 리포트에 반영됨
- [ ] 한/영 라벨 모두 검증

### 🗄️ db
- [ ] 마이그레이션 스크립트 reversible (down 함수)
- [ ] 인덱스 추가/제거가 합리적
- [ ] 대용량 테이블 변경 시 락 영향 검토

### 🔐 auth
- [ ] 토큰 만료/갱신 흐름 검증
- [ ] OAuth state/PKCE 사용
- [ ] 비밀번호 해싱 알고리즘 (bcrypt/argon2)

### 🏗️ infra / ci
- [ ] 워크플로 변경이 다른 job을 깨지 않음
- [ ] 비밀값은 GitHub Secrets / Vault
- [ ] 캐시 키가 적절

---

## 4. 리뷰 코멘트 매너

### 표기
- `nit:` — 사소한 제안, 무시 가능
- `suggestion:` — 더 나은 방법 제안
- `question:` — 의도 확인 질문 (반드시 답변 필요는 X)
- `blocking:` — 머지 전 반드시 해결
- `praise:` — 잘한 부분 칭찬 (자주!)

### 톤
- ❌ "이거 왜 이렇게 했어요?" → ✅ "여기서 X 대신 Y를 쓰면 N+1을 피할 수 있을 것 같아요. 어떻게 생각하세요?"
- ❌ "틀렸음" → ✅ "이 경우에 ... 케이스가 누락된 것 같습니다 — 예: ..."
- ✅ 코드를 비판, 사람은 비판하지 않음
- ✅ 좋은 코드는 명시적으로 칭찬

### 우선순위
1. 정확성 (버그·보안)
2. 의도 명확성 (네이밍·구조)
3. 테스트 커버리지
4. 성능 (병목이 보일 때만)
5. nit (포매팅·스타일)

---

## 5. Approve 기준

다음을 모두 만족할 때 ✅ Approve:

- [ ] PR 본문의 "체크리스트" 모두 체크됨
- [ ] CI 모든 체크 green
- [ ] `blocking:` 코멘트가 모두 resolved
- [ ] 의도가 명확하고 의도대로 동작함을 확인
- [ ] 테스트가 핵심 동작을 커버함

> 🛑 `LGTM`만 남기지 마세요. 짧아도 무엇을 봤는지 알 수 있도록.

---

## 6. Request Changes 기준

- 정확성/보안 문제
- 의도와 코드 불일치
- 테스트 부재 (핵심 기능)
- 영역 경계 침범 (다른 팀 영역을 무단 변경)

---

## 7. 한 페이지 요약

```
[작성자]
  └─ 자체 점검 → CI green → 리뷰 요청

[리뷰어]
  └─ 의도 이해 → 정확성 → 테스트 → 가독성 → 아키텍처 → 보안
  └─ 코멘트(nit/suggestion/question/blocking/praise)
  └─ Approve / Request changes

[작성자]
  └─ 코멘트 반영 → resolved 처리
  └─ develop 최신화 → Squash Merge
```

---

## 관련 문서

- [`PR_GUIDELINES.md`](./PR_GUIDELINES.md)
- [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md)
- [`CI_CD_GATES.md`](./CI_CD_GATES.md)
