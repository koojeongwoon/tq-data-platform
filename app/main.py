"""
TQ Data Platform API Server

진입점: 라우터 등록만 담당
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, welfare

app = FastAPI(
    title="TQ Data Platform API",
    description="Korean government welfare information API",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(welfare.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
