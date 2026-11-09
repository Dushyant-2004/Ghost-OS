import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.approval import Approval, ApprovalStatus
from app.services.approvals import decide_approval, expire_approvals

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class DecisionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=1_000)


def _response(approval: Approval) -> dict:
    return {
        "id": approval.id,
        "task_id": approval.task_id,
        "action": approval.action,
        "description": approval.description,
        "requested_permissions": json.loads(approval.requested_permissions),
        "risk_level": approval.risk_level,
        "agent_name": approval.agent_name,
        "status": approval.status,
        "requested_at": approval.requested_at,
        "expires_at": approval.expires_at,
        "decided_at": approval.decided_at,
        "decided_by": approval.decided_by,
        "decision_reason": approval.decision_reason,
    }


@router.get("")
async def list_approvals(session: AsyncSession = Depends(get_db)) -> list[dict]:
    await expire_approvals(session)
    await session.commit()
    result = await session.execute(select(Approval).order_by(Approval.requested_at.desc()))
    return [_response(item) for item in result.scalars()]


@router.get("/{approval_id}")
async def get_approval(approval_id: str, session: AsyncSession = Depends(get_db)) -> dict:
    approval = await session.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(404, "Approval not found")
    await expire_approvals(session)
    await session.commit()
    return _response(approval)


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, request: DecisionRequest, session: AsyncSession = Depends(get_db)) -> dict:
    return await _decide(approval_id, request, True, session)


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, request: DecisionRequest, session: AsyncSession = Depends(get_db)) -> dict:
    return await _decide(approval_id, request, False, session)


async def _decide(
    approval_id: str, request: DecisionRequest, approved: bool, session: AsyncSession
) -> dict:
    approval = await session.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(404, "Approval not found")
    try:
        await decide_approval(session, approval, approved, request.actor, request.reason)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    await session.commit()
    return _response(approval)
