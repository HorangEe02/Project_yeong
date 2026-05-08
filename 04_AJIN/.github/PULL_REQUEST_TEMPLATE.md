# PR — <type>: <subject>

<!-- 제목은 Conventional Commits 형식: `feat: ...`, `fix(scope): ...` 등 -->

## 변경 내용

<!-- 핵심 변경 사항 3~5줄 -->

## 관련 이슈

<!-- Closes #N / Refs #N -->

## 테스트 결과

- [ ] 로컬 backend 부팅 (`uvicorn backend.main:app`) 성공
- [ ] 로컬 frontend `npm run build` 성공
- [ ] `/api/health` 200 OK
- [ ] (해당 시) 채팅 endpoint smoke test 통과
- [ ] (해당 시) 단위 테스트 작성·통과

## 스크린샷 (UI 변경 시)

<!-- 변경 전·후 -->

## 체크리스트

- [ ] PR 제목이 Conventional Commits 형식 (`feat`/`fix`/`docs`/...)
- [ ] `.env`, `secrets/*` 등 민감 파일 변경 없음
- [ ] 새 의존성 추가 시 `requirements*.txt` / `package.json` 동기화
- [ ] 문서 영향 시 README/INSTALL/ARCHITECTURE 업데이트
- [ ] CI (lint + build) 통과 예상

## 후속 작업 (선택)

<!-- 별도 PR 로 처리할 항목, 알려진 한계 등 -->
