from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import partial
from logging import getLogger
from typing import Any

import yarl
from aiohttp import ClientRequest, ClientResponse, ClientResponseError, ClientSession, RequestInfo
from aiohttp.client import _RequestContextManager as ClientRequestContextManager
from fastapi import responses
from starlette.middleware.base import BaseHTTPMiddleware

from api_svc import context

logger = getLogger("client")
_session: ContextVar[ClientSession] = ContextVar("_session")

@dataclass
class CacheEntry:
    etag: str
    response: ClientResponse


@dataclass
class MemoryCache:
    cache: dict[tuple, CacheEntry] = field(default_factory=dict)
    vary_headers: dict = field(default_factory=dict)

    def _key(self, request: RequestInfo, vary_headers: list[str]):
        return (
            request.method,
            str(request.url),
            *((name, request.headers.get(name)) for name in vary_headers)
        )

    def store(self, request: RequestInfo, response: ClientResponse, etag: str):
        vary_headers = [name for name in response.headers.get('Vary', '').split(';') if name]
        self.vary_headers[str(request.url)] = vary_headers

        key = self._key(request, vary_headers)
        self.cache[key] = CacheEntry(etag, response)

    def get(self, request: RequestInfo) -> CacheEntry | None:
        vary_headers = self.vary_headers.get(str(request.url), [])

        key = self._key(request, vary_headers)
        return self.cache.get(key)


class CacheResponse(ClientResponse):
    def __init__(self, *args, cache, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = cache

    async def start(self, conn):
        await super().start(conn)

        if (
            self.status == 304
            and (entry := self.cache.get(self.request_info))
        ):
            self.status = entry.response.status
            self.reason = entry.response.reason
            self._body = entry.response._body

        elif (
            self.method == 'GET'
            and self.status == 200
            and (etag := self.headers.get("ETag"))
        ):
            self.cache.store(self.request_info, self, etag)
            logger.info("ETAG %s", etag)


class CacheRequest(ClientRequest):
    def __init__(self, *args, cache, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = cache

    async def send(self, conn):
        self.headers.update(context.current_headers())

        if entry := self.cache.get(self.request_info):
            self.headers["If-None-Match"] = entry.etag

        return await super().send(conn)


class CacheSession(ClientSession):
    def __init__(self, *args, cache, **kwargs):
        super().__init__(
            *args,
            request_class=partial(CacheRequest, cache=cache),
            response_class=partial(CacheResponse, cache=cache),
            **kwargs,
        )


class SessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cache):
        super().__init__(app)
        self.cache = cache

    async def dispatch(self, request, call_next):
        s = CacheSession(raise_for_status=True, cache=self.cache)

        try:
            _session.set(s)
            return await call_next(request)
        except ClientResponseError as ex:
            return responses.JSONResponse(content=dict(message=ex.message), status_code=ex.status)
        finally:
            if not s.closed:
                await s.close()


def get(url: yarl.URL, *, allow_redirects: bool = True, **kwargs: Any) -> ClientRequestContextManager:
    return ClientSession.get(_session.get(), url, allow_redirects=allow_redirects, **kwargs)


def options(url: yarl.URL, *, allow_redirects: bool = True, **kwargs: Any) -> ClientRequestContextManager:
    return ClientSession.options(_session.get(), url, allow_redirects=allow_redirects, **kwargs)


def head(url: yarl.URL, *, allow_redirects: bool = True, **kwargs: Any) -> ClientRequestContextManager:
    return ClientSession.head(_session.get(), url, allow_redirects=allow_redirects, **kwargs)


def post(
    url: yarl.URL, *, allow_redirects: bool = True, data: Any = None, **kwargs: Any
) -> ClientRequestContextManager:
    return ClientSession.post(_session.get(), url, data=data, **kwargs)


def put(
    url: yarl.URL, *, allow_redirects: bool = True, data: Any = None, **kwargs: Any
) -> ClientRequestContextManager:
    return ClientSession.put(_session.get(), url, allow_redirects=allow_redirects, data=data, **kwargs)


def patch(
    url: yarl.URL, *, allow_redirects: bool = True, data: Any = None, **kwargs: Any
) -> ClientRequestContextManager:
    return ClientSession.patch(_session.get(), url, allow_redirects=allow_redirects, data=data, **kwargs)


def delete(url: yarl.URL, allow_redirects: bool = True, **kwargs: Any) -> ClientRequestContextManager:
    return ClientSession.delete(_session.get(), url, allow_redirects=allow_redirects, **kwargs)
