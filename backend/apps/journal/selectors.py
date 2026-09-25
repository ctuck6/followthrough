from .models import Attachment, Day, Rule
from .serializers import serialize, serialize_attachment


def journal_state(account_id=None):
    return {
        "rules": list(Rule.objects.filter(active=True).values("id", "text", "weight")),
        "days": [
            serialize(day) for day in Day.objects.filter(account_id=account_id).order_by("-date")
        ],
    }


def attachments_for_day(day, account_id=None):
    return [
        serialize_attachment(item)
        for item in Attachment.objects.filter(
            date=day, trade_key="", account_id=account_id
        ).order_by("created_at", "id")
    ]


def attachment_by_id(attachment_id):
    return Attachment.objects.get(pk=attachment_id)
