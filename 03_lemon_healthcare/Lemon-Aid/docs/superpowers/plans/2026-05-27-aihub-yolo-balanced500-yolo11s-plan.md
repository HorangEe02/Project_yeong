# AI Hub YOLO balanced_500 + YOLO11s (PC2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PC2에서 50 클래스 YOLO 데이터셋을 클래스당 상한 500장으로 시드 고정 랜덤 다운샘플링(train만)하고, 그 서브셋으로 YOLO11s를 50 epoch 학습한 뒤 validation plots까지 산출한다.

**Architecture:** 다운샘플은 `scripts/data/downsample_balanced.py` 단일 스크립트가 처리한다. 원본을 무변경 보존하고 `data/food_images/aihub_yolo_50_balanced_500/`에 사진+라벨을 복사한다. 학습·검증은 ultralytics CLI(`yolo detect train|val`)를 PowerShell 래퍼 ps1로 감싸 사전 점검과 함께 실행한다. 모든 단계는 TDD: 다운샘플 결정론·매니페스트 직렬화·CLI 데이터 검증을 단위 테스트로 잠근다.

**Tech Stack:** Python 3.13, ultralytics 8.4.51, PyTorch 2.6.0 + CUDA 12.4, Pydantic v2, pytest, PowerShell 5.1 (Windows 11).

**Spec:** `docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md`

**Current branch adaptation:** `feat/db-internal-learning-pipeline` keeps food image
analysis code under `backend/Food-backend/`, not `backend/Nutrition-backend/`.
When applying this upstream plan in the current branch, place food-specific tests
under `backend/Food-backend/tests/...` and keep `Nutrition-backend` focused on the
existing OCR/health/supplement API.

---

## File Structure

**Create:**
- `scripts/data/__init__.py` — 빈 패키지 마커
- `scripts/data/downsample_balanced.py` — 다운샘플 스크립트 (CLI entry)
- `scripts/data/_dataset_audit.py` — 클래스 분포 분석 헬퍼 (스크립트 내부 + 테스트용 재사용)
- `scripts/data/_manifest_models.py` — Pydantic v2 매니페스트 모델
- `backend/tests/unit/scripts/__init__.py` — 빈 마커
- `backend/tests/unit/scripts/test_downsample_balanced.py` — 단위 테스트 (결정론 + 매니페스트)
- `docs/superpowers/plans/yolo11s_balanced500_run.ps1` — 학습 ps1 래퍼 (사전 점검 + train)
- `docs/superpowers/plans/yolo11s_balanced500_val.ps1` — validation ps1 래퍼 (best.pt + plots)

**Modify (실행 시점):**
- `docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md` — 진행 상태 업데이트 (작업 진행 중)

**No-touch (원본 보존):**
- `data/food_images/aihub_yolo_50/**` — 절대 수정 금지
- 기존 `backend/src/**` — 영향 없음 (스크립트는 backend 코드 의존 없음)

**왜 scripts/data/에 두나:** CLAUDE.md 표준 폴더 구조에 `scripts/`가 명시되어 있고 데이터 처리 스크립트는 backend 런타임 의존이 없음. 테스트는 backend 테스트 인프라(pyproject pytest 설정)를 그대로 활용.

---

## Task 1: Pydantic v2 매니페스트 모델

**Files:**
- Create: `scripts/data/_manifest_models.py`
- Test: `backend/tests/unit/scripts/test_downsample_balanced.py` (모델 부분만 먼저 작성)

**Why:** 매니페스트 JSON을 dict로 다루면 키 오타·타입 오류가 런타임에 잡힘. Pydantic 모델로 직렬화/역직렬화를 잠그면 재현성 검증이 안전해진다.

- [ ] **Step 1: 단위 테스트 파일과 첫 테스트 작성**

`backend/tests/unit/scripts/__init__.py` 빈 파일 생성.

`backend/tests/unit/scripts/test_downsample_balanced.py` 생성:

```python
"""scripts/data/downsample_balanced.py 단위 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.data._manifest_models import ClassManifest, TrainManifest


class TestManifestModels:
    """매니페스트 Pydantic v2 모델 검증."""

    def test_class_manifest_serializes_sorted_stems(self) -> None:
        """ClassManifest는 stems를 정렬된 리스트로 직렬화한다."""
        cm = ClassManifest(class_id=3, class_name="fried-rice", stems=["b", "a", "c"])
        dumped = cm.model_dump()
        assert dumped["stems"] == ["a", "b", "c"]

    def test_train_manifest_round_trip_via_json(self, tmp_path: Path) -> None:
        """TrainManifest는 JSON 직렬화 → 역직렬화 후 동일하다."""
        manifest = TrainManifest(
            seed=42,
            cap_per_class=500,
            classes=[
                ClassManifest(class_id=0, class_name="salad", stems=["s1", "s2"]),
                ClassManifest(class_id=1, class_name="mixed-rice-bowl", stems=["m1"]),
            ],
        )
        path = tmp_path / "manifest.json"
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

        loaded = TrainManifest.model_validate_json(path.read_text(encoding="utf-8"))
        assert loaded == manifest

    def test_train_manifest_rejects_duplicate_class_ids(self) -> None:
        """TrainManifest는 중복 class_id를 거부한다."""
        with pytest.raises(ValueError, match="duplicate"):
            TrainManifest(
                seed=42,
                cap_per_class=500,
                classes=[
                    ClassManifest(class_id=0, class_name="salad", stems=["s1"]),
                    ClassManifest(class_id=0, class_name="salad", stems=["s2"]),
                ],
            )
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py -v`

Expected: `ModuleNotFoundError: No module named 'scripts'` 또는 `scripts.data._manifest_models`.

- [ ] **Step 3: scripts 패키지 + 모델 구현**

`scripts/__init__.py` 빈 파일 생성 (이미 있으면 skip).
`scripts/data/__init__.py` 빈 파일 생성.

`scripts/data/_manifest_models.py` 생성:

```python
"""다운샘플 매니페스트 Pydantic v2 모델.

balanced_500 train 서브셋의 클래스별 선택 stem 목록을 직렬화/검증한다.

Reference:
    docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md §3.3
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ClassManifest(BaseModel):
    """한 클래스의 다운샘플 선택 결과."""

    model_config = ConfigDict(frozen=True)

    class_id: int = Field(ge=0, le=49, description="YOLO class id (0~49)")
    class_name: str = Field(min_length=1, description="클래스 이름")
    stems: list[str] = Field(description="선택된 파일 stem (확장자 제외, 정렬됨)")

    @field_validator("stems")
    @classmethod
    def _sort_stems(cls, value: list[str]) -> list[str]:
        """stems를 정렬된 리스트로 정규화한다."""
        return sorted(value)


class TrainManifest(BaseModel):
    """전체 train 서브셋 매니페스트."""

    model_config = ConfigDict(frozen=True)

    seed: int = Field(description="다운샘플에 사용한 random seed")
    cap_per_class: int = Field(gt=0, description="클래스당 상한 (예: 500)")
    classes: list[ClassManifest] = Field(description="50개 클래스의 선택 결과")

    @model_validator(mode="after")
    def _unique_class_ids(self) -> TrainManifest:
        """class_id 중복을 거부한다."""
        ids = [c.class_id for c in self.classes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate class_id in TrainManifest.classes")
        return self
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestManifestModels -v`

Expected: 3 passed.

- [ ] **Step 5: 커밋 (사용자 확인 후)**

사용자에게 묻고 OK시:

```powershell
git add scripts/__init__.py scripts/data/__init__.py scripts/data/_manifest_models.py backend/tests/unit/scripts/__init__.py backend/tests/unit/scripts/test_downsample_balanced.py
git status
git commit -m @'
data(data): balanced_500 매니페스트 Pydantic v2 모델 추가

ClassManifest/TrainManifest 정의 + 단위 테스트.
stems 자동 정렬, class_id 중복 거부, JSON round-trip 검증.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Task 2: 클래스 분포 분석 헬퍼

**Files:**
- Create: `scripts/data/_dataset_audit.py`
- Test: `backend/tests/unit/scripts/test_downsample_balanced.py` (TestDatasetAudit 클래스 추가)

**Why:** 원본 train 라벨에서 클래스별 stem 리스트를 뽑는 로직은 다운샘플 본 스크립트와 사전 분포 분석 양쪽에서 필요. 별도 헬퍼로 분리하면 테스트가 깔끔하고 단위 책임이 명확해짐.

- [ ] **Step 1: 단위 테스트 작성 (test 파일 끝에 추가)**

`backend/tests/unit/scripts/test_downsample_balanced.py` 에 클래스 추가:

```python
from scripts.data._dataset_audit import collect_stems_by_class


class TestDatasetAudit:
    """원본 라벨 디렉토리를 스캔해 클래스별 stem 맵을 만든다."""

    def _write_label(self, dir_path: Path, stem: str, lines: list[str]) -> None:
        (dir_path / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_collect_stems_groups_by_first_class_in_file(self, tmp_path: Path) -> None:
        """파일 안 첫 객체의 class_id로 stem이 묶인다."""
        labels = tmp_path / "labels"
        labels.mkdir()
        self._write_label(labels, "img_a", ["3 0.5 0.5 0.2 0.2"])
        self._write_label(labels, "img_b", ["3 0.1 0.1 0.1 0.1", "7 0.9 0.9 0.1 0.1"])
        self._write_label(labels, "img_c", ["7 0.2 0.2 0.1 0.1"])

        result = collect_stems_by_class(labels, num_classes=50)

        assert sorted(result[3]) == ["img_a", "img_b"]
        assert sorted(result[7]) == ["img_b", "img_c"]
        for cid in (0, 1, 2, 4, 5, 6, 8):
            assert result[cid] == []

    def test_collect_stems_ignores_blank_and_invalid_lines(self, tmp_path: Path) -> None:
        """빈 줄과 토큰 부족 줄은 무시한다."""
        labels = tmp_path / "labels"
        labels.mkdir()
        self._write_label(labels, "img_a", ["", "3 0.5 0.5 0.2 0.2", "   ", "bad"])

        result = collect_stems_by_class(labels, num_classes=50)
        assert result[3] == ["img_a"]

    def test_collect_stems_raises_on_out_of_range_class(self, tmp_path: Path) -> None:
        """num_classes 범위 밖 class_id는 명시 예외로 차단한다."""
        labels = tmp_path / "labels"
        labels.mkdir()
        self._write_label(labels, "img_a", ["77 0.5 0.5 0.2 0.2"])

        with pytest.raises(ValueError, match="class_id 77"):
            collect_stems_by_class(labels, num_classes=50)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestDatasetAudit -v`

Expected: `ImportError: cannot import name 'collect_stems_by_class'`.

- [ ] **Step 3: 구현 작성**

`scripts/data/_dataset_audit.py` 생성:

```python
"""원본 YOLO 라벨 디렉토리 분석 헬퍼.

다운샘플 스크립트와 분포 audit가 공통으로 사용한다.

Reference:
    docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md §3.4
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path


def collect_stems_by_class(labels_dir: Path, num_classes: int) -> dict[int, list[str]]:
    """라벨 디렉토리를 스캔해 클래스별 stem 목록을 만든다.

    한 라벨 파일에 여러 객체가 있어도 stem은 등장한 모든 class_id에 추가된다.
    빈 줄, 토큰 5개 미만, 첫 토큰이 정수가 아닌 줄은 무시한다.

    Args:
        labels_dir: YOLO 형식 .txt 라벨 파일이 들어있는 디렉토리.
        num_classes: 허용 class_id 상한 (0 <= id < num_classes).

    Returns:
        class_id → stem 리스트 (등장 순). 정렬은 호출자 책임.
        0..num_classes-1 모든 키가 포함되며, 없으면 빈 리스트.

    Raises:
        ValueError: 라벨에 num_classes 범위 밖 class_id가 발견된 경우.

    Examples:
        >>> result = collect_stems_by_class(Path("train/labels"), num_classes=50)
        >>> len(result[0])  # salad 클래스 stem 개수
        2547
    """
    result: dict[int, list[str]] = defaultdict(list)
    for txt in sorted(labels_dir.glob("*.txt")):
        seen_in_file: set[int] = set()
        for raw in txt.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            tokens = line.split()
            if len(tokens) < 5:
                continue
            try:
                cid = int(tokens[0])
            except ValueError:
                continue
            if not 0 <= cid < num_classes:
                raise ValueError(f"class_id {cid} out of range [0, {num_classes})")
            if cid in seen_in_file:
                continue
            seen_in_file.add(cid)
            result[cid].append(txt.stem)

    for cid in range(num_classes):
        result.setdefault(cid, [])
    return dict(result)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestDatasetAudit -v`

Expected: 3 passed.

- [ ] **Step 5: 전체 단위 테스트 회귀 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/ -v`

Expected: 6 passed (Task 1의 3개 + Task 2의 3개).

- [ ] **Step 6: 커밋 (사용자 확인 후)**

```powershell
git add scripts/data/_dataset_audit.py backend/tests/unit/scripts/test_downsample_balanced.py
git commit -m @'
data(data): 클래스별 stem 수집 헬퍼 추가

원본 YOLO 라벨 디렉토리를 스캔해 class_id 기준 stem 맵 생성.
빈 줄/이상 토큰 무시, 범위 밖 class_id 명시 예외.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Task 3: 다운샘플 핵심 함수 — 시드 고정 랜덤 샘플링

**Files:**
- Create: `scripts/data/downsample_balanced.py` (함수만, CLI 다음 task)
- Test: `backend/tests/unit/scripts/test_downsample_balanced.py` (TestSelectStemsPerClass 추가)

**Why:** spec §3.1 알고리즘의 결정론을 잠그는 가장 중요한 테스트. 같은 시드+입력이면 출력이 비트 단위로 같아야 한다.

- [ ] **Step 1: 단위 테스트 작성**

`backend/tests/unit/scripts/test_downsample_balanced.py` 에 추가:

```python
from scripts.data.downsample_balanced import select_stems_per_class


class TestSelectStemsPerClass:
    """spec §3.1: seed=42 고정 랜덤 샘플링."""

    def test_caps_at_500_when_class_has_more(self) -> None:
        """500장 초과 클래스는 정확히 500장으로 잘린다."""
        stems_by_class = {0: [f"img_{i:04d}" for i in range(1200)]}
        selected = select_stems_per_class(stems_by_class, cap_per_class=500, seed=42)
        assert len(selected[0]) == 500

    def test_keeps_all_when_class_below_cap(self) -> None:
        """500장 미만 클래스는 그대로 보존된다."""
        stems_by_class = {0: [f"img_{i:04d}" for i in range(123)]}
        selected = select_stems_per_class(stems_by_class, cap_per_class=500, seed=42)
        assert sorted(selected[0]) == sorted(stems_by_class[0])

    def test_deterministic_across_runs(self) -> None:
        """같은 seed+입력 → 같은 출력 (비트 동일)."""
        stems_by_class = {cid: [f"c{cid}_{i:05d}" for i in range(1500)] for cid in range(50)}
        first = select_stems_per_class(stems_by_class, cap_per_class=500, seed=42)
        second = select_stems_per_class(stems_by_class, cap_per_class=500, seed=42)
        for cid in range(50):
            assert first[cid] == second[cid]

    def test_different_seed_produces_different_selection(self) -> None:
        """seed가 다르면 선택이 달라진다 (랜덤성 sanity check)."""
        stems_by_class = {0: [f"img_{i:04d}" for i in range(1500)]}
        a = select_stems_per_class(stems_by_class, cap_per_class=500, seed=42)
        b = select_stems_per_class(stems_by_class, cap_per_class=500, seed=43)
        assert set(a[0]) != set(b[0])

    def test_input_order_does_not_affect_output(self) -> None:
        """입력 리스트 순서를 섞어도 같은 시드면 같은 결과 (sorted() 정규화)."""
        base = [f"img_{i:04d}" for i in range(1500)]
        sorted_input = {0: sorted(base)}
        shuffled_input = {0: list(reversed(base))}
        a = select_stems_per_class(sorted_input, cap_per_class=500, seed=42)
        b = select_stems_per_class(shuffled_input, cap_per_class=500, seed=42)
        assert sorted(a[0]) == sorted(b[0])
```

- [ ] **Step 2: 실패 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestSelectStemsPerClass -v`

Expected: ImportError on `select_stems_per_class`.

- [ ] **Step 3: 구현 작성**

`scripts/data/downsample_balanced.py` 생성 (CLI는 Task 4에서 추가):

```python
"""AI Hub YOLO 50 클래스 train 다운샘플링.

원본 train의 클래스당 이미지 수를 상한(기본 500)으로 자르고,
이미지+라벨을 새 폴더로 복사한다. val은 원본 전체를 복사한다.

샘플링은 spec §3.1대로 seed 고정 랜덤(random.sample on sorted stems).

Reference:
    docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md
"""

from __future__ import annotations

import random


def select_stems_per_class(
    stems_by_class: dict[int, list[str]],
    cap_per_class: int,
    seed: int,
) -> dict[int, list[str]]:
    """클래스별로 시드 고정 랜덤 샘플링을 적용한다.

    클래스의 원본 개수가 cap_per_class 초과면 cap만큼 sample,
    이하면 전체를 그대로 유지한다. 결과는 정렬된 stem 리스트로 반환한다.

    재현성: 같은 seed + 같은 입력(stems_by_class의 각 리스트가 동일 set)이면
    출력이 비트 단위로 동일하다. 입력 순서는 sorted()로 정규화하므로 무관.

    Args:
        stems_by_class: class_id → 원본 stem 리스트.
        cap_per_class: 클래스당 상한.
        seed: random.seed에 사용할 정수.

    Returns:
        class_id → 선택된 stem 리스트 (정렬됨). 입력의 모든 키 보존.

    Examples:
        >>> result = select_stems_per_class({0: ["a", "b", "c", "d"]}, cap_per_class=2, seed=42)
        >>> len(result[0])
        2
    """
    rng = random.Random(seed)
    output: dict[int, list[str]] = {}
    for cid in sorted(stems_by_class.keys()):
        canonical = sorted(stems_by_class[cid])
        if len(canonical) <= cap_per_class:
            output[cid] = list(canonical)
        else:
            picked = rng.sample(canonical, cap_per_class)
            output[cid] = sorted(picked)
    return output
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestSelectStemsPerClass -v`

Expected: 5 passed.

- [ ] **Step 5: 전체 회귀**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/ -v`

Expected: 11 passed.

- [ ] **Step 6: 커밋 (사용자 확인 후)**

```powershell
git add scripts/data/downsample_balanced.py backend/tests/unit/scripts/test_downsample_balanced.py
git commit -m @'
data(data): 시드 고정 랜덤 다운샘플 핵심 함수 추가

select_stems_per_class: cap 초과 클래스만 random.sample, seed 고정으로 재현성 보장.
입력 순서 무관(sorted 정규화), 5개 단위 테스트로 결정론 잠금.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Task 4: 파일 복사 + data.yaml 작성 함수

**Files:**
- Modify: `scripts/data/downsample_balanced.py`
- Modify: `backend/tests/unit/scripts/test_downsample_balanced.py` (TestCopyAndYaml 추가)

**Why:** 선택된 stem을 원본 → 새 폴더로 옮기고 data.yaml을 새로 쓰는 로직. tmp_path 위에서 실제 파일 I/O를 테스트해 회귀 방지.

- [ ] **Step 1: 단위 테스트 작성**

`backend/tests/unit/scripts/test_downsample_balanced.py` 에 추가:

```python
from scripts.data.downsample_balanced import (
    copy_selected_pairs,
    copy_full_split,
    write_dataset_yaml,
)


class TestCopyAndYaml:
    """파일 복사와 data.yaml 작성."""

    def _make_pair(self, root: Path, stem: str) -> None:
        (root / "images").mkdir(parents=True, exist_ok=True)
        (root / "labels").mkdir(parents=True, exist_ok=True)
        (root / "images" / f"{stem}.jpg").write_bytes(b"\xff\xd8\xff\xe0 fake jpg")
        (root / "labels" / f"{stem}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    def test_copy_selected_pairs_copies_only_listed_stems(self, tmp_path: Path) -> None:
        """선택된 stem만 새 train으로 복사한다."""
        src = tmp_path / "src" / "train"
        for s in ("a", "b", "c", "d"):
            self._make_pair(src, s)
        dst = tmp_path / "dst" / "train"

        copied = copy_selected_pairs(src, dst, selected_stems=["a", "c"])

        assert copied == 2
        assert sorted(p.stem for p in (dst / "images").glob("*.jpg")) == ["a", "c"]
        assert sorted(p.stem for p in (dst / "labels").glob("*.txt")) == ["a", "c"]

    def test_copy_selected_pairs_raises_on_missing_image(self, tmp_path: Path) -> None:
        """라벨은 있는데 이미지가 없으면 즉시 실패한다."""
        src = tmp_path / "src" / "train"
        (src / "labels").mkdir(parents=True)
        (src / "labels" / "ghost.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        (src / "images").mkdir()
        dst = tmp_path / "dst" / "train"

        with pytest.raises(FileNotFoundError, match="ghost.jpg"):
            copy_selected_pairs(src, dst, selected_stems=["ghost"])

    def test_copy_full_split_copies_all_pairs(self, tmp_path: Path) -> None:
        """val 전체 복사."""
        src = tmp_path / "src" / "val"
        for s in ("v1", "v2", "v3"):
            self._make_pair(src, s)
        dst = tmp_path / "dst" / "val"

        copied = copy_full_split(src, dst)

        assert copied == 3
        assert sorted(p.stem for p in (dst / "images").glob("*.jpg")) == ["v1", "v2", "v3"]

    def test_write_dataset_yaml_contains_path_and_names(self, tmp_path: Path) -> None:
        """data.yaml에 path, train, val, nc, names가 정확히 기록된다."""
        dst = tmp_path / "balanced_500"
        dst.mkdir()
        names = ["salad", "mixed-rice-bowl", "rice-bowl"]

        yaml_path = write_dataset_yaml(dst, names=names)

        content = yaml_path.read_text(encoding="utf-8")
        assert f"path: {dst.as_posix()}" in content
        assert "train: train/images" in content
        assert "val: val/images" in content
        assert "nc: 3" in content
        assert "- salad" in content
        assert "- mixed-rice-bowl" in content
```

- [ ] **Step 2: 실패 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestCopyAndYaml -v`

Expected: ImportError on the three new symbols.

- [ ] **Step 3: 구현 추가 (downsample_balanced.py 끝에)**

`scripts/data/downsample_balanced.py` 끝에 다음을 추가:

```python
import shutil
from pathlib import Path


def copy_selected_pairs(src_split: Path, dst_split: Path, selected_stems: list[str]) -> int:
    """src의 images/labels에서 stem 짝을 dst로 복사한다.

    Args:
        src_split: 원본 split 루트 (예: aihub_yolo_50/train).
        dst_split: 대상 split 루트 (예: aihub_yolo_50_balanced_500/train).
        selected_stems: 복사할 파일 stem 리스트 (확장자 제외).

    Returns:
        복사된 짝 개수.

    Raises:
        FileNotFoundError: stem의 jpg가 src에 없는 경우.
    """
    (dst_split / "images").mkdir(parents=True, exist_ok=True)
    (dst_split / "labels").mkdir(parents=True, exist_ok=True)

    count = 0
    for stem in selected_stems:
        src_img = src_split / "images" / f"{stem}.jpg"
        src_lbl = src_split / "labels" / f"{stem}.txt"
        if not src_img.exists():
            raise FileNotFoundError(f"missing image: {src_img.name}")
        shutil.copy2(src_img, dst_split / "images" / src_img.name)
        shutil.copy2(src_lbl, dst_split / "labels" / src_lbl.name)
        count += 1
    return count


def copy_full_split(src_split: Path, dst_split: Path) -> int:
    """split 전체(images + labels)를 dst로 복사한다.

    val을 다운샘플 없이 전체 그대로 옮길 때 사용한다.

    Args:
        src_split: 원본 split 루트.
        dst_split: 대상 split 루트.

    Returns:
        복사된 이미지 개수.
    """
    stems = sorted(p.stem for p in (src_split / "images").glob("*.jpg"))
    return copy_selected_pairs(src_split, dst_split, selected_stems=stems)


def write_dataset_yaml(dst_root: Path, names: list[str]) -> Path:
    """다운샘플 결과 폴더에 data.yaml을 작성한다.

    Args:
        dst_root: aihub_yolo_50_balanced_500 폴더 절대 경로.
        names: 클래스 이름 리스트 (순서 = class_id).

    Returns:
        생성된 data.yaml 경로.
    """
    yaml_path = dst_root / "data.yaml"
    lines = [
        "# YOLO dataset config - balanced_500 subset (train downsampled to <=500/class)",
        f"path: {dst_root.as_posix()}",
        "train: train/images",
        "val: val/images",
        "",
        f"nc: {len(names)}",
        "names:",
        *[f"  - {n}" for n in names],
        "",
    ]
    yaml_path.write_text("\n".join(lines), encoding="utf-8")
    return yaml_path
```

- [ ] **Step 4: 테스트 통과**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestCopyAndYaml -v`

Expected: 4 passed.

- [ ] **Step 5: 회귀 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/ -v`

Expected: 15 passed.

- [ ] **Step 6: 커밋 (사용자 확인 후)**

```powershell
git add scripts/data/downsample_balanced.py backend/tests/unit/scripts/test_downsample_balanced.py
git commit -m @'
data(data): 파일 복사 + data.yaml 작성 함수 추가

copy_selected_pairs / copy_full_split / write_dataset_yaml.
이미지 없는 stem 즉시 예외, data.yaml은 새 폴더 절대 경로 박음.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Task 5: CLI 엔트리 + 매니페스트/분포 CSV 출력

**Files:**
- Modify: `scripts/data/downsample_balanced.py` (argparse main 추가)
- Modify: `backend/tests/unit/scripts/test_downsample_balanced.py` (TestCli 추가)

**Why:** 사용자가 한 줄로 `python -m scripts.data.downsample_balanced ...` 호출할 수 있어야 한다. 매니페스트 JSON과 분포 CSV 2개도 함께 산출.

- [ ] **Step 1: 단위 테스트 작성 — main을 함수로 호출**

`backend/tests/unit/scripts/test_downsample_balanced.py` 에 추가:

```python
from scripts.data.downsample_balanced import run_downsample


class TestRunDownsample:
    """run_downsample 전체 파이프라인 (소형 데이터셋으로)."""

    def _make_dataset(self, root: Path, train_counts: dict[int, int], val_count: int) -> None:
        """class_id → 개수 dict 로 가짜 train을 만들고 val은 단일 클래스로 채운다."""
        (root / "train" / "images").mkdir(parents=True)
        (root / "train" / "labels").mkdir(parents=True)
        (root / "val" / "images").mkdir(parents=True)
        (root / "val" / "labels").mkdir(parents=True)

        for cid, n in train_counts.items():
            for i in range(n):
                stem = f"t_c{cid}_{i:04d}"
                (root / "train" / "images" / f"{stem}.jpg").write_bytes(b"\xff\xd8")
                (root / "train" / "labels" / f"{stem}.txt").write_text(
                    f"{cid} 0.5 0.5 0.2 0.2\n", encoding="utf-8"
                )
        for i in range(val_count):
            stem = f"v_{i:04d}"
            (root / "val" / "images" / f"{stem}.jpg").write_bytes(b"\xff\xd8")
            (root / "val" / "labels" / f"{stem}.txt").write_text(
                "0 0.5 0.5 0.2 0.2\n", encoding="utf-8"
            )

    def test_run_downsample_caps_train_keeps_val(self, tmp_path: Path) -> None:
        """train은 cap 적용, val은 무변경."""
        src = tmp_path / "src"
        # class 0 = 800장 (cap 적용), class 1 = 50장 (보존)
        self._make_dataset(src, train_counts={0: 800, 1: 50}, val_count=30)
        dst = tmp_path / "dst_balanced"
        names = ["cls_zero", "cls_one"]

        result = run_downsample(
            src_root=src,
            dst_root=dst,
            class_names=names,
            cap_per_class=500,
            seed=42,
        )

        assert result.train_copied == 550  # 500 + 50
        assert result.val_copied == 30

        assert len(list((dst / "train" / "images").glob("*.jpg"))) == 550
        assert len(list((dst / "val" / "images").glob("*.jpg"))) == 30
        assert (dst / "data.yaml").exists()
        assert (dst / "_manifest" / "train_manifest.json").exists()
        assert (dst / "_manifest" / "class_counts_original.csv").exists()
        assert (dst / "_manifest" / "class_counts_balanced.csv").exists()

    def test_run_downsample_is_deterministic(self, tmp_path: Path) -> None:
        """두 번 돌렸을 때 매니페스트가 비트 동일."""
        src = tmp_path / "src"
        self._make_dataset(src, train_counts={0: 800, 1: 700}, val_count=10)
        names = ["cls_zero", "cls_one"]

        dst_a = tmp_path / "dst_a"
        dst_b = tmp_path / "dst_b"
        run_downsample(src, dst_a, names, cap_per_class=500, seed=42)
        run_downsample(src, dst_b, names, cap_per_class=500, seed=42)

        manifest_a = (dst_a / "_manifest" / "train_manifest.json").read_text(encoding="utf-8")
        manifest_b = (dst_b / "_manifest" / "train_manifest.json").read_text(encoding="utf-8")
        assert manifest_a == manifest_b
```

- [ ] **Step 2: 실패 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestRunDownsample -v`

Expected: ImportError on `run_downsample`.

- [ ] **Step 3: 구현 추가 (downsample_balanced.py 끝)**

`scripts/data/downsample_balanced.py` 끝에 추가:

```python
import argparse
import csv
import sys
from dataclasses import dataclass

from scripts.data._dataset_audit import collect_stems_by_class
from scripts.data._manifest_models import ClassManifest, TrainManifest


@dataclass(frozen=True)
class DownsampleResult:
    """run_downsample 결과 요약."""

    train_copied: int
    val_copied: int
    manifest_path: Path


def _write_class_counts_csv(path: Path, counts: dict[int, int], names: list[str]) -> None:
    """class_id, class_name, count 3-열 CSV로 분포를 기록한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["class_id", "class_name", "count"])
        for cid in sorted(counts.keys()):
            writer.writerow([cid, names[cid], counts[cid]])


def run_downsample(
    src_root: Path,
    dst_root: Path,
    class_names: list[str],
    cap_per_class: int,
    seed: int,
) -> DownsampleResult:
    """다운샘플 파이프라인 전체를 실행한다.

    1) 원본 train 라벨 스캔 → 클래스별 stem 맵
    2) seed 고정 랜덤 샘플링으로 클래스당 cap 적용
    3) 선택된 train 짝과 val 전체를 dst로 복사
    4) data.yaml + 매니페스트 JSON + 분포 CSV 2개 작성

    Args:
        src_root: 원본 데이터셋 루트 (aihub_yolo_50).
        dst_root: 대상 데이터셋 루트 (없으면 생성).
        class_names: 클래스 이름 리스트 (순서 = class_id).
        cap_per_class: 클래스당 상한.
        seed: random seed.

    Returns:
        DownsampleResult (train/val 복사 개수, 매니페스트 경로).

    Raises:
        FileNotFoundError: 라벨에 짝꿍 이미지가 없는 경우.
        ValueError: 라벨에 범위 밖 class_id가 있는 경우.
    """
    num_classes = len(class_names)
    src_train_labels = src_root / "train" / "labels"

    stems_by_class = collect_stems_by_class(src_train_labels, num_classes=num_classes)
    original_counts = {cid: len(stems) for cid, stems in stems_by_class.items()}

    selected = select_stems_per_class(stems_by_class, cap_per_class=cap_per_class, seed=seed)
    balanced_counts = {cid: len(stems) for cid, stems in selected.items()}

    flat_selected: list[str] = []
    for cid in sorted(selected.keys()):
        flat_selected.extend(selected[cid])

    train_copied = copy_selected_pairs(
        src_root / "train", dst_root / "train", selected_stems=flat_selected
    )
    val_copied = copy_full_split(src_root / "val", dst_root / "val")

    write_dataset_yaml(dst_root, names=class_names)

    manifest = TrainManifest(
        seed=seed,
        cap_per_class=cap_per_class,
        classes=[
            ClassManifest(class_id=cid, class_name=class_names[cid], stems=selected[cid])
            for cid in sorted(selected.keys())
        ],
    )
    manifest_path = dst_root / "_manifest" / "train_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    _write_class_counts_csv(
        dst_root / "_manifest" / "class_counts_original.csv", original_counts, class_names
    )
    _write_class_counts_csv(
        dst_root / "_manifest" / "class_counts_balanced.csv", balanced_counts, class_names
    )

    return DownsampleResult(
        train_copied=train_copied, val_copied=val_copied, manifest_path=manifest_path
    )


def _load_class_names_from_yaml(yaml_path: Path) -> list[str]:
    """원본 data.yaml에서 'names:' 블록을 읽는다.

    PyYAML 없이 단순 파싱: '- ' 접두사 라인을 클래스로 본다.
    """
    names: list[str] = []
    in_names = False
    for raw in yaml_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("names:"):
            in_names = True
            continue
        if in_names:
            stripped = line.lstrip()
            if stripped.startswith("- "):
                names.append(stripped[2:].strip())
            elif line and not line.startswith(" "):
                break
    return names


def _main(argv: list[str] | None = None) -> int:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="AI Hub YOLO 50 train 다운샘플 (클래스당 상한 적용)"
    )
    parser.add_argument("--src", type=Path, required=True, help="원본 데이터셋 루트")
    parser.add_argument("--dst", type=Path, required=True, help="대상 데이터셋 루트")
    parser.add_argument("--cap", type=int, default=500, help="클래스당 상한 (기본 500)")
    parser.add_argument("--seed", type=int, default=42, help="random seed (기본 42)")
    args = parser.parse_args(argv)

    src_yaml = args.src / "data.yaml"
    names = _load_class_names_from_yaml(src_yaml)
    if not names:
        print(f"ERROR: failed to load class names from {src_yaml}", file=sys.stderr)
        return 2

    result = run_downsample(
        src_root=args.src,
        dst_root=args.dst,
        class_names=names,
        cap_per_class=args.cap,
        seed=args.seed,
    )
    print(f"train_copied={result.train_copied} val_copied={result.val_copied}")
    print(f"manifest={result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd <local-pc2-repo>\backend && .venv\Scripts\python -m pytest tests/unit/scripts/test_downsample_balanced.py::TestRunDownsample -v`

Expected: 2 passed.

- [ ] **Step 5: 전체 회귀 + lint/type**

```powershell
cd <local-pc2-repo>\backend
.venv\Scripts\python -m pytest tests/unit/scripts/ -v
cd <local-pc2-repo>
backend\.venv\Scripts\python -m black scripts --line-length=100
backend\.venv\Scripts\python -m ruff check scripts --fix
backend\.venv\Scripts\python -m mypy scripts --strict
```

Expected: 17 passed, black/ruff/mypy 모두 깨끗.

- [ ] **Step 6: 커밋 (사용자 확인 후)**

```powershell
git add scripts/data/downsample_balanced.py backend/tests/unit/scripts/test_downsample_balanced.py
git commit -m @'
data(data): 다운샘플 CLI 엔트리 + 매니페스트/분포 CSV 출력 추가

run_downsample: 스캔→샘플→복사→data.yaml→매니페스트JSON→CSV2개.
__main__으로 python -m scripts.data.downsample_balanced 호출 가능.
원본·다운샘플 결과 모두 결정론적으로 동일하게 재생성됨.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Task 6: 원본 분포 사전 분석 (audit)

**Files:**
- Modify: 없음 — 기존 `scripts/data/_dataset_audit.py` + CLI 한 줄로 실행
- Output: `data/food_images/aihub_yolo_50/_audit/class_counts.csv` (gitignored 영역)

**Why:** 본 다운샘플 실행 전, 사용자 가정(하위 15개 100~650, 중앙값 370)이 실제 데이터와 일치하는지 검증.

- [ ] **Step 1: 일회성 audit 스크립트 실행**

```powershell
cd <local-pc2-repo>
backend\.venv\Scripts\python -c @'
from pathlib import Path
import csv
from scripts.data._dataset_audit import collect_stems_by_class
from scripts.data.downsample_balanced import _load_class_names_from_yaml

src = Path("data/food_images/aihub_yolo_50")
names = _load_class_names_from_yaml(src / "data.yaml")
result = collect_stems_by_class(src / "train" / "labels", num_classes=len(names))

out = src / "_audit" / "class_counts.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["class_id", "class_name", "count"])
    for cid in sorted(result.keys()):
        w.writerow([cid, names[cid], len(result[cid])])
print(f"wrote {out}")

counts = sorted(len(v) for v in result.values())
print(f"min={counts[0]} q1={counts[12]} median={counts[25]} q3={counts[37]} max={counts[-1]}")
print(f"below_500: {sum(1 for c in counts if c < 500)} of 50")
'@
```

Expected: `wrote .../_audit/class_counts.csv` + 통계 5수치 + below_500 개수.

- [ ] **Step 2: 결과 확인 (사용자 가정과 비교)**

```powershell
Get-Content <local-pc2-repo>\data\food_images\aihub_yolo_50\_audit\class_counts.csv | Sort-Object { [int]($_.Split(",")[2]) } 2>$null | Select-Object -First 17
```

기대: 하위 15개 클래스의 count가 100~650 범위. 어긋나면 사용자 보고 후 cap 값 재검토.

- [ ] **Step 3: 커밋 없음 (audit CSV는 data/ 하위라 .gitignore 적용됨)**

---

## Task 7: 다운샘플 실행

**Files:**
- Output: `data/food_images/aihub_yolo_50_balanced_500/**` (gitignored 영역)

**Why:** 본 다운샘플 산출물 생성. 약 23K 짝 복사로 SSD에서 30~60분 예상.

- [ ] **Step 1: 다운샘플 실행**

```powershell
cd <local-pc2-repo>
backend\.venv\Scripts\python -m scripts.data.downsample_balanced `
  --src <local-pc2-repo>\data\food_images\aihub_yolo_50 `
  --dst <local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500 `
  --cap 500 `
  --seed 42
```

Expected stdout 마지막 두 줄:
```
train_copied=<약 23000> val_copied=13780
manifest=...\_manifest\train_manifest.json
```

- [ ] **Step 2: 검증 (spec §3.5 체크리스트)**

```powershell
$dst = "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500"
$ti = (Get-ChildItem "$dst\train\images" -Filter *.jpg).Count
$tl = (Get-ChildItem "$dst\train\labels" -Filter *.txt).Count
$vi = (Get-ChildItem "$dst\val\images" -Filter *.jpg).Count
$vl = (Get-ChildItem "$dst\val\labels" -Filter *.txt).Count
Write-Host "train images=$ti labels=$tl  val images=$vi labels=$vl"
Get-Content "$dst\_manifest\class_counts_balanced.csv" | Select-Object -First 5
Get-Content "$dst\data.yaml" | Select-Object -First 5
```

기대:
- `train images == train labels` (둘 다 동일, 약 23,030)
- `val images == val labels == 13780`
- balanced CSV의 count 컬럼은 모두 ≤ 500
- data.yaml의 `path:` 가 새 폴더 절대 경로

- [ ] **Step 3: 재현성 셀프 체크 (선택, 권장)**

```powershell
backend\.venv\Scripts\python -m scripts.data.downsample_balanced `
  --src <local-pc2-repo>\data\food_images\aihub_yolo_50 `
  --dst <local-pc2-repo>\data\food_images\_repro_check `
  --cap 500 `
  --seed 42

fc.exe `
  "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500\_manifest\train_manifest.json" `
  "<local-pc2-repo>\data\food_images\_repro_check\_manifest\train_manifest.json"
```

Expected: `FC: no differences encountered`.

확인 후 `_repro_check` 폴더는 `data/food_images/_archive/` 로 이동:

```powershell
$archive = "<local-pc2-repo>\data\food_images\_archive"
New-Item -ItemType Directory -Force -Path $archive | Out-Null
Move-Item "<local-pc2-repo>\data\food_images\_repro_check" "$archive\_repro_check_20260527"
```

- [ ] **Step 4: 커밋 없음 (`data/food_images/`는 .gitignore 적용됨)**

---

## Task 8: 학습 ps1 래퍼 작성

**Files:**
- Create: `docs/superpowers/plans/yolo11s_balanced500_run.ps1`

**Why:** 기존 baseline_run.ps1 패턴(사전 점검 + labels.cache archive + train)을 yolo11s + balanced_500용으로 재작성. 사용자가 별도 PowerShell에서 직접 실행.

- [ ] **Step 1: ps1 작성**

`docs/superpowers/plans/yolo11s_balanced500_run.ps1` 생성:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# PC2 YOLO11s + balanced_500 학습
# exp03_yolo11s_balanced500_pc2_b<BATCH>_w8_cache_disk_det_true
# 사전: docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md

param(
    [int]$Batch = 32,
    [int]$Epochs = 50,
    [string]$RunName = "exp03_yolo11s_balanced500_pc2"
)

$yolo       = "<local-pc2-repo>\backend\.venv\Scripts\yolo.exe"
$venvPython = "<local-pc2-repo>\backend\.venv\Scripts\python.exe"
$dataYaml   = "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500\data.yaml"
$project    = "<local-pc2-repo>\runs\food_yolo"
$fullName   = "$RunName" + "_b$Batch" + "_w8_cache_disk_det_true"
$trainCache = "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500\train\labels.cache"
$valCache   = "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500\val\labels.cache"

Write-Host ""
Write-Host "=== 사전 점검 ===" -ForegroundColor Cyan

if (-not (Test-Path $yolo)) {
    Write-Host "ERROR: yolo.exe 없음" -ForegroundColor Red; exit 1
}
Write-Host "OK: yolo.exe 존재" -ForegroundColor Green

if (-not (Test-Path $dataYaml)) {
    Write-Host "ERROR: data.yaml 없음 -> $dataYaml" -ForegroundColor Red
    Write-Host "       Task 7의 다운샘플 실행을 먼저 끝내세요." -ForegroundColor Yellow
    exit 1
}
Write-Host "OK: data.yaml 존재" -ForegroundColor Green

New-Item -ItemType Directory -Force -Path $project | Out-Null
Write-Host "OK: project 폴더 준비 ($project)" -ForegroundColor Green

Write-Host ""
Write-Host "=== data.yaml (앞 4줄) ===" -ForegroundColor Cyan
Get-Content $dataYaml -TotalCount 4

Write-Host ""
Write-Host "=== labels.cache 점검 ===" -ForegroundColor Cyan
$archive = "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500\_archive_cache"
$cacheFound = $false
foreach ($c in @($trainCache, $valCache)) {
    if (Test-Path $c) {
        $cacheFound = $true
        New-Item -ItemType Directory -Force -Path $archive | Out-Null
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $destName = "$($c.Split('\')[-2])_labels.cache.$stamp"
        Move-Item $c (Join-Path $archive $destName) -Force
        Write-Host "MOVED: $c -> $archive\$destName" -ForegroundColor Yellow
    }
}
if (-not $cacheFound) {
    Write-Host "OK: labels.cache 없음 -> fresh scan" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 데이터셋 파일 개수 ===" -ForegroundColor Cyan
$dst = "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500"
foreach ($s in @('train\images','train\labels','val\images','val\labels')) {
    $p = Join-Path $dst $s
    $cnt = (Get-ChildItem $p -File -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host "  $s : $cnt files"
}

Write-Host ""
Write-Host "=== GPU ===" -ForegroundColor Cyan
nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits

Write-Host ""
Write-Host "=== PyTorch CUDA ===" -ForegroundColor Cyan
& $venvPython -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

Write-Host ""
Write-Host "=== C 드라이브 여유 ===" -ForegroundColor Cyan
$c = Get-PSDrive C
"$([math]::Round($c.Free/1GB,1)) GB"

Write-Host ""
Write-Host "=== YOLO11s + balanced_500 학습 시작 ===" -ForegroundColor Cyan
Write-Host "name:   $fullName" -ForegroundColor White
Write-Host "model:  yolo11s.pt | batch: $Batch | epochs: $Epochs | imgsz: 640 | workers: 8 | cache: disk" -ForegroundColor White
Write-Host ""

& $yolo detect train `
    model=yolo11s.pt `
    data="$dataYaml" `
    epochs=$Epochs `
    imgsz=640 `
    batch=$Batch `
    workers=8 `
    cache=disk `
    device=0 `
    seed=42 `
    deterministic=true `
    patience=15 `
    plots=false `
    project="$project" `
    name=$fullName
```

- [ ] **Step 2: 문법 확인 (실행은 X)**

```powershell
powershell -NoProfile -Command "& { . { Get-Command -Syntax (Get-Item '<local-pc2-repo>\docs\superpowers\plans\yolo11s_balanced500_run.ps1').FullName } }" 2>&1 | Select-Object -First 5
```

또는 단순히:
```powershell
Get-Content <local-pc2-repo>\docs\superpowers\plans\yolo11s_balanced500_run.ps1 | Select-Object -First 5
```

Expected: 첫 5줄 출력, 파일 정상 생성 확인.

- [ ] **Step 3: 커밋 (사용자 확인 후)**

```powershell
git add docs/superpowers/plans/yolo11s_balanced500_run.ps1
git commit -m @'
data(data): yolo11s + balanced_500 학습 ps1 래퍼 추가

사전 점검(yolo.exe/data.yaml/GPU/CUDA/디스크)
+ labels.cache 자동 archive
+ yolo detect train 실행 (batch/epochs 파라미터화).
spec §4.2 본 학습 설정 그대로.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Task 9: OOM dry-run

**Files:**
- Output: `runs/food_yolo/_dryrun_yolo11s_b32/` (실험 후 `_archive/`로 이동)

**Why:** spec §4.1. 본 학습 25시간 전에 batch=32가 8GB VRAM에 들어가는지 10분 안에 확인.

- [ ] **Step 1: dry-run 실행 (사용자가 별도 PowerShell에서)**

사용자에게 안내:

```powershell
cd <local-pc2-repo>
$yolo = "backend\.venv\Scripts\yolo.exe"
$dataYaml = "data\food_images\aihub_yolo_50_balanced_500\data.yaml"
$project = "runs\food_yolo"

& $yolo detect train `
    model=yolo11s.pt `
    data="$dataYaml" `
    epochs=1 `
    imgsz=640 `
    batch=32 `
    workers=8 `
    cache=disk `
    device=0 `
    seed=42 `
    deterministic=true `
    plots=false `
    fraction=0.005 `
    project="$project" `
    name=_dryrun_yolo11s_b32
```

기대 (성공): 1 epoch이 시작되어 학습 step이 진행되다 종료. OOM 없음. GPU 메모리 < 7.5 GB.

- [ ] **Step 2: 결과 판정**

`runs/food_yolo/_dryrun_yolo11s_b32/` 에 `results.csv`와 `weights/last.pt`가 생기면 성공.

OOM 발생 시 `torch.cuda.OutOfMemoryError`가 stderr에 출력. 이 경우 batch=16으로 같은 명령 재시도. 16도 실패면 batch=12.

- [ ] **Step 3: dry-run 폴더 archive로 이동**

```powershell
$archive = "<local-pc2-repo>\runs\food_yolo\_archive"
New-Item -ItemType Directory -Force -Path $archive | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Move-Item "<local-pc2-repo>\runs\food_yolo\_dryrun_yolo11s_b32" "$archive\_dryrun_yolo11s_b32_$stamp"
```

(CLAUDE.md "삭제 대신 이동" 규칙 준수.)

- [ ] **Step 4: 확정된 batch 값 plan에 기록**

`docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md` 의 진행 중 섹션에 한 줄 추가:

```
- [x] dry-run: batch=<32 또는 16> 통과 (YYYY-MM-DD HH:MM)
```

커밋:

```powershell
git add docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md
git commit -m @'
docs(data): 2026-05-27 yolo11s batch dry-run 결과 기록

batch=<N> 통과 확인, 본 학습 설정 확정.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Task 10: 본 학습 실행

**Files:**
- Output: `runs/food_yolo/exp03_yolo11s_balanced500_pc2_b<N>_w8_cache_disk_det_true/` (gitignore 영역 외 — 결과 커밋 별도 결정)

**Why:** 본 작업. 약 25시간 (batch=32 기준). 사용자가 별도 PowerShell에서 직접 실행해 Claude Code 세션과 분리(spec §7 위험 완화).

- [ ] **Step 1: 사용자에게 실행 명령 전달**

```powershell
cd <local-pc2-repo>
.\docs\superpowers\plans\yolo11s_balanced500_run.ps1 -Batch <dry-run에서 통과한 값>
```

기본값은 `-Batch 32`. dry-run에서 batch=16으로 떨어졌으면 `-Batch 16`.

기대: 사전 점검 7개 섹션 모두 OK → 학습 시작. 50 epoch 진행, results.csv가 매 epoch 갱신.

- [ ] **Step 2: 모니터링 명령 안내 (참고용)**

학습 중 다른 PowerShell에서:

```powershell
# results.csv 마지막 줄
Get-Content <local-pc2-repo>\runs\food_yolo\exp03_yolo11s_balanced500_pc2_*\results.csv -Tail 1

# GPU 상태
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader

# 가중치 파일
Get-ChildItem <local-pc2-repo>\runs\food_yolo\exp03_yolo11s_balanced500_pc2_*\weights\
```

- [ ] **Step 3: 학습 완료 후 plan 업데이트**

`docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md` 에 완료 기록 + 본 학습 결과 (mAP50/mAP50-95, 소요 시간) 한 줄.

- [ ] **Step 4: 커밋 (사용자 확인 후)**

```powershell
git add docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md
git commit -m @'
data(data): exp03 yolo11s balanced_500 PC2 학습 완료 기록

mAP50=<X> mAP50-95=<Y>, 소요 약 <Z>시간, batch=<N>.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

results.csv, args.yaml 등의 학습 산출물은 별도 PR로 묶을지 사용자와 의논 (PC1 exp01 결과 커밋 패턴 c1a2fb2 참고).

---

## Task 11: Validation plots + 클래스별 분석

**Files:**
- Create: `docs/superpowers/plans/yolo11s_balanced500_val.ps1`
- Output: `runs/food_yolo/exp03_yolo11s_balanced500_pc2_val/` (별도 폴더)

**Why:** spec §5.1. best.pt로 validation을 한 번 더 돌려 plots + class별 metric 산출. handoff §16 패턴.

- [ ] **Step 1: validation ps1 작성**

`docs/superpowers/plans/yolo11s_balanced500_val.ps1` 생성:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

param(
    [Parameter(Mandatory=$true)]
    [string]$RunDir
)

$yolo     = "<local-pc2-repo>\backend\.venv\Scripts\yolo.exe"
$dataYaml = "<local-pc2-repo>\data\food_images\aihub_yolo_50_balanced_500\data.yaml"
$project  = "<local-pc2-repo>\runs\food_yolo"
$bestPt   = Join-Path $RunDir "weights\best.pt"

if (-not (Test-Path $bestPt)) {
    Write-Host "ERROR: best.pt 없음 -> $bestPt" -ForegroundColor Red; exit 1
}

$valName = (Split-Path $RunDir -Leaf) + "_val"
Write-Host "Validation run: $valName" -ForegroundColor Cyan

& $yolo detect val `
    model="$bestPt" `
    data="$dataYaml" `
    imgsz=640 `
    device=0 `
    plots=true `
    save_json=true `
    project="$project" `
    name=$valName
```

- [ ] **Step 2: validation 실행 (사용자가 별도 PowerShell에서)**

```powershell
cd <local-pc2-repo>
.\docs\superpowers\plans\yolo11s_balanced500_val.ps1 `
  -RunDir <local-pc2-repo>\runs\food_yolo\exp03_yolo11s_balanced500_pc2_b<N>_w8_cache_disk_det_true
```

Expected (약 30분): confusion_matrix.png, PR_curve.png, F1_curve.png, R_curve.png, P_curve.png, predictions.json, results.json 생성.

- [ ] **Step 3: 약한 클래스 식별**

```powershell
$valDir = "<local-pc2-repo>\runs\food_yolo\exp03_yolo11s_balanced500_pc2_b<N>_w8_cache_disk_det_true_val"
Get-Content "$valDir\results.json" | ConvertFrom-Json | Select-Object -First 1 | Format-List
```

또는 ultralytics가 stdout에 출력한 클래스별 metric 표를 plan에 기록.

- [ ] **Step 4: ps1 커밋 (사용자 확인 후)**

```powershell
git add docs/superpowers/plans/yolo11s_balanced500_val.ps1
git commit -m @'
data(data): yolo11s balanced_500 validation ps1 추가

best.pt 기준 plots=true + save_json=true로 confusion matrix·PR·F1 곡선과
predictions.json·results.json 산출. handoff §16 패턴.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

- [ ] **Step 5: 약한 클래스 5~10개를 plan에 기록**

`docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md` 끝에 "다음 작업" 섹션 갱신:

```markdown
## yolo11s balanced_500 validation 결과 (2026-MM-DD)
- 전체 mAP50: <X> | mAP50-95: <Y>
- 약한 클래스 (AP50 < 0.6):
  - <class_name> (<class_id>) AP50=<v> AP50-95=<v>
  - ...
- 강한 클래스 top 5: ...
```

커밋:

```powershell
git add docs/superpowers/plans/2026-05-27-aihub-yolo-todo.md
git commit -m @'
docs(data): yolo11s balanced_500 validation 결과 + 약한 클래스 정리

다음 단계(exp04~ 약한 클래스 보강 실험) 입력 데이터.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
'@
```

---

## Self-Review

### Spec coverage 점검

| Spec 섹션 | 구현 Task |
|---|---|
| §2 비교 설계 (yolov8n vs yolo11s, 동일 val) | Task 8, 10 |
| §3.1 seed=42 고정 랜덤 샘플링 | Task 3 (5개 단위 테스트로 잠금) |
| §3.2 상한 500/하한 그대로 + train만 | Task 3, 5 |
| §3.3 폴더 구조 + _manifest/ | Task 5 |
| §3.4 스크립트 6단계 | Task 1~5 |
| §3.5 검증 체크리스트 | Task 7 Step 2~3 |
| §4.1 OOM dry-run | Task 9 |
| §4.2 본 학습 명령 | Task 8 (ps1) + Task 10 (실행) |
| §4.3 사전 점검 ps1 | Task 8 |
| §5.1 validation plots | Task 11 (ps1 + 실행) |
| §5.2 클래스별 분석 | Task 11 Step 3, 5 |
| §5.3 PC1과의 비교 | spec 밖 후속 (plan §10에 명시) |
| §7 위험 (OOM/콘솔 종료/cache hang/디스크) | Task 8, 9 (ps1 사전 점검 + dry-run) |
| §8 CLAUDE.md 준수 | Task 1~5 (타입/docstring/Pydantic v2/테스트) |
| §9 팀 협업 (커밋 메시지) | 모든 Task의 commit step에 한국어 Conventional Commits |

모든 spec 요구사항이 plan task에 매핑됨.

### Placeholder 스캔

- Task 9 Step 4의 `<32 또는 16>` — dry-run 결과로 결정되는 동적 값, 명시 OK
- Task 10 ~ 11의 `b<N>`, `<X>`, `<Y>`, `<Z>` — 학습 결과로 채워지는 값, 명시 OK (실험 plan 특성)
- "TODO" / "TBD" / "implement later" 검색 결과 없음

### Type 일관성 점검

- `select_stems_per_class(stems_by_class, cap_per_class, seed) -> dict[int, list[str]]` — Task 3, 5에서 동일 시그니처 사용 ✓
- `collect_stems_by_class(labels_dir, num_classes) -> dict[int, list[str]]` — Task 2, 5에서 동일 ✓
- `copy_selected_pairs(src_split, dst_split, selected_stems) -> int` — Task 4, 5에서 동일 ✓
- `run_downsample(src_root, dst_root, class_names, cap_per_class, seed) -> DownsampleResult` — Task 5, 7에서 동일 ✓
- `ClassManifest(class_id, class_name, stems)`, `TrainManifest(seed, cap_per_class, classes)` — Task 1, 5에서 동일 ✓

타입/시그니처 모순 없음.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-aihub-yolo-balanced500-yolo11s-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Task 1~6은 코드 작성·테스트가 명확해 fresh subagent로 task별 위임 + 리뷰가 자연스럽습니다. Task 7~11은 사용자가 직접 실행해야 하는 부분이 많아 (다운샘플 60분, 학습 25시간) inline으로 진행해도 무방합니다. 하이브리드 가능.

**2. Inline Execution** — 이 세션에서 Task 1부터 순서대로 진행. 코드 작성·테스트는 제가 직접, 데이터 작업·학습은 사용자가 별도 PowerShell.

**Which approach?**
