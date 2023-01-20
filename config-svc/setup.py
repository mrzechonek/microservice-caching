#!python

from setuptools import find_packages, setup

# fmt: off
setup(
    name='config-svc',
    author_email='michal@rzechonek.net',
    description=(
        'Config Service',
    ),
    url='https://github.com/mrzechonek/caching.git',
    packages=find_packages(),
    setup_requires=[
        'pip-pin>=0.0.8',
    ],
    install_requires=[
        'aiohttp',
        'fastapi',
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
