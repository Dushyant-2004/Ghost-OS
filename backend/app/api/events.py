import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.task import TaskEvent

router = APIRouter(tags=["events"])


@router.websocket("/ws/tasks/{task_id}")
async def task_events(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    last_id = int(websocket.query_params.get("after", "0") or 0)
    try:
        while True:
            async with SessionLocal() as session:
                result = await session.execute(
                    select(TaskEvent)
                    .where(TaskEvent.task_id == task_id, TaskEvent.id > last_id)
                    .order_by(TaskEvent.id)
                )
                events = list(result.scalars())
            for event in events:
                await websocket.send_json({
                    "id": event.id,
                    "task_id": task_id,
                    "event_type": event.event_type,
                    "message": event.message,
                    "timestamp": event.timestamp.isoformat(),
                })
                last_id = event.id
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
