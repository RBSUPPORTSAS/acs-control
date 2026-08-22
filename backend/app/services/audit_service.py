from sqlalchemy import select
from app.models.audit import AuditLog


async def add_audit(
    db, action, target_id,
    before=None, after=None,
    result="SOLICITADO",
    message=None,
    username="acs-control"
):
    row = AuditLog(
        username=username,
        action=action,
        target_type="ONU",
        target_id=target_id,
        before_data=before,
        after_data=after,
        result=result,
        message=message,
    )

    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_audit(db, row, result, message=None, after=None):

    row.result = result

    if message is not None:
        row.message = message

    if after is not None:
        row.after_data = after

    await db.commit()
    await db.refresh(row)

    return row


async def get_audits(db, limit=100):

    r = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )

    return r.scalars().all()
