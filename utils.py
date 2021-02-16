from slack_sdk.web.async_client import AsyncSlackResponse
from slack_sdk.errors import SlackApiError

import asyncio
import logging
from typing import Coroutine

log = logging.getLogger()

class AsyncIteratorWithRetry:
    def __init__(self, iterator, retries=3):
        self._iterator = iterator
        self._retries = retries

    def __aiter__(self):
        self._iterator.__aiter__()
        return self

    async def __anext__(self):
        retry = 0
        while retry <= self._retries:
            try:
                return await self._iterator.__anext__()
            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    delay = int(e.response.headers["Retry-After"])
                    log.warning(f"API iterator rate limited by Slack for {delay} seconds")

                    await asyncio.sleep(delay + 1)
                    retry += 1
                else:
                    raise e

async def with_retry(api_call: Coroutine, retries=3, *args, **kwargs) -> AsyncSlackResponse:
    retry = 0
    while retry <= retries:
        try:
            return await api_call(*args, **kwargs)
        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                delay = int(e.response.headers["Retry-After"])
                log.warning(f"API call {api_call.__name__} rate limited by Slack for {delay} seconds")

                await asyncio.sleep(delay + 1)
                retry += 1
            else:
                raise e