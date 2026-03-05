from sqlalchemy import TIMESTAMP, Integer
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy.orm import declarative_base as _declarative_base
from sqlalchemy.sql import func


class BaseModel:
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[TIMESTAMP] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False
    )


Base = _declarative_base(cls=BaseModel)
