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

    def _key(self, method, url, request_headers, vary_headers):
        return (
            method,
            str(url),
            *((name, request_headers.get(name)) for name in vary_headers),
        )

    def get(self, method, url, request_headers):
        key = self._key(method, url, request_headers, self.vary.get(str(url), []))
        return self.cache.get(key)

    def store(self, method, url, request_headers, etag, response_headers):
        vary_headers = [
            name for name in response_headers.get("vary", "").split(";") if name
        ]
        self.vary[str(url)] = vary_headers
        key = self._key(method, url, request_headers, vary_headers)

        self.cache[key] = CacheEntry(etag, response_headers)


class CacheSend:
    def __init__(self, cache, method, url, request_headers, send):
        self.cache = cache
        self.method = method
        self.url = url
        self.send = send

        self.request_headers = request_headers
        self.response_start = None
        self.response_body = []

    @property
    def response_headers(self):
        return Headers(raw=self.response_start["headers"])

    async def __call__(self, message):
        if message["type"] == "http.response.start":
            self.response_start = message
            return

        assert message["type"] == "http.response.body"

        self.response_body.append(message)

        if message["more_body"]:
            return

        body = b"".join(body["body"] for body in self.response_body)
        etag = b64encode(sha1(body).digest())

        self.cache.store(
            self.method,
            self.url,
            self.request_headers,
            etag.decode(),
            self.response_headers,
        )
        self.response_start["headers"].append((b"etag", etag))

        await self.send(self.response_start)
        for body in self.response_body:
            await self.send(body)


class CacheMidleware:
    def __init__(self, app, cache: MemoryCache):
        self.app = app
        self.cache = cache

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope["method"]
        url = URL(scope=scope)
        request_headers = Headers(scope=scope)

        if if_none_match := request_headers.get("if-none-match"):
            if entry := self.cache.get(method, url, request_headers):
                if if_none_match == entry.etag:
                    await send(
                        dict(
                            type="http.response.start",
                            status=304,
                            headers=entry.response_headers.raw,
                        )
                    )
                    await send(dict(type="http.response.body", more_body=False))
                    return

        send = CacheSend(self.cache, method, url, request_headers, send)
        await self.app(scope, receive, send)
