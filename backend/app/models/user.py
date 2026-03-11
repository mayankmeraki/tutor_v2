import enum
from typing import Optional

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserRole(enum.Enum):
    admin = "admin"
    student = "student"
    professor = "professor"


class Users(Base):
    """Maps to the existing 'users' table in the Capacity PostgreSQL DB."""

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(20), default="local")
    user_profile_image: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
