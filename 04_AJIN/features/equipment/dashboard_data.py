"""
설비 종합 대시보드 데이터 집계
- 에러코드/금형/SPC/점검 전체 현황 통합
- 장비유형별 상태 요약
- ML 경고 통합
"""

import importlib
import sqlite3
from datetime import date, timedelta
from typing import Dict, List
from pathlib import Path

from core.data_lineage import should_include_non_real_data


def _real_where(base: str = "1=1") -> str:
    """Return a WHERE predicate honoring production real-data mode.

    Args:
        base: Existing SQL predicate.

    Returns:
        Predicate that excludes synthetic/demo rows in production mode.
    """
    if should_include_non_real_data():
        return base
    return f"({base}) AND data_class='real'"


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
            total = conn.execute(f"SELECT COUNT(*) FROM error_codes WHERE {_real_where()}").fetchone()[0]
            summary["error_codes"]["total"] = total
            for row in conn.execute(
                f"SELECT equipment_type, COUNT(*) FROM error_codes WHERE {_real_where()} GROUP BY equipment_type"
            ):
                summary["error_codes"]["by_type"][row[0]] = row[1]
            critical_where = _real_where("severity='critical'")
            critical = conn.execute(
                f"SELECT COUNT(*) FROM error_codes WHERE {critical_where}"
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
            molds = conn.execute(f"SELECT * FROM molds WHERE {_real_where()}").fetchall()
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
            summary["drawings"]["total"] = conn.execute(f"SELECT COUNT(*) FROM drawings WHERE {_real_where()}").fetchone()[0]
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
                f"SELECT equipment_type, COUNT(*) FROM error_codes WHERE {_real_where()} GROUP BY equipment_type"
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


def _load_module(module_name: str):
    """Import a Feature F module without initializing model singletons.

    Args:
        module_name: Fully qualified module name.

    Returns:
        Imported module object when dependencies are available, otherwise None.
    """

    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _has_any_file(path: Path, pattern: str) -> bool:
    """Check whether a data directory contains at least one expected artifact.

    Args:
        path: Directory to inspect.
        pattern: Glob pattern for required files.

    Returns:
        True when the directory exists and contains at least one matching file.
    """

    return path.exists() and any(path.glob(pattern))


def get_ml_status() -> Dict:
    """Return deployable status for the 7 Feature F ML/search engines.

    The check intentionally avoids loading model pickles or fitting estimators.
    It verifies that each module can import in the current runtime and that the
    minimal data artifacts needed to execute the public route are present.

    Returns:
        Mapping of stable status keys to readiness booleans.
    """

    ml_search = _load_module("features.equipment.ml_error_search")
    spc_ml = _load_module("features.equipment.spc_ml_predictor")
    mold_ml = _load_module("features.equipment.mold_ml_predictor")
    markov = _load_module("features.equipment.markov_predictor")
    maintenance = _load_module("features.equipment.maintenance_predictor")
    causality = _load_module("features.equipment.error_causality")
    manual_rag = _load_module("features.equipment.manual_rag")

    error_tfidf_ready = ml_search is not None and Path("data/equipment/error_codes.db").exists()
    spc_ready = spc_ml is not None and _has_any_file(Path("data/spc_ml"), "*.csv")

    mold_training = Path("data/mold_ml/mold_training_data.csv").exists()
    mold_cached = Path("data/mold_ml/xgb_mold_life.pkl").exists()
    mold_runtime_can_load_cache = bool(getattr(mold_ml, "XGBOOST_AVAILABLE", False)) if mold_ml else False
    mold_ready = mold_ml is not None and (mold_training or (mold_cached and mold_runtime_can_load_cache))

    markov_ready = markov is not None and (
        Path("data/markov_ml/markov_model.pkl").exists()
        or Path("data/markov_ml/event_sequences.json").exists()
    )
    mtbf_ready = maintenance is not None
    causality_ready = causality is not None and bool(getattr(causality, "CAUSALITY_RULES", None))
    manual_ready = manual_rag is not None and _has_any_file(Path("data/equipment/manuals"), "*")

    return {
        "intent_classifier": Path("data/intent_ml").exists(),
        "error_tfidf": error_tfidf_ready,
        "spc_anomaly": spc_ready,
        "mold_xgboost": mold_ready,
        "markov": markov_ready,
        "rf_mtbf": mtbf_ready,
        "causality": causality_ready,
        "manual_rag": manual_ready,
        # Backward-compatible aliases for older callers.
        "doc_quality": causality_ready,
        "reg_risk": manual_ready,
    }
