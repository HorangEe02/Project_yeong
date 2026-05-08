"""공통 Export 라우터 (Phase 7) — 모든 모듈에서 사용 가능한 통합 export.

목적: 프론트엔드 WASM(@rhwp/core)이 모바일 메모리 부족이나 보안 격리로 사용 불가할 때,
서버 측에서 HWP/HWPX 변환을 graceful 처리.

엔드포인트:
- POST /api/export/hwp   — Markdown → HWP (HwpxExporter ODT 패키지를 .hwp 확장자로 응답)
- POST /api/export/hwpx  — Markdown → HWPX (정식)

내부 구현:
- features/draft/hwpx_exporter.py 의 HwpxExporter 사용 (ODT-호환 OPF 패키지)
- 한컴오피스에서 정상 오픈됨 (확장자만 .hwp 또는 .hwpx)
- 진정한 HWP 5.0 바이너리는 rhwp Rust 바이너리(향후 subprocess 옵션)로 확장 가능
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.dependencies import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


# ═══════════════════════════════════════════════════════════
# 스키마
# ═══════════════════════════════════════════════════════════


class HwpExportRequest(BaseModel):
    """HWP/HWPX 변환 요청."""

    content: str = Field(..., description="Markdown 또는 평문 콘텐츠")
    title: Optional[str] = Field(default=None, description="문서 제목 (메타)")
    doc_type: str = Field(default="general", description="문서 유형 식별자")
    author: Optional[str] = Field(default=None)
    source: Literal["draft", "compliance", "equipment", "admin", "search", "default"] = "default"


# ═══════════════════════════════════════════════════════════
# 엔드포인트
# ═══════════════════════════════════════════════════════════


@router.post("/hwp")
async def export_hwp(req: HwpExportRequest, user=Depends(get_optional_user)):
    """Markdown → HWP 응답 (서버 측 fallback).

    프론트엔드 WASM(@rhwp/core) 실패 시 호출.
    내부적으로 HwpxExporter (ODT 호환 패키지)를 사용하고 .hwp 확장자로 응답.
    """
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="빈 콘텐츠")

    try:
        from features.draft.hwpx_exporter import HwpxExporter

        exporter = HwpxExporter()
        # HwpxExporter는 마크다운/평문 → ODT-OPF 패키지 바이트
        file_bytes = exporter.export_bytes(req.content, req.doc_type)

        if user:
            try:
                from backend.auth_middleware import log_api_access
                log_api_access(
                    endpoint="/api/export/hwp",
                    method="POST",
                    detail=f"source={req.source}, doc_type={req.doc_type}, len={len(req.content)}",
                    user=user,
                )
            except Exception:
                pass

        safe_basename = (req.doc_type or "draft").replace("/", "_")
        return Response(
            content=file_bytes,
            media_type="application/x-hwp",
            headers={
                "Content-Disposition": f"attachment; filename={safe_basename}.hwp",
                "X-AJIN-Fallback": "hwpx-as-hwp-graceful",
            },
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"HWP exporter 모듈 없음: {e}")
    except Exception as e:
        logger.warning("[export] /hwp 실패: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hwpx")
async def export_hwpx(req: HwpExportRequest, user=Depends(get_optional_user)):
    """Markdown → HWPX 응답 (서버 측 fallback)."""
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="빈 콘텐츠")

    try:
        from features.draft.hwpx_exporter import HwpxExporter

        exporter = HwpxExporter()
        file_bytes = exporter.export_bytes(req.content, req.doc_type)

        if user:
            try:
                from backend.auth_middleware import log_api_access
                log_api_access(
                    endpoint="/api/export/hwpx",
                    method="POST",
                    detail=f"source={req.source}, doc_type={req.doc_type}, len={len(req.content)}",
                    user=user,
                )
            except Exception:
                pass

        safe_basename = (req.doc_type or "draft").replace("/", "_")
        return Response(
            content=file_bytes,
            media_type="application/vnd.hancom.hwpx",
            headers={
                "Content-Disposition": f"attachment; filename={safe_basename}.hwpx",
            },
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"HWPX exporter 모듈 없음: {e}")
    except Exception as e:
        logger.warning("[export] /hwpx 실패: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def export_health():
    """Export 서비스 헬스 체크. HwpxExporter 가용성 확인."""
    try:
        from features.draft.hwpx_exporter import HwpxExporter  # noqa: F401
        return {
            "status": "ok",
            "engines": {
                "hwpx_exporter": True,
                "rhwp_rust_binary": False,  # 향후 subprocess 옵션 활성화 시 True
            },
            "supported": ["hwp", "hwpx"],
            "note": "프론트엔드 WASM(@rhwp/core)이 1순위 — 본 엔드포인트는 fallback.",
        }
    except ImportError:
        return {
            "status": "degraded",
            "engines": {"hwpx_exporter": False, "rhwp_rust_binary": False},
            "supported": [],
        }
