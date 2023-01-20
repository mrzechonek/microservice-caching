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


class CacheResponse(ClientResponse):
    pass


class CacheRequest(ClientRequest):
    async def send(self, conn):
        self.headers.update(context.current_headers())
        return await super().send(conn)


class CacheSession(ClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            request_class=CacheRequest,
            response_class=CacheResponse,
            **kwargs,
        )


class SessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        s = CacheSession(raise_for_status=True)

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
