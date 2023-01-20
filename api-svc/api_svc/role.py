import re

from starlette.middleware.base import BaseHTTPMiddleware

from api_svc import client, context, urls


class RoleMiddleware(BaseHTTPMiddleware):
    def _get_list_id(self, request):
        if m := re.match(r"^/lists/(?P<list_id>[a-f0-9]+)", request.url.path):
            return m.group("list_id")

    async def dispatch(self, request, call_next):
        if list_id := self._get_list_id(request):
            if email := context.current_headers().get("x-user"):
                async with client.get(
                    urls.TODO_SVC / "lists" / list_id / "collaborators" / email,
                    raise_for_status=False,
                ) as response:
                    if response.status == 200:
                        user = await response.json()
                        context.update_headers(**{"x-role": user["role"]})

        return await call_next(request)
