from slack_sdk.web.async_client import AsyncSlackResponse
from slack_sdk.errors import SlackApiError

import asyncio
import logging
from typing import Coroutine

log = logging.getLogger("utils")

class AsyncIteratorWithRetry:
    def __init__(self, iterator, retries=3):
        self._iterator = iterator
        self._retries = retries

    def __aiter__(self):
        self._iterator.__aiter__()
        return self

    async def __anext__(self):
        return await with_retry(self._iterator.__anext__, retries=self._retries)

async def with_retry(coro: Coroutine, retries=3, *args, **kwargs):
    retry = 0
    while retry <= retries:
        try:
            return await coro(*args, **kwargs)
        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                delay = int(e.response.headers["Retry-After"])
                log.warning(f"API call {api_call.__name__} rate limited by Slack for {delay} seconds")

                await asyncio.sleep(delay + 1)
                retry += 1
            else:
                raise e