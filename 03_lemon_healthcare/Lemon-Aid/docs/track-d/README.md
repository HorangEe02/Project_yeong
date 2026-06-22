# docs/track-d/ — Track D (모바일) 작업 산출물

Lemon Healthcare 트랙 D (Flutter 모바일 + 백엔드 통합) 의 phase 별 가이드 /
보고서 / 검증 명세를 모은 디렉토리.

다른 dev-guides 문서와의 차이: **dev-guides 는 "어떻게 구현하느냐"**, **track-d 는
"어떻게 검증하느냐"** 에 가깝다. 회귀 방지 + 시뮬레이터 cycle + 오류 시나리오 e2e.

---

## 인덱스

| 파일 | Phase | 용도 |
|---|---|---|
| [`m3v-sim-cycle-guide.md`](./m3v-sim-cycle-guide.md) | M-3-V.B | iOS/Android sim 매뉴얼 e2e cycle step-by-step (5 시나리오 × 2 플랫폼) |
| [`m3v-sim-cycle-report-template.md`](./m3v-sim-cycle-report-template.md) | M-3-V.B | guide 실행 결과 기입 양식 (체크박스 + 캡처 + elapsed_ms + 이슈) |
| [`m3v-c-error-scenarios.md`](./m3v-c-error-scenarios.md) | M-3-V.C | 오류 시나리오 4 자동 (shell script) + 2 매뉴얼 (sim) 명세 + 결과 양식 |

---

## 실행 흐름

```
M-3-V.A 백엔드 hotfix (commit) ─┐
                                 ↓
M-3-V.B guide 작성 (commit) ────┐ ↓
                                 ↓
                M-3-V.C script + 문서 (commit)
                                 ↓
                ┌────────────────┴────────────────┐
                ↓                                  ↓
        사용자 sim 실행                    Claude script 실행
        (B 결과 보고)                       (C 자동 4 결과)
                ↓                                  ↓
                └──── m3v-*-results-YYYY-MM-DD.md 신규 ────┘
                              (사용자 commit)
```

---

## 명명 규칙

| 종류 | 패턴 | 예 |
|---|---|---|
| Phase 명세 / guide | `<phase>-<topic>.md` | `m3v-sim-cycle-guide.md` |
| 결과 보고서 | `<phase>-<topic>-results-YYYY-MM-DD.md` | `m3v-sim-cycle-results-2026-05-19.md` |
| 캡처 image | `<phase>-<platform>-<scenario>-<step>.png` | `m3v-ios-A-01.png` |

---

## 참조

- 전체 plan: [twinkly-splashing-hejlsberg.md](/Users/yeong/.claude/plans/twinkly-splashing-hejlsberg.md)
- 기존 plan (M-1~M-3-V): [mossy-forging-hejlsberg.md](/Users/yeong/.claude/plans/mossy-forging-hejlsberg.md)
- 백엔드 컨벤션: [backend/CLAUDE.md](../../backend/CLAUDE.md)
- 컴플라이언스: [docs/10-compliance-checklist.md](../10-compliance-checklist.md)
