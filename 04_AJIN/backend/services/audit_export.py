"""v4.7 PR-E6 — SIEM export adapters.

audit.db row → SIEM-호환 포맷 변환:
- Splunk HEC (JSON, RFC-compliant)
- ArcSight CEF (Common Event Format, RFC 5424 syslog)
- IBM QRadar LEEF (Log Event Extended Format) 2.0

각 포맷은 SIEM 사양 준수:
- Splunk JSON: {time, host, source, sourcetype, event: {...}}
- CEF: "CEF:0|Vendor|Product|Version|SignatureID|Name|Severity|Extension"
- LEEF: "LEEF:2.0|Vendor|Product|Version|EventID|Delim|Extension"
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

VENDOR = "AJIN"
PRODUCT = "AI-Assistant"
VERSION = "4.7"


def to_siem_json(rows: Iterable[dict]) -> list[dict]:
    """audit row → Splunk HEC JSON list."""
    out = []
    for r in rows:
        out.append({
            "time": r.get("ts") or r.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "host": r.get("host", "ajin-backend"),
            "source": "ajin.audit_log",
            "sourcetype": "ajin:api_audit",
            "event": {
                "actor": r.get("actor") or r.get("employee_id"),
                "action": r.get("action") or r.get("endpoint"),
                "target": r.get("target") or r.get("detail"),
                "result": r.get("result") or r.get("status_code"),
                "ip": r.get("ip_address"),
                "user_agent": r.get("user_agent"),
                "metadata": r.get("metadata"),
            },
        })
    return out


def to_cef(rows: Iterable[dict]) -> list[str]:
    """audit row → ArcSight CEF lines."""
    out = []
    for r in rows:
        severity = _severity_to_cef(r.get("severity", "info"))
        action = r.get("action") or r.get("endpoint") or "unknown"
        ext = _cef_extension({
            "src": r.get("ip_address", ""),
            "suser": r.get("actor") or r.get("employee_id") or "",
            "act": action,
            "outcome": str(r.get("result") or r.get("status_code") or ""),
            "duser": r.get("target") or r.get("detail") or "",
            "rt": str(_to_ms_epoch(r.get("ts") or r.get("timestamp"))),
        })
        line = f"CEF:0|{VENDOR}|{PRODUCT}|{VERSION}|{action}|{action}|{severity}|{ext}"
        out.append(line)
    return out


def to_leef(rows: Iterable[dict]) -> list[str]:
    """audit row → IBM QRadar LEEF 2.0 lines."""
    out = []
    for r in rows:
        delim = "^"  # LEEF 2.0 tab-safe custom delimiter
        action = r.get("action") or r.get("endpoint") or "unknown"
        ext_pairs = {
            "devTime": _to_iso(r.get("ts") or r.get("timestamp")),
            "src": r.get("ip_address", ""),
            "usrName": r.get("actor") or r.get("employee_id") or "",
            "action": action,
            "outcome": str(r.get("result") or r.get("status_code") or ""),
            "target": r.get("target") or r.get("detail") or "",
        }
        ext = delim.join(f"{k}={v}" for k, v in ext_pairs.items() if v is not None)
        line = f"LEEF:2.0|{VENDOR}|{PRODUCT}|{VERSION}|{action}|{delim}|{ext}"
        out.append(line)
    return out


# ── Helpers ──────────────────────────────────────────────────────────────────

def _severity_to_cef(level: str) -> int:
    """info=3, warning=6, error=7, critical=9. CEF severity 0-10 scale."""
    return {"info": 3, "warning": 6, "error": 7, "critical": 9}.get(level.lower(), 3)


def _cef_extension(pairs: dict) -> str:
    """CEF extension key=value 페어. = 와 | 는 escape (\\=, \\|)."""
    parts = []
    for k, v in pairs.items():
        if v is None or v == "":
            continue
        v_escaped = (
            str(v)
            .replace("\\", "\\\\")
            .replace("=", "\\=")
            .replace("|", "\\|")
            .replace("\n", "\\n")
        )
        parts.append(f"{k}={v_escaped}")
    return " ".join(parts)


def _to_ms_epoch(ts) -> int:
    """ISO 문자열 또는 datetime → millisecond epoch. 변환 불가 시 0."""
    if ts is None:
        return 0
    if isinstance(ts, (int, float)):
        return int(ts * 1000)
    if isinstance(ts, datetime):
        return int(ts.timestamp() * 1000)
    try:
        # ISO 문자열 파싱 — 후미 Z 처리
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return 0


def _to_iso(ts) -> str:
    """ts → ISO 8601 문자열. 변환 불가 시 현재 UTC."""
    if ts is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(ts, datetime):
        return ts.isoformat()
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    s = str(ts).strip()
    if not s:
        return datetime.now(timezone.utc).isoformat()
    return s
