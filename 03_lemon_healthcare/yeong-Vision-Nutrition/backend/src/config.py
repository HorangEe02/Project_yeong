"""애플리케이션 설정.

Pydantic Settings 기반으로 환경 변수에서 설정값을 로드한다. 모든 게이트 플래그의
기본값은 ``False`` 이며, 발주처 리뷰 게이트 통과 후에만 운영 환경에서 ``True`` 로
설정한다.

Phase 00 수리 사항:
    D2: ``allow_external_llm`` 필드 삭제. 트랙 B는 로컬 Ollama 단일 채널만 사용한다.
        외부 LLM이 필요한 비식별 테스트는 별도 build profile에서 처리한다.
    D3: ``SettingsConfigDict.extra="forbid"`` 로 변경. unknown env 오타가 silent로
        흘러가는 사고를 차단한다.
    D4: ``image_retention_days`` 단일 정수 필드를 3개로 분리. ``docs/17 §5`` 의
        보유 정책 매트릭스(임시 / 히스토리 / 학습)를 한 변수로 강제할 수 없으므로
        데이터 유형별로 분리한다.

Reference:
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.1 D2-D4
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 3
    docs/17-image-collection-consent-plan.md §5, §9
    backend/CLAUDE.md Pattern 6
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정.

    게이트 플래그는 ``enable_*`` 접두사를 사용하며, 모든 기본값은 ``False`` 다.
    운영 환경에서 활성화하려면 ``docs/17`` 동의·게이트 절차를 통과해야 한다.

    Attributes:
        environment: 실행 환경. ``"development" | "staging" | "production"``.
        database_url: PostgreSQL 연결 URL.
        redis_url: Redis 연결 URL.
        llm_provider: LLM 공급자. 트랙 B는 ``"ollama"`` 단일값.
        ollama_base_url: Ollama 로컬 API 주소.
        ollama_model: 기본 Ollama 모델 태그.
        ollama_multimodal_model: 멀티모달 모델 태그 (게이트 #1 통과 시 활성).
        vision_classifier_model: YOLO 가중치 파일 경로 (게이트 #2 통과 시 활성).
        embedding_model: 임베딩 모델 (게이트 #3 통과 시 활성).
        image_retention_temporary_hours: 분석용 임시 이미지 보유 시간(시).
        image_retention_history_days: 사용자 히스토리 이미지 보유 일수.
        image_retention_training_days: 학습 적재 이미지 보유 일수.
    """

    # ``extra="forbid"`` — D3 수리: 정의되지 않은 env 변수가 들어오면 즉시 실패.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )

    environment: Literal["development", "staging", "production"] = "development"
    database_url: str = Field(..., description="PostgreSQL 연결 URL")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ------------------------------------------------------------------
    # LLM — 트랙 B는 로컬 Ollama 단일 채널만 사용 (D2 수리).
    # ------------------------------------------------------------------
    llm_provider: Literal["ollama"] = "ollama"
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen3.5:9b")

    # ------------------------------------------------------------------
    # 외부 자격 증명
    # ------------------------------------------------------------------
    google_application_credentials: Path | None = Field(
        default=None,
        description="Google Cloud Vision service account JSON 파일 경로.",
    )
    mfds_api_key: SecretStr = Field(default=SecretStr(""))

    # ------------------------------------------------------------------
    # OCR provider — host-local PaddleOCR (default) 또는 cloud Google Vision.
    # ------------------------------------------------------------------
    ocr_provider: Literal["paddleocr", "google_vision"] = Field(
        default="paddleocr",
        description=(
            "OCR 엔진 선택. paddleocr=host-local (모델 자동 다운로드), "
            "google_vision=cloud (GOOGLE_APPLICATION_CREDENTIALS 필요)."
        ),
    )
    paddleocr_lang: str = Field(
        default="korean",
        description="PaddleOCR 언어 코드 — 한국어='korean', 영어='en'.",
    )

    # ------------------------------------------------------------------
    # 게이트 플래그 — docs/17 §9 매핑. 운영 활성화 전에는 절대 변경 금지.
    # ------------------------------------------------------------------

    # 기능 B — Ollama 멀티모달 보조 채널 (게이트 #1, Phase 2)
    enable_multimodal_llm: bool = Field(
        default=False,
        description="Gemma 4 등 멀티모달 보조 채널 활성화. docs/17 §9 게이트 #1 통과 필요.",
    )
    ollama_multimodal_model: str = Field(default="gemma4:e4b")

    # 기능 A — YOLO 비전 검출 (게이트 #2, Phase 3)
    enable_vision_classifier: bool = Field(
        default=False,
        description="라벨 영역 검출용 YOLO 활성화. docs/17 §9 게이트 #2 통과 필요.",
    )
    vision_classifier_model: str = Field(default="yolov8n.pt")

    # 기능 C — 이미지 학습 적재 파이프라인 (게이트 #3, Phase 4)
    enable_image_learning_pipeline: bool = Field(
        default=False,
        description="가명화 이미지의 학습 데이터셋 적재 활성화. docs/17 §9 게이트 #3 통과 필요.",
    )
    enable_pgvector_storage: bool = Field(default=False)
    embedding_model: str = Field(default="clip-ViT-B-32")

    # ------------------------------------------------------------------
    # 이미지 보유 기간 — D4 수리: docs/17 §5의 4단 매트릭스를 3개 변수로 분리.
    # ------------------------------------------------------------------
    image_retention_temporary_hours: int = Field(
        default=0,
        ge=0,
        le=72,
        description="장애 복구 백업용 임시 보유 시간(시). 0 = 분석 직후 즉시 삭제(기본).",
    )
    image_retention_history_days: int = Field(
        default=90,
        ge=0,
        le=730,
        description="사용자 히스토리 저장 보유 일수. docs/17 §3 동의 매트릭스 항목 2.",
    )
    image_retention_training_days: int = Field(
        default=0,
        ge=0,
        le=730,
        description="학습 적재 데이터셋 보유 일수. 게이트 #3 통과 전 0 고정.",
    )

    log_level: str = Field(default="INFO")

    # ------------------------------------------------------------------
    # JWT / 인증 — Phase 05.
    # ------------------------------------------------------------------
    jwt_secret_key: SecretStr = Field(
        ...,
        description="JWT 서명용 비밀키. 운영 환경에서는 ≥32 바이트 무작위 값.",
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_ttl_days: int = Field(default=14, ge=1, le=90)

    # ------------------------------------------------------------------
    # API 미들웨어 — Phase 05.
    # ------------------------------------------------------------------
    cors_allowed_origins: list[str] = Field(
        default_factory=list,
        description="CORS 허용 origin 목록. 빈 리스트는 모든 origin 차단.",
    )
    rate_limit_register_per_minute: int = Field(
        default=10,
        ge=1,
        description="사용자당 supplement.register 1분 한도.",
    )
    ip_hash_salt: SecretStr = Field(
        default=SecretStr("change-me"),
        description="IP 주소 SHA-256 hash 시 사용할 서버 비밀 salt.",
    )


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴을 반환한다.

    Returns:
        애플리케이션 설정. ``lru_cache`` 로 1회만 로드된다.

    Examples:
        >>> s = get_settings()
        >>> s.llm_provider
        'ollama'
    """
    return Settings()
