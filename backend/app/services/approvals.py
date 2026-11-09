import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval, ApprovalStatus


async def expire_approvals(session: AsyncSession) -> None:
    result = await session.execute(
        select(Approval).where(
            Approval.status == ApprovalStatus.PENDING,
            Approval.expires_at <= datetime.utcnow(),
        )
    )
    for approval in result.scalars():
        approval.status = ApprovalStatus.EXPIRED
        approval.decided_at = datetime.utcnow()
    await session.flush()


async def create_approval(
    session: AsyncSession,
    *,
    task_id: str,
    action: str,
    description: str,
    permissions: list[str],
    agent_name: str,
    risk_level: str = "high",
) -> Approval:
    approval = Approval(
        task_id=task_id,
        action=action,
        description=description,
        requested_permissions=json.dumps(permissions),
        agent_name=agent_name,
        risk_level=risk_level,
    )
    session.add(approval)
    await session.flush()
    return approval


async def decide_approval(
    session: AsyncSession, approval: Approval, approved: bool, actor: str, reason: str | None
) -> Approval:
    await expire_approvals(session)
    if approval.status != ApprovalStatus.PENDING:
        raise ValueError(f"Approval is not pending: {approval.status}")
    approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
    approval.decided_at = datetime.utcnow()
    approval.decided_by = actor
    approval.decision_reason = reason
    await session.flush()
    return approval
