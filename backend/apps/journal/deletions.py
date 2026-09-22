from django.db import transaction
from .models import Execution, Rule, TradeReview, Attachment, PendingFileDeletion
from .executions import ledger


def ids_from(data, strings=False):
    ids=data.get('ids')
    if not isinstance(ids,list) or not ids or len(ids)>10000:raise ValueError('Select one or more items.')
    if any((not isinstance(x,str) or not x) if strings else (type(x) is not int or x<1) for x in ids):raise ValueError('Invalid selection.')
    return set(ids)

@transaction.atomic
def delete_rules(data):
    ids=ids_from(data)
    rows=Rule.objects.filter(pk__in=ids,active=True)
    if rows.count()!=len(ids):raise ValueError('Some rules no longer exist. Reload and try again.')
    rows.update(active=False)
    return {'rules':list(Rule.objects.filter(active=True).values('id','text','weight'))}


def delete_executions(data):
    ids=ids_from(data,True)
    with transaction.atomic():
        rows=Execution.objects.filter(trade_id__in=ids)
        if rows.count()!=len(ids):raise ValueError('Some executions no longer exist. Reload and try again.')
        before=ledger()['trades']
        rows.delete()
        result=ledger()
        for old in before:
            if not ids.intersection(old['execution_ids']):continue
            survivors=set(old['execution_ids'])-ids
            candidates=[t for t in result['trades'] if survivors.intersection(t['execution_ids'])]
            new=max(candidates,key=lambda t:len(survivors.intersection(t['execution_ids']))) if candidates else None
            key=old['trade_id']
            if new and new['trade_id']==key:continue
            review=TradeReview.objects.filter(pk=key).first()
            if new:
                target=new['trade_id']
                if review:
                    dest,_=TradeReview.objects.get_or_create(trade_key=target)
                    dest.notes='\n\n'.join(filter(None,[dest.notes,review.notes]));dest.save();review.delete()
                Attachment.objects.filter(trade_key=key).update(trade_key=target)
            else:
                for name in Attachment.objects.filter(trade_key=key).values_list('file',flat=True):
                    PendingFileDeletion.objects.get_or_create(name=name)
                Attachment.objects.filter(trade_key=key).delete()
                TradeReview.objects.filter(pk=key).delete()
    storage=Attachment._meta.get_field('file').storage
    for item in PendingFileDeletion.objects.all():
        try:storage.delete(item.name)
        except OSError:continue
        item.delete()
    return {**result,'deleted':len(ids),'pending_files':PendingFileDeletion.objects.count()}
