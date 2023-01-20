FROM python:3.10


COPY ./.pip-pin .pip-pin
COPY setup.py .


RUN python setup.py sync -itd

COPY . /config-svc
WORKDIR /config-svc
CMD pip install -e . && uvicorn config:app --reload --reload-dir=/config-svc --reload-dir=/common --host 0.0.0.0 --port 80

EXPOSE 80
