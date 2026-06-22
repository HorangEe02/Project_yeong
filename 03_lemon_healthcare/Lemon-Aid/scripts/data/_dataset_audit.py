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
