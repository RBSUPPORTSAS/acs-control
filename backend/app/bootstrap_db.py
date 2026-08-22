import asyncio

from app.core.database import engine
from app.models.base import Base
from app.models.audit import AuditLog
from app.models.device_profile import DeviceProfile


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Tablas ACS Control creadas/verificadas correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
