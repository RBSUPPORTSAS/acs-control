from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TagDefinition(Base):
    """Etiqueta predefinida por admin. El rol technical solo asigna estas."""

    __tablename__ = "tag_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#64748b")
    description: Mapped[str | None] = mapped_column(String(160), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
