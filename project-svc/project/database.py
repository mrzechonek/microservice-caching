import os

from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from yarl import URL

from project.crud import CrudMixin

DB_URL = URL.build(
    scheme="postgresql+asyncpg",
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
    path="/",
) / os.getenv("DB_NAME", "project")

Model: DeclarativeMeta = declarative_base()


class Project(CrudMixin, Model):
    __tablename__ = "projects"

    project_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)

    collaborators = relationship(
        "Collaborator", lazy="joined", cascade="all, delete-orphan", backref="project"
    )

    areas = relationship("Area", lazy="joined", cascade="all, delete-orphan", backref="project")


class Area(CrudMixin, Model):
    __tablename__ = "areas"

    area_id = Column(Text, primary_key=True, unique=True)
    name = Column(Text, nullable=False)
    scenario = Column(Text, nullable=False)
    project_id = Column(Text, ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True)


class Collaborator(CrudMixin, Model):
    __tablename__ = "collaborators"

    project_id = Column(Text, ForeignKey("projects.project_id"), primary_key=True)
    email = Column(Text, primary_key=True)
    role = Column(Text, nullable=False)
