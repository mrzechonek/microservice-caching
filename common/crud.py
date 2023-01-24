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


class CrudMixin:
    @classmethod
    async def create(cls, **kwargs):
        stmt = insert(cls).values(kwargs)
        await db.session.execute(stmt)

    @classmethod
    async def update(cls, *key, **data):
        stmt = update(cls).where(*key).values(**data)
        await db.session.execute(stmt)

    @classmethod
    async def merge(cls, key, /, **data):
        stmt = insert(cls).values(**key, **data)
        await db.session.execute(
            stmt.on_conflict_do_update(index_elements=key, set_=data)
        )

    @classmethod
    async def delete(cls, *args, **kwargs):
        stmt = delete(cls).filter(*args, **kwargs)
        await db.session.execute(stmt)

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
