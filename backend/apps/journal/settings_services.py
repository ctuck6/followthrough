from django.db import transaction
from .models import Attachment, Day, Execution, TradeReview, PendingFileDeletion


def clear_trading_data():
    # Retain deletion work until storage confirms it, including after a failed retry.
    with transaction.atomic():
        for name in Attachment.objects.exclude(file='').values_list('file', flat=True):
            PendingFileDeletion.objects.get_or_create(name=name)
        Attachment.objects.all().delete()
        TradeReview.objects.all().delete()
        Execution.objects.all().delete()
        Day.objects.all().delete()
    storage = Attachment._meta.get_field('file').storage
    for item in PendingFileDeletion.objects.all():
        try:
            storage.delete(item.name)
        except OSError:
            continue
        item.delete()
    return {'cleared': True, 'pending_files': PendingFileDeletion.objects.count()}
