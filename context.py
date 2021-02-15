from dataclasses import dataclass
import json
from typing import Dict, Any

from slack_sdk.web.async_client import AsyncWebClient

from downloader import FileDownloader

class JsonSerializable:
    def to_json(self) -> str:
        return json.dumps(self.__dict__, separators=(',', ':'))

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

@dataclass
class ExporterMetadata(JsonSerializable):
    export_time: int

@dataclass
class ExporterContext(JsonSerializable):
    export_time: int
    slack_client: AsyncWebClient
    downloader: FileDownloader
    last_export_time: int = 0

    async def close(self):
        await self.downloader.close()

    def to_metadata(self) -> ExporterMetadata:
        return ExporterMetadata(self.export_time)