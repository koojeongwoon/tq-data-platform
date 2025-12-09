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

settings = Settings()
