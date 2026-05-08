"""
문서 버전 비교 (diff) 엔진
- difflib 기반 unified diff → HTML 하이라이트
- 유사도 비율 계산
"""

import difflib
from typing import Tuple, Dict


def compute_diff(text_old: str, text_new: str, context_lines: int = 3) -> Tuple[str, Dict]:
    """
    두 텍스트의 diff를 HTML로 생성

    Returns:
        (diff_html, stats) — stats: {"added": N, "removed": N, "unchanged": N}
    """
    old_lines = text_old.splitlines(keepends=True)
    new_lines = text_new.splitlines(keepends=True)

    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=context_lines))

    if not diff:
        return "<p style='color:var(--hud-text-dim, #D5CFC5);'>변경 사항이 없습니다.</p>", {"added": 0, "removed": 0, "unchanged": len(old_lines)}

    stats = {"added": 0, "removed": 0, "unchanged": 0}
    html_parts = ['<div style="font-family:monospace;font-size:12px;line-height:1.6;border:1px solid var(--hud-border,#D6CFC3);border-radius:4px;padding:12px;overflow-x:auto;">']

    for line in diff:
        escaped = _escape(line.rstrip("\n"))

        if line.startswith("+++") or line.startswith("---"):
            html_parts.append(f'<div style="color:var(--hud-text-dim, #D5CFC5);font-weight:600;">{escaped}</div>')
        elif line.startswith("@@"):
            html_parts.append(f'<div style="color:#1976D2;background:rgba(25,118,210,0.08);padding:2px 6px;margin:4px 0;">{escaped}</div>')
        elif line.startswith("+"):
            stats["added"] += 1
            html_parts.append(f'<div style="background:rgba(46,125,50,0.15);color:#2E7D32;padding:1px 6px;">{escaped}</div>')
        elif line.startswith("-"):
            stats["removed"] += 1
            html_parts.append(f'<div style="background:rgba(198,40,40,0.12);color:#C62828;text-decoration:line-through;padding:1px 6px;">{escaped}</div>')
        else:
            stats["unchanged"] += 1
            html_parts.append(f'<div style="color:var(--hud-text,#2C241A);padding:1px 6px;">{escaped}</div>')

    html_parts.append("</div>")
    return "\n".join(html_parts), stats


def compute_similarity_ratio(text_old: str, text_new: str) -> float:
    """두 텍스트의 유사도 비율 (0.0~1.0)"""
    return difflib.SequenceMatcher(None, text_old, text_new).ratio()


def _escape(text: str) -> str:
    """HTML 이스케이프"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
