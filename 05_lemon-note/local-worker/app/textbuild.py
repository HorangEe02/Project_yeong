"""내보내기(MD/TXT)와 Slack 메시지 텍스트 빌더 (exports/share 공용)."""


def fmt_ms(ms) -> str:
    if ms is None:
        return "00:00"
    s = int(ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def fmt_when(value) -> str:
    """녹음 일시 표시. postgres 는 timestamptz 를 UTC 로 돌려줄 수 있어 로컬로 변환한다."""
    from datetime import datetime
    if not isinstance(value, datetime):
        try:
            value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return str(value or "")
    if value.tzinfo:
        value = value.astimezone()
    return value.strftime("%Y-%m-%d %H:%M")


def _seg_display_text(seg: dict) -> str:
    return seg.get("corrected_text") or seg.get("text") or ""


def _seg_speaker(seg: dict) -> str:
    return seg.get("speaker_name") or seg.get("speaker_label") or ""


def build_markdown(meeting: dict, summary: dict, segments: list,
                   include_transcript: bool = True) -> str:
    lines = []
    lines.append(f"# {meeting.get('title', '회의')}\n")
    lines.append(f"- 녹음 일시: {fmt_when(meeting.get('recorded_at'))}")
    lines.append(f"- 회의 길이: {fmt_ms(meeting.get('duration_ms'))}")
    lines.append(f"- 처리 상태: {meeting.get('status', '')}\n")

    if summary:
        lines.append("## 요약\n")
        lines.append(f"{summary.get('summary', '')}\n")

        keywords = summary.get("keywords") or []
        if keywords:
            lines.append("**주요 키워드:** " + " · ".join(keywords) + "\n")

        sections = summary.get("sections") or []
        if sections:
            lines.append("## 구간 요약\n")
            for s in sections:
                head = s.get("heading") or ""
                lines.append(f"- `{fmt_ms(s.get('start_ms'))}` **{head}** {s.get('text', '')}".replace("** ", "** ", 1))
            lines.append("")

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
    lines.append(f"녹음 일시: {fmt_when(meeting.get('recorded_at'))}")
    lines.append(f"회의 길이: {fmt_ms(meeting.get('duration_ms'))}")
    lines.append("")

    if summary:
        lines.append("■ 요약")
        lines.append(summary.get("summary", ""))
        lines.append("")
        if summary.get("keywords"):
            lines.append("■ 주요 키워드")
            lines.append(" · ".join(summary["keywords"]))
            lines.append("")
        if summary.get("sections"):
            lines.append("■ 구간 요약")
            for s in summary["sections"]:
                head = f"[{s.get('heading')}] " if s.get("heading") else ""
                lines.append(f"[{fmt_ms(s.get('start_ms'))}] {head}{s.get('text', '')}")
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
