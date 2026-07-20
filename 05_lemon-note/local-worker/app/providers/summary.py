"""요약 Provider.

계약: summarize(segments, language, context) -> dict
반환 dict: title, summary, decisions[], action_items[], calendar_candidates[]
segments 는 DB 저장 후의 dict 리스트로 'id' 필드를 포함 → source_segment_ids 로 참조.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional


def _parse_dt(value) -> datetime:
    """recorded_at 정규화.

    sqlite 백엔드는 ISO 문자열, postgres(psycopg) 백엔드는 datetime 객체를 돌려준다.
    문자열로만 가정하면 datetime.replace(year=..., month=...) 로 해석되어 TypeError 가 난다.
    """
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.now(timezone.utc).astimezone()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).astimezone()


def _seg_text(s: dict) -> str:
    return s.get("corrected_text") or s.get("text") or ""


class StubSummaryProvider:
    name = "stub"

    def summarize(self, segments: List[dict], language: str = "ko",
                  context: Optional[dict] = None) -> dict:
        context = context or {}
        ids = [s.get("id") for s in segments]

        def sid(i):
            return [ids[i]] if 0 <= i < len(ids) and ids[i] else []

        base = _parse_dt(context.get("recorded_at"))
        due = (base + timedelta(days=7)).date().isoformat()
        cal_start = (base + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0)
        cal_end = cal_start + timedelta(minutes=30)
        title = context.get("title") or "제품 MVP 회의"
        return {
            "title": f"{title} 요약",
            "summary": ("이번 회의에서는 MVP 범위와 처리 아키텍처, 일정을 논의했다. "
                        "초기에는 Mac 로컬 Worker로 전사와 요약을 처리하고, 서버 준비 후 "
                        "동일한 API 계약을 유지한 채 서버 Worker로 이전하기로 했다."),
            "decisions": [
                {"text": "초기 처리는 Mac 로컬 Worker로 진행하고 서버 준비 후 이전한다.",
                 "source_segment_ids": sid(2) + sid(3)},
                {"text": "원본 음성과 원본 전사는 보존하고 요약본만 별도 버전으로 저장한다.",
                 "source_segment_ids": sid(5) + sid(6)},
                {"text": "일정 후보는 자동 등록하지 않고 사용자가 확인한 뒤 등록한다.",
                 "source_segment_ids": sid(7)},
            ],
            "action_items": [
                {"owner": "홍길동", "task": "Mac 로컬 Worker 프로토타입 준비", "due_date": due,
                 "source_segment_ids": sid(11), "confidence": 0.82, "status": "open"},
                {"owner": "담당 미정", "task": "웹 녹음 UI 준비", "due_date": due,
                 "source_segment_ids": sid(11), "confidence": 0.78, "status": "open"},
            ],
            "calendar_candidates": [
                {"title": "MVP 진행 상황 점검",
                 "start_at": cal_start.isoformat(timespec="seconds"),
                 "end_at": cal_end.isoformat(timespec="seconds"),
                 "attendees": ["team@example.com"], "source_segment_ids": sid(9),
                 "confidence": 0.76, "status": "pending"}],
        }


class OllamaSummaryProvider:
    """Ollama 로컬 LLM 요약. SUMMARY_PROVIDER=ollama 로 활성화.

    전사에 [n] 인덱스를 붙여 LLM에 넣고, LLM이 근거를 인덱스로 참조하게 한 뒤
    인덱스를 실제 segment id로 매핑한다(할루시네이션된 id 방지).
    """

    name = "ollama"

    def summarize(self, segments: List[dict], language: str = "ko",
                  context: Optional[dict] = None) -> dict:
        import urllib.request
        from .. import config

        context = context or {}
        ids = [s.get("id") for s in segments]
        transcript = "\n".join(
            f'[{i}] ({s.get("speaker_name") or s.get("speaker_label")}) {_seg_text(s)}'
            for i, s in enumerate(segments)
        )
        base = _parse_dt(context.get("recorded_at"))
        today = base.date().isoformat()

        schema_hint = (
            '{"title": str, "summary": str, '
            '"decisions": [{"text": str, "source_indices": [int]}], '
            '"action_items": [{"owner": str|null, "task": str, "due_date": "YYYY-MM-DD"|null, '
            '"source_indices": [int], "confidence": float}], '
            '"calendar_candidates": [{"title": str, "start_at": ISO8601|null, '
            '"end_at": ISO8601|null, "attendees": [str], "source_indices": [int], "confidence": float}]}'
        )
        prompt = (
            "너는 한국어 회의록 요약 도우미다. 아래 전사를 읽고 회의 요약을 만든다.\n"
            f"오늘 날짜는 {today} 이다. 상대적 날짜(다음 주 수요일 등)는 이 기준으로 절대 날짜로 변환한다.\n"
            "각 항목의 근거가 된 발화는 전사 앞의 [번호]를 source_indices 배열(정수)로 표기한다.\n"
            "반드시 아래 JSON 스키마로만 답하고, 다른 설명은 쓰지 않는다.\n"
            f"스키마: {schema_hint}\n\n"
            f"전사:\n{transcript}"
        )
        req_body = {
            "model": config.OLLAMA_MODEL, "prompt": prompt,
            "stream": False, "format": "json", "options": {"temperature": 0.2},
        }
        # 추론 모델(gemma4/qwen3.5) 제어. 미지원 모델엔 아예 미전송(빈 값).
        if config.OLLAMA_THINK in ("false", "0", "no"):
            req_body["think"] = False
        elif config.OLLAMA_THINK in ("true", "1", "yes"):
            req_body["think"] = True

        req = urllib.request.Request(
            f"{config.OLLAMA_URL}/api/generate",
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json"})

        raw = ""
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                raw = body.get("response", "")
                parsed = self._extract_json(raw)
        except Exception as e:  # noqa: BLE001
            # 파싱 실패해도 저장 가능한 최소 형태로 폴백 (findings #9)
            print(f"[ollama] JSON 파싱 실패, 폴백: {e}")
            return {
                "title": (context.get("title") or "회의") + " 요약",
                "summary": (self._strip_think(raw)[:1500] if raw
                            else "요약 생성에 실패했습니다. 재시도해 주세요."),
                "decisions": [], "action_items": [], "calendar_candidates": [],
                "_raw_model_output": raw,
            }

        return self._normalize(parsed, ids, context)

    @staticmethod
    def _strip_think(text: str) -> str:
        """추론 모델의 <think>...</think> 블록과 코드펜스를 제거."""
        import re
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"```(?:json)?", "", text)
        return text.strip()

    @classmethod
    def _extract_json(cls, raw: str) -> dict:
        """응답에서 JSON 객체만 안전하게 추출(추론 모델 대비)."""
        cleaned = cls._strip_think(raw)
        try:
            return json.loads(cleaned)
        except (ValueError, TypeError):
            pass
        # 첫 '{' ~ 마지막 '}' 구간을 JSON으로 시도
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise ValueError("응답에서 JSON을 찾지 못했습니다.")

    @staticmethod
    def _map_indices(indices, ids):
        out = []
        for x in (indices or []):
            try:
                i = int(x)
            except (ValueError, TypeError):
                continue
            if 0 <= i < len(ids) and ids[i]:
                out.append(ids[i])
        return out

    def _normalize(self, parsed: dict, ids: list, context: dict) -> dict:
        title = parsed.get("title") or ((context.get("title") or "회의") + " 요약")
        result = {
            "title": title,
            "summary": parsed.get("summary", ""),
            "decisions": [], "action_items": [], "calendar_candidates": [],
        }
        for d in parsed.get("decisions", []) or []:
            text = (d.get("text") or "").strip()
            if not text:
                continue
            result["decisions"].append({
                "text": text,
                "source_segment_ids": self._map_indices(d.get("source_indices"), ids),
            })
        for a in parsed.get("action_items", []) or []:
            task = (a.get("task") or "").strip()
            if not task:
                continue
            result["action_items"].append({
                "owner": a.get("owner"), "task": task,
                "due_date": a.get("due_date"),
                "source_segment_ids": self._map_indices(a.get("source_indices"), ids),
                "confidence": a.get("confidence"), "status": "open",
            })
        for c in parsed.get("calendar_candidates", []) or []:
            title = (c.get("title") or "").strip()
            if not title:
                continue
            result["calendar_candidates"].append({
                "title": title, "start_at": c.get("start_at"),
                "end_at": c.get("end_at"), "attendees": c.get("attendees", []) or [],
                "source_segment_ids": self._map_indices(c.get("source_indices"), ids),
                "confidence": c.get("confidence"), "status": "pending",
            })
        return result
