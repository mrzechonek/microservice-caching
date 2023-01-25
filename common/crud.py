from collections import defaultdict
from contextlib import suppress
from logging import getLogger

import click
from fastapi import HTTPException
from fastapi_sqlalchemy import async_db as db
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert  # type: ignore
from starlette.status import HTTP_404_NOT_FOUND

logger = getLogger("crud")

def match(received, expected):
    def _match(lhs, rhs):
        if rhs is ...:
            return True

        if isinstance(rhs, list):
            return len(rhs) == len(lhs) and all(match(*i) for i in zip(lhs, rhs))

        if isinstance(rhs, dict):
            _lhs = {k: v for k, v in lhs.items()}
            return all(match(v, rhs.get(k, ...)) for k, v in _lhs.items())

        return lhs == rhs

    return _match(received, expected)


class Signal:
    def __init__(self):
        self.callbacks = set()

    def subscribe(self, callback, filter):
        def _callback(obj):
            if not match(obj, filter):
                return

            callback(obj)

        self.callbacks.add(_callback)

    def publish(self, obj):
        for callback in self.callbacks:
            callback(obj)

SIGNALS = defaultdict(Signal)

class CrudMixin:
    @classmethod
    def subscribe(cls, callback, **filter):
        SIGNALS[cls].subscribe(callback, filter)

    @classmethod
    def publish(cls, objs):
        for obj in objs:
            SIGNALS[cls].publish(obj._mapping)

    @classmethod
    async def create(cls, **kwargs):
        stmt = insert(cls).values(kwargs).returning('*')
        objs = await db.session.execute(stmt)
        cls.publish(objs.fetchall())

    @classmethod
    async def update(cls, *key, **data):
        stmt = update(cls).where(*key).values(**data).returning('*')
        objs = await db.session.execute(stmt)
        cls.publish(objs.fetchall())

    @classmethod
    async def merge(cls, key, /, **data):
        stmt = insert(cls).values(**key, **data).returning('*')
        objs =await db.session.execute(
            stmt.on_conflict_do_update(index_elements=key, set_=data)
        )
        cls.publish(objs.fetchall())

    @classmethod
    async def delete(cls, *args, **kwargs):
        stmt = delete(cls).filter(*args, **kwargs).returning('*')
        objs = await db.session.execute(stmt)
        cls.publish(objs.fetchall())

    @classmethod
    async def get(cls, *args, **kwargs):
        logger.info(
            "%s %s",
            click.style("SELECT", fg="red", bold=True),
            cls.__name__,
        )
        statement = select(cls).filter(*args, **kwargs)
        obj = (await db.session.execute(statement)).unique().scalars().one_or_none()
        if not obj:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"{cls.__name__} doesn't exist",
            )

        return obj

    @classmethod
    async def select(cls, *args, **kwargs):
        statement = select(cls).filter(*args, **kwargs)
        objs = (await db.session.execute(statement)).unique().scalars().all()
        logger.info(
            "%s %s",
            click.style("SELECT", fg="red", bold=True),
            cls.__name__,
        )
        return objs
