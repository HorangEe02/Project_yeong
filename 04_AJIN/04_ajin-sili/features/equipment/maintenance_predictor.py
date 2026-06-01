"""v3.3: 수리 이력 기반 예측 정비 엔진

기능:
  1. 기계별 수리 이력 타임스탬프 분석 → MTBF(평균 고장 간격) 계산
  2. 주기별/계절별 고장 패턴 도출
  3. 다음 예상 정비 시점 예측
  4. 정비 주기 요약 대시보드 데이터 생성

데이터: 가상 수리 이력 (seed_maintenance_history)으로 시연
실제 도입 시: IoT 센서 또는 MES 연동으로 실제 데이터 수집
"""
from __future__ import annotations

import sqlite3
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

DB_PATH = Path(__file__).parent.parent.parent / "data" / "equipment" / "maintenance.db"


@dataclass
class MaintenanceRecord:
    """수리 이력 레코드"""
    record_id: int
    machine_id: str
    machine_name: str
    maintenance_type: str     # "고장수리" / "예방정비" / "부품교체"
    description: str
    timestamp: str            # ISO format
    duration_hours: float     # 수리 소요 시간
    cost: float               # 수리 비용 (만원)
    season: str               # "봄" / "여름" / "가을" / "겨울"
    month: int


@dataclass
class MachineMTBF:
    """기계별 MTBF(평균 고장 간격) 분석 결과"""
    machine_id: str
    machine_name: str
    total_repairs: int
    mtbf_days: float                 # 평균 고장 간격 (일)
    mtbf_std_days: float             # 표준편차 (일)
    last_repair_date: str
    next_predicted_date: str         # 예측 다음 정비일
    days_until_next: int             # 남은 일수
    risk_level: str                  # "정상" / "주의" / "긴급"
    seasonal_pattern: dict           # {"봄": 30%, "여름": 25%, ...}
    monthly_pattern: dict            # {1: 5, 2: 3, ...}
    avg_repair_hours: float
    avg_repair_cost: float


@dataclass
class MaintenanceSummary:
    """전체 예측 정비 요약"""
    total_machines: int
    machines_needing_attention: int  # "주의" + "긴급"
    upcoming_7days: list[MachineMTBF]
    upcoming_30days: list[MachineMTBF]
    seasonal_insights: dict          # 현재 계절 주의 사항
    top_cost_machines: list[tuple[str, float]]  # (machine_name, total_cost)


# ═══════════════════════════════════════════════
# DB 초기화 + 가상 데이터 생성
# ═══════════════════════════════════════════════

# 가상 기계 목록
MACHINES = [
    ("MCH-EWP-01", "EWP 조립라인 #1"),
    ("MCH-EWP-02", "EWP 조립라인 #2"),
    ("MCH-CCH-01", "CCH 생산라인"),
    ("MCH-PRS-01", "프레스 #1 (500t)"),
    ("MCH-PRS-02", "프레스 #2 (800t)"),
    ("MCH-PRS-03", "프레스 #3 (1200t)"),
    ("MCH-WLD-01", "용접로봇 #1"),
    ("MCH-WLD-02", "용접로봇 #2"),
    ("MCH-INJ-01", "사출기 #1"),
    ("MCH-INJ-02", "사출기 #2"),
    ("MCH-CNC-01", "CNC 머시닝센터 #1"),
    ("MCH-CNC-02", "CNC 머시닝센터 #2"),
    ("MCH-PAINT-01", "도장라인"),
    ("MCH-CONV-01", "컨베이어 시스템"),
    ("MCH-OBC-01", "OBC 조립라인"),
]

MAINTENANCE_TYPES = ["고장수리", "예방정비", "부품교체"]
DESCRIPTIONS = {
    "고장수리": [
        "모터 과열로 정지", "유압 호스 누유", "센서 오작동", "컨트롤러 리셋 필요",
        "베어링 마모 교체", "전기 접촉 불량", "에어 실린더 고착", "냉각수 순환 불량",
    ],
    "예방정비": [
        "정기 윤활유 교체", "필터 교체", "벨트 장력 조정", "얼라인먼트 점검",
        "볼트 체결력 점검", "전기 절연저항 측정", "안전장치 작동 확인",
    ],
    "부품교체": [
        "유압펌프 교체", "서보모터 교체", "PLC 카드 교체", "터치패널 교체",
        "감속기 교체", "쿨링팬 교체", "리미트스위치 교체",
    ],
}


def _get_season(month: int) -> str:
    if month in (3, 4, 5):
        return "봄"
    elif month in (6, 7, 8):
        return "여름"
    elif month in (9, 10, 11):
        return "가을"
    return "겨울"


def init_maintenance_db():
    """수리 이력 DB 초기화"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_history (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            maintenance_type TEXT NOT NULL,
            description TEXT,
            timestamp TEXT NOT NULL,
            duration_hours REAL DEFAULT 0,
            cost REAL DEFAULT 0,
            season TEXT,
            month INTEGER
        )
    """)
    conn.commit()
    conn.close()


def seed_maintenance_history(force: bool = False):
    """가상 수리 이력 데이터 생성 (2년치)"""
    init_maintenance_db()
    conn = sqlite3.connect(str(DB_PATH))

    existing = conn.execute("SELECT COUNT(*) FROM maintenance_history").fetchone()[0]
    if existing > 0 and not force:
        conn.close()
        return

    if force:
        conn.execute("DELETE FROM maintenance_history")

    random.seed(42)
    base_date = datetime(2024, 4, 1)
    records = []

    for machine_id, machine_name in MACHINES:
        # 기계별 고장 빈도 특성 (일 단위 평균 간격)
        if "PRS" in machine_id:
            mean_interval = 35    # 프레스: 약 5주 간격
            summer_boost = 1.4    # 여름에 고장 증가 (과열)
        elif "WLD" in machine_id:
            mean_interval = 45    # 용접: 약 6주
            summer_boost = 1.2
        elif "EWP" in machine_id:
            mean_interval = 55
            summer_boost = 1.1
        elif "CNC" in machine_id:
            mean_interval = 60
            summer_boost = 1.0
        else:
            mean_interval = 50
            summer_boost = 1.1

        current = base_date + timedelta(days=random.randint(0, 30))

        while current < datetime(2026, 4, 1):
            month = current.month
            season = _get_season(month)

            # 계절 보정
            interval_factor = summer_boost if season == "여름" else 1.0
            if season == "겨울":
                interval_factor = 1.15  # 겨울에도 약간 증가 (저온)

            interval = max(7, int(np.random.normal(
                mean_interval / interval_factor,
                mean_interval * 0.3,
            )))

            current += timedelta(days=interval)
            if current >= datetime(2026, 4, 1):
                break

            # 수리 유형 (고장수리 60%, 예방정비 25%, 부품교체 15%)
            mtype = random.choices(MAINTENANCE_TYPES, weights=[60, 25, 15])[0]
            desc = random.choice(DESCRIPTIONS[mtype])

            # 소요 시간 / 비용
            if mtype == "고장수리":
                duration = round(random.uniform(2, 24), 1)
                cost = round(random.uniform(50, 500), 0)
            elif mtype == "예방정비":
                duration = round(random.uniform(1, 4), 1)
                cost = round(random.uniform(10, 80), 0)
            else:
                duration = round(random.uniform(4, 16), 1)
                cost = round(random.uniform(100, 800), 0)

            records.append((
                machine_id, machine_name, mtype, desc,
                current.isoformat(), duration, cost, season, month,
            ))

    conn.executemany(
        """INSERT INTO maintenance_history
           (machine_id, machine_name, maintenance_type, description,
            timestamp, duration_hours, cost, season, month)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        records,
    )
    conn.commit()
    conn.close()
    return len(records)


# ═══════════════════════════════════════════════
# 분석 엔진
# ═══════════════════════════════════════════════

def analyze_machine_mtbf(machine_id: str) -> Optional[MachineMTBF]:
    """단일 기계의 MTBF 분석"""
    init_maintenance_db()
    seed_maintenance_history()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT * FROM maintenance_history
           WHERE machine_id = ? AND maintenance_type = '고장수리'
           ORDER BY timestamp""",
        (machine_id,),
    ).fetchall()

    if len(rows) < 2:
        conn.close()
        return None

    # MTBF 계산
    timestamps = [datetime.fromisoformat(r["timestamp"]) for r in rows]
    intervals = [(timestamps[i+1] - timestamps[i]).days for i in range(len(timestamps)-1)]

    mtbf = np.mean(intervals)
    mtbf_std = np.std(intervals)

    # 계절별 패턴
    season_counts: dict[str, int] = {"봄": 0, "여름": 0, "가을": 0, "겨울": 0}
    month_counts: dict[int, int] = {m: 0 for m in range(1, 13)}
    for r in rows:
        season_counts[r["season"]] = season_counts.get(r["season"], 0) + 1
        month_counts[r["month"]] = month_counts.get(r["month"], 0) + 1

    total_seasonal = sum(season_counts.values()) or 1
    seasonal_pct = {k: round(v / total_seasonal * 100, 1) for k, v in season_counts.items()}

    # 평균 수리 시간/비용
    all_rows = conn.execute(
        "SELECT * FROM maintenance_history WHERE machine_id = ?", (machine_id,)
    ).fetchall()
    avg_hours = np.mean([r["duration_hours"] for r in all_rows])
    avg_cost = np.mean([r["cost"] for r in all_rows])

    # 다음 예상 정비일
    last_date = timestamps[-1]
    next_date = last_date + timedelta(days=int(mtbf))
    days_until = (next_date - datetime.now()).days

    # 위험도
    if days_until <= 0:
        risk = "긴급"
    elif days_until <= 14:
        risk = "주의"
    else:
        risk = "정상"

    conn.close()

    return MachineMTBF(
        machine_id=machine_id,
        machine_name=rows[0]["machine_name"],
        total_repairs=len(rows),
        mtbf_days=round(mtbf, 1),
        mtbf_std_days=round(mtbf_std, 1),
        last_repair_date=last_date.strftime("%Y-%m-%d"),
        next_predicted_date=next_date.strftime("%Y-%m-%d"),
        days_until_next=days_until,
        risk_level=risk,
        seasonal_pattern=seasonal_pct,
        monthly_pattern=month_counts,
        avg_repair_hours=round(avg_hours, 1),
        avg_repair_cost=round(avg_cost, 0),
    )


def get_all_machine_analysis() -> list[MachineMTBF]:
    """전체 기계 MTBF 분석"""
    results = []
    for machine_id, _ in MACHINES:
        r = analyze_machine_mtbf(machine_id)
        if r:
            results.append(r)
    return sorted(results, key=lambda x: x.days_until_next)


def get_maintenance_summary() -> MaintenanceSummary:
    """전체 예측 정비 요약 대시보드"""
    all_machines = get_all_machine_analysis()

    attention = [m for m in all_machines if m.risk_level in ("주의", "긴급")]
    upcoming_7 = [m for m in all_machines if m.days_until_next <= 7]
    upcoming_30 = [m for m in all_machines if m.days_until_next <= 30]

    # 현재 계절 인사이트
    current_season = _get_season(datetime.now().month)
    season_machines = []
    for m in all_machines:
        if m.seasonal_pattern.get(current_season, 0) > 30:
            season_machines.append(m.machine_name)

    seasonal_insights = {
        "current_season": current_season,
        "high_risk_machines": season_machines,
        "message": f"{current_season}철에 고장 빈도가 높은 설비: {', '.join(season_machines[:5])}" if season_machines
                   else f"{current_season}철 특별 주의 설비 없음",
    }

    # 비용 상위 기계
    init_maintenance_db()
    seed_maintenance_history()
    conn = sqlite3.connect(str(DB_PATH))
    cost_rows = conn.execute(
        """SELECT machine_name, SUM(cost) as total_cost
           FROM maintenance_history GROUP BY machine_id
           ORDER BY total_cost DESC LIMIT 5"""
    ).fetchall()
    conn.close()
    top_cost = [(r[0], r[1]) for r in cost_rows]

    return MaintenanceSummary(
        total_machines=len(all_machines),
        machines_needing_attention=len(attention),
        upcoming_7days=upcoming_7,
        upcoming_30days=upcoming_30,
        seasonal_insights=seasonal_insights,
        top_cost_machines=top_cost,
    )
