FROM python:3.10

COPY dist dist
COPY ./.pip-pin .pip-pin
COPY setup.py .

RUN pip install dist/* -c .pip-pin/constraints.txt
RUN python setup.py sync -itd

COPY . /node-svc
WORKDIR /node-svc
CMD pip install -e . && uvicorn node:app --reload --reload-dir=/node-svc --reload-dir=/common --host 0.0.0.0 --port 80

EXPOSE 80
