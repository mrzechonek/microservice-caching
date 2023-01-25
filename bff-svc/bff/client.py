from contextvars import ContextVar
from dataclasses import dataclass
from functools import partial
from logging import getLogger
from typing import Any

import aiohttp
import click
import yarl
from fastapi import responses
from starlette.datastructures import URL, Headers
from starlette.middleware.base import BaseHTTPMiddleware

from bff import context

logger = getLogger("client")
_session: ContextVar[aiohttp.ClientSession] = ContextVar("_session")

@dataclass
class CacheEntry:
    etag: str
    response: aiohttp.ClientResponse

class MemoryCache:
    def __init__(self):
        self.cache = {}
        self.vary = {}

    def _key(self, method, url, request_headers, vary_headers):
        return (method, str(url), *((i, request_headers.get(i)) for i in vary_headers))

    def get(self, method, url, request_headers):
        vary_headers = self.vary.get(str(url), [])
        key = self._key(method, url, request_headers, vary_headers)
        return self.cache.get(key)

    def store(self, method, url, request_headers, etag, response):
        vary_headers = [i for i in response.headers.get('vary', '').split(';') if i]
        self.vary[str(url)] = vary_headers

        key = self._key(method, url, request_headers, vary_headers)
        self.cache[key] = CacheEntry(etag, response)


class ClientRequest(aiohttp.ClientRequest):
    def __init__(self, *args, cache, **kwargs):
        self.cache = cache
        super().__init__(*args, **kwargs)

    async def send(self, conn):
        self.headers.update(context.current_headers())

        if entry := self.cache.get(self.method, self.url, self.headers):
            self.headers['if-none-match'] = entry.etag

        return await super().send(conn)

class ClientResponse(aiohttp.ClientResponse):
    def __init__(self, *args, cache, **kwargs):
        self.cache = cache
        super().__init__(*args, **kwargs)

    async def start(self, conn):
        await super().start(conn)

        if self.status == 304:
            if entry := self.cache.get(self.method, self.url, self.request_info.headers):
                self.status = entry.response.status
                self.reason = entry.response.reason
                self._body = entry.response._body

        elif etag := self.headers.get('etag'):
            self.cache.store(self.method, self.url, self.request_info.headers, etag, self)


class ClientSession(aiohttp.ClientSession):
    def __init__(self, *args, cache, **kwargs):
        super().__init__(
            *args,
            request_class=partial(ClientRequest, cache=cache),
            response_class=partial(ClientResponse, cache=cache),
            **kwargs,
        )


class SessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cache):
        self.cache = cache
        super().__init__(app)

    async def dispatch(self, request, call_next):
        s = ClientSession(raise_for_status=True, cache=self.cache)

        try:
            _session.set(s)
            return await call_next(request)
        except aiohttp.ClientResponseError as ex:
            return responses.JSONResponse(content=dict(message=ex.message), status_code=ex.status)
        finally:
            if not s.closed:
                await s.close()


def get(
    url: yarl.URL, *, allow_redirects: bool = True, **kwargs: Any
) -> aiohttp.client._RequestContextManager:
    return aiohttp.ClientSession.get(_session.get(), url, allow_redirects=allow_redirects, **kwargs)


def options(
    url: yarl.URL, *, allow_redirects: bool = True, **kwargs: Any
) -> aiohttp.client._RequestContextManager:
    return aiohttp.ClientSession.options(_session.get(), url, allow_redirects=allow_redirects, **kwargs)


def head(
    url: yarl.URL, *, allow_redirects: bool = True, **kwargs: Any
) -> aiohttp.client._RequestContextManager:
    return aiohttp.ClientSession.head(_session.get(), url, allow_redirects=allow_redirects, **kwargs)


def post(
    url: yarl.URL, *, allow_redirects: bool = True, data: Any = None, **kwargs: Any
) -> aiohttp.client._RequestContextManager:
    return aiohttp.ClientSession.post(_session.get(), url, data=data, **kwargs)


def put(
    url: yarl.URL, *, allow_redirects: bool = True, data: Any = None, **kwargs: Any
) -> aiohttp.client._RequestContextManager:
    return aiohttp.ClientSession.put(
        _session.get(), url, allow_redirects=allow_redirects, data=data, **kwargs
    )


def patch(
    url: yarl.URL, *, allow_redirects: bool = True, data: Any = None, **kwargs: Any
) -> aiohttp.client._RequestContextManager:
    return aiohttp.ClientSession.patch(
        _session.get(), url, allow_redirects=allow_redirects, data=data, **kwargs
    )


def delete(
    url: yarl.URL, allow_redirects: bool = True, **kwargs: Any
) -> aiohttp.client._RequestContextManager:
    return aiohttp.ClientSession.delete(_session.get(), url, allow_redirects=allow_redirects, **kwargs)
