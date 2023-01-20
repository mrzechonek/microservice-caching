FROM python:3.10

COPY . /todo-svc
WORKDIR /todo-svc
RUN pip install -e .
CMD uvicorn todo_svc:asgi --reload --reload-dir=/todo-svc --reload-dir=/common --host 0.0.0.0 --port 80

EXPOSE 80
