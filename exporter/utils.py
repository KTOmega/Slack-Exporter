import asyncio
import logging
import time
from typing import Coroutine, List

from slack_sdk.web.async_client import AsyncSlackResponse
from slack_sdk.errors import SlackApiError

log = logging.getLogger("utils")

class AsyncIteratorWithRetry:
    def __init__(self, coro: Coroutine, retries=5, *args, **kwargs):
        self._iterator = None
        self._retries = retries

        self._coro = (coro, args, kwargs)

    async def run(self):
        coro, args, kwargs = self._coro
        self._iterator = await with_retry(coro, *args, **kwargs)

    def __aiter__(self):
        if self._iterator is None:
            raise RuntimeError("Need to await the run method first")

        self._iterator.__aiter__()
        return self

    async def __anext__(self):
        return await with_retry(self._iterator.__anext__, retries=self._retries)

async def with_retry(coro: Coroutine, retries=5, *args, **kwargs):
    retry = 0
    while retry < retries:
        try:
            return await coro(*args, **kwargs)
        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                delay = int(e.response.headers["Retry-After"])
                log.warning(f"API call {coro.__name__} rate limited by Slack for {delay} seconds")

                await asyncio.sleep(delay + retry) # crappy additive increase
                retry += 1
            else:
                raise e
    else:
        raise RuntimeError("Rate limited by Slack")

class AggregateError(Exception):
    def __init__(self, message: str, errors: List[Exception]):
        self.errors = errors

        super(AggregateError, self).__init__(message)