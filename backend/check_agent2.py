import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from app.database import async_session_maker
from app.models.stream_event import StreamEvent, StreamEventType
from app.models.task import Task
from sqlalchemy import select, desc
import json

TASK_ID = "3bde1b66-4d67-4a58-af1d-68daffc6f4ec"

async def test():
    async with async_session_maker() as session:
        task = await session.get(Task, TASK_ID)
        print(f"Task status: {task.status if task else 'NOT FOUND'}")

        result = await session.execute(
            select(StreamEvent)
            .where(StreamEvent.task_id == TASK_ID)
            .order_by(desc(StreamEvent.sequence_number))
            .limit(20)
        )
        events = result.scalars().all()
        print(f"\n--- Last {len(events)} stream events ---")
        for e in events:
            try:
                body = json.loads(e.body) if isinstance(e.body, str) else (
                    json.loads(e.content) if hasattr(e, 'content') else {}
                )
            except Exception:
                body = {}
            ts = str(e.timestamp)[:19] if hasattr(e, 'timestamp') else ''
            # Get error/relevant info
            info = body.get('error_type') or body.get('message') or body.get('reasoning') or body.get('from','') + '->' + body.get('to','') or ''
            print(f"  seq={e.sequence_number} [{e.event_type}] {ts}  {str(info)[:200]}")

asyncio.run(test())
