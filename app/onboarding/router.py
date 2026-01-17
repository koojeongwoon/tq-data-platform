"""Onboarding router - 회원가입 후 대화형 프로필 수집"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.router import get_current_user
from app.onboarding.schemas import (
    CREATE_ONBOARDING_SESSIONS_TABLE,
    CREATE_USER_PREFERENCES_TABLE,
    CompleteRequest,
    CompleteResponse,
    ConversationRequest,
    ConversationResponse,
    OnboardingProfile,
)
from app.onboarding.service import OnboardingService
from shared.db.postgres import PostgresClient

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def _init_tables():
    """온보딩 관련 테이블 초기화"""
    postgres = PostgresClient()
    postgres.execute_ddl(CREATE_USER_PREFERENCES_TABLE)
    postgres.execute_ddl(CREATE_ONBOARDING_SESSIONS_TABLE)


# 앱 시작 시 테이블 생성
_init_tables()


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/conversation", response_model=ConversationResponse)
async def conversation(
    body: ConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    온보딩 대화

    대화형으로 사용자 프로필 정보를 수집합니다.
    - 지역 → 생애주기 → 관심분야 순서로 수집
    - 첫 요청 시 message를 빈 문자열로 보내면 인사말 반환

    Authorization: Bearer <access_token> 필요
    """
    service = OnboardingService()

    result = service.process_message(
        user_id=current_user["id"],
        user_name=current_user["name"],
        message=body.message,
        session_id=body.session_id
    )

    return ConversationResponse(
        response=result["response"],
        session_id=result["session_id"],
        step=result["step"],
        profile=OnboardingProfile(
            region=result["profile"].get("region"),
            life_cycle=result["profile"].get("life_cycle"),
            interests=result["profile"].get("interests")
        ),
        is_completed=result["is_completed"],
        quick_replies=result["quick_replies"]
    )


@router.post("/complete", response_model=CompleteResponse)
async def complete(
    body: CompleteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    온보딩 완료

    온보딩을 완료 처리하고 프로필을 저장합니다.

    Authorization: Bearer <access_token> 필요
    """
    service = OnboardingService()

    profile_dict = {
        "region": body.profile.region,
        "life_cycle": body.profile.life_cycle,
        "interests": body.profile.interests
    }

    result = service.complete_onboarding(
        user_id=current_user["id"],
        session_id=body.session_id,
        profile=profile_dict
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "온보딩 완료에 실패했습니다")
        )

    return CompleteResponse(
        message="온보딩이 완료되었습니다.",
        user=result["user"]
    )


@router.delete("/conversation/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    온보딩 세션 삭제

    온보딩을 건너뛸 때 세션을 삭제합니다.

    Authorization: Bearer <access_token> 필요
    """
    service = OnboardingService()

    service.delete_session(
        user_id=current_user["id"],
        session_id=session_id
    )

    return {"message": "온보딩 세션이 삭제되었습니다."}
