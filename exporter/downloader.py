import asyncio
import collections
import os
from typing import Any, List

import httpx
import ujson as json

from .utils import AggregateError

class FileDownloadError(Exception):
    def __init__(self, url: str, inner_exception: Exception):
        self.url = url
        self.inner_exception = inner_exception

        message = f"{self.inner_exception.__class__.__name__}: {str(self.inner_exception)}" \
            f" (URL: {self.url})"

        super(FileDownloadError, self).__init__(message)

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
        self._pending_exceptions: List[Exception] = []

    async def close(self):
        """Attempts to finish up all running tasks."""

        await self.flush_download_queue()
        await self._httpclient.aclose()

    def _ensure_directories_exist(self, filename: str):
        file_dirname = os.path.dirname(filename)
        full_path = os.path.join(self._outdir, file_dirname)

        if not os.path.exists(full_path):
            os.makedirs(full_path)

    async def _process_waiting_queue(self):
        i = 0
        while i < len(self._download_tasks):
            task, url = self._download_tasks[i]

            if task.done():
                task_exc = task.exception()
                if task_exc is not None:
                    exc = FileDownloadError(url, task_exc)
                    self._pending_exceptions.append(exc)
                else:
                    await task

                del self._download_tasks[i]
            else:
                i += 1

        while len(self._download_tasks) < self._concurrency and len(self._waiting_queue) > 0:
            url, args, kwargs = self._waiting_queue.popleft()
            self.enqueue_download(url, *args, **kwargs)

    def enqueue_download(self, url: str, *args, **kwargs):
        """Queues up the download for future processing, limited by the downloader's concurrency.

        Parameters are equivalent to `_download`, that is:

        Parameters
        ----------
        url : str
            The URL of the file to download.
        filename : str, optional
            The filename to save to. If not specified, it will use the filename of the URL.
        overwrite : bool, optional
            Whether to overwrite the destination file, or to quietly dismiss the download.
        use_auth : bool, optional
            Whether to use the bearer token for the download.
        throw_on_nonsuccess : bool, optional
            Whether to throw on a non-success response (4xx, 5xx).
        """

        if len(self._download_tasks) >= self._concurrency:
            self._waiting_queue.append((url, args, kwargs))
        else:
            task = asyncio.create_task(self._download(url, *args, **kwargs))

            self._download_tasks.append((task, url))

    async def flush_download_queue(self):
        """Finish downloading all queued files."""

        if len(self._download_tasks) == 0 and len(self._waiting_queue) == 0:
            return

        while len(self._download_tasks) != 0 or len(self._waiting_queue) != 0:
            all_tasks = map(lambda x: x[0], self._download_tasks)

            await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
            await self._process_waiting_queue()

        if len(self._pending_exceptions) > 0:
            raise AggregateError("One or more errors occurred.", self._pending_exceptions)

    def exists(self, filename: str) -> bool:
        full_filename = os.path.join(self._outdir, filename)

        return os.path.exists(full_filename)

    def _save_file(self, filename: str, content: bytes):
        full_filename = os.path.join(self._outdir, filename)

        with open(full_filename, "wb") as fd:
            fd.write(content)

    def write_json(self, filename: str, content: Any):
        self._ensure_directories_exist(filename)

        full_filename = os.path.join(self._outdir, filename)

        with open(full_filename, "w") as fd:
            json.dump(content, fd)

    def _get_filename(self, url: str) -> str:
        last_path_element = url.split("/")[-1]

        if "?" in last_path_element:
            return last_path_element.split("?")[0]

        return last_path_element

    async def _download(self, url: str, filename: str = None, overwrite=False, use_auth=False, throw_on_nonsuccess=True):
        if filename is None:
            filename = self._get_filename(url)

        self._ensure_directories_exist(filename)

        if self.exists(filename):
            return

        headers = {}

        if use_auth:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        res = await self._httpclient.get(url, headers=headers)

        if throw_on_nonsuccess:
            res.raise_for_status()

        self._save_file(filename, res.content)

        await self._process_waiting_queue()