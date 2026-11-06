"""Consulta del registro de auditoria.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db


router = APIRouter()


# ACS_AUDIT_10A
@router.get("/api/audit")
async def audit_list(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    from app.services.audit_service import get_audits

    rows = await get_audits(db, limit)

    return {
        "count": len(rows),
        "audits": [
            {
                "id": row.id,
                "created_at": (
                    row.created_at.isoformat()
                    if row.created_at
                    else None
                ),
                "username": row.username,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "before": row.before_data,
                "after": row.after_data,
                "result": row.result,
                "message": row.message,
            }
            for row in rows
        ]
    }
