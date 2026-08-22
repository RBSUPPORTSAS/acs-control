from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeviceProfile(Base):
    __tablename__ = "device_profiles"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    manufacturer: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    product_class: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    profile_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    profile_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
