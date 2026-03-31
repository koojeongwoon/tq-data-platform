"""
TQ Data Platform API Server

진입점: 라우터 등록 및 전역 에러 핸들러 설정
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import TQBaseException
from app.middleware.error_handler import (
    custom_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

# Domain routers
from app.auth import router as auth_router
from app.chat import router as chat_router
from app.onboarding import router as onboarding_router
from app.dashboard import router as dashboard_router
from app.welfare import router as welfare_router
from app.search import router as search_router
from app.chat.service import RAGService
from app.core import health_router

from shared.config.settings import settings
from shared.services.qdrant_service import QdrantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager

    Startup:
    - Pre-load embedding models (multilingual-e5-large + BM25)

    Shutdown:
    - Cleanup resources
    """
    # Startup
    print("\n🚀 Starting TQ Data Platform API...")

    # Pre-load embedding models
    print("📦 Loading embedding models...")
    try:
        qdrant_service = QdrantService(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        # Trigger lazy loading of both models
        qdrant_service._get_dense_model()   # multilingual-e5-large
        qdrant_service._get_sparse_model()  # BM25

        # Store in app state for reuse
        app.state.qdrant_service = qdrant_service
        app.state.rag_service = RAGService(qdrant_service=qdrant_service)
        print("✅ Embedding models and RAG service loaded successfully")
    except Exception as e:
        print(f"⚠️  Warning: Failed to load embedding models: {e}")
        print("   Models will be loaded on first request")
        app.state.qdrant_service = None

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
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(dashboard_router)
app.include_router(welfare_router)
app.include_router(search_router)
app.include_router(chat_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
