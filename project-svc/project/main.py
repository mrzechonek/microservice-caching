import logging
import logging.config
from secrets import token_hex
from typing import List

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config as alembic_config
from fastapi import Depends, FastAPI, exceptions, responses, status
from fastapi_sqlalchemy import AsyncDBSessionMiddleware
from pkg_resources import resource_filename
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine

from project.context import RequestHeadersMiddleware, current_headers
from project.database import DB_URL, Area, Collaborator, Project
from project.log_config import LOG_CONFIG
from project.route import LoggingRoute
from project.cache import MemoryCache, CacheMiddleware


class CreateProject(BaseModel):
    name: str


class CreateArea(BaseModel):
    name: str
    scenario: str


class UpdateArea(BaseModel):
    name: str | None = None
    scenario: str | None = None


class CreateCollaborator(BaseModel):
    email: str
    role: str

    class Config:
        orm_mode = True


def project_role():
    async def _project_role():
        if not current_headers().get("x-role", None):
            raise exceptions.HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project doesn't exist or you don't have access",
            )

    return Depends(_project_role)


def project_svc() -> FastAPI:
    logging.config.dictConfig(LOG_CONFIG)
    logger = logging.getLogger("svc")

    app = FastAPI()
    app.router.route_class = LoggingRoute
    app.add_middleware(
        AsyncDBSessionMiddleware,
        db_url=str(DB_URL),
        commit_on_exit=True,
    )
    app.add_middleware(RequestHeadersMiddleware)

    cache = MemoryCache()
    app.add_middleware(CacheMiddleware, cache=cache)

    @app.on_event("startup")
    async def run_migrations():
        def upgrade(connection, cfg):
            cfg.attributes["connection"] = connection
            alembic_upgrade(cfg, "head")

        config = alembic_config(resource_filename("project", "alembic.ini"))

        async_engine = create_async_engine(str(DB_URL))
        async with async_engine.connect() as connection:
            await connection.run_sync(upgrade, config)

    @app.get("/projects")
    async def get_projects(response: responses.Response, cache_vary = Depends(cache.vary_on)):
        user = current_headers().get("x-user")
        projects = await Project.select(Project.collaborators.any(Collaborator.email == user))

        cache_drop = cache_vary('x-user')

        for project in projects:
            Project.subscribe(cache_drop, project_id=project.project_id)

        Collaborator.subscribe(cache_drop, email=user)

        return projects

    @app.post(
        "/projects",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def post_projects(create_project: CreateProject):
        project_id = token_hex(4)
        await Project.create(project_id=project_id, name=create_project.name)
        await Collaborator.create(project_id=project_id, email=current_headers().get("x-user"), role="owner")
        return f"/projects/{project_id}"

    @app.get(
        "/projects/{project_id}",
        dependencies=[project_role()],
    )
    async def get_project(project_id: str):
        project = await Project.get(Project.project_id == project_id)

        return project

    @app.patch(
        "/projects/{project_id}",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[project_role()],
    )
    async def patch_project(project_id: str, update_project: CreateProject):
        await Project.update(Project.project_id == project_id, update_project.dict(exclude_none=True))
        return f"/projects/{project_id}"

    @app.get(
        "/projects/{project_id}/collaborators",
        response_model=List[CreateCollaborator],
        dependencies=[project_role()],
    )
    async def get_collaborators(project_id: str):
        collaborators = await Collaborator.select(Collaborator.project_id == project_id)

        return collaborators

    @app.patch(
        "/projects/{project_id}/collaborators",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[project_role()],
    )
    async def patch_collaborators(project_id: str, create_collaborators: List[CreateCollaborator]):
        for collaborator in create_collaborators:
            await Collaborator.merge(
                dict(project_id=project_id, email=collaborator.email),
                role=collaborator.role,
            )

        return f"/projects/{project_id}/collaborators"

    @app.get("/projects/{project_id}/collaborators/{email}")
    async def get_collaborator(project_id: str, email: str):
        collaborator = await Collaborator.get(
            Collaborator.project_id == project_id, Collaborator.email == email
        )

        return collaborator

    @app.delete(
        "/projects/{project_id}/collaborators",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[project_role()],
    )
    async def delete_collaborators(project_id: str, delete_collaborators: List[str]):
        for email in delete_collaborators:
            await Collaborator.delete(Collaborator.project_id == project_id, Collaborator.email == email)

        return f"/projects/{project_id}/collaborators"

    @app.delete(
        "/projects/{project_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[project_role()],
    )
    async def delete_project(project_id: str):
        return await Project.delete(Project.project_id == project_id)

    @app.get(
        "/projects/{project_id}/areas",
        dependencies=[project_role()],
    )
    async def get_areas(project_id: str):
        await Project.get(Project.project_id == project_id)
        areas = await Area.select(Area.project_id == project_id)

        return areas

    @app.post(
        "/projects/{project_id}/areas",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[project_role()],
    )
    async def post_areas(project_id: str, create_area: CreateArea):
        area_id = token_hex(4)
        await Project.get(Project.project_id == project_id)
        await Area.create(
            project_id=project_id, area_id=area_id, name=create_area.name, scenario=create_area.scenario
        )
        return f"/projects/{project_id}/areas/{area_id}"

    @app.get(
        "/projects/{project_id}/areas/{area_id}",
        dependencies=[project_role()],
    )
    async def get_area(project_id: str, area_id: str):
        area = await Area.get(Area.project_id == project_id, Area.area_id == area_id)

        return area

    @app.patch(
        "/projects/{project_id}/areas/{area_id}",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[project_role()],
    )
    async def patch_area(project_id: str, area_id: str, update_area: UpdateArea):
        await Area.update(
            Area.project_id == project_id, Area.area_id == area_id, **update_area.dict(exclude_none=True)
        )

        return f"/projects/{project_id}/areas/{area_id}"

    @app.delete(
        "/projects/{project_id}/areas/{area_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[project_role()],
    )
    async def delete_area(project_id: str, area_id: str):
        return await Area.delete(Area.project_id == project_id, Area.area_id == area_id)

    @app.get("/health")
    async def get_health():
        return "OK"

    return app
