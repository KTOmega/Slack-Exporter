class BlobDataManipulator:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool, bearer_token: str):
        self._bucket = bucket
        self._bearer_token = bearer_token
        self._minio = Minio(endpoint, access_key, secret_key, secure=secure)
        self._httpclient = httpx.AsyncClient()

        self._download_queue: List[asyncio.Task] = []

    async def close(self):
        await self._httpclient.aclose()

    def _ensure_bucket_exists(self):
        if not self._minio.bucket_exists(self._bucket):
            self._minio.make_bucket(self._bucket)

    def enqueue_download(self, *args, **kwargs):
        task = asyncio.create_task(self.download_and_store(*args, **kwargs))

        self._download_queue.append(task)

    async def flush_download_queue(self):
        if len(self._download_queue) == 0:
            return

        await asyncio.wait(self._download_queue)

        self._download_queue = []

    async def download_and_store(self, id: str, url: str, use_auth=False, throw_on_nonsuccess=True):
        self._ensure_bucket_exists()

        headers = {}

        if use_auth:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        res = await self._httpclient.get(url, headers=headers)

        if throw_on_nonsuccess:
            res.raise_for_status()

        content_bytes = io.BytesIO(res.content)
        content_length = len(res.content)

        self._minio.put_object(self._bucket,
            id,
            content_bytes,
            content_length)

def get_pagination_metadata(data: AsyncSlackResponse):
    if "has_more" in data.data:
        if data["has_more"]:
            try:
                return (True, {"cursor": data["response_metadata"]["next_cursor"]})
            except KeyError as e:
                log.error("Error getting next cursor from response data", exc_info=e)

        return (False, None)

    if "paging" in data.data:
        try:
            cur_page = data["paging"]["page"]
            total_pages = data["paging"]["total"]

            if cur_page != total_pages:
                return (True, {"page": cur_page + 1})
        except KeyError as e:
            log.error("Error getting pagination data", exc_info=e)

        return (False, None)

async def get_generator(api_call: Coroutine, *args, **kwargs) -> AsyncIterator[AsyncSlackResponse]:
    stop = False

    while not stop:
        res = await api_call(*args, **kwargs)

        print("yield")
        yield res

        print("get metadata")
        has_more, next_data = get_pagination_metadata(res)
        stop = not has_more
        print(stop)

        if next_data is not None:
            kwargs.update(next_data)

        await asyncio.sleep(1)