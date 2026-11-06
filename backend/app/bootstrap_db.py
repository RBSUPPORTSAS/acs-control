import asyncio

from sqlalchemy import text

from app.core.database import engine
from app.models.base import Base
from app.models.audit import AuditLog
from app.models.device_profile import DeviceProfile
from app.models.user import User


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # El rol de administracion se llamo "staff" en una version previa
        # de la rama de login; hoy es "admin".
        await conn.execute(
            text("UPDATE users SET role = 'admin' WHERE role = 'staff'")
        )

    await engine.dispose()
    print("Tablas ACS Control creadas/verificadas correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
