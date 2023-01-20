import logging.config
from typing import Dict

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config as alembic_config
from fastapi import Depends, FastAPI, Query, responses, status
from fastapi_sqlalchemy import AsyncDBSessionMiddleware
from pkg_resources import resource_filename
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine

from node.cache import CachingMiddleware, MemoryCache
from node.context import RequestHeadersMiddleware
from node.database import DB_URL, Node
from node.log_config import LOG_CONFIG
from node.route import LoggingRoute


class CreateNode(BaseModel):
    name: str
    configuration: Dict = Field(default_factory=dict)


class UpdateNode(BaseModel):
    name: str | None = None
    configuration: Dict | None = None


def node_svc() -> FastAPI:
    logging.config.dictConfig(LOG_CONFIG)
    cache = MemoryCache()

    app = FastAPI()
    app.router.route_class = LoggingRoute
    app.add_middleware(
        AsyncDBSessionMiddleware,
        db_url=str(DB_URL),
        commit_on_exit=True,
    )
    app.add_middleware(CachingMiddleware, cache=cache)
    app.add_middleware(RequestHeadersMiddleware)

    @app.on_event("startup")
    async def run_migrations():
        def upgrade(connection, cfg):
            cfg.attributes["connection"] = connection
            alembic_upgrade(cfg, "head")

        config = alembic_config(resource_filename("node", "alembic.ini"))

        async_engine = create_async_engine(str(DB_URL))
        async with async_engine.connect() as connection:
            await connection.run_sync(upgrade, config)

    @app.get("/nodes")
    async def list_nodes(
        project_id: str = Query(...), area_id: str = Query(...), cache_vary=Depends(cache.vary)
    ):
        nodes = await Node.select(Node.tags.comparator.contains(dict(project_id=project_id, area_id=area_id)))

        with cache_vary() as invalidate:
            invalidate(Node, tags=dict(project_id=project_id, area_id=area_id))

        return nodes

    @app.get("/nodes/{node_id}")
    async def get_node(
        node_id: str,
        project_id: str = Query(...),
        area_id: str = Query(...),
        cache_vary=Depends(cache.vary),
    ):
        node = await Node.get(
            Node.node_id == node_id,
            Node.tags.comparator.contains(dict(project_id=project_id, area_id=area_id)),
        )

        with cache_vary() as invalidate:
            invalidate(Node, node_id=node_id)

        return node

    @app.put(
        "/nodes/{node_id}", response_class=responses.RedirectResponse, status_code=status.HTTP_303_SEE_OTHER
    )
    async def put_node(
        node_id: str, create_node: CreateNode, project_id: str = Query(...), area_id: str = Query(...)
    ):
        await Node.merge(
            dict(node_id=node_id),
            name=create_node.name,
            tags=dict(project_id=project_id, area_id=area_id),
            configuration=create_node.configuration,
        )

        return f"/nodes/{node_id}?project_id={project_id}&area_id={area_id}"

    @app.patch(
        "/nodes/{node_id}", response_class=responses.RedirectResponse, status_code=status.HTTP_303_SEE_OTHER
    )
    async def patch_node(
        node_id: str, update_node: UpdateNode, project_id: str = Query(...), area_id: str = Query(...)
    ):
        await Node.update(
            Node.node_id == node_id,
            tags=dict(project_id=project_id, area_id=area_id),
            **update_node.dict(exclude_none=True),
        )

        return f"/nodes/{node_id}?project_id={project_id}&area_id={area_id}"

    @app.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_node(node_id: str, project_id: str = Query(...), area_id: str = Query(...)):
        # FIXME: sqlalchemy.exc.InvalidRequestError: Could not evaluate current criteria in Python
        # when using delete() with contains()
        await Node.get(
            Node.node_id == node_id,
            Node.tags.comparator.contains(dict(project_id=project_id, area_id=area_id)),
        )
        await Node.delete(
            Node.node_id == node_id,
        )

    @app.get("/health")
    async def get_health():
        return "OK"

    return app
