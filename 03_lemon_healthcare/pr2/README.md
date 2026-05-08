# pr2 — TBD

> 🚧 **Placeholder** — 두 번째 기업 과제를 위한 자리입니다. 과제가 확정되면 본 문서를 실제 내용으로 교체하세요.

## 채워야 할 항목

- [ ] 과제명 / 발주처
- [ ] 한 줄 요약
- [ ] 핵심 페르소나 / 차별화 포인트
- [ ] 폴더 구성 (backend / mobile / docs / data 중 무엇이 필요한지)
- [ ] 일정 / 마일스톤

## 정합성 체크리스트 (콘텐츠 추가 시)

새 영역 폴더를 추가하면 다음도 함께 업데이트해야 CI·리뷰 흐름이 정상 동작합니다.

- [ ] `03_lemon_healthcare/.github/CODEOWNERS` — `/03_lemon_healthcare/pr2/<area>/` 항목 추가
- [ ] `03_lemon_healthcare/.github/workflows/ci-backend.yml` — `paths` 에 `03_lemon_healthcare/pr2/backend/**` 추가 (백엔드가 있을 때)
- [ ] `03_lemon_healthcare/.github/workflows/ci-mobile.yml` — `paths` 에 `03_lemon_healthcare/pr2/mobile/**` 추가 (모바일이 있을 때)
- [ ] `03_lemon_healthcare/.github/workflows/ci-docs.yml` — 자동 매칭(`pr2/**/*.md`)이 필요하면 paths/lint glob/lychee args 보정
- [ ] main 보호 규칙의 `required_status_checks.contexts` 에 새 워크플로 job 이름이 추가될지 검토

## 참고

- 폴더 분리 패턴 출처: [pr1/docs/05-github-guidelines.md](../pr1/docs/05-github-guidelines.md)
- 자매 과제: [../pr1/](../pr1/), [../pr3/](../pr3/)
