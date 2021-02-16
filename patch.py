import slack_sdk.web

import logging
from typing import Union

async def _AsyncSlackResponse___anext__(self):
    """Retrieves the next portion of results, if 'next_cursor' is present.

    Note:
        Some responses return collections of information
        like channel and user lists. If they do it's likely
        that you'll only receive a portion of results. This
        method allows you to iterate over the response until
        your code hits 'break' or there are no more results
        to be found.

    Returns:
        (AsyncSlackResponse) self
            With the new response data now attached to this object.

    Raises:
        SlackApiError: If the request to the Slack API failed.
        StopAsyncIteration: If 'next_cursor' is not present or empty.
    """
    from slack_sdk.web.internal_utils import _next_cursor_is_present
    def _page_data_is_present(data: Union[dict, bytes]) -> bool:
        return (
            "paging" in data and
            "page" in data["paging"] and
            "total" in data["paging"]
        )

    if isinstance(self.data, bytes):
        raise ValueError(
            "As the response.data is binary data, this operation is unsupported"
        )
    self._iteration += 1
    if self._iteration == 1:
        return self
    if _next_cursor_is_present(self.data):  # skipcq: PYL-R1705
        params = self.req_args.get("params", {})
        if params is None:
            params = {}
        params.update({"cursor": self.data["response_metadata"]["next_cursor"]})
        self.req_args.update({"params": params})

        response = await self._client._request(  # skipcq: PYL-W0212
            http_verb=self.http_verb,
            api_url=self.api_url,
            req_args=self.req_args,
        )

        self.data = response["data"]
        self.headers = response["headers"]
        self.status_code = response["status_code"]
        return self.validate()
    elif _page_data_is_present(self.data):
        cur_page = self.data["paging"]["page"]
        total_pages = self.data["paging"]["pages"]

        if cur_page >= total_pages:
            raise StopAsyncIteration

        params = self.req_args.get("params", {})
        if params is None:
            params = {}
        params.update({"page": cur_page + 1})
        self.req_args.update({"params": params})

        response = await self._client._request(  # skipcq: PYL-W0212
            http_verb=self.http_verb,
            api_url=self.api_url,
            req_args=self.req_args,
        )

        self.data = response["data"]
        self.headers = response["headers"]
        self.status_code = response["status_code"]
        return self.validate()
    else:
        raise StopAsyncIteration

def patch():
    log = logging.getLogger("patch")

    log.info("Patching slack_sdk.web.async_client.AsyncSlackResponse.__anext__")
    slack_sdk.web.async_client.AsyncSlackResponse.__anext__ = _AsyncSlackResponse___anext__