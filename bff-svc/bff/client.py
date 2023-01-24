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


class ClientRequest(aiohttp.ClientRequest):
    async def send(self, conn):
        self.headers.update(context.current_headers())
        return await super().send(conn)


class ClientSession(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            request_class=ClientRequest,
            **kwargs,
        )


class SessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        s = ClientSession(raise_for_status=True)

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
