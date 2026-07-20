"""내보내기(MD/TXT)와 Slack 메시지 텍스트 빌더 (exports/share 공용)."""


def fmt_ms(ms) -> str:
    if ms is None:
        return "00:00"
    s = int(ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def _seg_display_text(seg: dict) -> str:
    return seg.get("corrected_text") or seg.get("text") or ""


def _seg_speaker(seg: dict) -> str:
    return seg.get("speaker_name") or seg.get("speaker_label") or ""


def build_markdown(meeting: dict, summary: dict, segments: list,
                   include_transcript: bool = True) -> str:
    lines = []
    lines.append(f"# {meeting.get('title', '회의')}\n")
    lines.append(f"- 녹음 일시: {meeting.get('recorded_at', '')}")
    lines.append(f"- 회의 길이: {fmt_ms(meeting.get('duration_ms'))}")
    lines.append(f"- 처리 상태: {meeting.get('status', '')}\n")

    if summary:
        lines.append("## 요약\n")
        lines.append(f"{summary.get('summary', '')}\n")

        decisions = summary.get("decisions") or []
        if decisions:
            lines.append("## 결정사항\n")
            for d in decisions:
                lines.append(f"- {d.get('text', '')}")
            lines.append("")

        action_items = summary.get("action_items") or []
        if action_items:
            lines.append("## 할 일\n")
            lines.append("| 담당자 | 작업 | 마감일 |")
            lines.append("| --- | --- | --- |")
            for a in action_items:
                lines.append(
                    f"| {a.get('owner') or '-'} | {a.get('task', '')} | {a.get('due_date') or '-'} |")
            lines.append("")

        candidates = summary.get("calendar_candidates") or []
        if candidates:
            lines.append("## 일정 후보\n")
            lines.append("| 제목 | 시작 | 종료 | 신뢰도 |")
            lines.append("| --- | --- | --- | --- |")
            for c in candidates:
                conf = c.get("confidence")
                conf_s = f"{round(conf * 100)}%" if isinstance(conf, (int, float)) else "-"
                lines.append(
                    f"| {c.get('title', '')} | {c.get('start_at') or '-'} | {c.get('end_at') or '-'} | {conf_s} |")
            lines.append("")

    if include_transcript and segments:
        lines.append("## 전체 전사\n")
        for s in segments:
            lines.append(
                f"[{fmt_ms(s['start_ms'])} - {fmt_ms(s['end_ms'])}] "
                f"{_seg_speaker(s)}: {_seg_display_text(s)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_txt(meeting: dict, summary: dict, segments: list,
              include_transcript: bool = True) -> str:
    lines = []
    lines.append(f"[{meeting.get('title', '회의')}]")
    lines.append(f"녹음 일시: {meeting.get('recorded_at', '')}")
    lines.append(f"회의 길이: {fmt_ms(meeting.get('duration_ms'))}")
    lines.append("")

    if summary:
        lines.append("■ 요약")
        lines.append(summary.get("summary", ""))
        lines.append("")
        if summary.get("decisions"):
            lines.append("■ 결정사항")
            for d in summary["decisions"]:
                lines.append(f"- {d.get('text', '')}")
            lines.append("")
        if summary.get("action_items"):
            lines.append("■ 할 일")
            for a in summary["action_items"]:
                lines.append(
                    f"- {a.get('owner') or '담당 미정'}: {a.get('task', '')}"
                    f" ({a.get('due_date') or '마감 미정'})")
            lines.append("")
        if summary.get("calendar_candidates"):
            lines.append("■ 일정 후보")
            for c in summary["calendar_candidates"]:
                lines.append(f"- {c.get('start_at') or ''} {c.get('title', '')}")
            lines.append("")

    if include_transcript and segments:
        lines.append("■ 전체 전사")
        for s in segments:
            lines.append(f"[{fmt_ms(s['start_ms'])}] {_seg_speaker(s)}: {_seg_display_text(s)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_slack_text(meeting: dict, summary: dict) -> str:
    lines = [f"[회의 요약] {meeting.get('title', '회의')}", ""]
    if summary:
        lines.append("요약:")
        lines.append(f"- {summary.get('summary', '')}")
        lines.append("")
        if summary.get("decisions"):
            lines.append("결정사항:")
            for d in summary["decisions"]:
                lines.append(f"- {d.get('text', '')}")
            lines.append("")
        if summary.get("action_items"):
            lines.append("할 일:")
            for a in summary["action_items"]:
                lines.append(
                    f"- {a.get('owner') or '담당 미정'}: {a.get('task', '')}"
                    f" ({a.get('due_date') or '마감 미정'})")
            lines.append("")
        if summary.get("calendar_candidates"):
            lines.append("일정 후보:")
            for c in summary["calendar_candidates"]:
                lines.append(f"- {c.get('start_at') or ''} {c.get('title', '')}")
    return "\n".join(lines).strip()
