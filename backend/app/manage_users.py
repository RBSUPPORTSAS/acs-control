"""Gestion de usuarios desde la terminal.

Uso (desde la raiz del repositorio):

    PYTHONPATH=backend .venv/bin/python -m app.manage_users create --username admin --role admin
    PYTHONPATH=backend .venv/bin/python -m app.manage_users reset-password --username admin
    PYTHONPATH=backend .venv/bin/python -m app.manage_users list

La contrasena se pide de forma interactiva (no queda en el historial). Para
scripts, use --password-stdin y pasela por la entrada estandar.
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password, validate_password
from app.models.base import Base
from app.models.user import ROLES, User


def read_password(args) -> str:
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\n")

    first = getpass.getpass("Contraseña: ")
    second = getpass.getpass("Repita la contraseña: ")

    if first != second:
        sys.exit("Las contraseñas no coinciden.")

    return first


async def find(db, username):
    return (
        await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    ).scalar_one_or_none()


async def main(args):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        if args.command == "list":
            for u in (await db.execute(select(User).order_by(User.username))).scalars():
                estado = "activo" if u.active else "inactivo"
                print(f"{u.username:24} {u.role:10} {estado}")
            return

        user = await find(db, args.username)

        if args.command == "create":
            if user:
                sys.exit(f"El usuario {args.username} ya existe.")
            password = read_password(args)
            error = validate_password(password)
            if error:
                sys.exit(error)
            db.add(User(
                username=args.username,
                full_name=args.full_name,
                role=args.role,
                password_hash=hash_password(password),
                active=True,
            ))
            await db.commit()
            print(f"Usuario {args.username} creado con rol {args.role}.")

        elif args.command == "reset-password":
            if not user:
                sys.exit(f"El usuario {args.username} no existe.")
            password = read_password(args)
            error = validate_password(password)
            if error:
                sys.exit(error)
            user.password_hash = hash_password(password)
            user.active = True
            await db.commit()
            print(f"Contraseña de {args.username} actualizada (usuario activo).")

    await engine.dispose()


def parse():
    p = argparse.ArgumentParser(prog="manage_users", description="Usuarios de ACS Control")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create", help="crear usuario")
    c.add_argument("--username", required=True)
    c.add_argument("--role", choices=ROLES, default="technical")
    c.add_argument("--full-name")
    c.add_argument("--password-stdin", action="store_true")

    r = sub.add_parser("reset-password", help="cambiar contraseña y reactivar")
    r.add_argument("--username", required=True)
    r.add_argument("--password-stdin", action="store_true")

    sub.add_parser("list", help="listar usuarios")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse()))
