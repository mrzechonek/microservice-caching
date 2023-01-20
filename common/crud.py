from contextlib import suppress
from logging import getLogger

import click
from fastapi import HTTPException
from fastapi_sqlalchemy import async_db as db
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert  # type: ignore
from starlette.status import HTTP_404_NOT_FOUND

logger = getLogger("crud")


class Signal:
    def __init__(self):
        self.callbacks = set()

    def connect(self, callback):
        self.callbacks.add(callback)

    def disconnect(self, callback):
        with suppress(KeyError):
            self.callbacks.remove(callback)

    async def emit(self, **kwargs):
        for callback in list(self.callbacks):
            await callback(**kwargs)

    @property
    def connections(self) -> int:
        return len(self.callbacks)


class CrudMixin:
    @classmethod
    def _signal(cls):
        try:
            signal = getattr(cls, "_change")
        except AttributeError:
            signal = Signal()
            setattr(cls, "_change", signal)
        finally:
            return signal

    @classmethod
    def subscribe(cls, callback):
        cls._signal().connect(callback)

    @classmethod
    def unsubscribe(cls, callback):
        cls._signal().disconnect(callback)

    @classmethod
    async def notify(cls, objects, action):
        signal = cls._signal()
        for i in objects:
            await signal.emit(_action=action, **i._mapping)

    @classmethod
    async def create(cls, **kwargs):
        stmt = insert(cls).values(kwargs).returning("*")
        created = await db.session.execute(stmt)
        await cls.notify(created.fetchall(), "create")

    @classmethod
    async def update(cls, *key, **data):
        stmt = update(cls).where(*key).values(**data).returning("*")
        updated = await db.session.execute(stmt)
        await cls.notify(updated.fetchall(), "update")

    @classmethod
    async def merge(cls, key, /, **data):
        stmt = insert(cls).values(**key, **data).returning("*")
        merged = await db.session.execute(
            stmt.on_conflict_do_update(index_elements=key, set_=data)
        )
        await cls.notify(merged.fetchall(), "update")

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

    @classmethod
    async def delete(cls, *args, **kwargs):
        stmt = delete(cls).filter(*args, **kwargs).returning("*")
        deleted = await db.session.execute(stmt)
        await cls.notify(deleted.fetchall(), "delete")
