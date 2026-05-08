"""
설비 종합 대시보드 데이터 집계
- 에러코드/금형/SPC/점검 전체 현황 통합
- 장비유형별 상태 요약
- ML 경고 통합
"""

import sqlite3
from datetime import date, timedelta
from typing import Dict, List
from pathlib import Path


def get_equipment_summary() -> Dict:
    """설비 전체 현황 요약"""
    summary = {
        "error_codes": {"total": 0, "by_type": {}, "critical": 0},
        "molds": {"total": 0, "active": 0, "warning": 0, "critical": 0},
        "spc": {"processes": 0},
        "inspections": {"templates": 0, "recent_records": 0},
        "drawings": {"total": 0},
        "ml_alerts": [],
    }

    # 에러코드
    ec_db = Path("data/equipment/error_codes.db")
    if ec_db.exists():
        try:
            conn = sqlite3.connect(str(ec_db))
            total = conn.execute("SELECT COUNT(*) FROM error_codes").fetchone()[0]
            summary["error_codes"]["total"] = total
            for row in conn.execute(
                "SELECT equipment_type, COUNT(*) FROM error_codes GROUP BY equipment_type"
            ):
                summary["error_codes"]["by_type"][row[0]] = row[1]
            critical = conn.execute(
                "SELECT COUNT(*) FROM error_codes WHERE severity='critical'"
            ).fetchone()[0]
            summary["error_codes"]["critical"] = critical
            conn.close()
        except Exception:
            pass

    # 금형
    mold_db = Path("data/equipment/mold_lifecycle.db")
    if mold_db.exists():
        try:
            conn = sqlite3.connect(str(mold_db))
            conn.row_factory = sqlite3.Row
            molds = conn.execute("SELECT * FROM molds").fetchall()
            conn.close()
            summary["molds"]["total"] = len(molds)
            for m in molds:
                m = dict(m)
                status = m.get("status", "active")
                if status == "active":
                    summary["molds"]["active"] += 1
                shots = m.get("current_shots", 0) or 0
                max_life = m.get("max_shots", m.get("designed_life", 100000)) or 100000
                ratio = shots / max_life * 100 if max_life > 0 else 0
                if ratio >= 95:
                    summary["molds"]["critical"] += 1
                    summary["ml_alerts"].append({
                        "level": "critical",
                        "source": "MOLD",
                        "message": f"{m.get('mold_id', '?')} 수명 {ratio:.0f}% — 즉시 교체 필요",
                    })
                elif ratio >= 80:
                    summary["molds"]["warning"] += 1
                    summary["ml_alerts"].append({
                        "level": "warning",
                        "source": "MOLD",
                        "message": f"{m.get('mold_id', '?')} 수명 {ratio:.0f}% — 교체 준비 필요",
                    })
        except Exception:
            pass

    # SPC
    spc_dir = Path("data/spc_ml")
    if spc_dir.exists():
        summary["spc"]["processes"] = len(list(spc_dir.glob("*.csv")))

    # 도면
    draw_db = Path("data/equipment/drawings.db")
    if draw_db.exists():
        try:
            conn = sqlite3.connect(str(draw_db))
            summary["drawings"]["total"] = conn.execute("SELECT COUNT(*) FROM drawings").fetchone()[0]
            conn.close()
        except Exception:
            pass

    # 점검
    insp_db = Path("data/equipment/inspection.db")
    if insp_db.exists():
        try:
            conn = sqlite3.connect(str(insp_db))
            summary["inspections"]["templates"] = conn.execute(
                "SELECT COUNT(*) FROM inspection_templates"
            ).fetchone()[0]
            try:
                summary["inspections"]["recent_records"] = conn.execute(
                    "SELECT COUNT(*) FROM inspection_records WHERE date >= ?",
                    ((date.today() - timedelta(days=7)).isoformat(),)
                ).fetchone()[0]
            except Exception:
                pass
            conn.close()
        except Exception:
            pass


    return summary


def get_equipment_type_status() -> List[Dict]:
    """장비유형별 상태 카드 데이터"""
    types_info = {
        "프레스": {"icon": "P", "key_metric": "가동률", "color": "#E8A317"},
        "용접기": {"icon": "W", "key_metric": "너겟 품질", "color": "#ff8c00"},
        "로봇": {"icon": "R", "key_metric": "정밀도", "color": "#2196F3"},
        "사출기": {"icon": "I", "key_metric": "사이클 타임", "color": "#4CAF50"},
        "CNC": {"icon": "C", "key_metric": "표면 조도", "color": "#9C27B0"},
        "레이저": {"icon": "L", "key_metric": "출력 안정성", "color": "#ff3b3b"},
        "공통설비": {"icon": "G", "key_metric": "가용성", "color": "#607D8B"},
    }

    # DB에서 실제 에러코드 수 집계
    ec_db = Path("data/equipment/error_codes.db")
    type_counts = {}
    if ec_db.exists():
        try:
            conn = sqlite3.connect(str(ec_db))
            for row in conn.execute(
                "SELECT equipment_type, COUNT(*) FROM error_codes GROUP BY equipment_type"
            ):
                type_counts[row[0]] = row[1]
            conn.close()
        except Exception:
            pass

    result = []
    for eq_type, info in types_info.items():
        result.append({
            "type": eq_type,
            "icon": info["icon"],
            "codes": type_counts.get(eq_type, 0),
            "key_metric": info["key_metric"],
            "color": info["color"],
        })

    return result


def get_ml_status() -> Dict:
    """ML 모델 상태 요약 — 파일 존재 여부로 경량 판단 (모델 초기화 없음)"""
    # 모델 초기화 없이 데이터/모델 파일 존재 여부로 판단 (< 1ms)
    return {
        "intent_classifier": Path("data/intent_ml").exists(),
        "error_tfidf": Path("data/equipment/error_codes.db").exists(),
        "spc_anomaly": Path("data/spc_ml").exists() and any(Path("data/spc_ml").glob("*.csv")),
        "mold_xgboost": Path("data/mold_ml/mold_training_data.csv").exists(),
        "markov": Path("data/markov_ml/event_sequences.json").exists(),
        "doc_quality": True,  # 규칙 기반
        "reg_risk": Path("data/regulation_ml").exists(),
    }
