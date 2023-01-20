import logging.config
from typing import Any, Dict, List

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from config.cache import CachingMiddleware, MemoryCache
from config.log_config import LOG_CONFIG
from config.route import LoggingRoute


class Node(BaseModel):
    name: str
    configuration: Dict


class Zone(BaseModel):
    name: str
    scenario: str


class Misconfiguration(BaseModel):
    name: str
    current: Any
    expected: Any


def config_svc() -> FastAPI:
    logging.config.dictConfig(LOG_CONFIG)
    cache = MemoryCache()

    app = FastAPI()
    app.router.route_class = LoggingRoute
    app.add_middleware(CachingMiddleware, cache=cache)

    @app.post("/misconfiguration", response_model=List[Misconfiguration])
    async def post_misconfigurations(node: Node, zone: Zone, cache_vary=Depends(cache.vary)):
        # https://httpwg.org/http-extensions/draft-ietf-httpbis-digest-headers.html#name-using-repr-digest-in-state-
        cache_vary("Repr-Digest")

        logging.getLogger("svc").warning("RUNNING AUDIT")
        return []

    @app.get("/health")
    async def get_health():
        return "OK"

    return app
