"""로그인 이력 데모 데이터 시더.

배경:
  Cloud Run 컨테이너 재시작 시 로컬 SQLite (`data/auth.db`)는 휘발된다.
  관리자 콘솔의 SecurityTab(보안 감사)은 `login_history` 테이블을 시간대 분포·
  최근 이력으로 표시하는데, 부팅 직후 빈 상태이면 그래프와 표가 비어있어
  시연 인상이 약하다.

동작:
  - 환경변수 `AJIN_DEMO_SEED=1` 일 때만 작동 (운영 환경 안전).
  - `login_history` 행 수가 0 이면 데모 데이터 80건 INSERT.
  - 최근 7일에 분산. 09:00~19:00 출근 패턴 (가중치).
  - users 테이블에서 최대 30명 샘플.
  - 5% 는 실패 로그 (보안 알림 패턴 시연 위해).

본 모듈은 lifespan 부팅 시 1회 호출되며, 이후 실로그인이 누적되면 다시 호출돼도
no-op (count > 0).
"""

from __future__ import annotations

import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from core.data_lineage import ensure_lineage_columns, lineage_values

logger = logging.getLogger(__name__)

DEFAULT_AUTH_DB = Path("data/auth.db")


def seed_login_history_if_empty(
    db_path: Path = DEFAULT_AUTH_DB,
    target_rows: int = 80,
) -> int:
    """데모용 login_history 데이터 생성. 운영 보호 위해 ENV 가드 필수.

    Returns:
        INSERT 된 행 수. 0 이면 skip (이미 데이터 있음 / ENV 비활성 / users 부재).
    """
    if os.environ.get("AJIN_DEMO_SEED") != "1":
        return 0

    if not db_path.exists():
        logger.warning("[seed] auth.db not found at %s — skip", db_path)
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_lineage_columns(conn, "login_history")
        count = conn.execute("SELECT COUNT(*) FROM login_history").fetchone()[0]
        if count > 0:
            return 0

        users = conn.execute(
            "SELECT user_id, employee_id FROM users WHERE employee_id IS NOT NULL LIMIT 30"
        ).fetchall()
        if not users:
            logger.warning("[seed] no users in auth.db — skip login_history seed")
            return 0

        now = datetime.now()
        rows: list[tuple] = []
        lineage = lineage_values("synthetic", "demo_login_history", "AJIN_DEMO_SEED")

        # 24-bin hour weights: 00~08 낮음, 09~18 높음, 19~21 중간, 22~23 낮음
        hour_weights = (
            [1] * 9      # 00~08
            + [8] * 10   # 09~18  (출근 시간대)
            + [3] * 3    # 19~21
            + [1] * 2    # 22~23
        )
        hours = list(range(24))

        for _ in range(target_rows):
            uid, emp = random.choice(users)
            days_ago = random.randint(0, 6)
            hour = random.choices(hours, weights=hour_weights)[0]
            minute = random.randint(0, 59)
            ts = now - timedelta(days=days_ago)
            ts = ts.replace(hour=hour, minute=minute, second=random.randint(0, 59))
            success = 0 if random.random() < 0.05 else 1
            ip = f"10.0.{random.randint(0, 5)}.{random.randint(1, 254)}"
            ua = "Mozilla/5.0 (X11; Linux x86_64) AjinDemo/1.0"
            rows.append((
                uid,
                emp,
                "login",
                success,
                ip,
                ua,
                ts.isoformat(timespec="seconds"),
                lineage["data_class"],
                lineage["source_system"],
                lineage["source_label"],
                lineage["source_updated_at"],
            ))

        conn.executemany(
            """INSERT INTO login_history
               (user_id, employee_id, action, success, ip_address, user_agent, timestamp,
                data_class, source_system, source_label, source_updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        logger.info("[seed] login_history 시드 %d rows", len(rows))
        return len(rows)
    except Exception as e:
        logger.warning("[seed] login_history 시드 실패: %s", e)
        return 0
    finally:
        conn.close()
