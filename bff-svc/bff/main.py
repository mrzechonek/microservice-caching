import logging.config
from base64 import b64encode
from hashlib import sha1
from typing import Any, Dict, List

from fastapi import FastAPI, status
from pydantic import BaseModel

from bff import client, context, log_config, role, route, urls


class CreateNode(BaseModel):
    name: str


class UpdateNode(BaseModel):
    name: str | None = None
    configuration: Dict | None = None


class AreaNode(BaseModel):
    node_id: str
    name: str


class Node(BaseModel):
    name: str
    configuration: Dict


class CreateArea(BaseModel):
    name: str
    scenario: str = "switch"


class UpdateArea(BaseModel):
    name: str | None = None
    scenario: str | None = None


class Area(BaseModel):
    area_id: str
    name: str
    scenario: str


class CreateCollaborator(BaseModel):
    email: str
    role: str = "user"


class ProjectCollaborator(BaseModel):
    email: str
    role: str


class CreateProject(BaseModel):
    name: str


class Project(CreateProject):
    project_id: str
    collaborators: List[ProjectCollaborator]
    areas: List[Area]


class ListProject(BaseModel):
    project_id: str
    name: str


class Misconfiguration(BaseModel):
    name: str
    current: Any
    expected: Any


def bff_svc() -> FastAPI:
    logging.config.dictConfig(log_config.LOG_CONFIG)
    cache = client.MemoryCache()

    app = FastAPI()
    app.router.route_class = route.LoggingRoute
    app.router.route_class.DELIMITER = True

    app.add_middleware(role.RoleMiddleware)
    app.add_middleware(client.SessionMiddleware, cache=cache)
    app.add_middleware(context.CorrelationIdMiddleware)
    app.add_middleware(context.RequestHeadersMiddleware)

    @app.get("/projects", response_model=List[ListProject])
    async def get_projects():
        async with client.get(urls.PROJECT_SVC / "projects") as response:
            return await response.json()

    @app.post("/projects", response_model=ListProject, status_code=status.HTTP_201_CREATED)
    async def post_projects(create_project: CreateProject):
        # FIXME: This is a workaround
        #
        # We can't follow the redirection automatically, because RoleMiddleware
        # doesn't ask for project role if URL doesn't contain the project id.
        # On the other hand, we've just created the project, so we know are the
        # owner...
        async with client.post(
            urls.PROJECT_SVC / "projects", json=create_project.dict(), allow_redirects=False
        ) as create_response:
            if create_response.status == status.HTTP_201_CREATED:
                location = urls.PROJECT_SVC.with_path(create_response.headers["Location"])
                async with client.get(location, headers={"x-role": "owner"}) as response:
                    return await response.json()

    @app.get("/projects/{project_id}", response_model=Project)
    async def get_project(project_id: str):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id) as response:
            return await response.json()

    @app.patch("/projects/{project_id}", response_model=Project)
    async def patch_project(project_id: str, patch_project: CreateProject):
        async with client.patch(
            urls.PROJECT_SVC / "projects" / project_id, json=patch_project.dict()
        ) as response:
            return await response.json()

    @app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_project(project_id: str):
        async with client.delete(urls.PROJECT_SVC / "projects" / project_id):
            return None

    @app.get("/projects/{project_id}/collaborators", response_model=List[ProjectCollaborator])
    async def get_collaborators(project_id: str):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "collaborators") as response:
            return await response.json()

    @app.patch("/projects/{project_id}/collaborators", response_model=List[ProjectCollaborator])
    async def patch_collaborators(project_id: str, create_collaborators: List[CreateCollaborator]):
        async with client.patch(
            urls.PROJECT_SVC / "projects" / project_id / "collaborators",
            json=[c.dict() for c in create_collaborators],
        ) as response:
            return await response.json()

    @app.delete("/projects/{project_id}/collaborators")
    async def delete_collaborators(project_id: str, delete_collaborators: List[str]):
        async with client.delete(
            urls.PROJECT_SVC / "projects" / project_id / "collaborators", json=delete_collaborators
        ) as response:
            return await response.json()

    @app.get("/projects/{project_id}/areas", response_model=List[Area])
    async def get_areas(project_id: str):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "areas") as response:
            return await response.json()

    @app.post(
        "/projects/{project_id}/areas",
        response_model=Area,
        status_code=status.HTTP_201_CREATED,
    )
    async def post_areas(project_id: str, create_area: CreateArea):
        async with client.post(
            urls.PROJECT_SVC / "projects" / project_id / "areas", json=create_area.dict()
        ) as response:
            return await response.json()

    @app.get("/projects/{project_id}/areas/{area_id}", response_model=Area)
    async def get_area(project_id: str, area_id: str):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id) as response:
            return await response.json()

    @app.patch("/projects/{project_id}/areas/{area_id}", response_model=Area)
    async def patch_area(project_id: str, area_id: str, update_area: UpdateArea):
        async with client.patch(
            urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id, json=update_area.dict()
        ) as response:
            return await response.json()

    @app.delete("/projects/{project_id}/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_area(project_id: str, area_id: str):
        async with client.delete(urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id):
            return None

    @app.get("/projects/{project_id}/areas/{area_id}/nodes", response_model=List[AreaNode])
    async def get_nodes(project_id: str, area_id: str):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id), client.get(
            urls.NODE_SVC / "nodes", params=dict(project_id=project_id, area_id=area_id)
        ) as node_response:
            return await node_response.json()

    @app.get("/projects/{project_id}/areas/{area_id}/nodes/{node_id}", response_model=Node)
    async def get_node(project_id: str, area_id: str, node_id: str):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id), client.get(
            urls.NODE_SVC / "nodes" / node_id, params=dict(project_id=project_id, area_id=area_id)
        ) as response:
            return await response.json()

    @app.put(
        "/projects/{project_id}/areas/{area_id}/nodes/{node_id}",
        response_model=Node,
        status_code=status.HTTP_201_CREATED,
    )
    async def put_node(project_id: str, area_id: str, node_id: str, create_node: CreateNode):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id), client.put(
            urls.NODE_SVC / "nodes" / node_id,
            json=create_node.dict(),
            params=dict(project_id=project_id, area_id=area_id),
        ) as response:
            return await response.json()

    @app.patch(
        "/projects/{project_id}/areas/{area_id}/nodes/{node_id}",
        response_model=Node,
    )
    async def patch_node(project_id: str, area_id: str, node_id: str, update_node: UpdateNode):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id), client.patch(
            urls.NODE_SVC / "nodes" / node_id,
            json=update_node.dict(exclude_none=True),
            params=dict(project_id=project_id, area_id=area_id),
        ) as response:
            return await response.json()

    @app.delete(
        "/projects/{project_id}/areas/{area_id}/nodes/{node_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_node(project_id: str, area_id: str, node_id: str):
        async with client.get(urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id), client.delete(
            urls.NODE_SVC / "nodes" / node_id,
            params=dict(project_id=project_id, area_id=area_id),
        ):
            return None

    @app.get(
        "/projects/{project_id}/areas/{area_id}/nodes/{node_id}/misconfiguration",
        response_model=List[Misconfiguration],
    )
    async def get_misconfigurations(project_id: str, area_id: str, node_id: str):
        async with client.get(
            urls.PROJECT_SVC / "projects" / project_id / "areas" / area_id
        ) as area_response, client.get(
            urls.NODE_SVC / "nodes" / node_id, params=dict(project_id=project_id, area_id=area_id)
        ) as node_response:
            area_etag = area_response.headers.get("ETag")
            area = await area_response.json()

            node_etag = node_response.headers.get("ETag")
            node = await node_response.json()

        if area_etag and node_etag:
            repr_digest = sha1((area_etag + node_etag).encode()).digest()
        else:
            repr_digest = None

        async with client.post(
            urls.CONFIG_SVC / "misconfiguration",
            headers={"Repr-Digest": f"sha1=:{b64encode(repr_digest).decode()}:"} if repr_digest else {},
            json=dict(area=area, node=node),
        ) as response:
            return await response.json()

    @app.get("/health")
    async def get_health():
        return "OK"

    return app
