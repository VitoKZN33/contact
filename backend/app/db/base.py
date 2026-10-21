from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Единые имена ограничений — стабильные миграции Alembic
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Значения server_default/onupdate (created_at, status …) возвращаются через RETURNING
    # сразу при INSERT/UPDATE: в async-режиме ленивая подгрузка поля после записи невозможна.
    __mapper_args__ = {"eager_defaults": True}
