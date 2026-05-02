from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User, get_db
from api.dependencies import get_current_user, get_session_token
from api.schemas.auth import (
    AuthMessageResponse,
    LoginRequest,
    MeResponse,
    RequestEmailCodeRequest,
    VerifyEmailCodeRequest,
)
from api.services.auth import (
    create_session_for_user,
    get_user_by_email,
    request_email_code,
    revoke_session_token,
    verify_email_code,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

SESSION_COOKIE_NAME = "auth_session"


@router.post("/login", response_model=AuthMessageResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_email(db, str(body.email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_token = await create_session_for_user(db, user.id)
    await db.commit()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=24 * 60 * 60,
    )
    return AuthMessageResponse(message="Logged in")


@router.post("/logout", response_model=AuthMessageResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Depends(get_session_token),
):
    if session_token:
        await revoke_session_token(db, session_token)
        await db.commit()

    response.delete_cookie(SESSION_COOKIE_NAME)
    return AuthMessageResponse(message="Logged out")


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/request-code", response_model=AuthMessageResponse)
async def request_code(
    body: RequestEmailCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    await request_email_code(db, email=str(body.email), purpose=body.purpose)
    await db.commit()
    return AuthMessageResponse(message="Code sent")


@router.post("/verify-code", response_model=AuthMessageResponse)
async def verify_code(
    body: VerifyEmailCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    is_valid = await verify_email_code(
        db,
        email=str(body.email),
        purpose=body.purpose,
        code=body.code,
        new_password=body.new_password,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    await db.commit()
    return AuthMessageResponse(message="Code verified")
