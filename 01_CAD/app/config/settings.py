"""
DrawingLLM 설정 관리 모듈
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


def _auto_select_ollama_model() -> str:
    """시스템 RAM + Ollama 설치 모델 기반 최적 모델 자동 선택.

    Gemma 4 / Qwen3.5 중 RAM 용량에 맞는 최적 모델 선택.
    Ollama에 실제 설치된 모델만 후보로 고려.
    """
    try:
        import psutil
        total_gb = psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        total_gb = 16.0  # fallback: 16GB 가정

    # RAM 기반 선호 순위 (성능순)
    if total_gb >= 48:
        preference = [
            "gemma4:27b", "qwen3.5:27b",
            "gemma4:12b", "qwen3.5:9b",
        ]
    elif total_gb >= 16:
        preference = [
            "gemma4:12b", "qwen3.5:9b",
            "gemma4:4b", "qwen3.5:4b",
        ]
    else:
        preference = [
            "gemma4:4b", "qwen3.5:4b",
        ]

    # Ollama에 실제 설치된 모델 확인
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        if resp.status_code == 200:
            installed = {m["name"] for m in resp.json().get("models", [])}
            for model in preference:
                if model in installed:
                    return model
    except Exception:
        pass

    # Ollama 미연결 시 RAM 기반 기본값
    return preference[-1] if preference else "qwen3.5:9b"


class Settings(BaseSettings):
    """애플리케이션 전역 설정"""

    # === 프로젝트 경로 ===
    project_root: Path = Path(__file__).parent.parent
    upload_dir: Path = Field(default=Path("./data/sample_drawings"))
    chroma_persist_dir: Path = Field(default=Path("./data/vector_store"))

    # === Ollama ===
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = Field(default_factory=_auto_select_ollama_model)
    ollama_timeout: float = 300.0  # LLM 타임아웃 (초), 이미지 분석 시 충분한 여유

    # === 임베딩 모델 ===
    clip_model: str = "ViT-L-14"  # OpenCLIP 모델 아키텍처 (768-dim)
    clip_pretrained: str = "datacomp_xl_s13b_b90k"  # OpenCLIP pretrained 체크포인트
    clip_finetuned_path: str = ""  # Fine-tuned OpenCLIP 체크포인트 (빈 문자열이면 pretrained)
    text_embedding_model: str = "intfloat/multilingual-e5-small"

    # === 벡터 DB ===
    chroma_collection_name: str = "drawings"
    sqlite_db_path: str = "./data/vector_store/records.db"

    # === 검색 ===
    search_top_k: int = 10
    image_weight: float = 0.10  # 3채널: image(0.1) + text(0.6) + gnn(0.3) = 1.0
    text_weight: float = 0.60

    # === YOLO 분류기 ===
    yolo_cls_model_path: str = "./models/yolo_cls_v2_best.pt"
    yolo_cls_confidence_threshold: float = 0.5
    yolo_cls_enabled: bool = True
    yolo_cls_device: str = ""  # 빈 문자열이면 자동 선택

    # === YOLO 객체탐지기 ===
    yolo_det_model_path: str = "./models/yolo_det_best.pt"
    yolo_det_confidence_threshold: float = 0.3  # det는 recall 우선 → cls(0.5)보다 낮게
    yolo_det_enabled: bool = True
    yolo_det_device: str = ""  # 빈 문자열이면 자동 선택
    yolo_det_iou_threshold: float = 0.5  # NMS IoU 임계값

    # === Phase 4: LLM 컨텍스트 주입 ===
    llm_context_injection: bool = True       # YOLO/OCR 컨텍스트를 LLM에 주입
    llm_text_only_mode: bool = True          # 충분한 컨텍스트 시 이미지 없이 분석
    llm_hallucination_check: bool = True     # 환각 검증 활성화
    llm_num_predict_describe: int = 4096     # describe 토큰 (기존 8192 → 감소)
    llm_num_predict_metadata: int = 1024     # metadata 토큰
    llm_num_predict_qa: int = 2048           # Q&A 토큰

    # === GNN 구조 검색 ===
    gnn_model_path: str = "./models/gnn_encoder.pt"
    gnn_enabled: bool = True
    gnn_embedding_dim: int = 256
    gnn_weight: float = 0.3   # GNN v2 학습 완료 (R@5=0.765)
    gnn_k_neighbors: int = 8
    gnn_device: str = ""       # 빈 문자열이면 자동 선택

    # === 유사도면 알림 ===
    similarity_alert_threshold: float = 0.85  # 등록 시 유사도면 알림 임계값

    # === Reranker (Cross-Encoder 2차 정렬) ===
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_weight: float = 0.7   # blended = 0.7×reranker + 0.3×hybrid
    reranker_top_k_multiplier: int = 3  # 1차에서 top_k×3 → rerank → top_k

    # === OCR 병렬화 ===
    ocr_workers: int = 4   # 배치 OCR 워커 수 (0이면 순차)
    ocr_batch_size: int = 32

    # === REST API (FastAPI) ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000/api/v1"
    api_enabled: bool = False  # True면 Streamlit이 FastAPI를 통해 통신

    # === 보안: 모델 무결성 검증 ===
    yolo_cls_sha256: str = ""   # YOLO-cls 모델 SHA256 (빈 문자열이면 스킵)
    yolo_det_sha256: str = ""   # YOLO-det 모델 SHA256 (빈 문자열이면 스킵)

    # === 보안: LLM 레이트 리미팅 ===
    llm_rate_limit_rpm: int = 30   # 분당 최대 LLM 호출 횟수 (0이면 무제한)

    # === 보안: 로그 로테이션 ===
    log_rotation: str = "50 MB"    # 로그 파일 회전 크기
    log_retention: str = "7 days"  # 로그 보관 기간
    log_file: str = "logs/drawingllm.log"  # 로그 파일 경로

    # === 카테고리 키워드 (검색 임베딩 보강) ===
    category_keywords_path: str = "./data/category_keywords.json"

    # === 파일 경로 매핑 (Docker용) ===
    # 원본 도면 경로의 접두사(호스트 경로)를 컨테이너 경로로 치환
    # 예: /Volumes/ExtDrive/data → /app/data/sample_drawings
    drawing_path_remap_from: str = "<EXTERNAL_DRIVE>/00_work_out/02_ing/CAD/data/"
    drawing_path_remap_to: str = "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/data/"

    # === 파일 처리 ===
    max_file_size_mb: int = 50
    supported_formats: list[str] = ["png", "jpg", "jpeg", "pdf", "tiff", "tif", "dxf"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
