from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    target_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    target_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    before_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    after_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    result: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
