#!python

from setuptools import find_packages, setup

# fmt: off
setup(
    name='node-svc',
    author_email='michal@rzechonek.net',
    description=(
        'Node Service'
    ),
    url='https://github.com/mrzechonek/caching.git',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'node': [
            'alembic/**/*',
            'alembic/*',
            'alembic.ini',
        ],
    },
    setup_requires=[
        'pip-pin>=0.0.8',
    ],
    install_requires=[
        'alembic',
        'asyncpg',
        'fastapi',
        'fastapi_sqlalchemy',
        'uvicorn',
        'watchfiles',
        'yarl',
    ],
    develop_requires=[
        'black',
        'flake8',
        'isort',
        'mypy',
    ],
    tests_require=[]
)
# fmt: on
