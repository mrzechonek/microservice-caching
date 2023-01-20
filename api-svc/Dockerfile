FROM python:3.10

COPY . /api-svc
WORKDIR /api-svc
RUN pip install -e .

CMD uvicorn api_svc:asgi --reload --reload-dir=/api-svc --reload-dir=/common --host 0.0.0.0 --port 80

EXPOSE 80
