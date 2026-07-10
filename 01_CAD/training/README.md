# 01_CAD 학습 파이프라인

CAD Vision의 모델 학습·평가 스크립트 모음입니다. 원본 학습 데이터(도면 이미지 72,730장)는 저작권·용량 문제로 저장소에 포함되지 않으며, 결과 리포트(`quality_report/`, `preprocessed_dataset/`의 manifest·평가 JSON)만 커밋되어 있습니다.

## 구성

- `scripts/` — 데이터 준비(step4a~c, run_step4/5) · CLIP 파인튜닝(`train_clip.py` / `train_clip_v2.py` / `train_clip_multipos.py` — 실험 반복 버전) · GNN 학습(`train_gnn.py`) · 품질 검사(`inspect_quality.py`)
- `quality_report/` — 데이터 품질 검사 결과
- `clip_finetune_dataset/` · `preprocessed_dataset/` — 데이터셋 구성 메타데이터
- `PROJECT_GUIDE.md` — 과거 로컬 환경 기준 작업 기록 (현행 구조와 다름, 아래 배너 참조)

## 의존성

```bash
pip install -r requirements.txt   # 학습용 (torch · open-clip · torch-geometric)
```
