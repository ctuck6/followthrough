from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from django.db import transaction
from PIL import Image, UnidentifiedImageError
from apps.core.validation import bounded_text
from .models import Attachment, Day, Rule

STATUSES = {"pending", "followed", "broken", "na"}

def save_rule(data):
    text = bounded_text(data.get("text"), 300)
    weight = data.get("weight", 1)
    if not text or type(weight) is not int or not 1 <= weight <= 10:
        raise ValueError("Enter a rule and a weight from 1 to 10.")
    with transaction.atomic():
        if data.get("id"):
            old = Rule.objects.get(id=data["id"], active=True)
            old.active = False
            old.save()
        rule = Rule.objects.create(text=text, weight=weight)

    return rule


def save_day(parsed, data):
    plan = bounded_text(data.get("plan", ""), 20000)
    reflection = bounded_text(data.get("reflection", ""), 20000)
    draft = data.get("draft_trade", {})
    if not isinstance(draft, dict):
        raise ValueError("Invalid trade draft.")
    clean_draft = {key: bounded_text(draft.get(key, "Long" if key == "side" else ""), limit) for key, limit in [("symbol",30),("side",10),("pnl",50),("notes",2000)]}
    if clean_draft["side"] not in ["Long", "Short"]:
        raise ValueError("Invalid draft direction.")
    checks = data.get("checks", [])
    trades = data.get("trades", [])
    if not isinstance(checks, list) or not isinstance(trades, list) or len(trades) > 500:
        raise ValueError("Invalid checklist or trades.")
    with transaction.atomic():
        existing = Day.objects.filter(date=parsed).first()
        template = existing.checks if existing else list(Rule.objects.filter(active=True).values("id", "text", "weight"))
        if len(checks) != len(template) or any(not isinstance(c, dict) for c in checks):
            raise ValueError("The rulebook changed. Reload before saving this new day.")
        statuses = {c.get("id"): c.get("status") for c in checks}
        if len(statuses) != len(template) or set(statuses) != {c["id"] for c in template} or any(s not in STATUSES for s in statuses.values()):
            raise ValueError("Invalid rule assessment.")
        clean_checks = [{**c, "status": statuses[c["id"]]} for c in template]
        clean_trades = []
        for t in trades:
            if not isinstance(t, dict) or t.get("side") not in ["Long", "Short"]:
                raise ValueError("Invalid trade direction.")
            symbol = bounded_text(t.get("symbol"), 30).upper()
            if not symbol:
                raise ValueError("A trade needs a symbol.")
            pnl = Decimal(str(t.get("pnl")))
            if not pnl.is_finite() or abs(pnl) > Decimal("999999999") or pnl != pnl.quantize(Decimal("0.01")):
                raise ValueError("P&L must be a finite amount with at most two decimal places.")
            clean_trades.append({"symbol": symbol, "side": t["side"], "pnl": str(pnl), "notes": bounded_text(t.get("notes", ""), 2000)})
        record, _ = Day.objects.update_or_create(date=parsed, defaults={"plan": plan, "reflection": reflection, "checks": clean_checks, "trades": clean_trades, "draft_trade": clean_draft})

    return record


def save_attachment(parsed, upload):
    if not upload or upload.size > 20 * 1024 * 1024 or upload.size == 0:
        raise ValueError("Choose a nonempty file up to 20 MB.")
    mime = 'application/octet-stream'
    try:
        with Image.open(upload) as image:
            if image.format in ['PNG', 'JPEG', 'GIF', 'WEBP']:
                mime = Image.MIME[image.format]
                image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        mime = 'application/octet-stream'
    upload.seek(0)
    name = Path(upload.name).name[:255]
    attachment = Attachment(date=parsed, name=name, content_type=mime)
    attachment.file.save(uuid4().hex, upload, save=True)

    return attachment


def delete_attachment(day, attachment_id):
    with transaction.atomic():
        attachment = Attachment.objects.select_for_update().get(pk=attachment_id, date=day)
        attachment.file.delete(save=False)
        attachment.delete()
