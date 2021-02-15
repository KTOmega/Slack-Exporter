from slack_sdk.web.async_client import AsyncWebClient, AsyncSlackResponse
from slack_sdk.errors import SlackApiError

import asyncio
import json
import logging
import sys
import time
from typing import Dict, Any

from context import ExporterContext
from downloader import FileDownloader
import patch
import settings

root = logging.getLogger()
root.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

log = logging.getLogger()

async def main():
    # Patch Slack API functions
    patch.patch()

    # DEPENDENCY INJECTION: Construct all needed instances of objects
    downloader = FileDownloader(settings.file_output_directory,
        settings.slack_token)

    slack_client = AsyncWebClient(token=settings.slack_token)

    # Initialize context
    ctx = ExporterContext(export_time=int(time.time()), slack_client=slack_client, downloader=downloader)

    # Run
    try:
        await test(ctx)
    except Exception as e:
        log.error(f"Uncaught {e.__class__.__name__}", exc_info=e)

    # Clean up
    await ctx.close()

async def test(ctx: ExporterContext):
    try:
        files_generator = await ctx.slack_client.files_list(count=1, ts_to=ctx.export_time, ts_from=1613267318)

        async for slack_response in files_generator:
            print(json.dumps(slack_response.data, indent=2))
            # for slack_file in slack_response["files"]:
            #     ctx.downloader.enqueue_download(slack_file["id"], slack_file["url_private"], use_auth=True)

        await ctx.downloader.flush_download_queue()
    except SlackApiError as e:
        log.error("Got an error when calling Slack API", exc_info=e)

if __name__ == "__main__":
    asyncio.run(main())