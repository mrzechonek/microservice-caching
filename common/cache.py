import logging
from base64 import b64encode
from dataclasses import dataclass, field
from hashlib import sha1

from fastapi import Request, Response
from starlette.datastructures import Headers, Scope
from starlette.types import ASGIApp, Message, Receive, Send

logger = logging.getLogger("cache")


@dataclass
class CacheEntry:
    etag: str
    response_headers: Headers


@dataclass
class MemoryCache:
    cache: dict[tuple, CacheEntry] = field(default_factory=dict)
    vary_headers: dict = field(default_factory=dict)

    def _key(self, request: Request, vary_headers: list[str]):
        return (
            request.method,
            str(request.url),
            *((name, request.headers.get(name)) for name in vary_headers)
        )

    def store(self, request: Request, response_headers: Headers, etag: str):
        vary_headers = [name for name in response_headers.get('Vary', '').split(';') if name]
        self.vary_headers[str(request.url)] = vary_headers

        key = self._key(request, vary_headers)
        self.cache[key] = CacheEntry(etag, response_headers)

    def get(self, request: Request) -> CacheEntry | None:
        vary_headers = self.vary_headers.get(str(request.url), [])
        key = self._key(request, vary_headers)
        return self.cache.get(key)


@dataclass
class CacheSend:
    cache: MemoryCache
    request: Request
    send: Send

    response_start: Message | None = None
    response_body: list[Message] = field(default_factory=list)

    @property
    def response_headers(self):
        return Headers(raw=self.response_start["headers"])

    async def __call__(self, message: Message):
        if message["type"] == "http.response.start":
            self.response_start = message
            return

        self.response_body.append(message)

        if message["more_body"] is True:
            return

        body = b''.join(b["body"] for b in self.response_body)
        etag = b64encode(sha1(body).digest())

        self.response_start["headers"].append((b'ETag', etag))

        self.cache.store(self.request, self.response_headers, etag.decode())

        await self.send(self.response_start)
        for body in self.response_body:
            await self.send(body)


@dataclass
class CacheMiddleware:
    app: ASGIApp
    cache: MemoryCache

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope=scope)

        if (
            (if_none_match := request.headers.get("If-None-Match"))
            and (entry := self.cache.get(request))
            and (if_none_match == entry.etag)
        ):
            logger.info("IF NONE MATCH %s %s", if_none_match, entry)
            await send(dict(type="http.response.start", status=304, headers=entry.response_headers.raw))
            await send(dict(type="http.response.body", more_body=False))
            return

        await self.app(scope, receive, CacheSend(self.cache, request, send))
