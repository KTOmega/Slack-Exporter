import asyncio
import os
from typing import List

import httpx

class FileDownloader:
    def __init__(self, output_directory: str, bearer_token: str):
        self._bearer_token = bearer_token
        self._outdir = output_directory
        self._httpclient = httpx.AsyncClient()

        self._download_queue: List[asyncio.Task] = []

    async def close(self):
        await self._httpclient.aclose()

    def _ensure_outdir_exists(self):
        if not os.path.exists(self._outdir):
            os.mkdir(self._outdir)

    def enqueue_download(self, *args, **kwargs):
        task = asyncio.create_task(self.download_and_store(*args, **kwargs))

        self._download_queue.append(task)

    async def flush_download_queue(self):
        if len(self._download_queue) == 0:
            return

        await asyncio.wait(self._download_queue)

        self._download_queue = []

    def _exists(self, filename: str) -> bool:
        full_filename = os.path.join(self._outdir, filename)

        return os.path.exists(full_filename)

    def _save_file(self, filename: str, content: bytes):
        full_filename = os.path.join(self._outdir, filename)

        with open(full_filename, "wb") as fd:
            fd.write(content)

    async def download_and_store(self, id: str, url: str, overwrite=False, use_auth=False, throw_on_nonsuccess=True):
        self._ensure_outdir_exists()

        if self._exists(id):
            return

        headers = {}

        if use_auth:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        res = await self._httpclient.get(url, headers=headers)

        if throw_on_nonsuccess:
            res.raise_for_status()

        self._save_file(id, res.content)