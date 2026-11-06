from sqlalchemy import select
from app.core.security import current_username
from app.models.audit import AuditLog


async def add_audit(
    db, action, target_id,
    before=None, after=None,
    result="SOLICITADO",
    message=None,
    username=None,
    target_type="ONU",
):
    if username is None:
        username = current_username.get() or "acs-control"

    row = AuditLog(
        username=username,
        action=action,
        target_type=target_type,
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


async def get_audits(db, limit=100, target_type=None, username=None):

    query = select(AuditLog)

    if target_type:
        query = query.where(AuditLog.target_type == target_type)

    if username:
        query = query.where(AuditLog.username == username)

    r = await db.execute(
        query
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )

    return r.scalars().all()


def client_info(request) -> dict:
    """IP de origen (respeta X-Forwarded-For de Nginx) y navegador."""

    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else None

    if not ip and request.client:
        ip = request.client.host

    return {
        "ip": ip,
        "navegador": (request.headers.get("user-agent") or "")[:200],
    }


async def log_event(
    db,
    action,
    target_type,
    target_id,
    request=None,
    before=None,
    after=None,
    result="OK",
    message=None,
    username=None,
):
    """Registra un movimiento de usuario (sesiones, gestion de usuarios, etc.)."""

    after = dict(after or {})

    if request is not None:
        after.update(client_info(request))

    return await add_audit(
        db,
        action=action,
        target_id=target_id,
        before=before,
        after=after or None,
        result=result,
        message=message,
        username=username,
        target_type=target_type,
    )
