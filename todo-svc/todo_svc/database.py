import os

from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.ext.declarative import DeclarativeMeta  # type: ignore
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship  # type: ignore
from yarl import URL

from todo_svc.crud import CrudMixin

DB_URL = URL.build(
    scheme="postgresql+asyncpg",
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
    path="/",
) / os.getenv("DB_NAME", "todo")

Model: DeclarativeMeta = declarative_base()


class TodoList(CrudMixin, Model):
    __tablename__ = "lists"

    list_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)

    collaborators = relationship("Collaborator", lazy="joined", cascade="all, delete-orphan", backref="list")

    entries = relationship("TodoEntry", lazy="joined", cascade="all, delete-orphan", backref="list")


class TodoEntry(CrudMixin, Model):
    __tablename__ = "entries"

    entry_id = Column(Text, primary_key=True, unique=True)
    list_id = Column(Text, ForeignKey("lists.list_id", ondelete="CASCADE"), primary_key=True)
    text = Column(Text, nullable=False)


class Collaborator(CrudMixin, Model):
    __tablename__ = "collaborators"

    list_id = Column(Text, ForeignKey("lists.list_id"), primary_key=True)
    email = Column(Text, primary_key=True)
    role = Column(Text, nullable=False)
