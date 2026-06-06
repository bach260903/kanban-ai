import asyncio
from app.database import async_session_maker
from app.models.agent_run import AgentRun
from sqlalchemy import select, desc
import json

async def test():
    async with async_session_maker() as session:
        result = await session.execute(
            select(AgentRun)
            .order_by(desc(AgentRun.started_at))
            .limit(10)
        )
        runs = result.scalars().all()
        if not runs:
            print("No agent runs found")
            return
        for r in runs:
            print(f"\n--- AgentRun {r.id} ---")
            print(f"  status     : {r.status}")
            print(f"  agent_type : {r.agent_type}")
            print(f"  task_id    : {r.task_id}")
            print(f"  started_at : {r.started_at}")
            print(f"  completed_at: {r.completed_at}")
            if r.result:
                try:
                    res = r.result if isinstance(r.result, dict) else json.loads(r.result)
                    err = res.get("error") or res.get("message") or res.get("code") or str(res)
                    print(f"  result     : {str(err)[:500]}")
                except Exception:
                    print(f"  result     : {str(r.result)[:500]}")

asyncio.run(test())
