import logging
from base64 import b64encode
from dataclasses import dataclass, field
from hashlib import sha1

from fastapi import Request, Response
from starlette.datastructures import Headers, Scope
from starlette.types import ASGIApp, Message, Receive, Send

logger = logging.getLogger("cache")
