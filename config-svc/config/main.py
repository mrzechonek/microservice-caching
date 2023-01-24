import logging
import logging.config
from typing import Any, Dict, List

from fastapi import Depends, FastAPI
from pydantic import BaseModel

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
    logger = logging.getLogger("svc")

    app = FastAPI()
    app.router.route_class = LoggingRoute

    @app.post("/misconfiguration", response_model=List[Misconfiguration])
    async def post_misconfigurations(node: Node, zone: Zone):
        logger.warning("RUNNING AUDIT")
        return []

    @app.get("/health")
    async def get_health():
        return "OK"

    return app
