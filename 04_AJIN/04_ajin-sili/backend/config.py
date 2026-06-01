"""FastAPI 백엔드 설정."""

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000

# CORS
CORS_ORIGINS = [
    # Vite dev server (Day 1+ React 마이그레이션)
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Streamlit 호환 (legacy v3.5)
    "http://localhost:8502",
    "http://localhost:8501",
    "http://127.0.0.1:8502",
    "http://127.0.0.1:8501",
    # Firebase Hosting (production)
    "https://ajin-cb.web.app",
    "https://ajin-cb.firebaseapp.com",
    # Vercel frontend hosting. Normal browser traffic uses same-origin /api rewrites,
    # but direct Cloud Run API testing from this origin should also pass CORS.
    "https://ajin-ai-assistant-frontend.vercel.app",
]

# API prefix
API_PREFIX = "/api"
