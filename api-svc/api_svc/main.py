import logging
import logging.config

from fastapi import FastAPI, status
from pydantic import BaseModel, validator

from api_svc import client, context, log_config, role, route, urls


class CreateTodoEntry(BaseModel):
    text: str


class UpdateTodoEntry(BaseModel):
    text: str | None = None


class TodoEntry(BaseModel):
    entry_id: str
    text: str


class CreateCollaborator(BaseModel):
    email: str
    role: str = "user"


class Collaborator(BaseModel):
    email: str
    role: str


class CreateTodoList(BaseModel):
    name: str


class TodoList(CreateTodoList):
    list_id: str
    collaborators: list[str]
    entries: list[TodoEntry]

    @validator("collaborators", pre=True)
    def simplify_collaborators(cls, collaborators):
        return [user["email"] for user in collaborators]


class ListTodoList(BaseModel):
    list_id: str
    name: str


def api_svc() -> FastAPI:
    logging.config.dictConfig(log_config.LOG_CONFIG)

    cache = client.MemoryCache()

    app = FastAPI()
    app.router.route_class = route.LoggingRoute
    app.router.route_class.DELIMITER = True

    app.add_middleware(role.RoleMiddleware)
    app.add_middleware(client.SessionMiddleware, cache=cache)
    app.add_middleware(context.CorrelationIdMiddleware)
    app.add_middleware(context.RequestHeadersMiddleware)

    @app.get("/lists", response_model=list[ListTodoList])
    async def get_todo_lists():
        async with client.get(urls.TODO_SVC / "lists") as response:
            return await response.json()

    @app.post("/lists", response_model=ListTodoList, status_code=status.HTTP_201_CREATED)
    async def post_todo_lists(create_todo_list: CreateTodoList):
        # FIXME: This is a workaround
        #
        # We can't follow the redirection automatically, because RoleMiddleware
        # doesn't ask for list role if URL doesn't contain the list id.
        # On the other hand, we've just created the list, so we know are the
        # owner...
        async with client.post(
            urls.TODO_SVC / "lists",
            json=create_todo_list.dict(),
            allow_redirects=False,
        ) as create_response:
            if create_response.status == status.HTTP_201_CREATED:
                location = urls.TODO_SVC.with_path(create_response.headers["Location"])
                async with client.get(location, headers={"x-role": "owner"}) as response:
                    return await response.json()

    @app.get("/lists/{list_id}", response_model=TodoList)
    async def get_todo_list(list_id: str):
        async with client.get(urls.TODO_SVC / "lists" / list_id) as response:
            return await response.json()

    @app.patch("/lists/{list_id}", response_model=TodoList)
    async def patch_todo_list(list_id: str, patch_todo_list: CreateTodoList):
        async with client.patch(urls.TODO_SVC / "lists" / list_id, json=patch_todo_list.dict()) as response:
            return await response.json()

    @app.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_todo_list(list_id: str):
        async with client.delete(urls.TODO_SVC / "lists" / list_id):
            return None

    @app.get("/lists/{list_id}/collaborators", response_model=list[Collaborator])
    async def get_collaborators(list_id: str):
        async with client.get(urls.TODO_SVC / "lists" / list_id / "collaborators") as response:
            return await response.json()

    @app.patch("/lists/{list_id}/collaborators", response_model=list[Collaborator])
    async def patch_collaborators(list_id: str, create_collaborators: list[str]):
        async with client.patch(
            urls.TODO_SVC / "lists" / list_id / "collaborators",
            json=[dict(email=email, role="friend") for email in create_collaborators],
        ) as response:
            return await response.json()

    @app.delete("/lists/{list_id}/collaborators")
    async def delete_collaborators(list_id: str, delete_collaborators: list[str]):
        async with client.delete(
            urls.TODO_SVC / "lists" / list_id / "collaborators",
            json=delete_collaborators,
        ) as response:
            return await response.json()

    @app.get("/lists/{list_id}/entries", response_model=list[TodoEntry])
    async def get_entries(list_id: str):
        async with client.get(urls.TODO_SVC / "lists" / list_id / "entries") as response:
            return await response.json()

    @app.post(
        "/lists/{list_id}/entries",
        response_model=TodoEntry,
        status_code=status.HTTP_201_CREATED,
    )
    async def post_entries(list_id: str, create_todo_entry: CreateTodoEntry):
        async with client.post(
            urls.TODO_SVC / "lists" / list_id / "entries",
            json=create_todo_entry.dict(),
        ) as response:
            return await response.json()

    @app.get("/lists/{list_id}/entries/{todo_entry_id}", response_model=TodoEntry)
    async def get_todo_entry(list_id: str, todo_entry_id: str):
        async with client.get(urls.TODO_SVC / "lists" / list_id / "entries" / todo_entry_id) as response:
            return await response.json()

    @app.patch("/lists/{list_id}/entries/{todo_entry_id}", response_model=TodoEntry)
    async def patch_todo_entry(list_id: str, todo_entry_id: str, update_todo_entry: UpdateTodoEntry):
        async with client.patch(
            urls.TODO_SVC / "lists" / list_id / "entries" / todo_entry_id,
            json=update_todo_entry.dict(),
        ) as response:
            return await response.json()

    @app.delete(
        "/lists/{list_id}/entries/{todo_entry_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_todo_entry(list_id: str, todo_entry_id: str):
        async with client.delete(urls.TODO_SVC / "lists" / list_id / "entries" / todo_entry_id):
            return None

    @app.get("/health")
    async def get_health():
        return "OK"

    return app
