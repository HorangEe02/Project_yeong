"""식단 인식 fusion 엔진.

YOLO detection 리스트와 GCV hint 리스트를 받아 신뢰도 정책과 alias
매핑에 따라 `RecognizedMealItem` 리스트를 생성한다. 본 모듈은 파일 I/O를
하지 않으며, `aliases` mapping은 생성자 의존성 주입으로만 받는다.

A2.3 정책 요약:
    - YOLO primary — 모든 RecognizedMealItem은 YOLO detection에서 시작.
    - GCV alias 보강 — 같은 canonical key(이름 또는 food_code)면 sources에
      "google_vision" 추가. 별도 item을 만들지 않는다.
    - 충돌(orphan GCV hint) — 최고 confidence YOLO item을
      `needs_user_review=True`로 표시.
    - 동일 음식 다중 bbox — 최고 confidence 1개 + 나머지 alternatives.
    - 신뢰도 정책 3구간 — `>= AUTO_CANDIDATE_THRESHOLD` → review=False,
      그 외 → review=True. 낮은 confidence도 버리지 않는다.
    - `food_code`는 None (A3 RDA matching 책임).
    - `estimated_grams`는 임시 기본값, `portion_confidence=0.0` (A2.4 책임).
    - `ocr_text`는 A3 text_parser 책임 — 본 단계에서는 사용하지 않는다.

Reference:
    docs/dev-guides/16-meal-recognition.md §"구현 명세 / 4. fusion.py"
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from src.meal.base import DetectionSource, MealDetection, RecognizedMealItem

DEFAULT_ESTIMATED_GRAMS = 100.0
"""A2.4 PortionEstimator 도입 전 임시 추정 중량 (g).

PortionEstimator가 들어오면 본 상수는 fallback 용도로 강등되거나 제거된다.
"""

AUTO_CANDIDATE_THRESHOLD = 0.70
"""신뢰도가 이 값 이상이면 자동 후보(review=False), 미만이면 review=True.

dev-guide 16 §"결과 신뢰도 정책"의 ≥0.70 / 0.40~0.69 / <0.40 3구간 중
≥0.70 임계점. 0.40 미만이라도 detection 자체는 버리지 않는다.
"""

_FALLBACK_PORTION_CONFIDENCE = 0.0
"""양 추정 전 `portion_confidence` 기본값."""


class MealFusionEngine:
    """YOLO + GCV hint를 RecognizedMealItem 리스트로 결합한다.

    파일 I/O 없음 — `aliases` mapping은 생성자에서 주입받는다.
    `food_aliases.json`을 직접 읽지 않으며, 호출자(파이프라인 또는
    테스트)가 매핑을 구성해서 전달한다.

    Examples:
        >>> engine = MealFusionEngine(aliases={"공기밥": "F001", "쌀밥": "F001"})
        >>> items = engine.fuse(
        ...     yolo_detections=[...],
        ...     gcv_hints=[...],
        ... )
    """

    def __init__(self, aliases: Mapping[str, str] | None = None) -> None:
        """alias mapping을 주입한다.

        Args:
            aliases: alias_name → food_code 매핑. None이면 빈 매핑으로
                처리하며, 이 경우 detection의 `class_name_ko` 자체가
                canonical key로 쓰인다.
        """
        self._aliases: Mapping[str, str] = aliases or {}

    def _canonical_key(self, name: str) -> str:
        """alias mapping이 있으면 food_code, 없으면 name 자체를 키로 사용한다.

        Args:
            name: detection의 `class_name_ko`.

        Returns:
            그룹핑·매칭 비교에 쓰일 canonical 키 문자열.
        """
        return self._aliases.get(name, name)

    def fuse(
        self,
        *,
        yolo_detections: list[MealDetection],
        gcv_hints: list[MealDetection],
        ocr_text: str = "",
    ) -> list[RecognizedMealItem]:
        """YOLO + GCV를 결합해 RecognizedMealItem 리스트를 만든다.

        Args:
            yolo_detections: YOLO 어댑터 출력. 비면 빈 리스트 반환.
            gcv_hints: GCV 어댑터 출력 (label/object hint). OCR은 별도.
            ocr_text: GCV OCR 원문. A2.3에서는 사용하지 않으며, A3
                text_parser 도입 시 본 인자를 통해 OCR 보강 로직이
                추가될 예정이다.

        Returns:
            RecognizedMealItem 리스트.
            동일 canonical key(이름 또는 같은 food_code alias) 다중 detection은
            최고 confidence 1개로 합쳐지고 나머지는 alternatives에 보관된다.
            GCV hint 중 어떤 YOLO 후보와도 매칭되지 않는 항목이 있으면
            최고 confidence YOLO item을 review로 표시한다 (별도 item 생성 X).
        """
        del ocr_text  # A3 text_parser 책임 — 본 단계에서는 사용하지 않는다.

        if not yolo_detections:
            return []

        # 1. YOLO를 canonical key로 묶는다.
        groups: dict[str, list[MealDetection]] = defaultdict(list)
        for det in yolo_detections:
            groups[self._canonical_key(det.class_name_ko)].append(det)

        # 2. 각 그룹의 대표를 confidence 최고로 뽑고, 나머지는 alternatives.
        items_with_keys: list[tuple[str, RecognizedMealItem]] = []
        for key, dets in groups.items():
            sorted_dets = sorted(dets, key=lambda d: d.confidence, reverse=True)
            representative = sorted_dets[0]
            alternatives = sorted_dets[1:]
            item = RecognizedMealItem(
                name_ko=representative.class_name_ko,
                food_code=None,
                estimated_grams=DEFAULT_ESTIMATED_GRAMS,
                estimated_amount="",
                confidence=representative.confidence,
                portion_confidence=_FALLBACK_PORTION_CONFIDENCE,
                needs_user_review=representative.confidence < AUTO_CANDIDATE_THRESHOLD,
                sources=["yolo_v8"],
                alternatives=alternatives,
            )
            items_with_keys.append((key, item))

        # 3. GCV hint 처리: 매칭 → source 보강 후보, 미매칭 → orphan flag.
        item_keys = {key for key, _ in items_with_keys}
        items_with_gcv: set[str] = set()
        has_orphan_gcv = False
        for hint in gcv_hints:
            hint_key = self._canonical_key(hint.class_name_ko)
            if hint_key in item_keys:
                items_with_gcv.add(hint_key)
            else:
                has_orphan_gcv = True

        # 4. orphan 충돌 시 review로 강제할 최고 confidence item index.
        highest_conf_idx = max(
            range(len(items_with_keys)),
            key=lambda i: items_with_keys[i][1].confidence,
        )

        # 5. 최종 item 빌드 — frozen DTO라 model_copy(update=...)로 갱신.
        final_items: list[RecognizedMealItem] = []
        for i, (key, item) in enumerate(items_with_keys):
            new_sources: list[DetectionSource] = list(item.sources)
            new_review = item.needs_user_review
            if key in items_with_gcv:
                new_sources.append("google_vision")
            if has_orphan_gcv and i == highest_conf_idx:
                new_review = True
            final_items.append(
                item.model_copy(
                    update={
                        "sources": new_sources,
                        "needs_user_review": new_review,
                    }
                )
            )

        return final_items
