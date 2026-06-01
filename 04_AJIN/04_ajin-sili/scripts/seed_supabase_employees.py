#!/usr/bin/env python3
"""아진산업 AJIN Supabase employee_embeddings 시드 스크립트.

기본은 --dry-run (통계 출력만, 임베딩·DB 업서트 없음).
--apply 플래그로 실제 Ollama 임베딩 생성 + Supabase 업서트를 실행한다.

사용 예:
    python3 scripts/seed_supabase_employees.py --dry-run
    python3 scripts/seed_supabase_employees.py --apply
    python3 scripts/seed_supabase_employees.py --apply --batch-size=8
    python3 scripts/seed_supabase_employees.py --apply --ollama-url=http://localhost:11434
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass
class Employee:
    id: str
    name: str
    department: str
    position: str
    profile_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 데이터 로딩
# ---------------------------------------------------------------------------

def load_employees(source_path: str | Path) -> list[Employee]:
    """JSON 시드 파일을 읽어 Employee 객체 리스트로 반환.

    Args:
        source_path: employee_seed.json 경로 (절대 또는 repo 루트 기준 상대).

    Returns:
        Employee 리스트.

    Raises:
        ValueError: JSON 형식이 배열이 아닌 경우.
    """
    path = Path(source_path)
    if not path.is_absolute():
        path = ROOT / path

    raw: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"employee_seed.json은 배열이어야 합니다: {path}")

    employees: list[Employee] = []
    for item in raw:
        emp = Employee(
            id=item["id"],
            name=item["name"],
            department=item["department"],
            position=item["position"],
            profile_text=item["profile_text"],
            metadata=item.get("metadata", {}),
        )
        employees.append(emp)

    return employees


# ---------------------------------------------------------------------------
# 임베딩 (Ollama bge-m3, 1024dim)
# ---------------------------------------------------------------------------

async def embed_batch_async(
    texts: list[str],
    ollama_url: str = "http://localhost:11434",
    model: str = "bge-m3",
) -> list[list[float]]:
    """Ollama /api/embed 엔드포인트로 배치 임베딩 생성.

    Args:
        texts: 임베딩할 텍스트 리스트.
        ollama_url: Ollama 서버 URL.
        model: 임베딩 모델명 (기본: bge-m3, 1024차원).

    Returns:
        1024차원 float 리스트의 리스트.

    Raises:
        RuntimeError: Ollama 요청 실패 또는 차원 불일치 시.
    """
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx 패키지가 필요합니다: pip install httpx") from exc

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{ollama_url.rstrip('/')}/api/embed",
            json={"model": model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()

    embeddings: list[list[float]] = data.get("embeddings", [])
    if not embeddings:
        raise RuntimeError(f"Ollama 응답에 embeddings 키가 없습니다: {list(data.keys())}")

    # 차원 검증 — Supabase employee_embeddings_dim_check (embedding_dim = 1024)
    for i, emb in enumerate(embeddings):
        if len(emb) != 1024:
            raise RuntimeError(
                f"임베딩 차원 불일치: texts[{i}]의 차원={len(emb)}, 기대=1024 (bge-m3)"
            )

    return embeddings


def embed_batch_sync(
    texts: list[str],
    ollama_url: str = "http://localhost:11434",
    model: str = "bge-m3",
) -> list[list[float]]:
    """embed_batch_async의 동기 래퍼."""
    return asyncio.run(embed_batch_async(texts, ollama_url, model))


# ---------------------------------------------------------------------------
# Supabase 업서트
# ---------------------------------------------------------------------------

def _mask_secret(value: str) -> str:
    """시크릿 값 마스킹 (앞 8자 + ***)."""
    if not value:
        return "***"
    return value[:8] + "***"


def upsert_employee_embeddings(
    sb_client: Any,
    employees: list[Employee],
    embeddings: list[list[float]],
) -> int:
    """employee_embeddings 테이블에 인원 프로필 + 임베딩을 업서트.

    profile_tsv는 generated always column이므로 직접 입력하지 않는다.
    on_conflict='employee_id'로 기존 레코드 갱신.

    Args:
        sb_client: supabase-py 클라이언트.
        employees: Employee 리스트.
        embeddings: 1024차원 임베딩 리스트 (employees와 길이 동일).

    Returns:
        업서트 성공 행 수.

    Raises:
        ValueError: employees와 embeddings 길이 불일치 시.
    """
    if len(employees) != len(embeddings):
        raise ValueError(
            f"employees({len(employees)})와 embeddings({len(embeddings)}) 길이 불일치"
        )

    rows = [
        {
            "employee_id": emp.id,
            "display_name": emp.name,
            "department": emp.department,
            "position": emp.position,
            "profile_text": emp.profile_text,
            "embedding": embedding,          # list[float] 1024개
            "embedding_model": "bge-m3",
            "embedding_dim": 1024,
            "embedding_version": "v1",
            "metadata": emp.metadata,
            "data_class": "demo",
            "is_active": True,
        }
        for emp, embedding in zip(employees, embeddings)
    ]

    # 배치 16행씩 업서트 (employee_id 충돌 시 전체 컬럼 갱신)
    success_count = 0
    batch_size = 16
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        result = (
            sb_client.table("employee_embeddings")
            .upsert(batch, on_conflict="employee_id")
            .execute()
        )
        if result.data:
            success_count += len(result.data)

    return success_count


# ---------------------------------------------------------------------------
# 통계 헬퍼
# ---------------------------------------------------------------------------

def _dept_stats(employees: list[Employee]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for emp in employees:
        stats[emp.department] = stats.get(emp.department, 0) + 1
    return dict(sorted(stats.items()))


def _position_stats(employees: list[Employee]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for emp in employees:
        stats[emp.position] = stats.get(emp.position, 0) + 1
    return dict(sorted(stats.items()))


def _avg_profile_len(employees: list[Employee]) -> float:
    if not employees:
        return 0.0
    return sum(len(e.profile_text) for e in employees) / len(employees)


def _print_dry_run_summary(employees: list[Employee]) -> None:
    """--dry-run 시 30 rows 통계 출력."""
    print(f"\n  총 인원: {len(employees)}명")
    print(f"  평균 profile_text 길이: {_avg_profile_len(employees):.0f}자")

    print("\n  [부서별 분포]")
    print(f"  {'부서':<15} {'인원':>5}")
    print(f"  {'-'*22}")
    for dept, cnt in _dept_stats(employees).items():
        print(f"  {dept:<15} {cnt:>5}")

    print("\n  [직급별 분포]")
    print(f"  {'직급':<10} {'인원':>5}")
    print(f"  {'-'*17}")
    for pos, cnt in _position_stats(employees).items():
        print(f"  {pos:<10} {cnt:>5}")

    # 페르소나 3명 확인
    persona_ids = {
        "EMP-A-20260301-001": "김민준 (신입·생산기술팀)",
        "EMP-A-20150412-014": "박성훈 (안전관리자·안전환경팀)",
        "EMP-A-20220305-008": "이현아 (품질보증팀·8D Report)",
    }
    print("\n  [페르소나 3명 확인]")
    emp_map = {e.id: e for e in employees}
    for pid, label in persona_ids.items():
        found = pid in emp_map
        status = "OK" if found else "MISSING"
        print(f"  [{status}] {pid} — {label}")

    # 시연 키워드 확인
    keyword_checks = [
        ("EMP-A-20150412-014", "안전관리자", "박성훈 검색 top-1 보장"),
        ("EMP-A-20260301-001", "신입", "신입 사원 검색 매칭"),
        ("EMP-A-20220305-008", "8D Report", "8D Report 담당자 검색 매칭"),
    ]
    print("\n  [시연 키워드 확인]")
    for emp_id, keyword, desc in keyword_checks:
        emp = emp_map.get(emp_id)
        found = emp is not None and keyword in emp.profile_text
        status = "OK" if found else "MISSING"
        print(f"  [{status}] '{keyword}' in {emp_id} — {desc}")


# ---------------------------------------------------------------------------
# 메인 시드 흐름
# ---------------------------------------------------------------------------

def seed_main(args: argparse.Namespace) -> int:
    """시드 메인 흐름.

    Args:
        args: argparse 파싱 결과.

    Returns:
        종료 코드 (0=성공, 1=실패).
    """
    try:
        from tqdm import tqdm
    except ImportError:
        class tqdm:  # type: ignore[no-redef]
            def __init__(self, iterable=None, **kwargs):
                self._it = iter(iterable) if iterable is not None else iter([])
                self.n = 0
                desc = kwargs.get("desc", "")
                total = kwargs.get("total", "?")
                print(f"[진행] {desc} (total={total})")

            def __iter__(self):
                return self

            def __next__(self):
                val = next(self._it)
                self.n += 1
                return val

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def set_postfix_str(self, s: str):
                print(f"  {s}")

    # --- 환경변수 로딩 ---
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    ollama_url = args.ollama_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    if args.apply:
        if not supabase_url:
            print("[오류] SUPABASE_URL 환경변수가 설정되지 않았습니다.", file=sys.stderr)
            return 1
        if not supabase_key:
            print("[오류] SUPABASE_SECRET_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
            return 1
        print(f"[정보] Supabase URL: {supabase_url}")
        print(f"[정보] Supabase KEY: {_mask_secret(supabase_key)}")
        print(f"[정보] Ollama URL:   {ollama_url}")

    # --- 인원 데이터 로딩 ---
    print(f"\n[1/3] 인원 데이터 로딩: {args.source}")
    employees = load_employees(args.source)
    print(f"  로딩 완료: {len(employees)}명")

    _print_dry_run_summary(employees)

    if args.dry_run:
        print("\n[dry-run 완료] --apply 없이 데이터 검증만 수행했습니다.")
        print("  실제 시드를 실행하려면: python3 scripts/seed_supabase_employees.py --apply")
        return 0

    # --- Supabase 클라이언트 생성 ---
    print("\n[2/3] Supabase 클라이언트 초기화")
    try:
        from supabase import create_client
    except ImportError:
        print(
            "[오류] supabase 패키지가 필요합니다: pip install supabase",
            file=sys.stderr,
        )
        return 1

    sb = create_client(supabase_url, supabase_key)
    print("  클라이언트 생성 완료")

    # --- 임베딩 + 업서트 (배치 처리) ---
    print(f"\n[3/3] bge-m3 임베딩 + employee_embeddings 업서트 (batch_size={args.batch_size})")

    all_embeddings: list[list[float]] = []
    texts = [emp.profile_text for emp in employees]
    failed = False

    with tqdm(
        total=len(texts),
        desc="임베딩",
        unit="명",
    ) as pbar:
        for batch_start in range(0, len(texts), args.batch_size):
            batch_texts = texts[batch_start : batch_start + args.batch_size]
            try:
                batch_embs = embed_batch_sync(batch_texts, ollama_url)
                all_embeddings.extend(batch_embs)
                pbar.update(len(batch_texts))
                pbar.set_postfix_str(f"누적={len(all_embeddings)}")
                time.sleep(0.05)  # Ollama 과부하 방지
            except Exception as exc:
                print(f"\n[오류] 임베딩 배치 실패 (start={batch_start}): {exc}", file=sys.stderr)
                failed = True
                break

    if failed:
        print("[실패] 임베딩 생성 중 오류가 발생했습니다.", file=sys.stderr)
        return 1

    if len(all_embeddings) != len(employees):
        print(
            f"[오류] 임베딩 수({len(all_embeddings)}) != 인원 수({len(employees)})",
            file=sys.stderr,
        )
        return 1

    # --- Supabase 업서트 ---
    print(f"\n  employee_embeddings 업서트 중... ({len(employees)}행)")
    try:
        success_count = upsert_employee_embeddings(sb, employees, all_embeddings)
    except Exception as exc:
        print(f"[오류] 업서트 실패: {exc}", file=sys.stderr)
        return 1

    # --- 최종 결과 출력 ---
    print("\n" + "=" * 50)
    print("[시드 완료]")
    print(f"  인원 수:       {len(employees)}명")
    print(f"  임베딩 모델:   bge-m3 (1024dim)")
    print(f"  업서트 성공:   {success_count}행")
    print(f"  data_class:    demo")
    print("=" * 50)

    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="데이터 검증만 수행, 임베딩·DB 업서트 없음 (기본값)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="실제 Ollama 임베딩 + Supabase 업서트 실행",
    )

    parser.add_argument(
        "--source",
        default="data/demo_employees/employee_seed.json",
        help="시드 JSON 경로 (repo 루트 기준, 기본: data/demo_employees/employee_seed.json)",
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Ollama 서버 URL (기본: http://localhost:11434 또는 OLLAMA_BASE_URL 환경변수)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="임베딩 배치 크기 (기본: 16)",
    )

    args = parser.parse_args()

    # --apply 지정 시 dry_run=False
    if args.apply:
        args.dry_run = False

    return args


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(seed_main(parse_args()))
