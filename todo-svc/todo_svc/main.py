import logging
import logging.config
from secrets import token_hex
from typing import List

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config as alembic_config
from fastapi import Depends, FastAPI, exceptions, responses, status
from fastapi_async_sqlalchemy import SQLAlchemyMiddleware
from pkg_resources import resource_filename
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine

from todo_svc.context import RequestHeadersMiddleware, current_headers
from todo_svc.database import DB_URL, Collaborator, TodoEntry, TodoList
from todo_svc.log_config import LOG_CONFIG
from todo_svc.route import LoggingRoute
from todo_svc.cache import MemoryCache, CacheMiddleware


class CreateTodoList(BaseModel):
    name: str


class CreateTodoEntry(BaseModel):
    text: str


class UpdateTodoEntry(BaseModel):
    text: str | None = None


class CreateCollaborator(BaseModel):
    email: str
    role: str

    class Config:
        from_attributes = True


def todo_list_role():
    async def _todo_list_role():
        if not current_headers().get("x-role", None):
            raise exceptions.HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TodoList doesn't exist or you don't have access",
            )

    return Depends(_todo_list_role)


def todo_svc() -> FastAPI:
    logging.config.dictConfig(LOG_CONFIG)

    cache = MemoryCache()

    app = FastAPI()
    app.router.route_class = LoggingRoute
    app.add_middleware(
        SQLAlchemyMiddleware,
        db_url=str(DB_URL),
        commit_on_exit=True,
    )
    app.add_middleware(RequestHeadersMiddleware)
    app.add_middleware(CacheMiddleware, cache=cache)

    @app.on_event("startup")
    async def run_migrations():
        def upgrade(connection, cfg):
            cfg.attributes["connection"] = connection
            alembic_upgrade(cfg, "head")

        config = alembic_config(resource_filename("todo_svc", "alembic.ini"))

        async_engine = create_async_engine(str(DB_URL))
        async with async_engine.connect() as connection:
            await connection.run_sync(upgrade, config)

    @app.get("/lists")
    async def get_todo_lists(response: responses.Response, vary_on=Depends(cache.vary_on)):
        user = current_headers().get("x-user")
        todo_lists = await TodoList.select(TodoList.collaborators.any(Collaborator.email == user))
        vary_on('x-user')

        return todo_lists

    @app.post(
        "/lists",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def post_todo_lists(create_todo_list: CreateTodoList):
        list_id = token_hex(2)
        await TodoList.create(list_id=list_id, name=create_todo_list.name)
        await Collaborator.create(list_id=list_id, email=current_headers().get("x-user"), role="owner")
        return f"/lists/{list_id}"

    @app.get(
        "/lists/{list_id}",
        dependencies=[todo_list_role()],
    )
    async def get_todo_list(list_id: str):
        todo_list = await TodoList.get(TodoList.list_id == list_id)

        return todo_list

    @app.patch(
        "/lists/{list_id}",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[todo_list_role()],
    )
    async def patch_todo_list(list_id: str, update_todo_list: CreateTodoList):
        await TodoList.update(TodoList.list_id == list_id, **update_todo_list.dict(exclude_none=True))
        return f"/lists/{list_id}"

    @app.delete(
        "/lists/{list_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[todo_list_role()],
    )
    async def delete_todo_list(list_id: str):
        return await TodoList.delete(TodoList.list_id == list_id)

    @app.get(
        "/lists/{list_id}/collaborators",
        response_model=List[CreateCollaborator],
        dependencies=[todo_list_role()],
    )
    async def get_collaborators(list_id: str):
        collaborators = await Collaborator.select(Collaborator.list_id == list_id)

        return collaborators

    @app.patch(
        "/lists/{list_id}/collaborators",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[todo_list_role()],
    )
    async def patch_collaborators(list_id: str, create_collaborators: List[CreateCollaborator]):
        for user in create_collaborators:
            await Collaborator.merge(
                dict(list_id=list_id, email=user.email),
                role=user.role,
            )

        return f"/lists/{list_id}/collaborators"

    @app.get("/lists/{list_id}/collaborators/{email}")
    async def get_collaborator(list_id: str, email: str):
        user = await Collaborator.get(Collaborator.list_id == list_id, Collaborator.email == email)

        return user

    @app.delete(
        "/lists/{list_id}/collaborators",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[todo_list_role()],
    )
    async def delete_collaborators(list_id: str, delete_collaborators: List[str]):
        for email in delete_collaborators:
            await Collaborator.delete(
                Collaborator.list_id == list_id, Collaborator.email == email, Collaborator.role != "owner"
            )

        return f"/lists/{list_id}/collaborators"

    @app.get(
        "/lists/{list_id}/entries",
        dependencies=[todo_list_role()],
    )
    async def get_entries(list_id: str):
        await TodoList.get(TodoList.list_id == list_id)
        entries = await TodoEntry.select(TodoEntry.list_id == list_id)

        return entries

    @app.post(
        "/lists/{list_id}/entries",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[todo_list_role()],
    )
    async def post_todo_entries(list_id: str, create_todo_entry: CreateTodoEntry):
        entry_id = token_hex(2)
        await TodoList.get(TodoList.list_id == list_id)
        await TodoEntry.create(
            list_id=list_id,
            entry_id=entry_id,
            text=create_todo_entry.text,
        )
        return f"/lists/{list_id}/entries/{entry_id}"

    @app.get(
        "/lists/{list_id}/entries/{entry_id}",
        dependencies=[todo_list_role()],
    )
    async def get_todo_entry(list_id: str, entry_id: str):
        area = await TodoEntry.get(TodoEntry.list_id == list_id, TodoEntry.entry_id == entry_id)

        return area

    @app.patch(
        "/lists/{list_id}/entries/{entry_id}",
        response_class=responses.RedirectResponse,
        status_code=status.HTTP_303_SEE_OTHER,
        dependencies=[todo_list_role()],
    )
    async def patch_todo_entry(list_id: str, entry_id: str, update_todo_entry: UpdateTodoEntry):
        await TodoEntry.update(
            TodoEntry.list_id == list_id,
            TodoEntry.entry_id == entry_id,
            **update_todo_entry.dict(exclude_none=True),
        )

        return f"/lists/{list_id}/entries/{entry_id}"

    @app.delete(
        "/lists/{list_id}/entries/{entry_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[todo_list_role()],
    )
    async def delete_todo_entry(list_id: str, entry_id: str):
        return await TodoEntry.delete(TodoEntry.list_id == list_id, TodoEntry.entry_id == entry_id)

    @app.get("/health")
    async def get_health():
        return "OK"

    return app
