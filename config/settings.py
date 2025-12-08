import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # 여러 API 키 지원 (콤마로 구분)
    API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
    API_KEY = os.getenv("API_KEY")  # 단일 키 (호환성)
    if API_KEY and API_KEY not in API_KEYS:
        API_KEYS.insert(0, API_KEY)
    API_BASE_URL = os.getenv("API_BASE_URL")
    CENTRAL_LIST_URL = os.getenv("CENTRAL_LIST_URL")
    CENTRAL_DETAILED_URL = os.getenv("CENTRAL_DETAILED_URL")
    REGIONAL_LIST_URL = os.getenv("REGIONAL_LIST_URL")
    REGIONAL_DETAILED_URL = os.getenv("REGIONAL_DETAILED_URL")
    DB_URL = os.getenv("DB_URL", "sqlite:///./tq_data.db")
    
    # Concurrency Settings
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 10))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

    # Cloudflare D1 Settings
    CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
    CLOUDFLARE_D1_DB_ID = os.getenv("CLOUDFLARE_D1_DB_ID")

settings = Settings()
