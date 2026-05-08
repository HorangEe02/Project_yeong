"""v3.3 Phase G-1 — DXF (AutoCAD Drawing Exchange Format) 추출기.

ezdxf 라이브러리로 DXF 파일을 파싱하고:
- 헤더 변수 ($AUTHOR, $LASTSAVEDBY, $ACADVER 등)
- 모델 스페이스 엔티티 카운트 (LINE / CIRCLE / ARC / TEXT / DIMENSION 등)
- 레이어 목록
- 바운딩 박스

추가로 matplotlib 백엔드로 PNG 미리보기 렌더 (graceful — 실패 시 생략).
"""

from __future__ import annotations

import io
import logging
from collections import Counter

logger = logging.getLogger(__name__)


def _safe_bbox(msp) -> tuple[float, float, float, float] | None:
    """모델 스페이스의 바운딩 박스 (xmin, ymin, xmax, ymax). 실패 시 None."""
    try:
        from ezdxf.math import BoundingBox  # type: ignore

        bbox = BoundingBox()
        for e in msp:
            try:
                # 일부 엔티티는 bbox 계산 미지원 — graceful skip
                from ezdxf.bbox import extents  # type: ignore

                ee = extents([e])
                if ee.has_data:
                    bbox.extend(ee)
            except Exception:
                continue
        if not bbox.has_data:
            return None
        ext = bbox.extmin, bbox.extmax
        return (
            float(ext[0].x), float(ext[0].y),
            float(ext[1].x), float(ext[1].y),
        )
    except Exception:
        return None


def _render_preview_png(doc) -> str:
    """matplotlib 백엔드로 DXF 모델 스페이스를 PNG base64 로 렌더. 실패 시 빈 문자열."""
    try:
        import base64

        from ezdxf.addons.drawing import RenderContext, Frontend  # type: ignore
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore

        msp = doc.modelspace()
        fig, ax = plt.subplots(figsize=(4, 4), dpi=80)
        try:
            ax.set_axis_off()
            ctx = RenderContext(doc)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(msp, finalize=True)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.05)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("ascii")
        finally:
            plt.close(fig)
    except Exception as e:
        logger.debug("DXF 미리보기 렌더 실패 (graceful): %s", e)
        return ""


def extract(data: bytes) -> dict:
    """DXF 메타데이터 + 엔티티 분포 + (옵션) 미리보기 PNG."""
    metadata: dict = {
        "format": "DXF",
        "size_bytes": len(data),
    }

    try:
        import ezdxf  # type: ignore
    except ImportError:
        return {
            "text": "",
            "metadata": {
                **metadata,
                "summary": "DXF 라이브러리(ezdxf) 미설치",
                "extracted_chars": 0,
                "error": "ezdxf_not_installed",
            },
            "preview_image_b64": "",
        }

    try:
        # ezdxf 는 텍스트 스트림 기반
        text_stream = io.StringIO(data.decode("utf-8", errors="replace"))
        doc = ezdxf.read(text_stream)
    except Exception as e:
        logger.warning("DXF 파싱 실패: %s", e)
        return {
            "text": "",
            "metadata": {
                **metadata,
                "summary": f"DXF 파싱 실패: {e}",
                "extracted_chars": 0,
                "error": "dxf_parse_failed",
            },
            "preview_image_b64": "",
        }

    # 메타 수집
    msp = doc.modelspace()
    counts: Counter[str] = Counter()
    for e in msp:
        try:
            counts[e.dxftype()] += 1
        except Exception:
            continue

    layers = []
    try:
        layers = [layer.dxf.name for layer in doc.layers]
    except Exception:
        pass

    bbox = _safe_bbox(msp)
    bbox_summary = ""
    if bbox:
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        bbox_summary = f", {w:.0f}×{h:.0f}"

    total_entities = sum(counts.values())
    top_3_types = ", ".join(f"{k}={v}" for k, v in counts.most_common(3))

    summary = (
        f"DXF · {total_entities} 엔티티 ({top_3_types}) · {len(layers)} 레이어{bbox_summary}"
    )

    # LLM 컨텍스트용 텍스트 (메타 요약)
    text_parts = [
        f"[DXF 메타]",
        f"엔티티 수: {total_entities}",
        f"엔티티 분포: {dict(counts.most_common(10))}",
        f"레이어 ({len(layers)}): {layers[:20]}",
    ]
    if bbox:
        text_parts.append(f"바운딩박스: x[{bbox[0]:.1f}~{bbox[2]:.1f}] y[{bbox[1]:.1f}~{bbox[3]:.1f}]")

    # 헤더 변수
    try:
        for var in ("$AUTHOR", "$LASTSAVEDBY", "$ACADVER", "$DWGCODEPAGE", "$INSUNITS"):
            val = doc.header.get(var, None)
            if val:
                text_parts.append(f"{var}: {val}")
    except Exception:
        pass

    text = "\n".join(text_parts)

    return {
        "text": text,
        "metadata": {
            **metadata,
            "summary": summary,
            "extracted_chars": len(text),
            "entity_count": total_entities,
            "layer_count": len(layers),
            "entity_distribution": dict(counts.most_common(10)),
            "bbox": bbox,
        },
        "preview_image_b64": _render_preview_png(doc),
    }
