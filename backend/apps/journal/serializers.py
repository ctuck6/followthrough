from .grading import grade

def serialize(day):
    return {"date": day.date.isoformat(), "plan": day.plan, "reflection": day.reflection, "checks": day.checks, "trades": day.trades, "draft_trade": day.draft_trade, **grade(day.checks)}

def serialize_attachment(attachment):
    return {"id": attachment.id, "name": attachment.name, "type": attachment.content_type,
            "url": f"/api/attachments/{attachment.id}/file/"}
