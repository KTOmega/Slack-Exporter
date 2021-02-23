from dataclasses import dataclass
import json
import os
from typing import Dict, Any

from slack_sdk.web.async_client import AsyncWebClient

from . import constants
from .downloader import FileDownloader
from .fragment import FragmentFactory

class JsonSerializable:
    def to_json(self) -> str:
        return json.dumps(self.__dict__, separators=(',', ':'))

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

@dataclass
class ExporterMetadata(JsonSerializable):
    export_time: int

@dataclass
class ExporterContext:
    export_time: int
    output_directory: str
    slack_client: AsyncWebClient
    downloader: FileDownloader
    fragments: FragmentFactory
    last_export_time: int = 0

    async def close(self):
        await self.downloader.close()
        self.fragments.close()

    def to_metadata(self) -> ExporterMetadata:
        return ExporterMetadata(self.export_time)

    def save(self):
        self.downloader.write_json(constants.CONTEXT_JSON_FILE, self.to_metadata().to_dict())

    @staticmethod
    def get_last_export_time(base_dir) -> int:
        context_file = os.path.join(base_dir, constants.CONTEXT_JSON_FILE)

        if os.path.exists(context_file):
            with open(context_file, "r") as fd:
                context = json.load(fd)

                if "export_time" in context:
                    return context["export_time"]

        return 0