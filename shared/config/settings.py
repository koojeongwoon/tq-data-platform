import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    # 여러 API 키 지원 (콤마로 구분)
    API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
    API_BASE_URL = "https://apis.data.go.kr/B554287"
    CENTRAL_LIST_URL = "/NationalWelfareInformationsV001/NationalWelfarelistV001"
    CENTRAL_DETAILED_URL = "/NationalWelfareInformationsV001/NationalWelfaredetailedV001"
    REGIONAL_LIST_URL = "/LocalGovernmentWelfareInformations/LcgvWelfarelist"
    REGIONAL_DETAILED_URL = "/LocalGovernmentWelfareInformations/LcgvWelfaredetailed"
    DB_URL = "sqlite:///./tq_data.db"

    # Concurrency Settings
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 10))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

    # Cloudflare D1 Settings
    CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
    CLOUDFLARE_D1_DB_ID = os.getenv("CLOUDFLARE_D1_DB_ID")

    # PostgreSQL Settings
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "welfare_db")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "welfare_user")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "welfare_password")

    # Qdrant Settings
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
    QDRANT_CACHE_COLLECTION = os.getenv("QDRANT_CACHE_COLLECTION", "llm_cache")
    QDRANT_CACHE_THRESHOLD = float(os.getenv("QDRANT_CACHE_THRESHOLD", 0.95))

    # Embedding Settings
    USE_EMBEDDINGS = os.getenv("USE_EMBEDDINGS", "true").lower() == "true"

    # OpenAI Settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # JWT Settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-key-in-production")

settings = Settings()
