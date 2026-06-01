# 2026-05-31 백엔드 OCR·보안·인프라 작업 인덱스

> 작성 기준: 2026-05-31 백엔드 세션 (영양제 라벨 OCR/파서/보안/DB/인프라)
> 정리일: 2026-06-01
> 범위: Nutrition-backend OCR 파이프라인 진단·개선, 프롬프트 인젝션 보안, 로깅 버그, FORCE RLS 로드맵, 시뮬레이터/에뮬레이터 갤러리, Docker 복구
> 비고: 같은 폴더의 `2026-05-31-react-mobile-web-ui-*` / `*-vercel-supabase-*` 문서는 **별개 프론트엔드 작업 스트림**이며 본 인덱스와 무관하다.

---

## 문서 목록 (브랜치별 분리)

각 문서는 "하나의 논리적 브랜치(커밋 단위)"처럼 독립적으로 읽을 수 있게 분리했다.

- `01-ocr-ingredient-declaration.md`
  - 원재료명(원재료명/원료명) 선언부에서 성분명 후보를 추출하는 기능 추가
  - 영양정보(성분표)가 없어도 성분명만으로 후보 생성, 함량은 위조하지 않음(None)
  - 대응 커밋: `6e1b42c` (일부)

- `02-security-injection-sanitizer.md`
  - 선언부 성분명이 프롬프트 인젝션/HTML/제어문자 sanitizer를 우회하던 CRITICAL 수정
  - 코드 리뷰가 적발 → 수정 → 런타임 차단 검증
  - 대응 커밋: `6e1b42c` (일부)

- `03-logging-redaction-bugfix.md`
  - RedactingFilter가 `record.args=None`으로 비워 uvicorn AccessFormatter 언패킹을 깨뜨리던 회귀 수정
  - 대응 커밋: `6e1b42c` (일부)

- `04-ocr-preprocess-default.md`
  - 로컬 OCR 전처리 기본값 `none → autocontrast`
  - 대응 커밋: `6e1b42c` (일부)

- `05-force-rls-rollout.md`
  - FORCE RLS 마이그레이션 3종(역할/정책/FORCE) + 세션 GUC 배선 파일 작성(라이브 미적용)
  - throwaway DB 증명, 라이브 DB 무변경 확인
  - 대응 커밋: `ed54f82`, 설계문서 `641ce27`

- `06-ocr-pipeline-diagnosis.md`
  - "PaddleOCR이 텍스트를 못 뽑는다" 증상의 근본 원인 진단
  - 결론: OCR 정상(신뢰도 0.96), 원인은 이미지에 영양정보 표 없음 (DB 증거)
  - 코드 변경 없음 — 진단 기록

- `07-simulator-emulator-gallery.md`
  - naver 영양제 샘플 이미지를 iOS 시뮬레이터 2종 + Android 에뮬레이터 갤러리에 삽입
  - 헬퍼 스크립트 복원, addmedia/adb push 검증

- `08-docker-recovery-container-cleanup.md`
  - Docker Desktop stale bind-mount 버그로 backend 컨테이너 시작 불가 → 재시작으로 복구
  - 잔여 컨테이너(webtest 삭제 / edge_runtime 재기동) 정리

---

## 현재 핵심 상태

- 백엔드 컨테이너(`lemon-aid-backend-1`) **healthy**, `/health 200`. DB·redis·supabase 전부 정상.
- 코드 변경은 `feat/backend-supplement-ocr-db-hardening` 브랜치에 커밋·푸시됨 (`6e1b42c`까지, origin 동기화).
- FORCE RLS는 **파일만 작성·증명**, 라이브 DB 미적용(별도 승인 게이트).
- 미커밋: 모바일 helper 스크립트 2개(`select_naver_gallery_samples.py`, `dev_mac_camera_bridge.py`)는 의도적으로 작업트리에만 유지.

---

## 검증 신뢰도 표기

- ✅ 라이브/직접 실행 확인
- ◐ 에이전트 + 직접 교차검증
- ⚠️ 부분/환경 의존(별도 주의 명시)
