"""Health Check Router"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "TQ Data Platform API",
        "version": "0.1.0",
        "status": "running"
    }


@router.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}
