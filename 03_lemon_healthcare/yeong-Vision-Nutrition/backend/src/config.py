"""애플리케이션 설정.

Pydantic Settings 기반으로 환경 변수에서 설정값을 로드한다. 모든 게이트 플래그의
기본값은 ``False`` 이며, 발주처 리뷰 게이트 통과 후에만 운영 환경에서 ``true`` 로
설정한다.

Reference:
    docs/17-image-collection-consent-plan.md §9
    backend/CLAUDE.md Pattern 6
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정.

    게이트 플래그는 ``enable_*`` 접두사를 사용하며, 모든 기본값은 ``False`` 다.
    운영 환경에서 활성화하려면 ``docs/17`` 동의·게이트 절차를 통과해야 한다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    database_url: str = Field(..., description="PostgreSQL 연결 URL")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # LLM 기본 설정 — 환자 개인정보 보호를 위해 로컬 Ollama 사용
    llm_provider: Literal["ollama"] = "ollama"
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen3.5:9b")
    allow_external_llm: bool = Field(default=False)

    # 외부 자격 증명
    google_application_credentials: str = Field(default="")
    mfds_api_key: SecretStr = Field(default=SecretStr(""))

    # ------------------------------------------------------------------
    # 게이트 플래그 — docs/17 §9 매핑. 운영 활성화 전에는 절대 변경 금지.
    # ------------------------------------------------------------------

    # 기능 B — Ollama 멀티모달 LLM (게이트 #1, Phase 2)
    enable_multimodal_llm: bool = Field(
        default=False,
        description="Gemma 4 등 멀티모달 보조 채널 활성화. docs/17 §9 게이트 #1 통과 필요.",
    )
    ollama_multimodal_model: str = Field(default="gemma4:e4b")

    # 기능 A — YOLO 비전 분류기 (게이트 #2, Phase 3)
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

    # 이미지 보유 기간 — docs/17 §5. 0 = 분석 직후 즉시 삭제(기본)
    image_retention_days: int = Field(default=0, ge=0, le=730)

    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴.

    Returns:
        애플리케이션 설정. ``lru_cache`` 로 1회만 로드된다.
    """
    return Settings()  # type: ignore[call-arg]
