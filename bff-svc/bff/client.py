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
    response: Any


class CachingResponse(aiohttp.ClientResponse):
    def __init__(self, *args, cache, **kwargs):
        self.cache = cache
        super().__init__(*args, **kwargs)

    @property
    def should_cache(self):
        if not self.cache or self.status != 200:
            return False

        return self._request_info.method == "GET" or self.headers.get("Vary")

    async def start(self, conn):
        await super().start(conn)

        if self.should_cache:
            if etag := self.headers.get("ETag"):
                logger.info(
                    "%s %s: %s",
                    click.style("STORE", fg="cyan"),
                    self.url,
                    click.style(etag, fg="blue"),
                )

                self.cache.store(
                    self._request_info.method,
                    self.url,
                    request_headers=self._request_info.headers,
                    response_headers=self.headers,
                    etag=etag,
                    response=self,
                )

        if self.status == 304:
            if entry := self.cache.get(
                self._request_info.method, self.url, request_headers=self._request_info.headers
            ):
                logger.info(
                    "%s %s: %s",
                    click.style("FETCH", fg="cyan"),
                    self.url,
                    click.style(entry.etag, fg="blue"),
                )

                self.status = entry.response.status
                self.reason = entry.response.reason
                self._body = entry.response._body

        return self


class CachingRequest(aiohttp.ClientRequest):
    def __init__(self, *args, cache, **kwargs):
        self.cache = cache
        super().__init__(*args, **kwargs)

    async def send(self, conn):
        self.headers.update(context.current_headers())

        if self.cache:
            if entry := self.cache.get(self.method, self.url, request_headers=self.headers):
                self.headers["If-None-Match"] = entry.etag

        return await super().send(conn)


class ClientSession(aiohttp.ClientSession):
    """
    When we POST, and the service responds with 303, we follow the redirection but want to immediately
    cache the resource we've been redirected to

    We need to override the response class, as `aiohttp.ClientSession_request()` uses an internal loop to
    follow redirections
    """

    def __init__(self, cache, *args, **kwargs):
        super().__init__(
            *args,
            request_class=partial(CachingRequest, cache=cache),
            response_class=partial(CachingResponse, cache=cache),
            **kwargs,
        )
        self.cache = cache


class SessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cache=None):
        super().__init__(app)
        self.cache = cache

    async def dispatch(self, request, call_next):
        s = ClientSession(self.cache, raise_for_status=True)

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


class MemoryCache:
    """
    Response may contain a 'Vary' header, telling us which *request* headers (besides the URL) should be taken
    into account when constructing the cache key.

    We store this infromation per-URL when populating the cache, and use it when querying cached responses.

    See https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Vary
    """

    def __init__(self):
        self.entries = {}
        self.vary_headers = {}

    def get_key(self, method: str, url: URL, request_headers: Headers):
        vary_headers = self.vary_headers.get(url, ())
        return frozenset({method, url, *((name, request_headers.get(name)) for name in vary_headers)})

    def store(
        self, method: str, url: URL, request_headers: Headers, response_headers: Headers, etag, response
    ):
        if vary := response_headers.get("vary"):
            self.vary_headers[url] = tuple(i.strip().lower() for i in vary.split(";") if i)

        key = self.get_key(method, url, request_headers)
        self.entries[key] = CacheEntry(etag, response)

    def get(self, method, url, request_headers):
        key = self.get_key(method, url, request_headers)
        return self.entries.get(key)
