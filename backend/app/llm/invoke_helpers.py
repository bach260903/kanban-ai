"""Rate limiting and retries for Google Gemini free-tier quotas (429)."""



from __future__ import annotations



import asyncio

import logging

import re

import time

from typing import Any



from langchain_core.language_models.chat_models import BaseChatModel

from langchain_core.messages import BaseMessage



from app.config import settings



logger = logging.getLogger(__name__)



_google_spacing_lock = asyncio.Lock()

_last_google_call_monotonic = 0.0



_RETRY_IN_SECONDS = re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.IGNORECASE)





def _is_google_llm(llm: BaseChatModel) -> bool:

    return type(llm).__name__ == "ChatGoogleGenerativeAI"





def _retry_delay_seconds(exc: BaseException) -> float:

    match = _RETRY_IN_SECONDS.search(str(exc))

    if match:

        return float(match.group(1)) + 2.0

    return min(15.0 * 2, 70.0)





async def _wait_google_spacing() -> None:

    """Serialize Gemini calls and enforce minimum spacing (free tier ≈ 5 RPM)."""

    global _last_google_call_monotonic

    interval = settings.google_api_min_interval_seconds

    if interval <= 0:

        return

    async with _google_spacing_lock:

        now = time.monotonic()

        wait_for = interval - (now - _last_google_call_monotonic)

        if wait_for > 0:

            await asyncio.sleep(wait_for)

        _last_google_call_monotonic = time.monotonic()





async def ainvoke_llm(

    llm: BaseChatModel,

    messages: list[BaseMessage],

    **kwargs: Any,

) -> Any:

    """Invoke chat model; Gemini calls get spacing + 429 retries."""

    if not _is_google_llm(llm):

        return await llm.ainvoke(messages, **kwargs)



    import google.api_core.exceptions



    max_attempts = settings.google_api_max_retries

    last_exc: BaseException | None = None

    for attempt in range(1, max_attempts + 1):

        await _wait_google_spacing()

        try:

            return await llm.ainvoke(messages, **kwargs)

        except google.api_core.exceptions.ResourceExhausted as exc:

            last_exc = exc

            if attempt >= max_attempts:

                break

            delay = _retry_delay_seconds(exc)

            logger.warning(

                "Gemini rate limit (attempt %s/%s); waiting %.1fs before retry",

                attempt,

                max_attempts,

                delay,

            )

            await asyncio.sleep(delay)

    assert last_exc is not None

    raise last_exc


