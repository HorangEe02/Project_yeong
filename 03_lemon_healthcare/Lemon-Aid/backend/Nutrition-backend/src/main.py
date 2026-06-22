"""FastAPI 애플리케이션 진입점."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.api.v1.examples import HEALTH_RESPONSE_EXAMPLES
from src.api.v1.router import api_router
from src.config import Settings, get_settings
from src.db.session import dispose_engine, verify_stage2_privileged_database_urls
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.secure_headers import SecureHeadersMiddleware
from src.ocr.factory import OCRConfigurationError, build_supplement_ocr_adapter
from src.readiness import ReadinessResponse, build_readiness_response
from src.utils.image_safety import configure_pillow_limits
from src.utils.logger import setup_logging
from src.vision.food_dino_classifier import (
    food_classifier_model_label,
    get_shared_food_dino_classifier,
)

logger = logging.getLogger(__name__)


def _warm_food_classifier(settings: Settings) -> None:
    """Preload the food classifier (and CLIP non-food filter) at startup.

    Builds the process-shared classifier and loads its models now so the heavy
    first-load (YOLO + DINOv3, and the ~600MB CLIP filter when enabled) does not land
    on a user request. Best-effort: callers wrap this so a load failure never crashes
    startup, and the request path still fails open to "no classifier".

    Args:
        settings: Runtime settings.
    """
    label = food_classifier_model_label(
        settings.meal_food_classifier_model_label,
        settings.meal_food_classifier_probe_path,
    )
    if label is None:
        return
    classifier = get_shared_food_dino_classifier(
        module_dir=settings.meal_food_classifier_module_dir,
        exp16b_model_path=settings.meal_food_classifier_exp16b_model_path or "",
        probe_path=settings.meal_food_classifier_probe_path or "",
        nutrition_csv_path=settings.meal_food_classifier_nutrition_csv_path or "",
        model_label=label,
        detector_confidence=settings.meal_food_classifier_gate_confidence,
        max_px=settings.meal_food_classifier_max_px,
        enable_food_filter=settings.enable_food_clip_filter,
        food_filter_threshold=settings.food_clip_filter_threshold,
        food_filter_model_id=settings.food_clip_filter_model_id,
    )
    classifier.warmup()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """애플리케이션 시작과 종료 라이프사이클을 관리한다.

    Args:
        _app: FastAPI 애플리케이션 인스턴스.

    Yields:
        애플리케이션 실행 구간 제어권.
    """
    settings = get_settings()
    setup_logging(settings.log_level)
    # Fail fast if the request role is lemon_app but its privileged audit/learning
    # engines are not configured (FORCE RLS Stage-2 misconfiguration).
    verify_stage2_privileged_database_urls(settings)
    logger.info(
        "TrustedHost allowed_hosts=%s active=%s",
        settings.allowed_hosts or ["<sentinel>"],
        "explicit" if settings.allowed_hosts else "dev-sentinel",
    )
    configure_pillow_limits(settings.supplement_image_max_pixels)
    if settings.paddle_disable_model_source_check:
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "true")
    # Fail fast on an inconsistent OCR provider config (e.g. CLOVA selected without
    # ALLOW_EXTERNAL_OCR/credentials, or PaddleOCR primary while local OCR is disabled
    # during retraining) instead of surfacing it as a 500 on the first analyze request.
    try:
        build_supplement_ocr_adapter(settings)
    except OCRConfigurationError as exc:
        raise RuntimeError(f"OCR provider configuration is invalid at startup: {exc}") from exc
    # Preload the food classifier (+ CLIP non-food filter when enabled) at boot so the
    # heavy first-load (YOLO + DINOv3 + ~600MB CLIP) is not paid on a user request and
    # does not stall the worker. Fail-open: a model-load failure must NOT crash startup;
    # the request path already degrades to "no classifier".
    if settings.enable_food_dino_classifier:
        try:
            await anyio.to_thread.run_sync(_warm_food_classifier, settings)
            logger.info(
                "Food classifier warm-up complete (clip_filter=%s).",
                settings.enable_food_clip_filter,
            )
        except Exception:  # never crash startup; the request path fails open
            logger.warning(
                "Food classifier warm-up failed; first request will load lazily.",
                exc_info=True,
            )
    # TODO: Phase 2에서 Redis/LLM adapter readiness check를 분리한다.
    try:
        yield
    finally:
        await dispose_engine()


def configure_security_middleware(app: FastAPI, settings: Settings) -> None:
    """Register HTTP security middleware.

    Args:
        app: FastAPI app to configure.
        settings: Loaded application settings.

    Returns:
        None.
    """
    # Always install TrustedHostMiddleware. Staging/production validators require
    # explicit ALLOWED_HOSTS; in development we fall back to a TestClient-safe
    # sentinel so the middleware can never silently fail-open.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts or ["testserver", "localhost", "127.0.0.1"],
    )
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )
    app.add_middleware(SecureHeadersMiddleware, settings=settings)
    # Rate limit + concurrency cap on the expensive OCR/LLM endpoints. Added last
    # so it runs first (outermost) and sheds load before any heavier work.
    app.add_middleware(RateLimitMiddleware, settings=settings)


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI 앱 인스턴스를 생성한다.

    Args:
        settings: 테스트와 명시적 구성에 사용할 설정 객체. None이면 환경에서 로드한다.

    Returns:
        설정과 기본 라우트가 등록된 FastAPI 앱.
    """
    app_settings = settings or get_settings()
    docs_url = "/docs" if app_settings.environment != "production" else None
    redoc_url = "/redoc" if app_settings.environment != "production" else None

    app = FastAPI(
        title="Lemon Healthcare API",
        description="만성질환자 중심의 AI 헬스케어 플랫폼 API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
    )
    configure_security_middleware(app, app_settings)

    @app.get(
        "/health",
        tags=["health"],
        responses={200: {"content": {"application/json": {"examples": HEALTH_RESPONSE_EXAMPLES}}}},
    )
    async def health_check() -> dict[str, str]:
        """서비스 상태를 반환한다.

        Returns:
            서비스 상태와 API 버전.
        """
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/ready", tags=["health"], response_model=ReadinessResponse)
    async def readiness_check() -> ReadinessResponse:
        """Return sanitized runtime readiness for mobile OCR smoke tests.

        Returns:
            OCR, YOLO, and parser readiness flags without credentials, raw OCR text,
            provider payloads, image bytes, object URIs, or public tunnel URLs.
        """
        return build_readiness_response(app_settings)

    app.include_router(api_router)

    return app


app = create_app()
