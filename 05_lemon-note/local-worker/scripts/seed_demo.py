#!/usr/bin/env python3
"""LN 07(실제 빌드 스크린샷) 재캡처용 데모 데이터 시드.

LN 07 은 as-built 대조의 *기준* 이라, 다시 찍을 때 데이터가 달라지면 변경과 무관한
차이가 섞여 비교가 불가능해진다. 그래서 데이터를 재현 가능하게 고정한다.
목표 데이터는 **LN 05·06 목업과 동일** 하다 — 그래야 세 페이지를 나란히 놓고 볼 수 있다.

    docs/design-system-figma.md §8 갱신 절차 3·4

사용:
    DB_BACKEND=sqlite DB_PATH=/tmp/ln07/app.db DATA_ROOT=/tmp/ln07 \
      ASR_PROVIDER=stub SUMMARY_PROVIDER=stub STUB_STAGE_DELAY=0 WRITE_PROTECTED=0 \
      .venv/bin/uvicorn app.main:app --port 8971 &
    python3 scripts/seed_demo.py --base http://127.0.0.1:8971

⚠️ DB 경로 변수는 `DB_PATH` 다(config.py:19). `SQLITE_PATH` 같은 이름을 주면 조용히
무시되고 리포의 `data/app.db` 에 쌓인다 — 실제로 한 번 그렇게 오염시켰다.
시드는 빈 DB 를 전제한다(기존 데이터가 있으면 개수 검사에서 멈춘다).

주의: 프로덕션에는 절대 쓰지 않는다. --base 가 localhost 가 아니면 거부한다.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import uuid

# LN 05 M-01 · LN 06 col-list 와 같은 6건. 순서·길이·날짜까지 맞춘다.
RECORDED_AT = "2026-07-27T14:54:00+09:00"          # LN 05 상세의 "2026.07.27(월) 오후 02:54"
MEETINGS = [
    ("제품 MVP 킥오프", 2_730_000),                 # 45:30
    ("주간 스프린트 리뷰", 1_692_000),              # 28:12
    ("디자인 시스템 정리", 3_760_000),              # 1:02:40
    ("로드맵 우선순위 회의", 965_000),              # 16:05
    ("고객 인터뷰 정리", 3_138_000),                # 52:18
    ("채용 프로세스 논의", 2_027_000),              # 33:47
]
HOTWORDS = "킥오프, 로드맵, 스프린트"


def _multipart(fields, file_field, filename, content):
    """의존성 없이 multipart/form-data 를 만든다(requests 를 쓰지 않기 위해)."""
    boundary = "----seed" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        if v is None:
            continue
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
        out += f"{v}\r\n".encode()
    out += f"--{boundary}\r\n".encode()
    out += (f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\n').encode()
    out += b"Content-Type: audio/wav\r\n\r\n"
    out += content + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def post_job(base, title, duration_ms, audio):
    body, ctype = _multipart(
        {
            "title": title,
            "language": "ko",
            "duration_ms": str(duration_ms),
            "recorded_at": RECORDED_AT,
            "hotwords": HOTWORDS,
            "recording_consent_confirmed": "true",
        },
        "audio_file", "demo.wav", audio,
    )
    req = urllib.request.Request(base + "/v1/jobs", data=body,
                                 headers={"Content-Type": ctype}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8971")
    ap.add_argument("--wait", type=float, default=6.0,
                    help="스텁 파이프라인이 끝나기를 기다리는 초")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    # 프로덕션 사고 방지. 이 스크립트는 데이터를 만들기만 하지만 대상은 로컬로 못박는다.
    if not (base.startswith("http://127.0.0.1") or base.startswith("http://localhost")):
        sys.exit(f"거부: --base 는 localhost 여야 한다 (받은 값: {base})")

    audio = os.urandom(24_000)      # 스텁 ASR 이라 내용은 상관없다. 길이만 있으면 된다.

    for title, dur in MEETINGS:
        code = post_job(base, title, dur, audio)
        print(f"  {code}  {title}  ({dur // 60000}:{dur % 60000 // 1000:02d})")

    print(f"\n스텁 파이프라인 대기 {args.wait}s ...")
    time.sleep(args.wait)

    items = get(base, "/v1/meetings?limit=20").get("items", [])
    print(f"\n생성된 회의 {len(items)}건")
    for m in items:
        print(f"  {m['meeting_id']}  {m['status']:<18} {m['title']}")

    not_ready = [m for m in items if m["status"] != "ready_for_review"]
    if not_ready:
        sys.exit(f"\n실패: {len(not_ready)}건이 ready_for_review 가 아니다. --wait 을 늘려보라.")
    if len(items) != len(MEETINGS):
        sys.exit(f"\n실패: {len(MEETINGS)}건을 기대했는데 {len(items)}건이다(DB 가 비어 있지 않았나?).")
    print("\n완료. LN 07 캡처를 진행할 수 있다.")


if __name__ == "__main__":
    main()
