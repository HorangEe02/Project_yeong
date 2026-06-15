"""Day 6 Phase 1 — 설비/공정 AI (Module F) FastAPI 라우터.

features/equipment/* 19 모듈을 12 엔드포인트로 노출.
- Nelson 8 Rules SPC (#5 본선 평가)
- ML 7종 (#2 본선 평가)
- Markov + XGBoost + MTBF + Manual RAG

옵션 B (RTDB push): 백엔드는 위반 데이터만 반환, Frontend 가 RTDB 푸시 + 토스트.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.dependencies import get_current_user, resolve_user_role_level
from backend.schemas.equipment import (
    CategoryGroup,
    CausalityInfo,
    CascadeChainItem,
    CascadeStep,
    ChecklistItem,
    ChecklistTemplate,
    DashboardMetrics,
    EquipmentTypeCard,
    ErrorCategoriesResponse,
    ErrorSearchRequest,
    ErrorSearchResponse,
    ErrorSearchResult,
    InspectionChecklistResponse,
    ManualExcerpt,
    ManualSearchRequest,
    ManualSearchResponse,
    MarkovPrediction,
    MarkovResponse,
    MLAlert,
    MLEngineStatus,
    MLEnginesStatusResponse,
    MoldItem,
    MoldsResponse,
    MTBFItem,
    MTBFResponse,
    MTBFTopCost,
    NelsonViolationItem,
    OverviewResponse,
    ProcessHealthCard,
    RecentViolation,
    SPCData,
    SPCResponse,
    SPCUploadResponse,
    ViolationsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/equipment", tags=["equipment"])


# ═══════════════════════════════════════════════════════════
# 헬퍼 — features/equipment 모듈 lazy import + 폴백
# ═══════════════════════════════════════════════════════════


def _safe_import(module_path: str) -> Any:
    """features.equipment.* 를 lazy import. 실패 시 None."""
    try:
        import importlib

        return importlib.import_module(module_path)
    except Exception as e:
        logger.warning(f"[equipment] {module_path} import 실패: {e}")
        return None


EQUIPMENT_DEPARTMENT_KEYWORDS = ("생산", "품질", "자동화", "금형", "안전")


def _equipment_role_level(user: Any) -> int:
    """Resolve a numeric role level from user context.

    Args:
        user: Authenticated user context from JWT/cookie auth.

    Returns:
        int: Resolved RBAC level. Unknown roles fail closed to level 0.
    """
    return resolve_user_role_level(user)


def _is_equipment_department(user: Any) -> bool:
    """Return whether the user belongs to an equipment-facing department.

    Args:
        user: Authenticated user context.

    Returns:
        bool: True when the user's department is in the Feature F release scope.
    """
    department = str(getattr(user, "department", "") or "")
    return any(keyword in department for keyword in EQUIPMENT_DEPARTMENT_KEYWORDS)


def require_equipment_access(min_level: int = 1):
    """Require Feature F department scope and minimum role level.

    Args:
        min_level: Minimum numeric role level required for the endpoint.

    Returns:
        Callable dependency that returns the authenticated user.

    Raises:
        HTTPException: 403 when the user is outside the equipment domain or below
            the required level. Level 4+ users are allowed across departments.
    """

    async def _check(user=Depends(get_current_user)):
        role_level = _equipment_role_level(user)
        if role_level >= 4:
            return user
        if role_level < min_level:
            raise HTTPException(status_code=403, detail=f"role_level >= {min_level} required")
        if not _is_equipment_department(user):
            raise HTTPException(status_code=403, detail="equipment_department_required")
        return user

    return _check


def _feature_f_data_class(value: Any, default: str = "unknown") -> str:
    """Normalize Feature F lineage to real/synthetic/system/unknown.

    Args:
        value: Candidate data class from DB, file metadata, or DTO.
        default: Fallback data class when ``value`` is empty.

    Returns:
        One of ``real``, ``synthetic``, ``system``, or ``unknown``.
    """
    normalized = str(value or default or "unknown").strip().lower()
    if normalized == "demo":
        return "synthetic"
    if normalized in {"real", "synthetic", "system", "unknown"}:
        return normalized
    return "unknown"


def _source_value(source: Mapping[str, Any] | Any, key: str, default: str = "") -> str:
    """Read a lineage value from a dict or object.

    Args:
        source: Mapping or object containing lineage attributes.
        key: Field or attribute name.
        default: Fallback value.

    Returns:
        String value for the requested key.
    """
    if isinstance(source, Mapping):
        return str(source.get(key) or default)
    return str(getattr(source, key, default) or default)


def _lineage_kwargs(
    source: Mapping[str, Any] | Any,
    *,
    default_data_class: str = "unknown",
    default_source_system: str = "unknown",
    default_source_label: str = "",
) -> dict[str, str]:
    """Return response lineage fields for Feature F DTOs.

    Args:
        source: Mapping or object containing lineage values.
        default_data_class: Fallback data class.
        default_source_system: Fallback source system.
        default_source_label: Fallback source label.

    Returns:
        Dict with ``data_class``, ``source_system``, and ``source_label``.
    """
    source_system = _source_value(source, "source_system", default_source_system) or default_source_system
    return {
        "data_class": _feature_f_data_class(
            _source_value(source, "data_class", default_data_class),
            default_data_class,
        ),
        "source_system": source_system or "unknown",
        "source_label": _source_value(source, "source_label", default_source_label) or default_source_label,
    }


# 5공정 디스플레이 메타 (DAY6_7_PLAN Section 7-1) — process_id 는 spc_ml CSV 와 일치.
PROCESS_DISPLAY_MAP = {
    "ewp_housing_bore": {"slug": "cch", "name": "EWP 하우징 내경"},
    "cch_plate_thickness": {"slug": "cch_plate", "name": "CCH 냉각플레이트"},
    "obc_case_flatness": {"slug": "obc", "name": "OBC 케이스 평탄도"},
    "bumper_nugget_diameter": {"slug": "bumper_beam", "name": "범퍼빔 너겟 직경"},
    "seatrail_hole_position": {"slug": "ball_seat", "name": "시트레일 홀 위치도"},
}


def _resolve_process_id(slug_or_id: str) -> Optional[str]:
    """slug ('cch', 'obc' 등) 또는 process_id 직접 모두 허용."""
    if slug_or_id in PROCESS_DISPLAY_MAP:
        return slug_or_id
    for proc_id, meta in PROCESS_DISPLAY_MAP.items():
        if meta["slug"] == slug_or_id:
            return proc_id
    # 표준 5 슬러그 추가 매핑 (DAY6_7_PLAN Section 7-1)
    slug_aliases = {
        "cch": "cch_plate_thickness",
        "obc": "obc_case_flatness",
        "bumper_beam": "bumper_nugget_diameter",
        "door": "ewp_housing_bore",  # 도어 — EWP 하우징 으로 매핑
        "ball_seat": "seatrail_hole_position",
    }
    return slug_aliases.get(slug_or_id)


# ═══════════════════════════════════════════════════════════
# 1. GET /equipment/dashboard/overview
# ═══════════════════════════════════════════════════════════


@router.get("/dashboard/overview", response_model=OverviewResponse)
async def overview(_user=Depends(require_equipment_access(1))):
    """5공정 건강 + 7장비 + 핵심 메트릭 + ML 알림."""
    del _user
    # 5공정 건강 — features.equipment.spc_dashboard
    processes: list[ProcessHealthCard] = []
    spc_dashboard = _safe_import("features.equipment.spc_dashboard")
    if spc_dashboard is not None:
        try:
            dashboard = spc_dashboard.SPCDashboard()
            health_list = dashboard.get_all_process_health()
            for h in health_list:
                slug = PROCESS_DISPLAY_MAP.get(h.process_id, {}).get("slug", h.process_id)
                processes.append(ProcessHealthCard(
                    process_id=slug,
                    process_name=h.process_name,
                    status=h.status,
                    current_cpk=h.current_cpk,
                    cpk_trend=h.cpk_trend,
                    violation_count=h.violation_count,
                    violated_rules=h.violated_rules,
                    risk_level=h.risk_level,
                    anomaly_rate=h.anomaly_rate,
                    **_lineage_kwargs(
                        h,
                        default_data_class="synthetic",
                        default_source_system="seed_equipment",
                        default_source_label="spc_dashboard",
                    ),
                ))
        except Exception as e:
            logger.warning(f"[overview] spc_dashboard 실패: {e}")

    # 5공정 폴백 — 모듈 부재 / 데이터 부재 시 mock
    if not processes:
        for proc_id, meta in PROCESS_DISPLAY_MAP.items():
            processes.append(ProcessHealthCard(
                process_id=meta["slug"],
                process_name=meta["name"],
                status="good",
                current_cpk=1.40,
                cpk_trend="stable",
                violation_count=0,
                violated_rules=[],
                risk_level="normal",
                anomaly_rate=0.0,
                data_class="synthetic",
                source_system="seed_equipment",
                source_label="overview_fallback",
            ))

    # 7장비 + 메트릭 + ML 알림 — features.equipment.dashboard_data
    equipment_types: list[EquipmentTypeCard] = []
    metrics = DashboardMetrics()
    ml_alerts: list[MLAlert] = []

    dashboard_data = _safe_import("features.equipment.dashboard_data")
    if dashboard_data is not None:
        try:
            type_cards = dashboard_data.get_equipment_type_status()
            for c in type_cards:
                equipment_types.append(EquipmentTypeCard(
                    **{
                        **c,
                        **_lineage_kwargs(
                            c,
                            default_data_class="synthetic",
                            default_source_system="seed_equipment",
                            default_source_label="equipment_type_status",
                        ),
                    }
                ))
        except Exception as e:
            logger.warning(f"[overview] equipment_type_status 실패: {e}")

        try:
            summary = dashboard_data.get_equipment_summary()
            metrics = DashboardMetrics(
                error_codes_total=summary["error_codes"]["total"],
                error_codes_critical=summary["error_codes"]["critical"],
                molds_total=summary["molds"]["total"],
                molds_warning=summary["molds"]["warning"],
                molds_critical=summary["molds"]["critical"],
                spc_processes=summary["spc"]["processes"],
                inspections_templates=summary["inspections"]["templates"],
                inspections_recent=summary["inspections"]["recent_records"],
            )
            for a in summary.get("ml_alerts", []):
                ml_alerts.append(MLAlert(
                    **{
                        **a,
                        **_lineage_kwargs(
                            a,
                            default_data_class="system",
                            default_source_system="equipment_summary",
                            default_source_label="ml_alert",
                        ),
                    }
                ))
        except Exception as e:
            logger.warning(f"[overview] equipment_summary 실패: {e}")

    # 7장비 폴백 — 모듈 부재 시 7개 카드 mock
    if not equipment_types:
        for typ, info in [
            ("프레스", ("P", "가동률", "#E8A317")),
            ("용접기", ("W", "너겟 품질", "#ff8c00")),
            ("로봇", ("R", "정밀도", "#2196F3")),
            ("사출기", ("I", "사이클 타임", "#4CAF50")),
            ("CNC", ("C", "표면 조도", "#9C27B0")),
            ("레이저", ("L", "출력 안정성", "#ff3b3b")),
            ("공통설비", ("G", "가용성", "#607D8B")),
        ]:
            equipment_types.append(EquipmentTypeCard(
                type=typ,
                icon=info[0],
                codes=0,
                key_metric=info[1],
                color=info[2],
                data_class="synthetic",
                source_system="seed_equipment",
                source_label="equipment_type_fallback",
            ))

    return OverviewResponse(
        processes=processes,
        equipment_types=equipment_types,
        metrics=metrics,
        ml_alerts=ml_alerts,
    )


# ═══════════════════════════════════════════════════════════
# 1-B. GET /equipment/headline — Daily Headline (W8)
# 데일리 헤드라인: 공장장 시점 1줄 요약. LLM 호출 없음 — overview 집계 가공.
# ═══════════════════════════════════════════════════════════


class HeadlineItem(BaseModel):
    severity: str = "normal"  # critical | warning | normal
    label: str = ""
    detail: str = ""
    target_module: str = ""   # 'spc' | 'predictive' | 'alerts' | ''
    target_id: str = ""
    data_class: str = "system"
    source_system: str = "equipment_summary"
    source_label: str = "daily_headline"


class HeadlineResponse(BaseModel):
    generated_at: str
    summary: str
    items: list[HeadlineItem]
    active_alarm_count: int = 0


@router.get("/headline", response_model=HeadlineResponse)
async def daily_headline(_user=Depends(require_equipment_access(1))):
    """오늘의 위험 신호 1줄 요약 카드."""
    del _user
    from datetime import datetime

    ov = await overview()
    items: list[HeadlineItem] = []

    # 최저 Cpk 공정 1개
    worst_proc = None
    for p in ov.processes:
        if worst_proc is None or (p.current_cpk or 9.99) < (worst_proc.current_cpk or 9.99):
            worst_proc = p
    if worst_proc:
        sev = "critical" if (worst_proc.current_cpk or 0) < 1.0 else (
            "warning" if (worst_proc.current_cpk or 0) < 1.33 else "normal"
        )
        items.append(HeadlineItem(
            severity=sev,
            label=f"{worst_proc.process_name} · Cpk {worst_proc.current_cpk:.2f}",
            detail=(
                f"위반 {worst_proc.violation_count}건"
                + (f" (Rule {','.join(str(r) for r in worst_proc.violated_rules[:3])})"
                   if worst_proc.violated_rules else "")
            ),
            target_module="spc",
            target_id=worst_proc.process_id,
        ))

    # 위험 금형 — overview 메트릭 활용
    metrics = ov.metrics
    if metrics.molds_critical > 0:
        items.append(HeadlineItem(
            severity="critical",
            label=f"금형 critical {metrics.molds_critical}대",
            detail=f"warning {metrics.molds_warning}대 · 총 {metrics.molds_total}대",
            target_module="predictive",
        ))
    elif metrics.molds_warning > 0:
        items.append(HeadlineItem(
            severity="warning",
            label=f"금형 warning {metrics.molds_warning}대",
            detail=f"총 {metrics.molds_total}대 중 교체 임박",
            target_module="predictive",
        ))

    # 활성 ML 알림
    crit_alerts = [a for a in ov.ml_alerts if getattr(a, "severity", "") == "critical"]
    warn_alerts = [a for a in ov.ml_alerts if getattr(a, "severity", "") == "warning"]
    alarm_count = len(crit_alerts) + len(warn_alerts)
    if crit_alerts:
        a = crit_alerts[0]
        items.append(HeadlineItem(
            severity="critical",
            label=getattr(a, "title", "ML 알림"),
            detail=getattr(a, "message", ""),
            target_module="alerts",
        ))

    # 한 줄 요약 — 첫 3개를 콤마로 연결
    if items:
        summary = " · ".join(f"{i.label}" for i in items[:3])
    else:
        summary = "모든 라인 정상 — Cpk 평균 1.4 이상, 위험 금형 없음"

    return HeadlineResponse(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        summary=summary,
        items=items,
        active_alarm_count=alarm_count,
    )


# ═══════════════════════════════════════════════════════════
# 2. GET /equipment/spc/{process_id}
# ═══════════════════════════════════════════════════════════


@router.get("/spc/{process_id}", response_model=SPCResponse)
async def spc_chart(process_id: str, _user=Depends(require_equipment_access(1))):
    """SPC 관리도 데이터 + Nelson 8 Rules 위반."""
    del _user
    full_id = _resolve_process_id(process_id)
    if full_id is None:
        raise HTTPException(status_code=404, detail=f"공정 '{process_id}' 가 존재하지 않습니다.")

    # 데이터 로드
    import pandas as pd
    from pathlib import Path

    csv_path = Path("data/spc_ml") / f"{full_id}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"SPC 데이터 파일이 없습니다: {full_id}.csv")

    try:
        df = pd.read_csv(csv_path)
        values = df["value"].astype(float).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SPC 데이터 로드 실패: {e}")

    # PROCESS_SPECS — scripts.generate_spc_ml_data
    spec: dict[str, Any] = {}
    try:
        from scripts.generate_spc_ml_data import PROCESS_SPECS  # type: ignore

        spec = PROCESS_SPECS.get(full_id, {})
    except Exception:
        spec = {}

    usl = spec.get("usl")
    lsl = spec.get("lsl")
    proc_name = spec.get("name", PROCESS_DISPLAY_MAP.get(full_id, {}).get("name", full_id))

    # Nelson 8 Rules 분석 — features.equipment.spc_realtime
    spc_realtime = _safe_import("features.equipment.spc_realtime")
    violations: list[NelsonViolationItem] = []
    out_of_control = False
    violation_count = 0

    mean = sum(values) / len(values) if values else 0.0
    import statistics

    sigma = statistics.stdev(values) if len(values) > 1 else 1e-10
    if sigma == 0:
        sigma = 1e-10
    ucl = mean + 3 * sigma
    lcl = mean - 3 * sigma

    if spc_realtime is not None and len(values) >= 10:
        try:
            result = spc_realtime.analyze_nelson_rules(
                values, spec_upper=usl, spec_lower=lsl, process_name=proc_name,
            )
            mean = result.mean
            sigma = result.std if result.std > 0 else 1e-10
            ucl = result.ucl
            lcl = result.lcl
            out_of_control = result.out_of_control
            violation_count = result.violation_count

            for v in result.violations:
                guide = spc_realtime.get_rule_guide(v.rule_number)
                violations.append(NelsonViolationItem(
                    rule_number=v.rule_number,
                    rule_name=v.rule_name,
                    description=v.description,
                    severity=v.severity,
                    points=v.violating_indices,
                    recommended_action=v.recommended_action,
                    chart_annotation=guide.get("chart_annotation", ""),
                    data_class="synthetic",
                    source_system="seed_equipment",
                    source_label="spc_csv",
                ))
        except Exception as e:
            logger.warning(f"[spc] Nelson 분석 실패: {e}")

    n = len(values)
    timestamps = list(range(n))

    data = SPCData(
        process_id=process_id,
        process_name=proc_name,
        timestamps=timestamps,
        values=values,
        mean=round(mean, 6),
        sigma=round(sigma, 6),
        ucl=round(ucl, 6),
        lcl=round(lcl, 6),
        sigma_1_upper=round(mean + sigma, 6),
        sigma_1_lower=round(mean - sigma, 6),
        sigma_2_upper=round(mean + 2 * sigma, 6),
        sigma_2_lower=round(mean - 2 * sigma, 6),
        usl=usl,
        lsl=lsl,
        data_class="synthetic",
        source_system="seed_equipment",
        source_label=str(csv_path),
    )

    return SPCResponse(
        data=data,
        violations=violations,
        out_of_control=out_of_control,
        violation_count=violation_count,
    )


# ═══════════════════════════════════════════════════════════
# 3. GET /equipment/spc/violations/recent
# ═══════════════════════════════════════════════════════════


@router.get("/spc/violations/recent", response_model=ViolationsResponse)
async def spc_violations_recent(
    since_ts: int = 0,
    limit: int = 20,
    _user=Depends(require_equipment_access(1)),
):
    """최근 SPC 위반 — Frontend 5초 폴링용 (옵션 B).

    since_ts (ms epoch) 이후 발생 위반만 반환.
    위반은 5공정 모두 분석하여 가장 최근 N개를 timestamp 내림차순 반환.
    """
    del _user
    items: list[RecentViolation] = []
    spc_realtime = _safe_import("features.equipment.spc_realtime")
    if spc_realtime is None:
        return ViolationsResponse(items=[], total=0)

    import pandas as pd
    from pathlib import Path

    now_ms = int(time.time() * 1000)

    for full_id, meta in PROCESS_DISPLAY_MAP.items():
        csv_path = Path("data/spc_ml") / f"{full_id}.csv"
        if not csv_path.exists():
            continue
        try:
            df = pd.read_csv(csv_path)
            values = df["value"].astype(float).tolist()
            if len(values) < 10:
                continue
            result = spc_realtime.analyze_nelson_rules(
                values, process_name=meta["name"]
            )
            for v in result.violations:
                vid = f"{full_id}_R{v.rule_number}_{v.violating_indices[0] if v.violating_indices else 0}"
                items.append(RecentViolation(
                    id=vid,
                    process_id=meta["slug"],
                    process_name=meta["name"],
                    rule_number=v.rule_number,
                    severity=v.severity,
                    message=f"{meta['name']} · Rule {v.rule_number} {v.rule_name}",
                    timestamp=now_ms,
                    data_class="synthetic",
                    source_system="seed_equipment",
                    source_label="spc_csv",
                ))
        except Exception as e:
            logger.warning(f"[spc/violations] {full_id} 분석 실패: {e}")

    # since_ts 필터 — 데이터가 정적이라 since_ts 가 0 이면 모두 반환,
    # 아니면 최초 1회만 반환 후 빈 리스트 (mock 흐름).
    if since_ts > 0 and now_ms - since_ts < 60_000:
        # 1분 이내 재요청 — 새 위반 없다고 응답 (폴링 차단)
        items = []

    items.sort(key=lambda x: (x.severity != "critical", -x.timestamp))
    items = items[:limit]
    return ViolationsResponse(items=items, total=len(items))


# ═══════════════════════════════════════════════════════════
# 4. POST /equipment/error/search
# ═══════════════════════════════════════════════════════════


@router.post("/error/search", response_model=ErrorSearchResponse)
async def error_search(req: ErrorSearchRequest, _user=Depends(require_equipment_access(1))):
    """ML TF-IDF 에러 검색 + 인과 + 매뉴얼 인용 (Phase 4 사용)."""
    del _user
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query 가 비어 있습니다.")

    results: list[ErrorSearchResult] = []
    causality: Optional[CausalityInfo] = None
    manual_excerpts: list[ManualExcerpt] = []

    ml_search = _safe_import("features.equipment.ml_error_search")
    if ml_search is not None:
        try:
            raw = ml_search.ml_search_error_codes(
                req.query, top_k=req.top_k, equipment_filter=req.equipment_filter,
            )
            for r in raw:
                results.append(ErrorSearchResult(
                    code=r.get("code", ""),
                    equipment_type=r.get("equipment_type", ""),
                    category=r.get("category", ""),
                    description=r.get("description", ""),
                    cause=r.get("cause", ""),
                    action=r.get("action", ""),
                    severity=r.get("severity", "warning"),
                    score=r.get("score", 0.0),
                    rank=r.get("rank", 0),
                    **_lineage_kwargs(
                        r,
                        default_data_class="synthetic",
                        default_source_system="seed_equipment",
                        default_source_label="error_code_db",
                    ),
                ))
        except Exception as e:
            logger.warning(f"[error_search] ML 검색 실패: {e}")

    # 인과 규칙 (TOP-1)
    if results:
        ec = _safe_import("features.equipment.error_causality")
        if ec is not None:
            try:
                rules = ec.CAUSALITY_RULES.get(results[0].category, [])
                if rules:
                    causality = CausalityInfo(
                        causes=[r[0] for r in rules[:3]],
                        actions=[results[0].action] if results[0].action else [],
                    )
            except Exception:
                pass

    # 매뉴얼 인용 (옵션 — ChromaDB 부재 시 빈 리스트)
    manual_rag = _safe_import("features.equipment.manual_rag")
    if manual_rag is not None:
        try:
            rag = manual_rag.ManualRAG()
            excerpts = rag.search(req.query, n_results=2)
            for ex in excerpts:
                meta = ex.get("metadata", {}) or {}
                manual_excerpts.append(ManualExcerpt(
                    content=ex.get("content", "")[:600],
                    source=meta.get("source", ""),
                    page=str(meta.get("page", "")),
                    relevance=ex.get("relevance", 0.0),
                    **_lineage_kwargs(
                        meta,
                        default_data_class="synthetic",
                        default_source_system="seed_equipment",
                        default_source_label=str(meta.get("source", "") or "manual_rag"),
                    ),
                ))
        except Exception:
            pass

    return ErrorSearchResponse(
        results=results,
        causality=causality,
        manual_excerpts=manual_excerpts,
    )


# ═══════════════════════════════════════════════════════════
# 5. GET /equipment/error/categories
# ═══════════════════════════════════════════════════════════


@router.get("/error/categories", response_model=ErrorCategoriesResponse)
async def error_categories(_user=Depends(require_equipment_access(1))):
    """39 동의어 + 카테고리 — Phase 5 매뉴얼 RAG 증상 가이드."""
    del _user
    ml_search = _safe_import("features.equipment.ml_error_search")
    groups: list[CategoryGroup] = []
    total = 0

    if ml_search is not None:
        try:
            for eq_type, symptoms in ml_search.EQUIPMENT_SYMPTOM_CATEGORIES.items():
                groups.append(CategoryGroup(equipment_type=eq_type, symptoms=symptoms))
                total += len(symptoms)
        except Exception as e:
            logger.warning(f"[error/categories] 실패: {e}")

    return ErrorCategoriesResponse(groups=groups, total_synonyms=total)


# ═══════════════════════════════════════════════════════════
# 6. GET /equipment/markov/{error_code}
# ═══════════════════════════════════════════════════════════


@router.get("/markov/{error_code}", response_model=MarkovResponse)
async def markov_chain(
    error_code: str,
    depth: int = 3,
    _user=Depends(require_equipment_access(1)),
):
    """Markov 연쇄 트리 (Phase 4)."""
    del _user
    markov = _safe_import("features.equipment.markov_predictor")
    if markov is None:
        raise HTTPException(status_code=503, detail="Markov 예측기를 사용할 수 없습니다.")

    try:
        predictor = markov.get_markov_predictor()
        analysis = predictor.predict_next(error_code, top_k=5)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"학습 시퀀스 부재: {e}")
    except Exception as e:
        logger.exception("[markov] 예측 실패")
        raise HTTPException(status_code=500, detail=f"Markov 예측 실패: {e}")

    next_predictions = [
        MarkovPrediction(
            code=p.code,
            category=p.category,
            equipment_type=p.equipment_type,
            probability=p.probability,
            expected_delay_hours=p.expected_delay_hours,
            description=p.description,
            recommended_action=p.recommended_action,
        )
        for p in analysis.next_predictions
    ]

    cascade_chains = []
    for chain in analysis.cascade_chains:
        cascade_chains.append(CascadeChainItem(
            steps=[
                CascadeStep(
                    code=s.code,
                    category=s.category,
                    probability=s.probability,
                    expected_delay_hours=s.expected_delay_hours,
                )
                for s in chain.steps
            ],
            total_probability=chain.total_probability,
            total_hours=chain.total_hours,
        ))

    return MarkovResponse(
        current_code=analysis.current_code,
        current_category=analysis.current_category,
        next_predictions=next_predictions,
        cascade_chains=cascade_chains,
        risk_level=analysis.risk_level,
        prevention_message=analysis.prevention_message,
    )


# ═══════════════════════════════════════════════════════════
# 7. GET /equipment/molds
# ═══════════════════════════════════════════════════════════


@router.get("/molds", response_model=MoldsResponse)
async def molds_list(_user=Depends(require_equipment_access(1))):
    """25개 금형 + XGBoost 잔여수명 (Phase 4)."""
    del _user
    items: list[MoldItem] = []

    mold_lifecycle = _safe_import("features.equipment.mold_lifecycle")
    if mold_lifecycle is not None:
        try:
            molds = mold_lifecycle.get_all_molds()
            for m in molds:
                items.append(MoldItem(
                    mold_id=m.get("mold_id", ""),
                    mold_name=m.get("mold_name", ""),
                    mold_type=m.get("mold_type", ""),
                    part_name=m.get("part_name", ""),
                    current_shots=m.get("current_shots", 0) or 0,
                    max_shots=m.get("max_shots", 0) or 0,
                    life_percent=m.get("life_percent", 0.0),
                    remaining_shots=m.get("remaining_shots", 0),
                    status=m.get("status", "active"),
                    **_lineage_kwargs(
                        m,
                        default_data_class="synthetic",
                        default_source_system="seed_equipment",
                        default_source_label="mold_lifecycle",
                    ),
                ))
        except Exception as e:
            logger.warning(f"[molds] lifecycle 로드 실패: {e}")

    # XGBoost 예측 (선택 — 모델 부재 시 skip)
    xgb = _safe_import("features.equipment.mold_ml_predictor")
    if xgb is not None and items:
        try:
            predictor = xgb.get_mold_predictor()
            for it in items:
                try:
                    pred = predictor.predict(it.mold_id)
                    if pred:
                        it.predicted_remaining_life = pred["predicted_remaining_life"]
                        it.predicted_replacement_date = pred["predicted_replacement_date"]
                        it.risk_level = pred["risk_level"]
                        ci = pred.get("confidence_interval")
                        if ci:
                            it.confidence_interval = list(ci)
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[molds] XGBoost 예측 실패 (mock fallback): {e}")

    critical = sum(1 for i in items if i.risk_level == "critical")
    warning = sum(1 for i in items if i.risk_level == "warning")
    active = sum(1 for i in items if i.status == "active")

    return MoldsResponse(items=items, total=len(items), critical=critical, warning=warning, active=active)


# ═══════════════════════════════════════════════════════════
# 8. GET /equipment/mtbf
# ═══════════════════════════════════════════════════════════


@router.get("/mtbf", response_model=MTBFResponse)
async def mtbf_data(_user=Depends(require_equipment_access(1))):
    """MTBF (Phase 4)."""
    del _user
    items: list[MTBFItem] = []
    top5: list[MTBFTopCost] = []
    seasonal_message = ""
    machines_attention = 0

    maint = _safe_import("features.equipment.maintenance_predictor")
    if maint is not None:
        try:
            summary = maint.get_maintenance_summary()
            machines_attention = summary.machines_needing_attention
            seasonal_message = summary.seasonal_insights.get("message", "")
            for name, cost in summary.top_cost_machines[:5]:
                top5.append(MTBFTopCost(machine_name=name, total_cost=float(cost)))

            machines = maint.get_all_machine_analysis()
            for m in machines:
                items.append(MTBFItem(
                    machine_id=m.machine_id,
                    machine_name=m.machine_name,
                    total_repairs=m.total_repairs,
                    mtbf_days=m.mtbf_days,
                    mtbf_std_days=m.mtbf_std_days,
                    last_repair_date=m.last_repair_date,
                    next_predicted_date=m.next_predicted_date,
                    days_until_next=m.days_until_next,
                    risk_level=m.risk_level,
                    avg_repair_hours=m.avg_repair_hours,
                    avg_repair_cost=m.avg_repair_cost,
                    seasonal_pattern={k: float(v) for k, v in m.seasonal_pattern.items()},
                    data_class="synthetic",
                    source_system="seed_equipment",
                    source_label="maintenance_predictor",
                ))
        except Exception as e:
            logger.warning(f"[mtbf] 실패: {e}")

    return MTBFResponse(
        items=items,
        top5_cost=top5,
        seasonal_message=seasonal_message,
        machines_attention=machines_attention,
    )


# ═══════════════════════════════════════════════════════════
# 9. GET /equipment/ml-engines/status
# ═══════════════════════════════════════════════════════════


@router.get("/ml-engines/status", response_model=MLEnginesStatusResponse)
async def ml_engines_status(_user=Depends(require_equipment_access(1))):
    """7종 ML 모델 상태 (DAY6_7_PLAN Section 8)."""
    del _user
    dashboard_data = _safe_import("features.equipment.dashboard_data")
    status_map: dict[str, bool] = {}
    if dashboard_data is not None:
        try:
            status_map = dashboard_data.get_ml_status()
        except Exception as e:
            logger.warning(f"[ml-engines] dashboard_data 실패: {e}")

    engines = [
        MLEngineStatus(
            id="tfidf_error_search",
            name_en="TF-IDF Error Search",
            name_ko="TF-IDF 에러 검색",
            library="sklearn",
            status="online" if status_map.get("error_tfidf", False) else "warning",
            accuracy=None,
            last_trained="2일 전",
            description="자연어 증상 → 에러코드 검색",
            data_class="system",
            source_system="equipment_ml_registry",
            source_label="ml_engines_status",
        ),
        MLEngineStatus(
            id="isolation_forest",
            name_en="Isolation Forest SPC",
            name_ko="Isolation Forest SPC",
            library="sklearn",
            status="online" if status_map.get("spc_anomaly", False) else "warning",
            accuracy=None,
            last_trained="오늘",
            description="SPC 측정값 이상 탐지",
            data_class="system",
            source_system="equipment_ml_registry",
            source_label="ml_engines_status",
        ),
        MLEngineStatus(
            id="xgboost_mold",
            name_en="XGBoost Mold Life",
            name_ko="XGBoost 금형 수명",
            library="xgboost/sklearn-fallback",
            status="online" if status_map.get("mold_xgboost", False) else "warning",
            accuracy=None,
            last_trained="3일 전",
            description="금형 잔여수명 회귀 예측",
            data_class="system",
            source_system="equipment_ml_registry",
            source_label="ml_engines_status",
        ),
        MLEngineStatus(
            id="markov",
            name_en="Markov Chain",
            name_ko="Markov 연쇄 예측",
            library="numpy",
            status="online" if status_map.get("markov", False) else "warning",
            accuracy=None,
            last_trained="1주 전",
            description="에러코드 다음 발생 확률",
            data_class="system",
            source_system="equipment_ml_registry",
            source_label="ml_engines_status",
        ),
        MLEngineStatus(
            id="rf_mtbf",
            name_en="MTBF Predictor",
            name_ko="MTBF 예측",
            library="numpy+sqlite",
            status="online" if status_map.get("rf_mtbf", False) else "warning",
            accuracy=None,
            last_trained="5일 전",
            description="평균 고장 간격 예측",
            data_class="system",
            source_system="equipment_ml_registry",
            source_label="ml_engines_status",
        ),
        MLEngineStatus(
            id="causality",
            name_en="Causality Rules",
            name_ko="에러 인과 규칙",
            library="rule-based",
            status="online" if status_map.get("causality", False) else "warning",
            accuracy=None,
            last_trained="정적",
            description="에러코드 인과관계 규칙",
            data_class="system",
            source_system="equipment_ml_registry",
            source_label="ml_engines_status",
        ),
        MLEngineStatus(
            id="manual_rag",
            name_en="Manual RAG",
            name_ko="매뉴얼 RAG",
            library="chromadb+text-fallback",
            status="online" if status_map.get("manual_rag", False) else "warning",
            accuracy=None,
            last_trained="실시간",
            description="설비 매뉴얼 임베딩 검색",
            data_class="system",
            source_system="equipment_ml_registry",
            source_label="ml_engines_status",
        ),
    ]

    online_count = sum(1 for e in engines if e.status == "online")
    return MLEnginesStatusResponse(engines=engines, online_count=online_count, total=len(engines))


# ═══════════════════════════════════════════════════════════
# 10. POST /equipment/manual/search
# ═══════════════════════════════════════════════════════════


@router.post("/manual/search", response_model=ManualSearchResponse)
async def manual_search(req: ManualSearchRequest, _user=Depends(require_equipment_access(1))):
    """매뉴얼 RAG 검색 (Phase 5)."""
    del _user
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query 가 비어 있습니다.")

    items: list[ManualExcerpt] = []
    manual_rag = _safe_import("features.equipment.manual_rag")
    if manual_rag is not None:
        try:
            rag = manual_rag.ManualRAG()
            results = rag.search(req.query, equipment_type=req.equipment_type, n_results=req.n_results)
            for r in results:
                meta = r.get("metadata", {}) or {}
                items.append(ManualExcerpt(
                    content=r.get("content", ""),
                    source=meta.get("source", ""),
                    page=str(meta.get("page", "")),
                    relevance=r.get("relevance", 0.0),
                    **_lineage_kwargs(
                        meta,
                        default_data_class="synthetic",
                        default_source_system="seed_equipment",
                        default_source_label=str(meta.get("source", "") or "manual_rag"),
                    ),
                ))
        except Exception as e:
            logger.warning(f"[manual/search] 실패: {e}")

    return ManualSearchResponse(items=items, total=len(items))


# ═══════════════════════════════════════════════════════════
# 11. POST /equipment/spc/upload-csv
# ═══════════════════════════════════════════════════════════


@router.post("/spc/upload-csv", response_model=SPCUploadResponse)
async def spc_upload_csv(
    file: UploadFile = File(...),
    _user=Depends(require_equipment_access(3)),
):
    """CSV 업로드 + 즉시 SPC 분석 (Phase 4)."""
    del _user
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV 5MB 초과")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("euc-kr", errors="ignore")

    spc = _safe_import("features.equipment.spc_analyzer")
    if spc is None:
        raise HTTPException(status_code=503, detail="SPC 분석기를 사용할 수 없습니다.")

    try:
        values = spc.parse_csv_data(text, column=1, skip_header=True)
        if not values:
            # 단일 컬럼 폴백
            values = spc.parse_csv_data(text, column=0, skip_header=True)
        if not values:
            raise HTTPException(status_code=400, detail="CSV 에서 측정값을 추출할 수 없습니다.")

        result = spc.analyze_spc(values)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[spc/upload] 분석 실패")
        raise HTTPException(status_code=500, detail=f"CSV 분석 실패: {e}")

    # Nelson 위반 카운트
    violation_count = 0
    spc_realtime = _safe_import("features.equipment.spc_realtime")
    if spc_realtime is not None and len(values) >= 10:
        try:
            nelson = spc_realtime.analyze_nelson_rules(values)
            violation_count = nelson.violation_count
        except Exception:
            pass

    return SPCUploadResponse(
        process_id=file.filename or "uploaded",
        n_samples=result.n,
        mean=result.mean,
        std=result.std,
        cpk=result.cpk,
        grade=result.grade,
        violation_count=violation_count,
        data_class="real",
        source_system="csv_upload",
        source_label=file.filename or "uploaded",
    )


# ═══════════════════════════════════════════════════════════
# 12. GET /equipment/inspection/checklist/{type}
# ═══════════════════════════════════════════════════════════


@router.get("/inspection/checklist/{equipment_type}", response_model=InspectionChecklistResponse)
async def inspection_checklist(
    equipment_type: str,
    _user=Depends(require_equipment_access(1)),
):
    """장비 유형별 점검 체크리스트 (Phase 4 메타)."""
    del _user
    inspection = _safe_import("features.equipment.inspection_db")
    templates: list[ChecklistTemplate] = []

    if inspection is not None:
        try:
            raw = inspection.get_templates(equipment_type=equipment_type)
            for t in raw:
                items = [ChecklistItem(**it) for it in t.get("items", [])]
                templates.append(ChecklistTemplate(
                    id=t["id"],
                    template_name=t["template_name"],
                    equipment_type=t["equipment_type"],
                    checklist_type=t["checklist_type"],
                    items=items,
                    **_lineage_kwargs(
                        t,
                        default_data_class="synthetic",
                        default_source_system="seed_equipment",
                        default_source_label="inspection_template",
                    ),
                ))
        except Exception as e:
            logger.warning(f"[inspection] 실패: {e}")

    return InspectionChecklistResponse(templates=templates, total=len(templates))


# ═══════════════════════════════════════════════════════════
# 13. GET /equipment/health — DB + 데이터셋 가용성 (Frontend 진단용)
# ═══════════════════════════════════════════════════════════


class HealthDbEntry(BaseModel):
    ok: bool
    rows: int = 0
    table: Optional[str] = None
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    generated_at: str
    overall_ok: bool
    dbs: dict[str, HealthDbEntry]
    spc_csv: dict[str, int]


# DB → 핵심 테이블 (data 충실도 판정 기준)
_HEALTH_DB_TARGETS: list[tuple[str, str]] = [
    ("error_codes.db", "error_codes"),
    ("error_history.db", "error_history"),
    ("inspection.db", "inspection_logs"),
    ("maintenance.db", "maintenance_history"),
    ("mold_lifecycle.db", "mold_shot_logs"),
    ("molds.db", "molds"),
    ("drawings.db", "drawings"),
]


@router.get("/health", response_model=HealthResponse)
async def equipment_health(_user=Depends(require_equipment_access(1))):
    """Frontend 진단·운영 모니터링용 — 7 DB + 5 SPC CSV row count."""
    del _user
    import sqlite3
    from datetime import datetime

    from config import DATA_DIR

    equipment_dir = DATA_DIR / "equipment"
    spc_dir = DATA_DIR / "spc_ml"

    dbs: dict[str, HealthDbEntry] = {}
    overall_ok = True
    for db_name, key_table in _HEALTH_DB_TARGETS:
        db_path = equipment_dir / db_name
        if not db_path.exists():
            dbs[db_name] = HealthDbEntry(ok=False, table=key_table, detail="파일 없음")
            overall_ok = False
            continue
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (key_table,),
                ).fetchone()
                if not exists:
                    dbs[db_name] = HealthDbEntry(ok=False, table=key_table, detail="테이블 없음")
                    overall_ok = False
                    continue
                rows = conn.execute(f"SELECT COUNT(*) FROM {key_table}").fetchone()[0]
                dbs[db_name] = HealthDbEntry(ok=rows > 0, rows=rows, table=key_table)
                if rows == 0:
                    overall_ok = False
            finally:
                conn.close()
        except sqlite3.Error as e:
            dbs[db_name] = HealthDbEntry(ok=False, table=key_table, detail=str(e))
            overall_ok = False

    spc_csv: dict[str, int] = {}
    if spc_dir.exists():
        for csv in sorted(spc_dir.glob("*.csv")):
            try:
                with csv.open("r", encoding="utf-8") as f:
                    spc_csv[csv.name] = max(0, sum(1 for _ in f) - 1)
            except OSError:
                spc_csv[csv.name] = -1
                overall_ok = False

    return HealthResponse(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        overall_ok=overall_ok,
        dbs=dbs,
        spc_csv=spc_csv,
    )


# ═══════════════════════════════════════════════════════════
# 14. v4.3 — 점검 이력 ETL (CSV 업로드 + PWA 실시간 제출 + ingest_log 조회)
# ═══════════════════════════════════════════════════════════


@router.post("/inspection/upload-csv")
async def upload_inspection_csv(
    file: UploadFile = File(...),
    dry_run: bool = False,
    user=Depends(require_equipment_access(3)),
):
    """
    점검 이력 CSV/XLSX 업로드. docs/INSPECTION_CSV_SCHEMA.md 스키마 준수.

    - role_level ≥ 3 (실무자 이상)
    - dry_run: 검증만 수행, DB 미변경
    - 응답: IngestResult (rows_total/inserted/updated/skipped/error + 첫 50 에러)
    """
    from features.equipment.inspection_etl import ingest_csv

    if not file.filename:
        raise HTTPException(status_code=400, detail="file 누락")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일")

    actor = getattr(user, "username", "") or getattr(user, "email", "") or "unknown"
    try:
        result = ingest_csv(
            data,
            source="csv_upload",
            actor=actor,
            file_name=file.filename,
            dry_run=dry_run,
        )
    except Exception as e:  # 광범위 catch — ETL 실패는 user 가 detail 로 확인
        logger.exception("[inspection/upload-csv] 실패")
        raise HTTPException(status_code=500, detail=f"적재 실패: {e}")

    return result


@router.post("/inspection/submit")
async def submit_inspection(
    payload: dict,
    user=Depends(require_equipment_access(2)),
):
    """
    PWA 현장 점검 단건 제출. role_level ≥ 2 (현장 작업자 이상).

    payload: InspectionSubmitRequest schema.
    inspector 는 토큰의 user.username 사용 (위변조 방지).
    """
    from backend.schemas.inspection_etl import (
        InspectionSubmitRequest,
        InspectionSubmitResponse,
    )
    from features.equipment.inspection_etl import submit_single

    try:
        req = InspectionSubmitRequest(**payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"payload schema: {e}")

    inspector = getattr(user, "username", "") or getattr(user, "email", "") or "anonymous"
    try:
        log_id, dedup = submit_single(
            equipment_id=req.equipment_id,
            template_id=req.template_id,
            inspector=inspector,
            inspection_date=req.inspection_date,
            results=[r.model_dump() for r in req.results],
            overall_status=req.overall_status,
            note=req.note,
            client_uuid=req.client_uuid,
            source="tablet_pwa",
        )
    except Exception as e:
        logger.exception("[inspection/submit] 실패")
        raise HTTPException(status_code=500, detail=f"제출 실패: {e}")

    return InspectionSubmitResponse(
        inspection_log_id=log_id,
        deduplicated=dedup,
        source="tablet_pwa",
    )


@router.get("/inspection/ingest-log/recent")
async def recent_ingest_log(
    limit: int = 20,
    user=Depends(require_equipment_access(3)),
):
    """최근 ingest_log 조회 — 운영 모니터링용. role_level ≥ 3."""
    del user

    from backend.schemas.inspection_etl import IngestLogEntry, IngestLogResponse
    from features.equipment.inspection_etl import list_ingest_logs

    items = list_ingest_logs(limit=min(limit, 100))
    return IngestLogResponse(
        items=[IngestLogEntry(**i) for i in items],
        total=len(items),
    )


# ═══════════════════════════════════════════════════════════
# 15. v4.8 Feature F 트랙 A — PLC 라이브 게이트웨이 상태
# ═══════════════════════════════════════════════════════════


class PLCStatusResponse(BaseModel):
    healthy: bool
    active_lanes: int
    last_message_ts: Optional[str] = None
    last_message_age_sec: Optional[float] = None
    rtdb_live: bool = False
    streams: list[str] = []
    data_class: str = "unknown"
    source_system: str = "unknown"
    source_label: str = "plc_status"
    error: Optional[str] = None


@router.get("/plc/status", response_model=PLCStatusResponse)
async def plc_status(_user=Depends(require_equipment_access(1))) -> PLCStatusResponse:
    """실시간 PLC ingest 게이트웨이 상태.

    healthy:
        - True  → 마지막 메시지가 30초 이내
        - False → 30초 초과 또는 Redis 미가용
    """
    del _user
    import os as _os

    try:
        import redis  # type: ignore
    except ImportError:
        return PLCStatusResponse(
            healthy=False, active_lanes=0, error="redis 패키지 미설치"
        )

    redis_url = _os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    prefix = _os.environ.get("PLC_REDIS_STREAM_KEY_PREFIX", "plc:lane:")
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
        client.ping()
    except Exception as e:
        return PLCStatusResponse(
            healthy=False, active_lanes=0, error=f"Redis 연결 실패: {e}"
        )

    try:
        keys = [str(k) for k in client.keys(f"{prefix}*")]
    except Exception as e:
        return PLCStatusResponse(
            healthy=False, active_lanes=0, error=f"키 조회 실패: {e}"
        )

    if not keys:
        return PLCStatusResponse(
            healthy=False,
            active_lanes=0,
            streams=[],
            rtdb_live=_check_rtdb_live(),
        )

    last_ts: Optional[str] = None
    last_ts_unix_ms: Optional[int] = None
    last_source_system = "unknown"

    for k in keys:
        try:
            info = client.xinfo_stream(k)
            last_entry = info.get("last-entry") if isinstance(info, dict) else None
            # last_entry 형식: [id, [k1, v1, k2, v2, ...]]
            if not last_entry:
                continue
            entry_id, fields = last_entry[0], last_entry[1]
            # entry_id 는 "1234567890-0" — ms epoch
            try:
                ts_ms = int(str(entry_id).split("-")[0])
            except (ValueError, IndexError):
                ts_ms = 0
            if ts_ms and (last_ts_unix_ms is None or ts_ms > last_ts_unix_ms):
                last_ts_unix_ms = ts_ms
                # field 가 list 면 ts 필드 추출 시도
                if isinstance(fields, list):
                    field_dict = dict(zip(fields[0::2], fields[1::2]))
                    last_ts = field_dict.get("ts")
                    raw_source = str(field_dict.get("source") or "").strip().lower()
                    last_source_system = str(field_dict.get("source_system") or "").strip()
                    if not last_source_system:
                        last_source_system = "plc_simulator" if raw_source == "simulator" else "plc_ingest"
        except Exception as e:
            logger.debug(f"xinfo_stream {k} 실패: {e}")

    age_sec: Optional[float] = None
    if last_ts_unix_ms:
        age_sec = max(0.0, (time.time() * 1000 - last_ts_unix_ms) / 1000.0)

    healthy = bool(age_sec is not None and age_sec < 30.0)

    return PLCStatusResponse(
        healthy=healthy,
        active_lanes=len(keys),
        last_message_ts=last_ts,
        last_message_age_sec=age_sec,
        rtdb_live=_check_rtdb_live(),
        streams=sorted(keys),
        data_class=(
            "synthetic"
            if last_source_system == "plc_simulator"
            else ("real" if last_source_system in {"opcua_bridge", "mqtt_bridge", "mes_adapter", "plc_ingest"} else "unknown")
        ),
        source_system=last_source_system,
        source_label="plc_status",
    )


def _check_rtdb_live() -> bool:
    try:
        from backend.services.firebase_rtdb import is_live

        return bool(is_live())
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# 16. v4.8 Feature F 트랙 A — 도면 Vision OCR (F-②)
# ═══════════════════════════════════════════════════════════


class DrawingOCRResponse(BaseModel):
    drawing_id: int
    part_numbers: list[str]
    source: str = "gemini-vision"
    data_class: str = "unknown"
    source_system: str = "unknown"
    source_label: str = "drawing_ocr"


_DRAWING_OCR_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
_DRAWING_OCR_SAMPLE_DIR = Path("data/equipment/drawings_samples")
_DRAWING_OCR_ALLOWED_BASE_DIRS = (
    Path("data/equipment/drawings"),
    _DRAWING_OCR_SAMPLE_DIR,
)


def _drawing_ocr_allowed_base_dirs() -> tuple[Path, ...]:
    """Return OCR allowlist roots from defaults plus optional environment config.

    Returns:
        Tuple of repo-relative or absolute directories allowed for OCR reads.
    """
    raw_env = (os.environ.get("EQUIPMENT_DRAWING_OCR_ALLOWED_DIRS") or "").strip()
    if not raw_env:
        return _DRAWING_OCR_ALLOWED_BASE_DIRS
    configured = [Path(part.strip()) for part in raw_env.split(",") if part.strip()]
    return tuple(configured) or _DRAWING_OCR_ALLOWED_BASE_DIRS


def _is_relative_to(path: Path, base: Path) -> bool:
    """Return whether a resolved path is inside a resolved base directory.

    Args:
        path: Candidate path.
        base: Allowed base directory.

    Returns:
        bool: True when path is under base.
    """
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _drawing_path_candidate(raw_file_path: str) -> Path:
    """Convert a stored drawing path into a repo-local candidate path.

    Args:
        raw_file_path: Raw `drawings.file_path` value from the drawing DB.

    Returns:
        Path: Candidate path before allowlist validation.

    Raises:
        HTTPException: 403 when traversal is present in the stored path.
    """
    candidate = Path(raw_file_path)
    if any(part == ".." for part in candidate.parts):
        raise HTTPException(status_code=403, detail="drawing_file_forbidden")
    if candidate.is_absolute() or (candidate.parts and candidate.parts[0] == "data"):
        return candidate
    return Path("data/equipment") / candidate


def _assert_drawing_path_allowed(candidate: Path) -> Path:
    """Resolve and validate a drawing image path against OCR allowlist roots.

    Args:
        candidate: Candidate drawing image path.

    Returns:
        Path: Resolved path safe to read.

    Raises:
        HTTPException: 403 when the path escapes all allowed base directories.
    """
    resolved = candidate.resolve(strict=False)
    allowed_bases = tuple(base.resolve(strict=False) for base in _drawing_ocr_allowed_base_dirs())
    if any(_is_relative_to(resolved, base) for base in allowed_bases):
        return resolved
    raise HTTPException(status_code=403, detail="drawing_file_forbidden")


def _resolve_drawing_ocr_image(drawing: dict, drawing_id: int) -> Path:
    """Resolve the drawing image file allowed for OCR.

    Args:
        drawing: Drawing row returned by `drawing_search.get_drawing`.
        drawing_id: Drawing id from the request path.

    Returns:
        Path: Existing PNG/JPG file inside an allowed base directory.

    Raises:
        HTTPException: 403 for forbidden stored paths.
        HTTPException: 404 when no readable supported image exists.
    """
    raw_file_path = str(drawing.get("file_path") or "").strip()
    candidate = (
        _drawing_path_candidate(raw_file_path)
        if raw_file_path
        else _DRAWING_OCR_SAMPLE_DIR / f"{drawing_id}.png"
    )
    img_path = _assert_drawing_path_allowed(candidate)
    if img_path.suffix.lower() not in _DRAWING_OCR_IMAGE_SUFFIXES or not img_path.is_file():
        raise HTTPException(status_code=404, detail="drawing_image_not_found")
    return img_path


@router.post("/drawing/{drawing_id}/ocr", response_model=DrawingOCRResponse)
async def drawing_ocr(
    drawing_id: int,
    _user=Depends(require_equipment_access(3)),
):
    """도면 ID 기반 이미지 로드 → Gemini Vision OCR → 부품 번호 추출.

    GEMINI_API_KEY 미설정 시 503 (vision_disabled).
    """
    del _user
    drawing_search = _safe_import("features.equipment.drawing_search")
    if drawing_search is None:
        raise HTTPException(status_code=503, detail="drawing_search 모듈 사용 불가")

    drawing = drawing_search.get_drawing(drawing_id)
    if not drawing:
        raise HTTPException(status_code=404, detail=f"도면 {drawing_id} 없음")

    img_path = _resolve_drawing_ocr_image(drawing, drawing_id)
    image_bytes = img_path.read_bytes()
    try:
        part_numbers = drawing_search.extract_part_numbers(image_bytes)
    except RuntimeError as e:
        if str(e) == "vision_disabled":
            raise HTTPException(status_code=503, detail="vision_disabled")
        raise HTTPException(status_code=502, detail=f"vision_failed: {e}")

    return DrawingOCRResponse(
        drawing_id=drawing_id,
        part_numbers=part_numbers,
        data_class=_feature_f_data_class(drawing.get("data_class"), "unknown"),
        source_system=str(drawing.get("source_system") or "drawing_db"),
        source_label=str(drawing.get("source_label") or drawing.get("drawing_no") or "drawing_ocr"),
    )
