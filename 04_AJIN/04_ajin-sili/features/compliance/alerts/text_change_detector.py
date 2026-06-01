"""Phase 4: 법규 변경 감지기

difflib 기반으로 법규 텍스트의 변경 사항을 감지하고,
변경 유형(추가/삭제/수정)과 핵심 변경 내용을 추출한다.
"""

import difflib
import re
from dataclasses import dataclass, field


@dataclass
class TextChange:
    """개별 텍스트 변경 항목"""
    change_type: str  # "added", "removed", "modified"
    before: str
    after: str
    context: str = ""


@dataclass
class ChangeAnalysis:
    """법규 텍스트 변경 분석 결과"""
    total_changes: int
    changes: list[TextChange] = field(default_factory=list)
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    modified_pairs: list[tuple[str, str]] = field(default_factory=list)
    key_numbers_changed: list[dict] = field(default_factory=list)
    summary: str = ""


class ChangeDetector:
    """법규 텍스트 변경 감지기"""

    def detect(self, before_text: str, after_text: str) -> ChangeAnalysis:
        """두 버전의 법규 텍스트를 비교하여 변경 사항을 분석한다."""
        before_lines = before_text.strip().splitlines()
        after_lines = after_text.strip().splitlines()

        diff = list(difflib.unified_diff(
            before_lines, after_lines,
            fromfile="구법", tofile="신법",
            lineterm="",
        ))

        changes = []
        added_lines = []
        removed_lines = []

        i = 0
        while i < len(diff):
            line = diff[i]
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                i += 1
                continue

            if line.startswith("-") and not line.startswith("---"):
                removed = line[1:].strip()
                # 다음 줄이 + 이면 수정으로 판단
                if i + 1 < len(diff) and diff[i + 1].startswith("+"):
                    added = diff[i + 1][1:].strip()
                    changes.append(TextChange(
                        change_type="modified",
                        before=removed,
                        after=added,
                    ))
                    i += 2
                    continue
                else:
                    removed_lines.append(removed)
                    changes.append(TextChange(
                        change_type="removed",
                        before=removed,
                        after="",
                    ))
            elif line.startswith("+") and not line.startswith("+++"):
                added = line[1:].strip()
                added_lines.append(added)
                changes.append(TextChange(
                    change_type="added",
                    before="",
                    after=added,
                ))
            i += 1

        # 숫자 변경 감지 (예: 300mm → 400mm, 90dB → 85dB)
        key_numbers = self._detect_number_changes(before_text, after_text)

        summary = self._build_summary(changes, key_numbers)

        return ChangeAnalysis(
            total_changes=len(changes),
            changes=changes,
            added_lines=added_lines,
            removed_lines=removed_lines,
            modified_pairs=[(c.before, c.after) for c in changes if c.change_type == "modified"],
            key_numbers_changed=key_numbers,
            summary=summary,
        )

    def _detect_number_changes(
        self, before_text: str, after_text: str
    ) -> list[dict]:
        """텍스트에서 수치 변경을 감지한다."""
        # 숫자+단위 패턴
        pattern = re.compile(
            r'(\d+(?:\.\d+)?)\s*'
            r'(밀리미터|미터|mm|cm|m|dB|dBA|dB\(A\)|V|Ω|℃|도|시간|분|초|kg|톤|%|ppm|mg)'
        )

        before_nums = {
            (m.group(2), m.start()): m.group(1)
            for m in pattern.finditer(before_text)
        }
        after_nums = {
            (m.group(2), m.start()): m.group(1)
            for m in pattern.finditer(after_text)
        }

        changes = []
        # 같은 단위의 숫자가 변경된 것을 찾음
        before_by_unit: dict[str, list[str]] = {}
        after_by_unit: dict[str, list[str]] = {}

        for (unit, _), val in before_nums.items():
            before_by_unit.setdefault(unit, []).append(val)
        for (unit, _), val in after_nums.items():
            after_by_unit.setdefault(unit, []).append(val)

        for unit in set(before_by_unit) & set(after_by_unit):
            b_vals = before_by_unit[unit]
            a_vals = after_by_unit[unit]
            for bv in b_vals:
                for av in a_vals:
                    if bv != av:
                        changes.append({
                            "unit": unit,
                            "before": f"{bv}{unit}",
                            "after": f"{av}{unit}",
                            "direction": "강화" if float(av) > float(bv) else "완화"
                            if unit not in ("dB", "dBA", "dB(A)", "ppm", "mg")
                            else "강화" if float(av) < float(bv) else "완화",
                        })

        return changes

    def _build_summary(
        self, changes: list[TextChange], key_numbers: list[dict]
    ) -> str:
        """변경 사항 요약문을 생성한다."""
        parts = []

        added = sum(1 for c in changes if c.change_type == "added")
        removed = sum(1 for c in changes if c.change_type == "removed")
        modified = sum(1 for c in changes if c.change_type == "modified")

        if modified:
            parts.append(f"수정 {modified}건")
        if added:
            parts.append(f"추가 {added}건")
        if removed:
            parts.append(f"삭제 {removed}건")

        summary = f"변경 사항: {', '.join(parts)}."

        if key_numbers:
            num_changes = []
            for kn in key_numbers:
                num_changes.append(f"{kn['before']} → {kn['after']} ({kn['direction']})")
            summary += f" 수치 변경: {', '.join(num_changes)}."

        return summary

    def get_diff_html(self, before_text: str, after_text: str) -> str:
        """HTML 형식의 diff를 반환한다 (UI 표시용)."""
        before_lines = before_text.strip().splitlines()
        after_lines = after_text.strip().splitlines()

        differ = difflib.HtmlDiff(wrapcolumn=80)
        return differ.make_table(
            before_lines, after_lines,
            fromdesc="구법", todesc="신법",
        )
