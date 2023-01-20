import os

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base  # type: ignore
from yarl import URL

from node.crud import CrudMixin

DB_URL = URL.build(
    scheme="postgresql+asyncpg",
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
    path="/",
) / os.getenv("DB_NAME", "node")

Model: DeclarativeMeta = declarative_base()


class Node(CrudMixin, Model):
    __tablename__ = "nodes"

    node_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)

    tags = Column(JSONB, nullable=False)

    configuration = Column(JSONB, nullable=False)
