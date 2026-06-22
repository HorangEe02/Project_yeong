"""Coordinate-based layout parser for supplement label OCR results."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median

from src.models.schemas.label_layout import (
    LabelBox,
    LabelCell,
    LabelLayout,
    LabelSection,
    LayoutParserOptions,
    SectionType,
)
from src.ocr.base import OCRBoundingPoly, OCRPage, OCRResult, OCRWord

LAYOUT_UNAVAILABLE_WARNING = "layout_unavailable"
LAYOUT_WORDS_UNAVAILABLE_WARNING = "layout_words_unavailable"
MISSING_BOUNDING_BOX_WARNING = "ocr_words_missing_bounding_box"
INVALID_BOUNDING_BOX_WARNING = "ocr_words_invalid_bounding_box"
COORDINATE_SCALE_WARNING = "ocr_word_coordinate_scale_mismatch"
SECTION_ROW_LIMIT_WARNING = "layout_section_row_limit_exceeded"
DEFAULT_ROW_TOLERANCE = 8.0
COLUMN_BAND_MERGE_RATIO = 0.60
COORDINATE_SCALE_TOLERANCE = 1.20
MIN_BOUNDING_VERTICES = 2
ANCHOR_NORMALIZE_PATTERN = re.compile("[\\s·ㆍ:\\uFF1A\\-\\(\\)\\[\\]/|]+")
SECTION_KEYWORDS: dict[SectionType, tuple[str, ...]] = {
    "daily_intake": (
        "일일섭취량",
        "1일섭취량",
        "일일 섭취량",
        "섭취량",
        "Serving Size",
        "Servings Per Container",
        "Amount Per Serving",
    ),
    "nutrition_function_info": (
        "영양·기능정보",
        "영양 기능정보",
        "영양정보",
        "기능정보",
        "Supplement Facts",
        "Nutrition Facts",
        "% Daily Value",
    ),
    "intake_method": (
        "섭취방법",
        "섭취 방법",
        "복용방법",
        "복용 방법",
        "Directions",
        "Suggested Use",
        "How To Take",
    ),
    "precautions": (
        "섭취 시 주의사항",
        "섭취시 주의사항",
        "주의사항",
        "주의",
        "Warning",
        "Warnings",
        "Caution",
    ),
    "allergen_warning": (
        "Allergy Information",
        "Allergen Information",
        "Allergy Warning",
        "Allergen Warning",
    ),
    "ingredients": (
        "원재료명",
        "원료명",
        "원재료",
        "Ingredients",
        "Other Ingredients",
    ),
    "functionality": ("기능성", "기능성 내용", "기능성분"),
    "storage_method": (
        "보관방법",
        "보관 방법",
        "보관 시 주의사항",
        "Storage",
        "Storage Instructions",
    ),
}
PRECAUTION_ALLERGEN_ROW_PATTERN = re.compile(
    r"\bcontains\b.*\b(?:soy(?:bean)?|milk(?:-derived)?|dairy|lactose|egg|fish|shellfish|"
    r"wheat|peanut|tree\s+nuts?|sesame|gluten)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _LayoutWord:
    """OCR word normalized into an axis-aligned layout box."""

    page_index: int
    text: str
    bounding_box: LabelBox
    confidence: float | None
    block_type: str | None

    @property
    def left(self) -> float:
        """Return the left coordinate."""
        return self.bounding_box.left

    @property
    def top(self) -> float:
        """Return the top coordinate."""
        return self.bounding_box.top

    @property
    def right(self) -> float:
        """Return the right coordinate."""
        return self.bounding_box.right

    @property
    def bottom(self) -> float:
        """Return the bottom coordinate."""
        return self.bounding_box.bottom

    @property
    def center_x(self) -> float:
        """Return the horizontal center coordinate."""
        return (self.left + self.right) / 2

    @property
    def center_y(self) -> float:
        """Return the vertical center coordinate."""
        return (self.top + self.bottom) / 2

    @property
    def width(self) -> float:
        """Return word width."""
        return self.right - self.left

    @property
    def height(self) -> float:
        """Return word height."""
        return self.bottom - self.top


@dataclass
class _MutableRow:
    """Mutable row accumulator used during y-band grouping."""

    page_index: int
    words: list[_LayoutWord]
    center_y: float


@dataclass(frozen=True)
class _LayoutCellCandidate:
    """Intermediate cell built from one or more OCR words."""

    text: str
    bounding_box: LabelBox
    confidence: float | None
    word_count: int

    @property
    def left(self) -> float:
        """Return the left coordinate."""
        return self.bounding_box.left

    @property
    def right(self) -> float:
        """Return the right coordinate."""
        return self.bounding_box.right

    @property
    def center_x(self) -> float:
        """Return the horizontal center coordinate."""
        return (self.left + self.right) / 2

    @property
    def width(self) -> float:
        """Return cell width."""
        return self.right - self.left


@dataclass(frozen=True)
class _LayoutRowCandidate:
    """Intermediate row with split cell candidates."""

    page_index: int
    row_order: int
    cells: tuple[_LayoutCellCandidate, ...]
    bounding_box: LabelBox
    text: str


@dataclass(frozen=True)
class _AnchorMatch:
    """Detected semantic section anchor."""

    row_order: int
    section_type: SectionType
    anchor_text: str
    anchor_box: LabelBox


@dataclass
class _ColumnBand:
    """Mutable x-band accumulator for section-local column assignment."""

    center_x: float
    left: float
    right: float
    count: int


def parse_label_layout(
    ocr_result: OCRResult,
    *,
    options: LayoutParserOptions | None = None,
) -> LabelLayout:
    """Parse OCR word coordinates into sectioned label rows and cells.

    Args:
        ocr_result: OCR result containing normalized page/block/word layout metadata.
        options: Optional deterministic parser thresholds.

    Returns:
        Parsed label layout. Empty sections with warnings indicate degraded input.
    """
    active_options = options or LayoutParserOptions()
    page_count = len(ocr_result.pages)
    if not ocr_result.pages:
        return LabelLayout(
            provider=ocr_result.provider,
            page_count=0,
            sections=[],
            warnings=[LAYOUT_UNAVAILABLE_WARNING],
        )

    warnings: list[str] = []
    words = _flatten_ocr_words(ocr_result.pages, warnings)
    if not words:
        warnings.append(LAYOUT_WORDS_UNAVAILABLE_WARNING)
        return LabelLayout(
            provider=ocr_result.provider,
            page_count=page_count,
            sections=[],
            warnings=warnings,
        )

    grouped_rows = _group_words_into_rows(words, active_options)
    row_candidates = _build_row_candidates(grouped_rows, active_options)
    sections = _build_sections(row_candidates, active_options, warnings)
    return LabelLayout(
        provider=ocr_result.provider,
        page_count=page_count,
        sections=sections,
        warnings=warnings,
    )


def _flatten_ocr_words(pages: Sequence[OCRPage], warnings: list[str]) -> list[_LayoutWord]:
    """Flatten OCR pages into coordinate-bearing words.

    Args:
        pages: OCR pages from a provider-normalized result.
        warnings: Mutable warning list.

    Returns:
        Layout words in provider order.
    """
    words: list[_LayoutWord] = []
    missing_box_count = 0
    invalid_box_count = 0
    scale_mismatch_count = 0
    for page_index, page in enumerate(pages):
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    text = word.text.strip()
                    if not text:
                        continue
                    box = _box_from_ocr_word(word, page_index)
                    if word.bounding_box is None:
                        missing_box_count += 1
                        continue
                    if box is None:
                        invalid_box_count += 1
                        continue
                    if _is_coordinate_scale_mismatch(box, page):
                        scale_mismatch_count += 1
                    words.append(
                        _LayoutWord(
                            page_index=page_index,
                            text=text,
                            bounding_box=box,
                            confidence=word.confidence,
                            block_type=block.block_type,
                        )
                    )
    _append_count_warning(warnings, MISSING_BOUNDING_BOX_WARNING, missing_box_count)
    _append_count_warning(warnings, INVALID_BOUNDING_BOX_WARNING, invalid_box_count)
    _append_count_warning(warnings, COORDINATE_SCALE_WARNING, scale_mismatch_count)
    return words


def _box_from_ocr_word(word: OCRWord, page_index: int) -> LabelBox | None:
    """Convert an OCR word polygon to an axis-aligned label box.

    Args:
        word: OCR word.
        page_index: Zero-based OCR page index.

    Returns:
        Label box, or None when the polygon is invalid.
    """
    return _box_from_bounding_poly(word.bounding_box, page_index)


def _box_from_bounding_poly(poly: OCRBoundingPoly | None, page_index: int) -> LabelBox | None:
    """Convert an OCR bounding polygon to an axis-aligned label box.

    Args:
        poly: OCR bounding polygon.
        page_index: Zero-based OCR page index.

    Returns:
        Label box, or None when coordinates are unusable.
    """
    if poly is None or len(poly.vertices) < MIN_BOUNDING_VERTICES:
        return None
    xs = [vertex.x for vertex in poly.vertices]
    ys = [vertex.y for vertex in poly.vertices]
    left = min(xs)
    right = max(xs)
    top = min(ys)
    bottom = max(ys)
    if left < 0 or top < 0 or right <= left or bottom <= top:
        return None
    return LabelBox(
        page_index=page_index,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
    )


def _is_coordinate_scale_mismatch(box: LabelBox, page: OCRPage) -> bool:
    """Check whether a word box appears far outside page dimensions.

    Args:
        box: Word bounding box.
        page: Source OCR page.

    Returns:
        True when page dimensions exist and coordinates exceed a tolerant bound.
    """
    if page.width is not None and box.right > page.width * COORDINATE_SCALE_TOLERANCE:
        return True
    return page.height is not None and box.bottom > page.height * COORDINATE_SCALE_TOLERANCE


def _group_words_into_rows(
    words: Sequence[_LayoutWord],
    options: LayoutParserOptions,
) -> list[_MutableRow]:
    """Group words into y-band rows.

    Args:
        words: Layout words.
        options: Parser thresholds.

    Returns:
        Mutable rows sorted in visual order.
    """
    rows: list[_MutableRow] = []
    for page_index in sorted({word.page_index for word in words}):
        page_words = sorted(
            (word for word in words if word.page_index == page_index),
            key=lambda word: (word.center_y, word.left),
        )
        row_tolerance = _row_tolerance(page_words, options)
        page_rows: list[_MutableRow] = []
        for word in page_words:
            row = _nearest_row(word, page_rows, row_tolerance)
            if row is None:
                page_rows.append(
                    _MutableRow(
                        page_index=page_index,
                        words=[word],
                        center_y=word.center_y,
                    )
                )
                continue
            row.words.append(word)
            row.center_y = _average(word.center_y for word in row.words) or row.center_y
        for row in page_rows:
            row.words.sort(key=lambda word: word.left)
        rows.extend(sorted(page_rows, key=lambda row: row.center_y))
    return rows


def _row_tolerance(words: Sequence[_LayoutWord], options: LayoutParserOptions) -> float:
    """Calculate y-band tolerance from median word height.

    Args:
        words: Page-local words.
        options: Parser thresholds.

    Returns:
        Row tolerance in provider coordinate units.
    """
    median_height = _median(word.height for word in words)
    if median_height is None:
        return DEFAULT_ROW_TOLERANCE
    return max(median_height * options.row_y_tolerance_ratio, DEFAULT_ROW_TOLERANCE)


def _nearest_row(
    word: _LayoutWord,
    rows: Sequence[_MutableRow],
    tolerance: float,
) -> _MutableRow | None:
    """Return the closest row within y-band tolerance.

    Args:
        word: Candidate word.
        rows: Existing rows.
        tolerance: Maximum center-y distance.

    Returns:
        Matching row or None.
    """
    if not rows:
        return None
    candidates = [(abs(word.center_y - row.center_y), row) for row in rows]
    distance, row = min(candidates, key=lambda item: item[0])
    if distance <= tolerance:
        return row
    return None


def _build_row_candidates(
    rows: Sequence[_MutableRow],
    options: LayoutParserOptions,
) -> list[_LayoutRowCandidate]:
    """Convert grouped rows into cell-bearing row candidates.

    Args:
        rows: Grouped rows.
        options: Parser thresholds.

    Returns:
        Row candidates in visual order.
    """
    candidates: list[_LayoutRowCandidate] = []
    for row_order, row in enumerate(rows):
        cells = _split_row_into_cells(row.words, options)
        if not cells:
            continue
        row_box = _merge_boxes(cell.bounding_box for cell in cells)
        row_text = " ".join(cell.text for cell in cells)
        candidates.append(
            _LayoutRowCandidate(
                page_index=row.page_index,
                row_order=row_order,
                cells=cells,
                bounding_box=row_box,
                text=row_text,
            )
        )
    return candidates


def _split_row_into_cells(
    words: Sequence[_LayoutWord],
    options: LayoutParserOptions,
) -> tuple[_LayoutCellCandidate, ...]:
    """Split a visual row into cells using x-axis gaps.

    Args:
        words: Row words sorted by x coordinate.
        options: Parser thresholds.

    Returns:
        Cell candidates in visual order.
    """
    if not words:
        return ()
    median_width = _median(word.width for word in words) or 1.0
    gap_threshold = median_width * options.column_gap_ratio
    cells: list[_LayoutCellCandidate] = []
    current_words: list[_LayoutWord] = []
    for word in sorted(words, key=lambda item: item.left):
        if current_words and word.left - current_words[-1].right > gap_threshold:
            cells.append(_build_cell_candidate(current_words))
            current_words = []
        current_words.append(word)
    if current_words:
        cells.append(_build_cell_candidate(current_words))
    return tuple(cells)


def _build_cell_candidate(words: Sequence[_LayoutWord]) -> _LayoutCellCandidate:
    """Build one cell candidate from adjacent OCR words.

    Args:
        words: Cell words.

    Returns:
        Cell candidate.
    """
    return _LayoutCellCandidate(
        text=" ".join(word.text for word in words),
        bounding_box=_merge_boxes(word.bounding_box for word in words),
        confidence=_average(word.confidence for word in words),
        word_count=len(words),
    )


def _build_sections(
    rows: Sequence[_LayoutRowCandidate],
    options: LayoutParserOptions,
    warnings: list[str],
) -> list[LabelSection]:
    """Build semantic sections from row candidates.

    Args:
        rows: Row candidates in visual order.
        options: Parser thresholds.
        warnings: Mutable warning list.

    Returns:
        Label sections.
    """
    if not rows:
        return []
    anchors: list[_AnchorMatch] = []
    for row in rows:
        anchor = _detect_anchor(row)
        if anchor is not None:
            anchors.append(anchor)
    if not anchors:
        return [_build_label_section("unknown", None, rows, options, warnings)]

    sections: list[LabelSection] = []
    first_anchor_index = anchors[0].row_order
    if first_anchor_index > 0:
        sections.append(
            _build_label_section(
                "unknown",
                None,
                rows[:first_anchor_index],
                options,
                warnings,
            )
        )

    for anchor_index, anchor in enumerate(anchors):
        next_start = (
            anchors[anchor_index + 1].row_order if anchor_index + 1 < len(anchors) else len(rows)
        )
        section_rows = rows[anchor.row_order : next_start]
        sections.append(
            _build_label_section(
                anchor.section_type,
                anchor,
                section_rows,
                options,
                warnings,
            )
        )
    return [section for section in sections if section.rows]


def _detect_anchor(row: _LayoutRowCandidate) -> _AnchorMatch | None:
    """Detect the highest-priority keyword anchor in a row.

    Args:
        row: Row candidate.

    Returns:
        Anchor match or None.
    """
    row_text = _normalize_anchor_text(row.text)
    best_match: tuple[SectionType, str, str] | None = None
    for section_type, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = _normalize_anchor_text(keyword)
            if normalized_keyword not in row_text:
                continue
            if best_match is None or len(normalized_keyword) > len(best_match[2]):
                best_match = (section_type, keyword, normalized_keyword)
    if best_match is None:
        if _looks_like_allergen_warning_row(row.text):
            return _AnchorMatch(
                row_order=row.row_order,
                section_type="allergen_warning",
                anchor_text="Contains allergen",
                anchor_box=row.bounding_box,
            )
        return None

    section_type, keyword, normalized_keyword = best_match
    anchor_box = _anchor_box_for_row(row, normalized_keyword)
    return _AnchorMatch(
        row_order=row.row_order,
        section_type=section_type,
        anchor_text=keyword,
        anchor_box=anchor_box,
    )


def _looks_like_allergen_warning_row(value: str) -> bool:
    """Return whether a row is a warning-like allergen statement.

    Args:
        value: Visual row text reconstructed from OCR words.

    Returns:
        True for bounded allergen statements that should start an allergen section.
    """
    normalized = _normalize_anchor_text(value)
    if any(token in normalized for token in ("allergy", "allergen", "알레르", "알러지")):
        return True
    if PRECAUTION_ALLERGEN_ROW_PATTERN.search(value):
        return True
    return "함유" in normalized and any(
        token in normalized
        for token in (
            "대두",
            "우유",
            "난류",
            "계란",
            "밀",
            "땅콩",
            "견과",
            "조개",
            "갑각류",
            "글루텐",
        )
    )


def _anchor_box_for_row(row: _LayoutRowCandidate, normalized_keyword: str) -> LabelBox:
    """Return the most specific anchor box for a row.

    Args:
        row: Row candidate.
        normalized_keyword: Normalized keyword text.

    Returns:
        Matching cell box or whole row box.
    """
    for cell in row.cells:
        if normalized_keyword in _normalize_anchor_text(cell.text):
            return cell.bounding_box
    return row.bounding_box


def _build_label_section(
    section_type: SectionType,
    anchor: _AnchorMatch | None,
    rows: Sequence[_LayoutRowCandidate],
    options: LayoutParserOptions,
    warnings: list[str],
) -> LabelSection:
    """Build a Pydantic label section from row candidates.

    Args:
        section_type: Semantic section type.
        anchor: Optional detected anchor.
        rows: Rows in the section.
        options: Parser thresholds.
        warnings: Mutable warning list.

    Returns:
        Label section.
    """
    if len(rows) > options.max_section_gap_rows:
        warnings.append(f"{SECTION_ROW_LIMIT_WARNING}:{section_type}")
    section_rows = _rows_to_label_cells(rows)
    return LabelSection(
        section_type=section_type,
        anchor_text=anchor.anchor_text if anchor is not None else None,
        anchor_box=anchor.anchor_box if anchor is not None else None,
        rows=section_rows,
    )


def _rows_to_label_cells(rows: Sequence[_LayoutRowCandidate]) -> list[list[LabelCell]]:
    """Convert section rows into validated label cells with column indexes.

    Args:
        rows: Section row candidates.

    Returns:
        Rows of label cells.
    """
    bands = _build_column_bands(rows)
    label_rows: list[list[LabelCell]] = []
    for row_index, row in enumerate(rows):
        row_cells: list[LabelCell] = []
        for fallback_index, cell in enumerate(row.cells):
            column_index = _column_index_for_cell(cell, bands, fallback_index, len(row.cells))
            row_cells.append(
                LabelCell(
                    row_index=row_index,
                    column_index=column_index,
                    text=cell.text,
                    bounding_box=cell.bounding_box,
                    confidence=cell.confidence,
                    word_count=cell.word_count,
                )
            )
        row_cells.sort(key=lambda item: (item.column_index, item.bounding_box.left))
        label_rows.append(row_cells)
    return label_rows


def _build_column_bands(rows: Sequence[_LayoutRowCandidate]) -> list[_ColumnBand]:
    """Build section-local x-axis column bands.

    Args:
        rows: Section row candidates.

    Returns:
        Column bands sorted left-to-right.
    """
    multi_cell_candidates = [cell for row in rows if len(row.cells) > 1 for cell in row.cells]
    source_cells = multi_cell_candidates or [cell for row in rows for cell in row.cells]
    if not source_cells:
        return []
    median_width = _median(cell.width for cell in source_cells) or 1.0
    merge_threshold = max(median_width * COLUMN_BAND_MERGE_RATIO, 1.0)
    bands: list[_ColumnBand] = []
    for cell in sorted(source_cells, key=lambda item: item.center_x):
        band = _nearest_column_band(cell, bands, merge_threshold)
        if band is None:
            bands.append(
                _ColumnBand(
                    center_x=cell.center_x,
                    left=cell.left,
                    right=cell.right,
                    count=1,
                )
            )
            continue
        band.center_x = ((band.center_x * band.count) + cell.center_x) / (band.count + 1)
        band.left = min(band.left, cell.left)
        band.right = max(band.right, cell.right)
        band.count += 1
    return sorted(bands, key=lambda item: item.left)


def _nearest_column_band(
    cell: _LayoutCellCandidate,
    bands: Sequence[_ColumnBand],
    threshold: float,
) -> _ColumnBand | None:
    """Return the nearest x-band within threshold.

    Args:
        cell: Cell candidate.
        bands: Existing column bands.
        threshold: Maximum center-x distance.

    Returns:
        Matching band or None.
    """
    if not bands:
        return None
    distance, band = min(
        ((abs(cell.center_x - candidate.center_x), candidate) for candidate in bands),
        key=lambda item: item[0],
    )
    if distance <= threshold:
        return band
    return None


def _column_index_for_cell(
    cell: _LayoutCellCandidate,
    bands: Sequence[_ColumnBand],
    fallback_index: int,
    row_cell_count: int,
) -> int:
    """Assign a section-local column index to one cell.

    Args:
        cell: Cell candidate.
        bands: Section column bands.
        fallback_index: Cell index within the current row.
        row_cell_count: Number of cells in the current row.

    Returns:
        Column index.
    """
    if row_cell_count == 1:
        return 0
    if not bands:
        return fallback_index
    _, band_index = min(
        ((abs(cell.center_x - band.center_x), index) for index, band in enumerate(bands)),
        key=lambda item: item[0],
    )
    return band_index


def _normalize_anchor_text(value: str) -> str:
    """Normalize text for conservative keyword matching.

    Args:
        value: Raw OCR or keyword text.

    Returns:
        Normalized comparable text.
    """
    return ANCHOR_NORMALIZE_PATTERN.sub("", value.casefold())


def _merge_boxes(boxes: Iterable[LabelBox]) -> LabelBox:
    """Return the union bounding box for boxes on the same visual row or section.

    Args:
        boxes: Label boxes.

    Returns:
        Union label box.
    """
    box_list = list(boxes)
    first_box = box_list[0]
    return LabelBox(
        page_index=first_box.page_index,
        left=min(box.left for box in box_list),
        top=min(box.top for box in box_list),
        right=max(box.right for box in box_list),
        bottom=max(box.bottom for box in box_list),
    )


def _append_count_warning(warnings: list[str], warning_code: str, count: int) -> None:
    """Append a count-bearing warning when count is non-zero.

    Args:
        warnings: Mutable warning list.
        warning_code: Warning code prefix.
        count: Number of occurrences.
    """
    if count > 0:
        warnings.append(f"{warning_code}:{count}")


def _median(values: Iterable[float]) -> float | None:
    """Return a median value when values are present.

    Args:
        values: Numeric values.

    Returns:
        Median or None.
    """
    value_list = list(values)
    if not value_list:
        return None
    return float(median(value_list))


def _average(values: Iterable[float | None]) -> float | None:
    """Return an average over present values.

    Args:
        values: Optional numeric values.

    Returns:
        Average or None.
    """
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


__all__ = [
    "parse_label_layout",
]
