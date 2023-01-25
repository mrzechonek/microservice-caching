import logging
from base64 import b64encode
from dataclasses import dataclass, field
from hashlib import sha1

from fastapi import Request, Response
from starlette.datastructures import URL, Headers
from starlette.types import ASGIApp, Message, Send

logger = logging.getLogger("cache")

@dataclass
class CacheEntry:
    etag: str
    response_headers: Headers

class MemoryCache:
    def __init__(self):
        self.cache = {}
        self.vary = {}

    def vary_on(self, request: Request, response: Response):
        def _vary_on(*vary_headers):
            response.headers['vary'] = ';'.join(vary_headers)
            key = self._key(request.method, request.url, request.headers, vary_headers)
            return lambda *args: self.cache.pop(key, None)

        return _vary_on

    def drop(self, key):
        self.cache.pop(key, None)

    def _key(self, method, url, request_headers: Headers, vary_headers: list[str]):
        return (method, str(url), *((name, request_headers.get(name)) for name in vary_headers))

    def store(self, method, url, request_headers, etag, response_headers):
        vary_headers = [name for name in response_headers.get('vary', '').split() if name]
        self.vary[str(url)] = vary_headers

        key = self._key(method, url, request_headers, vary_headers)
        self.cache[key] = CacheEntry(etag, response_headers)

    def get(self, method, url, request_headers: Headers):
        vary_headers = self.vary[str(url)]
        key = self._key(method, url, request_headers, vary_headers)
        return self.cache.get(key)


@dataclass
class CacheSend:
    cache: MemoryCache
    method: str
    url: URL
    request_headers: Headers
    send: Send

    response_start: Message | None = None
    response_body: list[Message] = field(default_factory=list)

    @property
    def response_headers(self):
        return Headers(raw=self.response_start["headers"])

    async def __call__(self, message):
        if message["type"] == "http.response.start":
            self.response_start = message
            return

        self.response_body.append(message)

        if message["more_body"]:
            return

        body = b"".join(i["body"] for i in self.response_body)
        etag = b64encode(sha1(body).digest())

        self.response_start["headers"].append((b'etag', etag))
        self.cache.store(self.method, self.url, self.request_headers, etag.decode(), self.response_headers)

        await self.send(self.response_start)
        for i in self.response_body:
            await self.send(i)


@dataclass
class CacheMiddleware:
    app: ASGIApp
    cache: MemoryCache

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope["method"]
        url = URL(scope=scope)
        request_headers = Headers(scope=scope)

        if if_none_match := request_headers.get('if-none-match'):
            if entry := self.cache.get(method, url, request_headers):
                if if_none_match == entry.etag:
                    await send(dict(type="http.response.start", status=304, headers=entry.response_headers.raw))
                    await send(dict(type="http.response.body", more_body=False))
                    return

        await self.app(scope, receive, CacheSend(self.cache, method, url, request_headers, send))
