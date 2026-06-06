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
        result = await session.execute(
            select(StreamEvent)
            .where(StreamEvent.task_id == TASK_ID)
            .order_by(desc(StreamEvent.sequence_number))
            .limit(20)
        )
        events = result.scalars().all()
        for e in events:
            # Try both 'body' and 'content' column names
            raw = getattr(e, 'body', None) or getattr(e, 'content', '') or ''
            try:
                body = json.loads(raw)
            except Exception:
                body = {'raw': raw[:300]}
            ts = str(getattr(e, 'timestamp', ''))[:19]
            print(f"\n=== seq={e.sequence_number} [{e.event_type}] {ts} ===")
            print(json.dumps(body, ensure_ascii=False, indent=2)[:600])

asyncio.run(test())
