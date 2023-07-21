from typing import Callable
from dataclasses import dataclass, field
from logging import getLogger

import click
from fastapi import HTTPException
from fastapi_async_sqlalchemy import db
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert  # type: ignore
from starlette.status import HTTP_404_NOT_FOUND

logger = getLogger("crud")


def match(filter, event):
    for k, v in filter.items():
        if event.get(k) != v:
            return False

    return True


@dataclass
class Signal:
    callbacks: list = field(default_factory=list)

    def subscribe(self, filter, callback):
        logger.info("SUBSCRIBE %s", filter)
        self.callbacks.append((filter, callback))

    def publish(self, event):
        for filter, callback in self.callbacks:
            if match(filter, event):
                logger.info("DROP %s %s", filter, event)
                callback()


class CrudMixin:
    @classmethod
    def signal(cls):
        if not (signal := getattr(cls, "_signal", None)):
            signal = Signal()
            setattr(cls, "_signal", signal)

        return signal

    @classmethod
    def subscribe(cls, filter, callback):
        cls.signal().subscribe(filter, callback)

    @classmethod
    def publish(cls, event):
        cls.signal().publish(event)

    @classmethod
    async def create(cls, **kwargs):
        stmt = insert(cls).values(kwargs)
        objs = await db.session.execute(stmt.returning('*'))
        for obj in objs:
            cls.publish(obj._mapping)

    @classmethod
    async def update(cls, *key, **data):
        stmt = update(cls).where(*key).values(**data)
        objs = await db.session.execute(stmt.returning('*'))
        for obj in objs:
            cls.publish(obj._mapping)

    @classmethod
    async def merge(cls, key, /, **data):
        stmt = insert(cls).values(**key, **data).on_conflict_do_update(index_elements=key, set_=data)
        objs = await db.session.execute(stmt.returning('*'))
        for obj in objs:
            cls.publish(obj._mapping)

    @classmethod
    async def delete(cls, *args, **kwargs):
        stmt = delete(cls).filter(*args, **kwargs)
        objs = await db.session.execute(stmt.returning('*'))
        for obj in objs:
            cls.publish(obj._mapping)

    @classmethod
    async def get(cls, *args, **kwargs):
        logger.info(
            "%s %s",
            click.style("QUERY", fg="red", bold=True),
            cls.__name__,
        )
        stmt = select(cls).filter(*args, **kwargs)
        obj = (await db.session.execute(stmt)).unique().scalars().one_or_none()
        if not obj:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"{cls.__name__} doesn't exist",
            )

        return obj

    @classmethod
    async def select(cls, *args, **kwargs):
        stmt = select(cls).filter(*args, **kwargs)
        objs = (await db.session.execute(stmt)).unique().scalars().all()
        logger.info(
            "%s %s",
            click.style("QUERY", fg="red", bold=True),
            cls.__name__
        )
        return objs
