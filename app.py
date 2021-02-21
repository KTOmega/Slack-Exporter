from slack_sdk.web.async_client import AsyncWebClient, AsyncSlackResponse

import exporter
from exporter import patch
from exporter.context import ExporterContext
from exporter.downloader import FileDownloader
from exporter.fragment import FragmentFactory

import asyncio
import logging
import sys
import time

import settings

root = logging.getLogger()
root.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

log = logging.getLogger()

async def run_exporter():
    # Patch Slack API functions
    patch.patch()

    # Construct all needed instances of objects
    downloader = FileDownloader(settings.file_output_directory,
        settings.slack_token)

    slack_client = AsyncWebClient(token=settings.slack_token)

    fragment_factory = FragmentFactory()

    # Initialize context
    ctx = ExporterContext(
        export_time=int(time.time()),
        output_directory=settings.file_output_directory,
        slack_client=slack_client,
        downloader=downloader,
        fragments=fragment_factory
    )

    # Run
    try:
        await exporter.export_all(ctx)
    except Exception as e:
        log.error(f"Uncaught {e.__class__.__name__}", exc_info=e)

    # Clean up
    await ctx.close()

async def authenticate():
    pass

async def main():
    await authenticate()
    await run_exporter()

if __name__ == "__main__":
    asyncio.run(main())