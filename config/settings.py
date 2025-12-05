import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    API_KEY = os.getenv("API_KEY")
    API_BASE_URL = os.getenv("API_BASE_URL")
    CENTRAL_LIST_URL = os.getenv("CENTRAL_LIST_URL")
    CENTRAL_DETAILED_URL = os.getenv("CENTRAL_DETAILED_URL")
    REGIONAL_LIST_URL = os.getenv("REGIONAL_LIST_URL")
    REGIONAL_DETAILED_URL = os.getenv("REGIONAL_DETAILED_URL")
    DB_URL = os.getenv("DB_URL", "sqlite:///./tq_data.db")
    
    # Concurrency Settings
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 10))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

settings = Settings()
