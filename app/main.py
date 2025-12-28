"""
TQ Data Platform API Server

진입점: 라우터 등록 및 전역 에러 핸들러 설정
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import TQBaseException
from app.middleware.error_handler import (
    custom_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.routers import health, search, welfare
from shared.services.embedding import get_embedding_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager

    Startup:
    - Pre-load BGE-M3 embedding model (prevents first-request timeout)

    Shutdown:
    - Cleanup resources
    """
    # Startup
    print("\n🚀 Starting TQ Data Platform API...")
    print("📦 Loading BGE-M3 embedding model...")
    try:
        embedding_service = get_embedding_service()
        print("✅ Embedding model loaded successfully")
        app.state.embedding_service = embedding_service
    except Exception as e:
        print(f"⚠️  Warning: Failed to load embedding model: {e}")
        print("   API will start without embedding capabilities")
        app.state.embedding_service = None

    print("✅ API server ready\n")

    yield

    # Shutdown
    print("\n🛑 Shutting down TQ Data Platform API...")
    print("✅ Shutdown complete\n")


app = FastAPI(
    title="TQ Data Platform API",
    description="Korean government welfare information API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handlers
app.add_exception_handler(TQBaseException, custom_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Register routers
app.include_router(health.router)
app.include_router(welfare.router)
app.include_router(search.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
