import os
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent

# 데이터 경로
DATA_DIR = PROJECT_ROOT / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
METADATA_PATH = DATA_DIR / "metadata" / "documents_metadata.json"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
GLOSSARY_DIR = KNOWLEDGE_BASE_DIR / "glossary"
CRAWLED_DIR = DATA_DIR / "crawled"
FACILITY_DIR = DATA_DIR / "facility_db"

# 벡터 DB 경로
VECTORSTORE_DIR = PROJECT_ROOT / "vectorstore"

# Ollama 설정
# Plan v2.0 — 환경변수 OLLAMA_BASE_URL 우선. 빈 문자열도 그대로(="비활성") 적용.
# 시연 환경(Cloudflare Tunnel)에서는 OLLAMA_BASE_URL=https://...trycloudflare.com 으로 외부 노출.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.5:9b")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")

# Plan A 변형 — Mac Ollama secret header 인증.
# Cloud Run 에서 Caddy(:8434) reverse proxy 경유로 Mac Ollama 호출 시 부착할 secret.
# 로컬 dev (localhost:11434 직접) 에서는 빈값 유지 (인증 불요).
AJIN_OLLAMA_SECRET = os.environ.get("AJIN_OLLAMA_SECRET", "")


def ollama_headers() -> dict:
    """Mac Ollama 호출 시 부착할 인증 헤더. Caddy reverse proxy 가 검증한다."""
    if AJIN_OLLAMA_SECRET:
        return {"X-AJIN-Secret": AJIN_OLLAMA_SECRET}
    return {}

# Ollama 0.18.x 호환: NEW_ENGINE 모드 필수
# Ollama App 시작 전 환경변수 설정 필요:
#   launchctl setenv OLLAMA_NEW_ENGINE true
# 또는 터미널에서:
#   OLLAMA_NEW_ENGINE=true ollama serve

# Ollama 성능 최적화
OLLAMA_KEEP_ALIVE = "24h"       # 모델 메모리 유지 시간 (콜드 스타트 방지)
OLLAMA_NUM_PREDICT_DEFAULT = 2048  # v2.5: 기본 최대 생성 토큰 수 (512→2048)
OLLAMA_NUM_PREDICT_MAP = {        # 기능별 최대 토큰 수
    "onboarding": 1024,           # v2.5: 온보딩 — 상세 답변 (300→1024)
    "onboarding_compose": 3072,   # v2.5: 온보딩 내 문서 작성 (신규)
    "onboarding_regulation": 2048,# v2.5: 온보딩 내 규제 조회 (신규)
    "search": 512,                # v2.5: 검색 요약 (200→512)
    "draft": 4096,                # v2.5: 문서 작성 — 완성 문서 (800→4096)
    "compliance": 2048,           # v2.5: 법규 분석 (500→2048)
}
OLLAMA_NUM_CTX = 8192             # v2.5: 컨텍스트 윈도우 확장 (4096→8192)

# ──────────────────────────────────────────────
# 모델 프로필 시스템
# ──────────────────────────────────────────────

MODEL_PROFILES = {
    # ── v3.5: 승인된 모델만 등록 (5개 패밀리 + 임베딩) ──

    # ── 1. Qwen 3.5 시리즈 ──
    "qwen3.5:4b": {
        "display": "Qwen 3.5 4B (경량)",
        "size_gb": 3.4,
        "lang": "multilingual",
        "vision": False,
        "speed": "fast",
        "quality": "good",
        "best_for": ["onboarding", "search"],
    },
    "qwen3.5:9b": {
        "display": "Qwen 3.5 9B (기본값)",
        "size_gb": 6.6,
        "lang": "multilingual",
        "vision": False,
        "speed": "medium",
        "quality": "high",
        "best_for": ["draft", "onboarding", "search", "compliance"],
    },

    # ── 2. EXAONE 시리즈 ──
    "exaone3.5:latest": {
        "display": "EXAONE 3.5 7.8B (한국어 특화)",
        "size_gb": 4.8,
        "lang": "korean",
        "vision": False,
        "speed": "medium",
        "quality": "high",
        "best_for": ["draft", "onboarding", "compliance"],
    },
    "exaone-deep:latest": {
        "display": "EXAONE Deep 7.8B (추론 강화)",
        "size_gb": 4.8,
        "lang": "korean",
        "vision": False,
        "speed": "slow",
        "quality": "very_high",
        "best_for": ["compliance", "draft"],
    },

    # ── 3. Nemotron Cascade 2 (향후 서버 업그레이드 대비) ──
    "nemotron-cascade-2:latest": {
        "display": "Nemotron Cascade 2 31.6B (고급)",
        "size_gb": 22.6,
        "lang": "multilingual",
        "vision": False,
        "speed": "slow",
        "quality": "very_high",
        "best_for": ["draft", "compliance"],
    },

    # ── 4. Gemma 4 시리즈 (비전 지원) ──
    "gemma4:latest": {
        "display": "Gemma 4 8B (균형)",
        "size_gb": 8.9,
        "lang": "multilingual",
        "vision": True,
        "speed": "medium",
        "quality": "high",
        "best_for": ["onboarding", "draft"],
    },
    "gemma4:e2b": {
        "display": "Gemma 4 5.1B (경량 비전)",
        "size_gb": 6.7,
        "lang": "multilingual",
        "vision": True,
        "speed": "fast",
        "quality": "good",
        "best_for": ["onboarding"],
    },
    "gemma4:26b": {
        "display": "Gemma 4 26B (대형 비전)",
        "size_gb": 16.8,
        "lang": "multilingual",
        "vision": True,
        "speed": "slow",
        "quality": "very_high",
        "best_for": ["onboarding", "draft", "compliance"],
    },

    # ── 5. GPT-OSS ──
    "gpt-oss:20b": {
        "display": "GPT-OSS 20B (고품질)",
        "size_gb": 13.8,
        "lang": "multilingual",
        "vision": False,
        "speed": "slow",
        "quality": "very_high",
        "best_for": ["draft", "compliance"],
    },
}

# 기능별 추천 모델 매핑
FEATURE_MODEL_MAP = {
    "search": "qwen3.5:9b",        # 검색: 빠르고 정확한 모델
    "draft": "exaone3.5:latest",    # 초안: 한국어 품질 우선
    "onboarding": "qwen3.5:9b",    # 온보딩: 균형 모델
    "compliance": "exaone-deep:latest",  # 법규: 추론 정확도 우선
}

# 파일 업로드 설정
UPLOAD_MAX_SIZE_MB = 20
# v2.3: .json/.py/.dxf/.xml/.yaml/.log 등 확장자 추가
UPLOAD_ALLOWED_TEXT = [
    ".txt", ".md", ".csv", ".pdf", ".docx",
    ".xlsx", ".xls", ".pptx", ".doc",  # v2.6: MS Office 전체 지원
    ".json", ".py", ".js", ".ts", ".html", ".css",  # 코드/데이터
    ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",  # 설정 파일
    ".log", ".dxf", ".step", ".stp", ".igs",  # CAD/로그 (텍스트 기반)
    ".hwpx", ".rtf",  # 문서
]
UPLOAD_ALLOWED_IMAGE = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"]
FILE_CONTEXT_MAX_CHARS = 8000  # LLM 컨텍스트에 삽입할 최대 문자 수

# 검색 설정
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
TOP_K = 5
RRF_K = 60

# 한국어 형태소 분석
USE_KIWI = True

# ──────────────────────────────────────────────
# 아진산업 조직 정보 (AJIN_ORGANIZATION_REFERENCE.md 기준)
# ──────────────────────────────────────────────

COMPANY_INFO = {
    "name": "아진산업(주)",
    "name_en": "AJIN Industrial Co., Ltd.",
    "ceo": "서정호",
    "headquarters": "경상북도 경산시 진량읍 공단8로 26길 40",
    "tel": "053-856-9100",
    "fax": "053-856-9111",
    "website": "https://www.ajin.co.kr",
    "stock_code": "013310",
    "stock_market": "KOSDAQ",
    "founded": "1976",
    "established": "1978",  # 법인 설립
    "industry": "자동차 차체용 신품 부품 제조업",
    "main_customer": ["현대자동차", "기아자동차"],
    "certifications": ["IATF 16949", "ISO 14001", "ISO 45001", "AEO AAA등급"],
    # v1.6: 사업 현황 업데이트
    "total_employees": 649,
    "revenue_2025": "1조 886억원",
    "revenue_2025_billion_krw": 10886,
    "operating_profit_2025": "643억원",
    "operating_profit_growth": "+99.4%",
    "domestic_sites": 6,
    "overseas_countries": 3,
    "overseas_subsidiaries_count": 6,
    "patents_applied": 164,
    "patents_registered": 65,
}

# v1.6: HMGMA (현대차 메타플랜트 아메리카) 정보
HMGMA_INFO = {
    "name": "Hyundai Motor Group Metaplant America",
    "name_short": "HMGMA",
    "location": "Ellabell, Bryan County, Georgia, USA",
    "capacity": 300_000,  # 연간 생산능력 (대)
    "investment": "$7.6 billion",
    "products": ["Ioniq 5", "Ioniq 9", "Genesis GV70 EV"],
    "ajin_products": ["EWP (전동워터펌프)", "CCH (쿨링채널하우징)", "EV Body Parts"],
    "ajin_subsidiary": "JOON INC",
    "start_of_production": "2025",
}

# v1.6: 해외법인 상세 정보 (config 레벨 — plants.json과 연동)
OVERSEAS_SUBSIDIARIES = {
    "SUB-US-JOON": {
        "name": "JOON INC",
        "name_ko": "준 주식회사",
        "country": "미국",
        "state": "Georgia",
        "city": "Statesboro, Bulloch County",
        "established": "2024",
        "investment": "$312M",
        "employees_target": 630,
        "products": ["EWP", "CCH", "EV Body Parts"],
        "partner_oem": "HMGMA",
        "lat": 32.3547,
        "lng": -81.7593,
    },
    "SUB-US-AJIN": {
        "name": "AJIN USA (Alabama)",
        "name_ko": "아진 USA",
        "country": "미국",
        "state": "Alabama",
        "city": "Cusseta, Chambers County",
        "established": "2008",
        "products": ["Body Parts", "Moving Parts"],
        "partner_oem": ["KMMG", "HMMA"],
        "lat": 32.7826,
        "lng": -85.3040,
    },
    "SUB-CN-SH": {
        "name": "아진실업 유한공사",
        "country": "중국",
        "city": "상해",
        "established": "2006",
    },
    "SUB-CN-YC": {
        "name": "강소아진기차배건 유한공사",
        "country": "중국",
        "city": "염성",
        "established": "2013",
    },
    "SUB-CN-DF": {
        "name": "동풍아진 기차영부건유한공사",
        "country": "중국",
        "city": "산동",
        "established": "2018",
    },
    "SUB-VN": {
        "name": "대우전자부품 베트남법인",
        "country": "베트남",
        "established": None,
    },
}

# ── 부서 목록 (27개: 6본부 + 기술연구소 + 독립부서) ──

DEPARTMENTS = [
    # 독립부서
    {"id": "DEPT-AUDIT", "name": "내부감사팀", "division": None, "is_independent": True,
     "ai_relevance": "low"},

    # 재경본부
    {"id": "DEPT-FIN", "name": "재무팀", "division": "재경본부", "ai_relevance": "medium"},
    {"id": "DEPT-ACC", "name": "회계팀", "division": "재경본부", "ai_relevance": "medium"},
    {"id": "DEPT-IT", "name": "IT전략팀", "division": "재경본부", "ai_relevance": "high",
     "note": "AI 시스템 도입 의사결정자"},
    {"id": "DEPT-COST", "name": "원가기획팀", "division": "재경본부", "ai_relevance": "medium"},

    # 관리본부
    {"id": "DEPT-HR", "name": "총무인사팀", "division": "관리본부", "ai_relevance": "medium"},
    {"id": "DEPT-QM", "name": "품질경영팀", "division": "관리본부", "ai_relevance": "high",
     "note": "내부 심사 및 SQ 평가. 기능 D 핵심 사용자"},
    {"id": "DEPT-ESG", "name": "ESG경영팀", "division": "관리본부", "ai_relevance": "medium"},
    {"id": "DEPT-EDU", "name": "기술교육원", "division": "관리본부", "ai_relevance": "high",
     "note": "기능 C(온보딩) 연계"},

    # 구매본부
    {"id": "DEPT-PURCH", "name": "구매팀", "division": "구매본부", "ai_relevance": "high",
     "note": "기능 B 협력사 이메일 핵심 사용자"},
    {"id": "DEPT-OVERSEAS", "name": "해외지원팀", "division": "구매본부", "ai_relevance": "medium"},
    {"id": "DEPT-COOP", "name": "상생협력팀", "division": "구매본부", "ai_relevance": "medium"},

    # 생산본부
    {"id": "DEPT-PRODMGMT", "name": "생산관리팀", "division": "생산본부", "ai_relevance": "high",
     "note": "공장 현장 핵심 관리 부서"},
    {"id": "DEPT-SAFETY", "name": "안전보건팀", "division": "생산본부", "ai_relevance": "high",
     "note": "기능 D 법규 변경 알림 1순위 수신 부서"},
    {"id": "DEPT-QA", "name": "품질보증팀", "division": "생산본부", "ai_relevance": "critical",
     "note": "기능 A/B 1순위 사용자. 8D/PPAP/SPC 주관"},
    {"id": "DEPT-SALES", "name": "영업팀", "division": "생산본부", "ai_relevance": "high",
     "note": "기능 B 납기 이메일 핵심 사용자"},
    {"id": "DEPT-MATERIAL", "name": "자재관리팀", "division": "생산본부", "ai_relevance": "medium"},

    # 개발본부
    {"id": "DEPT-TECHSALES", "name": "기술영업팀", "division": "개발본부", "ai_relevance": "high"},
    {"id": "DEPT-PARTDEV", "name": "부품개발팀", "division": "개발본부", "ai_relevance": "high",
     "note": "기능 A ECN/PPAP 문서 검색 주요 사용자"},
    {"id": "DEPT-MOLD", "name": "금형생산팀", "division": "개발본부", "ai_relevance": "medium"},

    # 생산기술본부
    {"id": "DEPT-AUTO", "name": "자동화기술팀", "division": "생산기술본부", "ai_relevance": "medium"},
    {"id": "DEPT-FA", "name": "FA사업팀", "division": "생산기술본부", "ai_relevance": "low"},
    {"id": "DEPT-PLANT", "name": "플랜트사업팀", "division": "생산기술본부", "ai_relevance": "low"},
    {"id": "DEPT-DESIGN", "name": "제품설계팀", "division": "생산기술본부", "ai_relevance": "high"},
    {"id": "DEPT-PROCESS", "name": "공법계획팀", "division": "생산기술본부", "ai_relevance": "medium"},
    {"id": "DEPT-PRODTECH", "name": "생산기술팀", "division": "생산기술본부", "ai_relevance": "high",
     "note": "기능 C(온보딩) 핵심 대상 부서, 4M 변경 관리"},
    {"id": "DEPT-CONTAINER", "name": "용기운영팀", "division": "생산기술본부", "ai_relevance": "low"},
    {"id": "DEPT-VISION", "name": "비전연구팀", "division": "생산기술본부", "ai_relevance": "low"},

    # 기술연구소
    {"id": "DEPT-BODY-RND", "name": "바디선행개발팀", "division": "기술연구소", "ai_relevance": "medium"},
    {"id": "DEPT-EE-RND", "name": "전장선행개발팀", "division": "기술연구소", "ai_relevance": "medium"},
]

# ── 국내 공장 (자사 3개 + 계열사 3개) ──

PLANTS = [
    {
        "id": "PLANT-KS-HQ",
        "name": "경산 본사 (제1공장)",
        "name_short": "경산 본사",
        "address": "경상북도 경산시 진량읍 공단8로 26길 40",
        "area_sqm": 24420,
        "established": "1993",
        "main_products": ["쿼터 패널", "대시 패널", "리어 플로어", "리어 패키지 트레이"],
        "main_processes": ["프레스", "용접", "조립"],
        "is_headquarters": True,
        "has_research_center": True,
        "departments_onsite": [
            "안전보건팀", "생산관리팀", "품질보증팀", "생산기술팀",
            "자동화기술팀", "비전연구팀", "금형생산팀",
            "바디선행개발팀", "전장선행개발팀",
        ],
        "zones": [
            {"zone_id": "DZ-KS-HQ-PR-A", "name": "프레스 라인 A", "hazard": "프레스 끼임"},
            {"zone_id": "DZ-KS-HQ-PR-B", "name": "프레스 라인 B", "hazard": "프레스 끼임"},
            {"zone_id": "DZ-KS-HQ-WD-A", "name": "용접 라인 A", "hazard": "로봇 용접 충돌"},
            {"zone_id": "DZ-KS-HQ-WD-B", "name": "용접 라인 B", "hazard": "로봇 용접 충돌"},
            {"zone_id": "DZ-KS-HQ-ASM", "name": "조립 라인", "hazard": "끼임·충돌"},
            {"zone_id": "DZ-KS-HQ-LOG", "name": "물류 구역", "hazard": "지게차 충돌"},
        ],
    },
    {
        "id": "PLANT-KS-2",
        "name": "경산 제2공장 (신상리)",
        "name_short": "경산 제2공장",
        "address": "경상북도 경산시 진량읍 공단4로 171",
        "established": None,
        "main_products": ["카울 멤버"],
        "main_processes": ["프레스", "용접"],
        "is_headquarters": False,
        "has_research_center": False,
        "zones": [
            {"zone_id": "DZ-KS-2-PR", "name": "프레스 구역", "hazard": "프레스 끼임"},
            {"zone_id": "DZ-KS-2-WD", "name": "용접 구역", "hazard": "로봇 용접 충돌"},
        ],
    },
    {
        "id": "PLANT-GJ",
        "name": "경주 구어공장",
        "name_short": "경주 구어",
        "address": "경상북도 경주시 구어리",
        "established": "2017-03",
        "main_products": ["차체 보강 패널류"],
        "main_processes": ["프레스", "용접"],
        "is_headquarters": False,
        "has_research_center": False,
        "zones": [
            {"zone_id": "DZ-GJ-PR-A", "name": "프레스 라인 A", "hazard": "프레스 끼임"},
            {"zone_id": "DZ-GJ-WD-A", "name": "용접 라인 A", "hazard": "로봇 용접 충돌"},
            {"zone_id": "DZ-GJ-LOG", "name": "물류 구역", "hazard": "지게차 충돌"},
        ],
    },
]

# ── 계열사 ──

SUBSIDIARIES_DOMESTIC = [
    {"id": "PLANT-GJ-KAINTECH", "name": "아진카인텍 (경주)", "address": "경상북도 경주시",
     "established": "2011-02", "products": ["차체 부품"]},
    {"id": "PLANT-JJ", "name": "대우전자부품 (정읍)", "address": "전라북도 정읍시 공단 2길 3",
     "established": "2009-12", "products": ["전장부품"]},
    {"id": "PLANT-KS-MOLDTECH", "name": "아진금형텍 (경산)", "address": "경상북도 경산시 진량읍",
     "established": "2017-02", "products": ["프레스 금형"]},
]

SUBSIDIARIES_OVERSEAS = [
    {"id": "SUB-CN-SH", "name": "아진실업 유한공사", "country": "중국", "city": "상해", "established": "2006-12"},
    {"id": "SUB-CN-YC", "name": "강소아진기차배건 유한공사", "country": "중국", "city": "염성", "established": "2013-02"},
    {"id": "SUB-CN-DF", "name": "동풍아진 기차영부건유한공사", "country": "중국", "city": "산동", "established": "2018-11"},
    {"id": "SUB-US-AJIN", "name": "AJIN USA (Alabama)", "country": "미국", "city": "앨라배마 Cusseta", "established": "2008-02"},
    {"id": "SUB-US-JOON", "name": "JOON INC (Georgia)", "country": "미국", "city": "조지아 Statesboro", "established": "2024"},
    {"id": "SUB-VN", "name": "대우전자부품 베트남법인", "country": "베트남", "established": None},
]

# ── AI Assistant 핵심 부서 (ai_relevance high/critical) ──

AI_ASSISTANT_KEY_DEPARTMENTS = [d for d in DEPARTMENTS if d.get("ai_relevance") in ("high", "critical")]

# ── 공장 ID → 이름 매핑 (편의용) ──

PLANT_NAME_MAP = {p["id"]: p["name_short"] for p in PLANTS}

# ── 부서 → 본부 매핑 (편의용) ──

DEPT_DIVISION_MAP = {d["name"]: d.get("division", "독립") for d in DEPARTMENTS}

# ── 온보딩 챗봇 대상 부서 ──

ONBOARDING_DEPARTMENTS = [
    d["name"] for d in DEPARTMENTS
    if d.get("ai_relevance") in ("high", "critical")
]
