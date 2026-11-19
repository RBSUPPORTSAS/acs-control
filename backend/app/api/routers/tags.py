"""Catalogo de etiquetas: admin las define, todos con sesion las ven.

El nombre no se puede cambiar despues de creado: en GenieACS la etiqueta se
guarda como texto en cada ONU y renombrarla aqui dejaria ONUs con el nombre
viejo. Borrar una etiqueta del catalogo no la quita de las ONUs.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_user
from app.core.database import get_db
from app.models.tag_definition import TagDefinition
from app.services.audit_service import add_audit

router = APIRouter()

COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def valid_tag_name(name: str) -> str:
    name = (name or "").strip()
    if not name or len(name) > 64 or "/" in name:
        raise HTTPException(400, "Etiqueta no válida (1 a 64 caracteres, sin '/')")
    return name


def as_dict(t: TagDefinition) -> dict:
    return {"id": t.id, "name": t.name, "color": t.color, "description": t.description}


async def catalog_names(db: AsyncSession) -> set[str]:
    return set((await db.execute(select(TagDefinition.name))).scalars())


class TagIn(BaseModel):
    name: str
    color: str = "#64748b"
    description: str | None = None


class TagPatch(BaseModel):
    color: str | None = None
    description: str | None = None


def check_color(color: str | None):
    if color is not None and not COLOR.match(color):
        raise HTTPException(400, "Color no válido (use #RRGGBB)")


def clean_description(text: str | None) -> str | None:
    text = (text or "").strip()
    if len(text) > 160:
        raise HTTPException(400, "Descripción de máximo 160 caracteres")
    return text or None


@router.get("/api/tags", dependencies=[Depends(require_user)])
async def list_tags(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(TagDefinition).order_by(TagDefinition.name))).scalars()
    return {"tags": [as_dict(t) for t in rows]}


@router.post("/api/tags", dependencies=[Depends(require_admin)], status_code=201)
async def create_tag(body: TagIn, db: AsyncSession = Depends(get_db)):
    name = valid_tag_name(body.name)
    check_color(body.color)
    exists = await db.scalar(
        select(TagDefinition).where(func.lower(TagDefinition.name) == name.lower())
    )
    if exists:
        raise HTTPException(409, f'La etiqueta "{exists.name}" ya existe')

    tag = TagDefinition(name=name, color=body.color.lower(), description=clean_description(body.description))
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    await add_audit(db, action="ETIQUETA_CATALOGO_CREAR", target_id=name,
                    after=as_dict(tag), result="CONFIRMADO", target_type="SISTEMA")
    return as_dict(tag)


@router.patch("/api/tags/{tag_id}", dependencies=[Depends(require_admin)])
async def update_tag(tag_id: int, body: TagPatch, db: AsyncSession = Depends(get_db)):
    tag = await db.get(TagDefinition, tag_id)
    if not tag:
        raise HTTPException(404, "Etiqueta no encontrada")
    before = as_dict(tag)
    if body.color is not None:
        check_color(body.color)
        tag.color = body.color.lower()
    if "description" in body.model_fields_set:
        tag.description = clean_description(body.description)
    await db.commit()
    await add_audit(db, action="ETIQUETA_CATALOGO_EDITAR", target_id=tag.name,
                    before=before, after=as_dict(tag), result="CONFIRMADO", target_type="SISTEMA")
    return as_dict(tag)


@router.delete("/api/tags/{tag_id}", dependencies=[Depends(require_admin)])
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    tag = await db.get(TagDefinition, tag_id)
    if not tag:
        raise HTTPException(404, "Etiqueta no encontrada")
    before = as_dict(tag)
    await db.delete(tag)
    await db.commit()
    await add_audit(db, action="ETIQUETA_CATALOGO_ELIMINAR", target_id=before["name"],
                    before=before, result="CONFIRMADO", target_type="SISTEMA")
    return {"ok": True}
