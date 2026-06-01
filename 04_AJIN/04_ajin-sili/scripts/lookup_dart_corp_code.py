#!/usr/bin/env python3
"""P4.1 §0 — DART 회사 corp_code 조회.

DART 의 corpCode.xml API 호출 → ZIP 응답 → XML 파싱 → 회사명 부분일치.
조회된 corp_code 를 .env 의 DART_CORP_CODE 에 입력하면 D17 baseline 이
실 재무제표 fetch (confidence=0.75) 로 동작한다.

Usage:
  python3 scripts/lookup_dart_corp_code.py "아진산업"
  python3 scripts/lookup_dart_corp_code.py "AJIN"
  python3 scripts/lookup_dart_corp_code.py "00126380"        # 8자리면 직접 매칭
  python3 scripts/lookup_dart_corp_code.py "아진산업" --write-env  # 1건일 때 .env 자동 갱신
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DART_CORPCODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
ENV_PATH = PROJECT_ROOT / ".env"


# ─────────────────────────────────────────────────────────────
# DART API 호출
# ─────────────────────────────────────────────────────────────


def fetch_corp_code_zip(api_key: str, *, timeout: float = 30.0) -> bytes:
    """corpCode.xml API 호출 → ZIP 바이트 반환.

    DART 응답이 ZIP 이 아닌 JSON(에러) 인 경우는 ValueError 로 raise.
    """
    if not api_key:
        raise ValueError("DART_API_KEY 미설정")
    import httpx
    r = httpx.get(DART_CORPCODE_URL, params={"crtfc_key": api_key}, timeout=timeout)
    r.raise_for_status()
    body = r.content
    # ZIP magic 검증 (응답이 status=403 등의 JSON 인 경우 구분)
    if not body.startswith(b"PK"):
        # JSON 에러 응답 — DART 형식: {"status":"010","message":"..."}
        try:
            import json as _j
            err = _j.loads(body.decode("utf-8", errors="replace"))
            raise ValueError(
                f"DART 에러 status={err.get('status')} message={err.get('message')}"
            )
        except (UnicodeDecodeError, ValueError):
            raise ValueError("DART 응답이 ZIP/JSON 형식이 아님")
    return body


# ─────────────────────────────────────────────────────────────
# XML 파싱
# ─────────────────────────────────────────────────────────────


def parse_corp_code_xml(zip_bytes: bytes) -> list[dict[str, str]]:
    """ZIP 압축 해제 → CORPCODE.xml 파싱 → list of dict.

    각 dict 키: corp_code, corp_name, corp_eng_name, stock_code, modify_date
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        target = next((n for n in names if n.lower().endswith(".xml")), None)
        if not target:
            raise ValueError("ZIP 안에 XML 파일 없음")
        xml_bytes = zf.read(target)

    root = ET.fromstring(xml_bytes)
    out: list[dict[str, str]] = []
    for node in root.findall(".//list"):
        out.append({
            "corp_code": (node.findtext("corp_code") or "").strip(),
            "corp_name": (node.findtext("corp_name") or "").strip(),
            "corp_eng_name": (node.findtext("corp_eng_name") or "").strip(),
            "stock_code": (node.findtext("stock_code") or "").strip(),
            "modify_date": (node.findtext("modify_date") or "").strip(),
        })
    return out


# ─────────────────────────────────────────────────────────────
# 검색
# ─────────────────────────────────────────────────────────────


def search(query: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """회사명·영문명·종목코드 부분 매치 (대소문자 무시).

    query 가 8자리 숫자면 corp_code 직접 매칭.
    """
    q = (query or "").strip()
    if not q:
        return []
    if re.fullmatch(r"\d{8}", q):
        return [r for r in rows if r["corp_code"] == q]
    q_low = q.lower()
    matched: list[dict[str, str]] = []
    for r in rows:
        haystacks = (
            r["corp_name"].lower(),
            r["corp_eng_name"].lower(),
            r["stock_code"],
        )
        if any(q_low in h for h in haystacks):
            matched.append(r)
    # 정확한 회사명 일치를 우선
    matched.sort(key=lambda r: (q_low != r["corp_name"].lower(), r["corp_name"]))
    return matched


# ─────────────────────────────────────────────────────────────
# .env 갱신
# ─────────────────────────────────────────────────────────────


def write_corp_code_to_env(corp_code: str, *, env_path: Path = ENV_PATH) -> bool:
    """`.env` 의 `DART_CORP_CODE=` 라인을 갱신. 라인 없으면 추가.

    이미 동일 값이면 False, 갱신했으면 True.
    """
    if not corp_code:
        return False
    if not env_path.exists():
        env_path.write_text(
            f"DART_CORP_CODE={corp_code}\n", encoding="utf-8",
        )
        return True
    text = env_path.read_text(encoding="utf-8")
    new_line = f"DART_CORP_CODE={corp_code}"
    pattern = re.compile(r"^DART_CORP_CODE=.*$", re.MULTILINE)
    if pattern.search(text):
        if pattern.search(text).group(0) == new_line:
            return False
        new_text = pattern.sub(new_line, text)
    else:
        new_text = text.rstrip() + f"\n{new_line}\n"
    env_path.write_text(new_text, encoding="utf-8")
    return True


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="DART 회사 corp_code 조회")
    parser.add_argument("query", help="회사명·영문명·종목코드 부분일치 (8자리 숫자면 corp_code)")
    parser.add_argument("--limit", type=int, default=20, help="결과 최대 출력 수")
    parser.add_argument("--write-env", action="store_true",
                        help="결과가 1건일 때 .env 의 DART_CORP_CODE 자동 갱신")
    args = parser.parse_args()

    api_key = (os.environ.get("DART_API_KEY") or "").strip()
    if not api_key:
        # .env 에서 직접 읽기 (load_dotenv 부재 환경 대응)
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                if line.startswith("DART_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("ERROR: DART_API_KEY 미설정 — .env 또는 환경변수 확인", file=sys.stderr)
        return 1

    print(f"[fetch] DART corpCode.xml 요청 …", file=sys.stderr)
    try:
        zip_bytes = fetch_corp_code_zip(api_key)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    rows = parse_corp_code_xml(zip_bytes)
    print(f"[parse] 총 {len(rows):,} 회사 적재", file=sys.stderr)

    matches = search(args.query, rows)
    if not matches:
        print(f"매치 결과 없음 — '{args.query}'", file=sys.stderr)
        print(f"힌트: 회사명 일부, 영문명, 또는 8자리 corp_code 로 검색 가능", file=sys.stderr)
        return 3

    # 표 출력
    print(f"\n매치된 회사: {len(matches)}개 (상위 {min(args.limit, len(matches))}개)")
    print(f"{'corp_code':<12} {'corp_name':<24} {'eng_name':<28} {'stock':<8} modify")
    print("-" * 90)
    for r in matches[:args.limit]:
        print(
            f"{r['corp_code']:<12} {r['corp_name'][:22]:<24} "
            f"{r['corp_eng_name'][:26]:<28} {r['stock_code'] or '-':<8} {r['modify_date']}"
        )

    if args.write_env:
        if len(matches) != 1:
            print(f"\n--write-env 는 결과가 정확히 1건일 때만 사용 가능 (현재 {len(matches)}건)",
                  file=sys.stderr)
            return 4
        target = matches[0]
        updated = write_corp_code_to_env(target["corp_code"])
        if updated:
            print(f"\n[ok] .env DART_CORP_CODE={target['corp_code']} ({target['corp_name']}) 갱신 완료",
                  file=sys.stderr)
        else:
            print(f"\n[skip] DART_CORP_CODE 이미 {target['corp_code']} 동일", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
