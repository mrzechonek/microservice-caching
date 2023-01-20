FROM python:3.10

COPY dist dist
COPY ./.pip-pin .pip-pin
COPY setup.py .

RUN pip install dist/* -c .pip-pin/constraints.txt
RUN python setup.py sync -itd

COPY . /project-svc
WORKDIR /project-svc
CMD pip install -e . && uvicorn project:app --reload --reload-dir=/project-svc --reload-dir=/common --host 0.0.0.0 --port 80

EXPOSE 80
