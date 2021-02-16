import asyncio
import collections
import os
from typing import List

import httpx

class FileDownloader:
    """
    Helper class for asynchronous file downloads.
    """

    def __init__(self, output_directory: str, bearer_token: str, concurrency: int = 10):
        self._bearer_token = bearer_token
        self._outdir = output_directory
        self._concurrency = concurrency
        self._httpclient = httpx.AsyncClient()

        self._waiting_queue = collections.deque()
        self._download_tasks: List[asyncio.Task] = []

    async def close(self):
        """Attempts to finish up all running tasks."""

        await self.flush_download_queue()
        await self._httpclient.aclose()

    def _ensure_outdir_exists(self):
        if not os.path.exists(self._outdir):
            os.mkdir(self._outdir)

    async def _process_waiting_queue(self):
        i = 0
        while i < len(self._download_tasks):
            task = self._download_tasks[i]
            if task.done():
                await task
                del self._download_tasks[i]
            else:
                i += 1

        while len(self._download_tasks) < self._concurrency and len(self._waiting_queue) > 0:
            args, kwargs = self._waiting_queue.popleft()
            self.enqueue_download(*args, **kwargs)

    def enqueue_download(self, *args, **kwargs):
        """Queues up the download for future processing, limited by the downloader's concurrency.

        Parameters are equivalent to `_download`, that is:

        Parameters
        ----------
        filename : str
            The filename to save to.
        url : str
            The URL of the file to download.
        overwrite : bool, optional
            Whether to overwrite the destination file, or to quietly dismiss the download.
        use_auth : bool, optional
            Whether to use the bearer token for the download.
        throw_on_nonsuccess : bool, optional
            Whether to throw on a non-success response (4xx, 5xx).
        """

        if len(self._download_tasks) >= self._concurrency:
            self._waiting_queue.append((args, kwargs))
        else:
            task = asyncio.create_task(self._download(*args, **kwargs))

            self._download_tasks.append(task)

    async def flush_download_queue(self):
        """Finish downloading all queued files."""

        if len(self._download_tasks) == 0 and len(self._waiting_queue) == 0:
            return

        while len(self._download_tasks) != 0 or len(self._waiting_queue) != 0:
            await asyncio.wait(self._download_tasks)
            await self._process_waiting_queue()

    def _exists(self, filename: str) -> bool:
        full_filename = os.path.join(self._outdir, filename)

        return os.path.exists(full_filename)

    def _save_file(self, filename: str, content: bytes):
        full_filename = os.path.join(self._outdir, filename)

        with open(full_filename, "wb") as fd:
            fd.write(content)

    async def _download(self, filename: str, url: str, overwrite=False, use_auth=False, throw_on_nonsuccess=True):
        self._ensure_outdir_exists()

        if self._exists(filename):
            return

        headers = {}

        if use_auth:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        res = await self._httpclient.get(url, headers=headers)

        if throw_on_nonsuccess:
            res.raise_for_status()

        self._save_file(filename, res.content)

        await self._process_waiting_queue()