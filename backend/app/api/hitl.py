"""Human-in-the-Loop (HITL) API endpoints.

Provides endpoints for:
- Submitting user responses to interrupts
- Fetching pending interrupts (for reconnection recovery)
- Cancelling pending interrupts
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.hitl.interrupt_manager import get_interrupt_manager
from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger

router = APIRouter(prefix="/hitl", tags=["hitl"])
logger = get_logger(__name__)


async def _verify_thread_ownership(thread_id: str, user_id: str, interrupt_manager) -> None:
    """Verify the requesting user owns the pending interrupt for a thread.

    Args:
        thread_id: Thread/conversation ID
        user_id: ID of the requesting user
        interrupt_manager: InterruptManager instance

    Raises:
        HTTPException: 403 if interrupt belongs to a different user
    """
    pending = await interrupt_manager.get_pending_interrupt(thread_id)
    if pending is not None:
        stored_user = pending.get("user_id")
        if stored_user and stored_user != user_id:
            raise HTTPException(status_code=403, detail="Access denied")


class InterruptResponseRequest(BaseModel):
    """Request to respond to an interrupt."""

    interrupt_id: str = Field(..., description="ID of the interrupt being responded to")
    action: Literal["approve", "deny", "skip", "select", "input", "approve_always", "cancel"] = Field(
        ..., description="User action"
    )
    value: str | None = Field(default=None, description="Selected value or input text")


class InterruptResponseResult(BaseModel):
    """Result of submitting an interrupt response."""

    success: bool
    message: str


class PendingInterruptResponse(BaseModel):
    """Response containing pending interrupt details."""

    has_pending: bool
    interrupt: dict | None = None


@router.post("/respond/{thread_id}", response_model=InterruptResponseResult)
async def respond_to_interrupt(
    thread_id: str,
    request: InterruptResponseRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> InterruptResponseResult:
    """Submit user response to a pending interrupt.

    Args:
        thread_id: Thread/conversation ID
        request: Interrupt response details

    Returns:
        Success status and message
    """
    interrupt_manager = get_interrupt_manager()

    try:
        await _verify_thread_ownership(thread_id, current_user.id, interrupt_manager)

        success = await interrupt_manager.submit_response(
            thread_id=thread_id,
            interrupt_id=request.interrupt_id,
            action=request.action,
            value=request.value,
        )

        if success:
            logger.info(
                "hitl_response_submitted",
                thread_id=thread_id,
                interrupt_id=request.interrupt_id,
                action=request.action,
            )
            return InterruptResponseResult(
                success=True,
                message=f"Response submitted: {request.action}",
            )
        else:
            # No subscribers - interrupt may have already timed out or been processed
            logger.warning(
                "hitl_response_no_subscribers",
                thread_id=thread_id,
                interrupt_id=request.interrupt_id,
            )
            return InterruptResponseResult(
                success=False,
                message="No active listener for this interrupt. It may have timed out.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "hitl_response_error",
            thread_id=thread_id,
            interrupt_id=request.interrupt_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


@router.get("/pending/{thread_id}", response_model=PendingInterruptResponse)
async def get_pending_interrupt(
    thread_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> PendingInterruptResponse:
    """Get any pending interrupt for a thread.

    Used for reconnection recovery - when a client reconnects, it can
    check if there's a pending interrupt that needs response.

    Args:
        thread_id: Thread/conversation ID

    Returns:
        Pending interrupt details if any
    """
    interrupt_manager = get_interrupt_manager()

    try:
        await _verify_thread_ownership(thread_id, current_user.id, interrupt_manager)

        interrupt = await interrupt_manager.get_pending_interrupt(thread_id)

        if interrupt:
            logger.info(
                "hitl_pending_interrupt_found",
                thread_id=thread_id,
                interrupt_id=interrupt.get("interrupt_id"),
            )
            return PendingInterruptResponse(
                has_pending=True,
                interrupt=interrupt,
            )
        else:
            return PendingInterruptResponse(
                has_pending=False,
                interrupt=None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "hitl_pending_check_error",
            thread_id=thread_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


@router.delete("/cancel/{thread_id}/{interrupt_id}", response_model=InterruptResponseResult)
async def cancel_interrupt(
    thread_id: str,
    interrupt_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> InterruptResponseResult:
    """Cancel a pending interrupt.

    Args:
        thread_id: Thread/conversation ID
        interrupt_id: Interrupt ID to cancel

    Returns:
        Success status and message
    """
    interrupt_manager = get_interrupt_manager()

    try:
        await _verify_thread_ownership(thread_id, current_user.id, interrupt_manager)

        cancelled = await interrupt_manager.cancel_interrupt(
            thread_id=thread_id,
            interrupt_id=interrupt_id,
        )

        if cancelled:
            logger.info(
                "hitl_interrupt_cancelled",
                thread_id=thread_id,
                interrupt_id=interrupt_id,
            )
            return InterruptResponseResult(
                success=True,
                message="Interrupt cancelled successfully",
            )
        else:
            return InterruptResponseResult(
                success=False,
                message="Interrupt not found or already processed",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "hitl_cancel_error",
            thread_id=thread_id,
            interrupt_id=interrupt_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
