FROM python:3.10


COPY ./.pip-pin .pip-pin
COPY setup.py .


RUN python setup.py sync -itd

COPY . /bff-svc
WORKDIR /bff-svc
CMD pip install -e . && uvicorn bff:app --reload --reload-dir=/bff-svc --reload-dir=/common --host 0.0.0.0 --port 80

EXPOSE 80
