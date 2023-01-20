import re

from starlette.middleware.base import BaseHTTPMiddleware

from bff import client, context, urls


class RoleMiddleware(BaseHTTPMiddleware):
    def _get_project_id(self, request):
        if m := re.match(r"^/projects/(?P<project_id>[a-f0-9]+)", request.url.path):
            return m.group("project_id")

    async def dispatch(self, request, call_next):
        if project_id := self._get_project_id(request):
            if email := context.current_headers().get("x-user"):
                async with client.get(
                    urls.PROJECT_SVC / "projects" / project_id / "collaborators" / email,
                    raise_for_status=False,
                ) as response:
                    if response.status == 200:
                        collaborator = await response.json()
                        context.update_headers(**{"x-role": collaborator["role"]})

        return await call_next(request)
