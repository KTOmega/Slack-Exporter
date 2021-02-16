import logging
import os
from typing import Any, Dict, List, Tuple

import context

log = logging.getLogger("models")

class SlackMessage:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "type" in self.data and self.data["type"] == "message"

    @property
    def has_replies(self):
        return "reply_count" in self.data and self.data["reply_count"] > 0

    @property
    def has_files(self):
        return (
            "files" in self.data and
            isinstance(self.data["files"], list) and
            len(self.data["files"]) > 0
        )

class SlackFile:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "id" in self.data and "mimetype" in self.data and "filetype" in self.data

    @classmethod
    async def from_id(cls, context: context.ExporterContext, id: str):
        slack_response = await context.slack_client.files_info(file=id)

        return cls(slack_response.data)

    def get_exportable_data(self) -> List[Tuple[str, str]]:
        if "url_private" not in self.data:
            log.warning(f"File {self.data['id']} does not have a url_private")
            return []

        return [(self.data["url_private"], self.data["id"])]

class SlackConversation:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "id" in self.data and "is_archived" in self.data

    @classmethod
    async def from_id(cls, context: context.ExporterContext, id: str):
        slack_response = await context.slack_client.conversations_info(channel=id)

        return cls(slack_response.data)

    @property
    def id(self):
        return self.data["id"]

class SlackUser:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

        assert "id" in self.data and "profile" in self.data

    @classmethod
    async def from_id(cls, context: context.ExporterContext, id: str):
        slack_response = await context.slack_client.users_info(user=id)

        return cls(slack_response.data)

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