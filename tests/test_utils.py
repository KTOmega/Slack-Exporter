import asyncio
import logging
import sys
import time

import src.utils

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_slack_response import AsyncSlackResponse

async def with_retry_coro():
    data = {
        "ok": False,
        "error": "ratelimited"
    }

    response = AsyncSlackResponse(
        client=None,
        http_verb=None,
        api_url=None,
        req_args=None,
        data=data,
        headers={
            "Retry-After": 1
        },
        status_code=429
    )

    raise SlackApiError("The request to the Slack API failed.", response)

async def with_retry_with_rate_limit(times=1, retries=1):
    tasks = []

    for i in range(times):
        task = src.utils.with_retry(with_retry_coro, retries=retries)

        tasks.append(asyncio.create_task(task))

    return await asyncio.wait(tasks)

def rate_limit_test(times=1):
    retries = 2
    awaitable = with_retry_with_rate_limit(times, retries=retries)
    expected_time = sum([1 + x for x in range(retries)])
    print(expected_time)

    time_start = time.time()
    done, _ = asyncio.run(awaitable)
    time_end = time.time()
    print(time_end - time_start)

    for task in done:
        assert task.done()

        exc = task.exception()
        assert exc is not None
        assert isinstance(exc, RuntimeError)

    assert len(done) == times
    assert abs(time_end - time_start - expected_time) <= 1

def test_with_retry_rate_limit_once():
    rate_limit_test(1)

def test_with_retry_rate_limit_a_lot():
    rate_limit_test(5)