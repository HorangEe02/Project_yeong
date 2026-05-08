"""
에러 발생 이력 합성 데이터 시딩 (v3.4)

201건 에러코드 × 0~8건 = 400~600건 합성 이력 생성
심각도별 복구시간 차등, 교대 분포, 공장 분포 적용
"""

import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from features.equipment.error_history_db import ErrorHistoryDB

# 에러코드 DB에서 코드 목록 로드
import sqlite3

ERROR_DB = Path("data/equipment/error_codes.db")

# 원인 풀 (심각도별)
CAUSE_POOLS = {
    "critical": ["설비 고장", "소재 불량", "금형 파손", "전원 이상", "안전장치 작동"],
    "warning": ["공구 마모", "소재 로트 변경", "설정값 편차", "냉각수 부족", "센서 오작동", "윤활 부족"],
    "info": ["정기 점검 중 발견", "작업자 보고", "일상 점검 이상", "환경 조건 변화"],
}

ACTION_POOLS = {
    "critical": ["긴급 정지 후 수리", "금형 교체", "부품 교체", "전문 업체 출동"],
    "warning": ["공구 교체", "설정값 보정", "냉각수 보충", "센서 교정", "윤활유 주입"],
    "info": ["조건 모니터링", "다음 정기 점검 시 확인", "작업자 교육", "기록 후 경과 관찰"],
}

PLANTS = ["경산본사", "경산본사", "경산본사", "경산본사", "경산본사",
          "경산본사", "경산본사", "경주구어공장", "경주구어공장", "경산제2공장"]

OPERATORS = ["김철수", "이영희", "박민수", "정수진", "최동원",
             "한지영", "오성호", "강미래", "윤대한", "임서연"]


def seed():
    """합성 이력 데이터 생성"""
    if not ERROR_DB.exists():
        print(f"에러코드 DB가 없습니다: {ERROR_DB}")
        return

    db = ErrorHistoryDB()
    conn = sqlite3.connect(str(ERROR_DB))
    conn.row_factory = sqlite3.Row
    codes = conn.execute("SELECT error_code, equipment_type, severity FROM error_codes").fetchall()
    conn.close()

    total = 0
    now = datetime.now()

    for row in codes:
        code = row["error_code"]
        eq_type = row["equipment_type"]
        sev = (row["severity"] or "warning").lower()

        # 심각도별 발생 건수 차등
        if sev == "critical":
            n = random.randint(0, 3)
        elif sev == "warning":
            n = random.randint(1, 6)
        else:
            n = random.randint(2, 8)

        for _ in range(n):
            # 최근 6개월 내 랜덤 발생 시점
            days_ago = random.randint(1, 180)
            occurred = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))

            # 복구 시간 (심각도별 차등)
            if sev == "critical":
                res_min = random.randint(60, 180)
            elif sev == "warning":
                res_min = random.randint(30, 90)
            else:
                res_min = random.randint(10, 30)

            resolved = occurred + timedelta(minutes=res_min)

            # 교대 (주간 60%, 야간 40%)
            shift = "주간" if random.random() < 0.6 else "야간"

            # 원인/조치
            cause_pool = CAUSE_POOLS.get(sev, CAUSE_POOLS["info"])
            action_pool = ACTION_POOLS.get(sev, ACTION_POOLS["info"])

            db.add_record(
                error_code=code,
                equipment_type=eq_type,
                equipment_id=f"{eq_type[:2].upper()}-{random.randint(1,5):03d}",
                occurred_at=occurred.isoformat(),
                resolved_at=resolved.isoformat(),
                resolution_minutes=res_min,
                root_cause=random.choice(cause_pool),
                action_taken=random.choice(action_pool),
                operator_name=random.choice(OPERATORS),
                shift=shift,
                plant=random.choice(PLANTS),
                severity=sev.upper(),
            )
            total += 1

    print(f"에러 이력 시딩 완료: {total}건 생성 ({len(codes)}개 에러코드)")


if __name__ == "__main__":
    seed()
