# 2026-05-27 작업 TODO

## 완료 ✅

- [x] PC2 환경에서 데이터셋 외장 D드라이브 → 내장 C드라이브 이전
  - 출발지: `<local-pc2-aihub-source>\data\processed\aihub_yolo_50`
  - 도착지: `<local-pc2-repo>\data\food_images\aihub_yolo_50`
  - 복사 범위: train/val의 jpg + txt만 (.npy 제외), 총 11.46 GB
  - 검증: train 108,580 / val 13,780 (전체 일치)
  - 방법: robocopy /MT:16 (jpg는 *.jpg 필터, txt는 *.txt 필터)

- [x] data.yaml path 수정
  - `path: <local-pc2-aihub-source>/data/processed/aihub_yolo_50` → `path: <local-pc2-repo>/data/food_images/aihub_yolo_50`

- [x] baseline_run.ps1 재작성
  - 경로: `<local-pc2-repo>\docs\superpowers\plans\baseline_run.ps1`
  - 이전 버전이 git untracked였고 git checkout 후 사라져서 새로 작성
  - 인터랙티브 Read-Host 프롬프트 제거 → labels.cache 자동 archive 이동
  - 사전 점검 추가 (yolo.exe, data.yaml, GPU, CUDA, 데이터 개수, C 여유)
  - 설정은 handoff §19.4 PC2 baseline 그대로 유지

- [x] cache=ram / cache=False 실험 실패 원인 학습
  - cache=ram: 186GB RAM 필요 → 자동 fallback → GPU 1%로 굶음 (CPU-bound)
  - cache=False: 워커 8개로 부족, 외장 SSD 1GB/s여도 augmentation CPU 병목
  - 결론: handoff 권장대로 cache=disk가 정답

## 진행 중 🔄

- [ ] exp01 YOLOv8n PC2 baseline 시작 대기
  - 실행 명령: `cd <local-pc2-repo>\docs\superpowers\plans; .\baseline_run.ps1`
  - run name: `exp01_yolov8n_baseline_pc2_b48_w8_cache_disk_det_true`
  - 설정: model=yolov8n.pt, epochs=50, batch=48, workers=8, cache=disk, imgsz=640, deterministic=true, seed=42, patience=15, plots=false
  - 예상 시간: 초기 cache=disk 캐싱 7~8시간 + 50 epoch × 약 75분 = 약 70시간

## 다음 작업 📋

- [ ] PC2 baseline 진행 모니터링
  - PowerShell 명령으로 results.csv, weights/, GPU, RAM 진척 추적
  - epoch별 mAP50/mAP50-95 기록
- [ ] PC2 baseline 완료 후 validation plots 실행 (handoff §16)
  - confusion matrix, PR curve, F1 curve, class별 metric
- [ ] PC1 vs PC2 baseline 비교 (handoff §19.2 원칙: 직접 비교 금지, 각자 baseline 대비)
- [ ] PC1의 exp02 YOLO11s 결과 확인 (별도 컴퓨터에서 진행 중)
- [ ] class별 AP, confusion matrix 분석 → 약한 클래스 식별
- [ ] 약한 클래스 기반 후속 실험 설계 (exp03~exp08, handoff §18)

## 환경 스냅샷

| 항목 | 값 |
| --- | --- |
| 브랜치 | `docs/data-yolo-food-detection` |
| 최근 커밋 | `248a682 docs(data): aihub_yolo balanced_500 + yolo11s PC2 학습 implementation plan 추가` |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU (8188 MiB) |
| Python | 3.13.13 |
| PyTorch | 2.6.0 + CUDA 12.4 |
| Ultralytics | 8.4.51 |
| 데이터셋 | `<local-pc2-repo>\data\food_images\aihub_yolo_50` (11.46 GB) |
| runs 폴더 | `<local-pc2-repo>\runs\food_yolo` (PC1 결과 이미 복사됨) |
| C 드라이브 여유 | 약 416 GB (cache=disk 130 GB 사용 예정) |
| labels.cache | 없음 (fresh scan 예정) |

## 주의사항 (이전 시도에서 학습)

- **cache=ram은 절대 사용 금지**: 186GB RAM 필요로 fallback되어 GPU 1%로 굶음
- **학습 띄운 콘솔은 절대 닫지 말 것**: 이전 세션에서 프로세스 트리 정리하다 학습 죽은 적 있음
- **robocopy 종료 코드 0~7은 모두 정상** (1=정상 복사 완료). PowerShell이 `$LASTEXITCODE=1`을 실패로 잡을 수 있으나 결과만 검증하면 됨
- **인터랙티브 Read-Host는 별도 콘솔 stdin으로 주입 불가** → baseline_run.ps1은 자동 처리하도록 작성됨
- **untracked 파일은 git checkout 시 사라질 수 있음**: baseline_run.ps1이 사라진 사례 발생 → 새로 작성 후 commit 검토 필요

## 참고 문서

- `docs/superpowers/plans/2026-05-22-aihub-yolo-handoff.md` — 전체 인수인계, 병렬 학습 계획
- `docs/superpowers/plans/2026-05-26-aihub-yolo-todo.md` — PC1 baseline 완료 기록, exp02 YOLO11s 시작
- `docs/superpowers/plans/2026-05-25-aihub-yolo-todo.md` — workers/cache 효과 없음 원인 분석
- `docs/superpowers/plans/2026-05-23-aihub-yolo-todo.md` — PC1 baseline 시작 기록
- `docs/superpowers/plans/2026-05-21-yolo-baseline-troubleshooting-report.md` — labels.cache 손상 hang 트러블슈팅
