from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User, get_db
from api.dependencies import (
    VkBotManagerUser,
    VkBotMemberUser,
    VkBotUser,
    get_current_user,
    verify_vk_bot_secret_header,
)
from api.schemas.auth import MeResponse
from api.schemas.rental import RentalsList
from api.schemas.rental_request import (
    RentalRequestCreate,
    RentalRequestDecision,
    RentalRequestResponse,
    RentalRequestUpdate,
)
from api.schemas.vk_integration import RequestVkLinkCodeResponse, VkLinkCompleteRequest
from api.services import vk_integration as vk_svc
from api.services.rentals import list_active_rentals_for_user
from api.routers.rental_request_helpers import (
    create_rental_request_for_user_response,
    manager_decide_rental_request_response,
    update_pending_rental_request_for_owner_response,
)
from api.routers.rentals import _build_rental_response

auth_vk_router = APIRouter(prefix="/api/auth/vk-link", tags=["Auth"])
integrations_router = APIRouter(prefix="/api/integrations/vk", tags=["VK Integration"])


@auth_vk_router.post("/request_code", response_model=RequestVkLinkCodeResponse)
async def request_vk_link_code(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code, expires_at = await vk_svc.request_vk_link_code(db, current_user.id)
    await db.commit()
    return RequestVkLinkCodeResponse(code=code, expires_at=expires_at)


@integrations_router.post("/link-complete", response_model=MeResponse)
async def vk_link_complete(
    body: VkLinkCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_vk_bot_secret_header),
):
    user, err = await vk_svc.complete_vk_link(db, code=body.code, vk_user_id=body.vk_user_id)
    if err == "invalid_code":
        raise HTTPException(status_code=400, detail="Invalid or expired link code")
    if err == "vk_already_linked":
        raise HTTPException(
            status_code=409,
            detail="This VK account is already linked to another user.",
        )
    assert user is not None
    await db.commit()
    return user


@integrations_router.get("/me", response_model=MeResponse)
async def vk_me(current_user: VkBotUser):
    return current_user


@integrations_router.post("/rental-requests", response_model=RentalRequestResponse)
async def vk_create_rental_request(
    body: RentalRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: VkBotMemberUser,
):
    return await create_rental_request_for_user_response(
        db, user=current_user, body=body
    )


@integrations_router.patch("/rental-requests/{rental_request_id}", response_model=RentalRequestResponse)
async def vk_update_rental_request(
    rental_request_id: int,
    body: RentalRequestUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: VkBotMemberUser,
):
    return await update_pending_rental_request_for_owner_response(
        db,
        rental_request_id=rental_request_id,
        owner=current_user,
        body=body,
    )


@integrations_router.get("/rentals/active", response_model=RentalsList)
async def vk_get_active_rentals(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: VkBotUser,
):
    """Активные аренды только для пользователя, привязанного к переданному vk_user_id."""
    rentals = await list_active_rentals_for_user(db, current_user.id)
    out = [await _build_rental_response(db, r) for r in rentals]
    return RentalsList(rentals=out)


@integrations_router.patch(
    "/manager/rental-requests/{rental_request_id}",
    response_model=RentalRequestResponse,
)
async def vk_manager_decide_rental_request(
    rental_request_id: int,
    decision: RentalRequestDecision,
    db: Annotated[AsyncSession, Depends(get_db)],
    manager: VkBotManagerUser,
):
    return await manager_decide_rental_request_response(
        db,
        rental_request_id=rental_request_id,
        manager=manager,
        decision=decision,
    )
