from .models import Attachment, Day, Rule
from .serializers import serialize, serialize_attachment

def journal_state():
    return {"rules": list(Rule.objects.filter(active=True).values("id", "text", "weight")),
            "days": [serialize(day) for day in Day.objects.order_by("-date")]}

def attachments_for_day(day):
    return [serialize_attachment(item) for item in Attachment.objects.filter(date=day).order_by("created_at", "id")]

def attachment_by_id(attachment_id):
    return Attachment.objects.get(pk=attachment_id)
