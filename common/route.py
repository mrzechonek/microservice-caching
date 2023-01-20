import logging
import sys
from functools import partial
from http.client import responses

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from yarl import URL

try:
    from aiohttp.client import ClientResponseError
except ImportError:
    ClientResponseError = AssertionError  # type: ignore

import click

COLORS = {
    1: partial(click.style, fg="bright_white"),
    2: partial(click.style, fg="green"),
    3: partial(click.style, fg="yellow"),
    4: partial(click.style, fg="red"),
    5: partial(click.style, fg="bright_red"),
}

logger = logging.getLogger("svc")


class LoggingRoute(APIRoute):
    DELIMITER = False

    def get_route_handler(self):
        _route_handler = super().get_route_handler()

        async def route_handler(request):
            url = URL(str(request.url)).relative()

            if self.DELIMITER:
                logger.info("――― BEGIN ―――")

            try:
                response = await _route_handler(request)
            except ClientResponseError as exc:
                response = JSONResponse(
                    status_code=exc.status, content=dict(message=exc.message)
                )
                exc_info = None
            except BaseException as exc:
                response = JSONResponse(
                    status_code=getattr(
                        exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR
                    ),
                    content=dict(
                        message=getattr(exc, "detail", "Internal Server Error")
                    ),
                )
                exc_info = sys.exc_info()
            else:
                exc_info = None

            if url.path != "/health":
                logger.log(
                    logging.ERROR if response.status_code >= 500 else logging.INFO,
                    "%6s %s: %s",
                    click.style(request.method, bold=True),
                    url,
                    COLORS[response.status_code // 100](
                        f"{response.status_code} {responses[response.status_code]}"
                    ),
                    exc_info=exc_info,
                )

                if self.DELIMITER:
                    logger.info("―――  END  ―――")

                sys.stdout.flush()

            return response

        return route_handler
