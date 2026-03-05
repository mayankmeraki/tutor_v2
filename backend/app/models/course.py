import enum
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DifficultyLevel(enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class Course(Base):
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel), nullable=False
    )
    rating: Mapped[int] = mapped_column(Numeric(4, 2), nullable=True, default=0.00)
    img_link: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    preview_video: Mapped[str] = mapped_column(String(2048), nullable=False)
    learning_outcomes: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"), nullable=True
    )
    featured_course: Mapped[bool] = mapped_column(Boolean, nullable=True)
    prerequisites: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"), nullable=True
    )
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"), nullable=True
    )
    special_tags: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"), nullable=True
    )
    course_summary: Mapped[str] = mapped_column(Text, nullable=True, default="")
    course_summary_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"), nullable=True
    )


class Module(Base):
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_keyword: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Lesson(Base):
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("module.id", ondelete="CASCADE"), nullable=False, index=True
    )
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(2048))
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_summary: Mapped[str] = mapped_column(Text, nullable=True, default="")
    lesson_summary_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"), nullable=True
    )
