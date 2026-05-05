from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User, get_db
from api.dependencies import require_manager_or_admin, require_rental_request_submitter
from api.schemas.rental_return_request import (
    RentalReturnRequestCreate,
    RentalReturnRequestDecision,
    RentalReturnRequestResponse,
)
from api.routers.rental_return_request_helpers import (
    create_rental_return_request_for_user_response,
    manager_decide_rental_return_request_response,
)

router = APIRouter(
    prefix="/api/rental-return-requests",
    tags=["RentalReturnRequests"],
)
manager_router = APIRouter(
    prefix="/api/manager/rental-return-requests",
    tags=["ManagerRentalReturnRequests"],
)


@router.post("/", response_model=RentalReturnRequestResponse)
async def create_rental_return_request_endpoint(
    body: RentalReturnRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_rental_request_submitter()),
):
    """Создаёт заявку на возврат (статус `pending`)."""

    return await create_rental_return_request_for_user_response(
        db, user=current_user, body=body
    )


@manager_router.patch("/{return_request_id}", response_model=RentalReturnRequestResponse)
async def decide_rental_return_request_endpoint(
    return_request_id: int,
    decision: RentalReturnRequestDecision,
    db: Annotated[AsyncSession, Depends(get_db)],
    manager: User = Depends(require_manager_or_admin()),
):
    """Принять или отклонить заявку на возврат."""

    return await manager_decide_rental_return_request_response(
        db,
        return_request_id=return_request_id,
        manager=manager,
        decision=decision,
    )
