# 2026-05-27 — AI Hub YOLO balanced_500 + YOLO11s (PC2) 학습 설계

> Current branch note: `feat/db-internal-learning-pipeline` stores the food image
> analysis backend under `backend/Food-backend/`. The source branch may refer to
> `backend/src` or `backend/tests`; in this branch, apply food-specific backend
> code and tests under `backend/Food-backend/` unless the main API integration is
> explicitly planned.

## 1. 목적

PC1에서 진행 중인 `YOLOv8n + balanced_500` 실험과 비교할 짝(pair)으로, PC2에서 **YOLO11s + balanced_500** 학습을 돌린다. 두 실험은 동일한 train/val 서브셋과 동일한 학습 하이퍼파라미터를 공유하며, 단일 독립변수는 **모델 아키텍처(yolov8n vs yolo11s)** 다.

부수 목적:
- 50개 클래스의 train 분포 불균형을 클래스당 상한 500장으로 다운샘플링하여 균형 효과를 측정한다.
- val은 원본 그대로 유지하여 평가 공정성과 PC1 baseline(yolov8n + 풀데이터 108K, mAP50 0.839)과의 간접 비교 여지를 확보한다.

## 2. 비교 설계

| 변수 | PC1 | PC2 (본 설계) |
|---|---|---|
| 모델 | yolov8n.pt | yolo11s.pt |
| Train | balanced_500 (≈23K) | balanced_500 (≈23K) — **동일 서브셋** |
| Val | 원본 13,780 | 원본 13,780 — **동일** |
| epochs | 50 | 50 |
| imgsz | 640 | 640 |
| workers | 8 | 8 |
| cache | disk | disk |
| seed | 42 | 42 |
| deterministic | true | true |
| patience | 15 | 15 |
| plots | false | false |
| batch | 48 (PC1 설정 사용 중) | 32 (OOM 시 16 폴백) |
| GPU | PC1 GPU | RTX 4060 Laptop 8GB |

**서브셋 동일성 보장**: 양 PC가 동일 다운샘플링 스크립트를 동일 시드(42)로 실행한다. 같은 원본 데이터에 적용하면 동일한 23K 파일이 선택된다(§3.1 참조). 검증은 train 파일 수와 매니페스트 JSON(클래스별 파일명 정렬 리스트)로 한다.

**비교 가능 범위**:
- 동일 val 기준 mAP50/mAP50-95 직접 비교 가능 (모델 아키텍처+용량 효과 측정)
- 학습 시간/GPU 메모리 절대값 비교 불가 (PC1·PC2 GPU 사양 다름)

## 3. 데이터 다운샘플링

### 3.1 샘플링 방식 — seed=42 고정 랜덤 샘플링

**방식**: 시드 고정 균등 랜덤 샘플링 (`random.sample`)

**알고리즘** (클래스별로 독립 적용):
```python
import random

random.seed(42)
for class_id in range(50):
    stems_of_class = sorted(label_files_with_class_id(class_id))  # 정렬로 입력 순서 결정론화
    k = min(500, len(stems_of_class))
    selected = random.sample(stems_of_class, k)                   # 시드 고정 랜덤 추출
```

**왜 랜덤?**
- 파일명 순(sorted 후 앞 N개)으로 자르면 AI Hub 데이터의 촬영 세션·각도 패턴 편향을 일으킬 수 있음 (예: 같은 음식의 같은 세션 사진이 연속). 랜덤은 이를 피한다.
- Stratified(메타 기반)는 파일명 스키마 추가 분석이 필요해 ROI 낮음.

**왜 시드 고정?**
- 시드 없이 돌리면 매 실행마다 다른 23K가 선택됨 → PC1·PC2 비교 불가, 재현 불가.
- `random.seed(42) + sorted(stems) + random.sample`은 Python random 모듈 사양상 입력만 같으면 출력이 동일. PC1과 PC2의 원본 데이터가 같다면(체크섬으로 확인 가능) 두 PC가 동일한 23K를 선택한다.

**적용 범위**: train만. val은 다운샘플링 없이 원본 13,780 전체 복사.

### 3.2 정책 요약
- **상한 500, 하한 그대로**: 500장 초과 클래스는 500장으로 다운샘플, 500장 미만(예: 100~499)은 원본 그대로 유지 (소수 클래스 보존)
- **train만 적용**, val 무변경
- **결정론적 랜덤**: §3.1 알고리즘대로 `random.seed(42)` + `sorted()` + `random.sample()`

### 3.3 폴더 구조 (생성 후)

```
data/food_images/
├── aihub_yolo_50/                      ← 원본 (무변경, 보존)
│   ├── data.yaml
│   ├── train/images/   108,580 jpg
│   ├── train/labels/   108,580 txt
│   ├── val/images/      13,780 jpg
│   ├── val/labels/      13,780 txt
│   └── yolo_class_index_50.json
│
└── aihub_yolo_50_balanced_500/         ← 새 서브셋 (이번 작업)
    ├── data.yaml                       ← path 본 폴더 가리킴
    ├── _manifest/
    │   ├── class_counts_original.csv   ← 원본 분포 스냅샷
    │   ├── class_counts_balanced.csv   ← 다운샘플 후 분포
    │   └── train_manifest.json         ← 클래스별 선택된 stem 리스트 (정렬됨)
    ├── train/
    │   ├── images/   ≈23,030 jpg       ← 원본에서 복사
    │   └── labels/   ≈23,030 txt
    └── val/
        ├── images/   13,780 jpg        ← 원본에서 복사 (전체)
        └── labels/   13,780 txt
```

### 3.4 스크립트 (`scripts/data/downsample_balanced.py`)

핵심 동작:
1. 원본 train/labels의 모든 txt 파일 스캔 → 파일별 라벨에서 class id 추출 → 클래스별 stem 리스트 작성
2. §3.1 알고리즘 그대로 클래스별 선택
3. 선택된 stem에 대해 원본 → 새 폴더로 jpg + txt 복사 (`shutil.copy2`)
4. val은 원본 전체를 복사
5. 새 `data.yaml` 작성 (path만 새 폴더, names는 원본 동일)
6. 매니페스트 3개 파일 저장

CLAUDE.md 규칙 준수: 타입 힌트 100%, Google-style docstring, dataclass 대신 Pydantic v2 (매니페스트 모델용).

### 3.5 검증 체크리스트

- [ ] 새 폴더 train/images 개수 == train/labels 개수
- [ ] 모든 jpg의 짝꿍 txt 존재
- [ ] 클래스별 새 폴더 분포: 어느 클래스도 500 초과하지 않음
- [ ] 500 미만 클래스의 개수는 원본과 동일 (보존 확인)
- [ ] val/images, val/labels 개수 == 원본 (각 13,780)
- [ ] data.yaml path가 새 폴더 가리킴
- [ ] 매니페스트 JSON: 클래스 50개 키 모두 존재, 각 리스트 정렬 상태
- [ ] **재현성 셀프 체크**: 스크립트를 두 번 돌렸을 때 같은 23K가 선택되는지 (`diff manifest1.json manifest2.json` == empty)

## 4. 학습 설정

### 4.1 OOM dry-run (필수, 본 학습 전)

YOLO11s + batch=32가 RTX 4060 8GB에서 OOM 없이 1 epoch을 시작할 수 있는지 확인.

```powershell
yolo detect train `
  model=yolo11s.pt `
  data=<balanced_500>/data.yaml `
  epochs=1 `
  imgsz=640 `
  batch=32 `
  workers=8 `
  cache=disk `
  device=0 `
  seed=42 `
  deterministic=true `
  plots=false `
  project=<runs>/food_yolo `
  name=_dryrun_yolo11s_b32 `
  fraction=0.005      # 약 100~150장만 사용해 빠르게 OOM 여부 확인
```

- 통과 기준: GPU OOM 없이 1 epoch 진입, GPU 메모리 사용량 < 7.5 GB
- 실패 시: batch=16으로 재시도. 16도 실패면 batch=12.
- dry-run 종료 후 `_dryrun_yolo11s_b32/` 폴더는 `_archive/`로 이동 (CLAUDE.md "삭제 대신 이동" 규칙).

### 4.2 본 학습

```powershell
yolo detect train `
  model=yolo11s.pt `
  data=<balanced_500>/data.yaml `
  epochs=50 `
  imgsz=640 `
  batch=<dry-run에서 통과한 값> `
  workers=8 `
  cache=disk `
  device=0 `
  seed=42 `
  deterministic=true `
  patience=15 `
  plots=false `
  project=<runs>/food_yolo `
  name=exp0X_yolo11s_balanced500_pc2_b<batch>_w8_cache_disk_det_true
```

X는 plans 정리 시점에 결정. run name에 실제 batch 값을 박아 추적성 확보.

### 4.3 사전 점검 ps1

`docs/superpowers/plans/yolo11s_balanced500_run.ps1` 신규 작성 (기존 baseline_run.ps1 패턴 재사용):
- yolo.exe / data.yaml / project 폴더 존재 확인
- labels.cache 자동 archive 이동
- 데이터셋 파일 개수 출력 (train ≈23K, val 13.78K)
- GPU / PyTorch CUDA / C 드라이브 여유 출력
- 본 학습 실행

## 5. 학습 후 분석

### 5.1 Validation plots

학습 종료 후 `best.pt`로 validation 1회 더 실행 (handoff §16):

```powershell
yolo detect val `
  model=<run>/weights/best.pt `
  data=<balanced_500>/data.yaml `
  imgsz=640 `
  device=0 `
  plots=true `
  save_json=true `
  project=<runs>/food_yolo `
  name=exp0X_yolo11s_balanced500_pc2_val
```

산출물: confusion_matrix.png, PR_curve.png, F1_curve.png, R_curve.png, P_curve.png, predictions.json, results.json

### 5.2 클래스별 분석

`results.json`에서 클래스별 AP 추출 → 약한 클래스 5~10개 식별. exp03~exp08 후속 실험 설계 입력.

### 5.3 PC1 결과와의 비교

PC1 (yolov8n + balanced_500) 학습 종료 후, 동일 val 기준 두 결과를 한 표로 정리:
- 전체 mAP50, mAP50-95
- 클래스별 AP delta (yolo11s − yolov8n)
- 약한 클래스가 모델 변경으로 개선됐는지 확인

별도 자동화 스크립트는 만들지 않음 (한 번성 작업, 수동 비교가 더 빠름).

## 6. 일정·산출물

| 단계 | 산출물 | 추정 소요 |
|---|---|---|
| 1. 원본 분포 분석 | `_audit/class_counts.csv` | 5분 |
| 2. 다운샘플 스크립트 작성 | `scripts/data/downsample_balanced.py` + 단위 테스트 | 20~30분 |
| 3. 스크립트 실행 + 검증 | `aihub_yolo_50_balanced_500/` 폴더 | 30~60분 |
| 4. OOM dry-run | dry-run 로그 + batch 확정 | 10~15분 |
| 5. ps1 작성 | `yolo11s_balanced500_run.ps1` | 10분 |
| 6. 본 학습 | run 폴더 + best.pt + results.csv | ≈25시간 (batch=32 기준) |
| 7. validation plots | val 폴더 + plots + class별 AP | 30분 |
| **합계 사람-시간** | — | 약 1.5~2시간 (학습 대기 제외) |

## 7. 위험·완화

| 위험 | 완화 |
|---|---|
| OOM (batch=32 실패) | dry-run으로 사전 확인, batch=16/12 폴백 경로 명시 |
| 다운샘플 결과가 PC1과 다름 | seed=42 + sorted + random.sample 보장. 매니페스트 JSON으로 사후 검증. 다르면 원본 데이터 동기화 상태 점검(파일 수 + 무작위 샘플 체크섬). |
| 학습 25시간 중 콘솔 종료/세션 끊김 | 사용자가 별도 PowerShell에서 직접 실행 (Claude Code 세션과 분리). plan 주의사항과 일치. |
| YOLO11s가 yolov8n보다 mAP가 낮음 | 가능한 결과. 그 자체가 데이터 (모델 용량 증가가 이 데이터셋·다운샘플 조건에서 도움 안 됨). 분석에 포함. |
| labels.cache 손상 hang | ps1이 cache 자동 archive 이동 (2026-05-21 troubleshooting 패턴 재사용) |
| 디스크 부족 | cache=disk 약 30 GB + 데이터 복사 약 3 GB. 현재 C 여유 416 GB로 충분. 검증 단계에서 재확인. |

## 8. CLAUDE.md 준수 사항 점검

- [x] 의료 도메인 금지 표현 없음 (분류/검출 작업)
- [x] 외부 API 직접 호출 없음 (ultralytics만 사용)
- [x] 새 Python 스크립트는 타입 힌트 + Google-style docstring + Pydantic v2 (매니페스트 모델용)
- [x] 단위 테스트 (다운샘플 결정론 + 매니페스트 직렬화) — `tests/unit/test_downsample_balanced.py` 동반
- [x] 민감 정보 커밋 없음
- [x] 한국·아시아 BMI 기준 — 본 작업 무관
- [x] 파일 삭제 금지, 폴더 이동: dry-run 결과 `_archive/` 이동, 원본 데이터셋 무변경
- [x] git commit은 사용자 확인 후

## 9. 팀 협업 규칙 준수 (docs/superpowers/team-collaboration/)

- 브런치: 현재 `docs/data-yolo-food-detection`에서 작업 중. 본 실험 결과 커밋은 같은 브런치 또는 신규 `data/data-balanced500-yolo11s-pc2`로 분기 가능
- 커밋 메시지: `data(data): exp0X yolo11s balanced_500 PC2 학습 결과 추가` 패턴 (한국어 명령형)
- PR base: develop. 본 작업은 결과 누적이라 단일 PR로 묶거나 단계별 분할 가능

## 10. 후속 작업 (이 spec 밖)

- PC1의 yolov8n + balanced_500 결과 정리 (다른 컴퓨터 작업)
- yolov8n vs yolo11s 비교 분석 (양쪽 학습 완료 후)
- 약한 클래스 기반 exp04~exp08 실험 설계 (handoff §18)
- mobile 인퍼런스용 모델 export (ONNX/TFLite) — 별도 spec

---

**작성자**: jongpil-Mun (Claude Code 보조)
**버전**: v1.1 (§3.1 샘플링 방식 명시 추가)
**상태**: 검토 대기
**참조**: `docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md`, `docs/superpowers/plans/2026-05-22-aihub-yolo-handoff.md`
