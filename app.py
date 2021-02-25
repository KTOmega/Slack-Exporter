import asyncio
import logging
from multiprocessing import Process
import sys
import time

from slack_sdk.web.async_client import AsyncSlackResponse, AsyncWebClient

import exporter
from exporter import patch
from exporter.context import ExporterContext
from exporter.downloader import FileDownloader
from exporter.fragment import FragmentFactory
import settings

log = logging.getLogger()
log.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

async def run_exporter():
    # Patch Slack API functions
    patch.patch()

    # Construct all needed instances of objects
    downloader = FileDownloader(settings.file_output_directory,
        settings.slack_token)

    slack_client = AsyncWebClient(token=settings.slack_token)

    fragment_factory = FragmentFactory()

    # Initialize context
    last_export_time = ExporterContext.get_last_export_time(settings.file_output_directory)

    ctx = ExporterContext(
        export_time=int(time.time()),
        last_export_time=last_export_time,
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
    if settings.slack_token is None:
        import auth.server

        auth.server.run()

async def main():
    await authenticate()
    await run_exporter()

if __name__ == "__main__":
    asyncio.run(main())