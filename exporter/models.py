import asyncio
import logging
import os
from typing import Any, Dict, List, Tuple, Union, Callable

from . import constants, context, utils

log = logging.getLogger("models")

class SlackFile:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "id" in self.data and "mimetype" in self.data and "filetype" in self.data

    @property
    def id(self):
        return self.data["id"]

    @classmethod
    async def from_id(cls, context: context.ExporterContext, id: str):
        slack_response = await utils.with_retry(context.slack_client.files_info, file=id)

        return cls(slack_response.data["file"])

    def get_exportable_data(self) -> List[Tuple[str, str]]:
        url = self.data.get("url_private")
        if url is None:
            log.warning(f"File {self.data['id']} does not have a url_private")
            return []

        if self.data.get("external_type", "") == "gdrive":
            # skip gdrive files
            return []

        return [(url, self.data["id"])]

class SlackConversation:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "id" in self.data and "is_archived" in self.data

    @property
    def id(self):
        return self.data["id"]

    @classmethod
    async def from_id(cls, context: context.ExporterContext, id: str):
        slack_response = await utils.with_retry(context.slack_client.conversations_info, channel=id)

        return cls(slack_response.data["channels"])

class SlackMessage:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "type" in self.data and self.data["type"] == "message"

    @property
    def ts(self):
        return self.data["ts"]

    @property
    def has_replies(self):
        return (
            "reply_count" in self.data and
            self.data["reply_count"] > 0 and
            "thread_ts" in self.data
        )

    @property
    def has_files(self):
        return (
            "files" in self.data and
            isinstance(self.data["files"], list) and
            len(self.data["files"]) > 0
        )

    async def get_files(self, context: context.ExporterContext, filter_lambda: Callable = None) -> List[SlackFile]:
        if not self.has_files:
            return []

        files = self.data["files"]
        if filter_lambda is not None:
            files = list(filter(filter_lambda, files))

        if len(files) == 0:
            return []

        files_done, _ = await asyncio.wait([SlackFile.from_id(context, f["id"]) for f in files])

        return [await f for f in files_done]

    async def populate_replies(self, context: context.ExporterContext, channel: Union[str, SlackConversation]):
        if not self.has_replies:
            return

        thread_id = self.data["thread_ts"]

        id = channel
        if isinstance(channel, SlackConversation):
            id = channel.id

        replies_iterator = utils.AsyncIteratorWithRetry(context.slack_client.conversations_replies, channel=id, ts=thread_id)
        all_replies = []

        await replies_iterator.run()

        async for reply_resp in replies_iterator:
            for msg in reply_resp["messages"]:
                if msg["ts"] == thread_id:
                    continue

                all_replies.append(msg)

        self.data[constants.REPLIES_KEY] = all_replies

class SlackUser:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "id" in self.data and "profile" in self.data

    @classmethod
    async def from_id(cls, context: context.ExporterContext, id: str):
        slack_response = await utils.with_retry(context.slack_client.users_info, user=id)

        return cls(slack_response.data["members"])

    def get_exportable_data(self) -> List[Tuple[str, str]]:
        data: List[Tuple[str, str]] = []

        for profile_key, profile_value in self.data["profile"].items():
            if not isinstance(profile_value, str) or not profile_value.startswith("https://"):
                continue

            url = profile_value
            filename = os.path.basename(url)

            if "%2F" in filename:
                filename = url.split("%2F")[-1]

            data.append((url, filename))

        return data