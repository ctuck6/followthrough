import json
from datetime import date
from decimal import InvalidOperation
from django.http import FileResponse, Http404, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_http_methods
from . import selectors, services
from .models import Attachment, Rule
from .serializers import serialize, serialize_attachment

def payload(request):
    value = json.loads(request.body)

    if not isinstance(value, dict):
        raise ValueError("Expected an object.")

    return value

@require_http_methods(["GET"])
def state(request):
    return JsonResponse({"csrfToken": get_token(request), **selectors.journal_state()})

@require_http_methods(["POST"])
def rules(request):
    try:
        rule = services.save_rule(payload(request))

        return JsonResponse({"id": rule.id, "text": rule.text, "weight": rule.weight}, status=201)
    except (ValueError, TypeError, Rule.DoesNotExist) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

@require_http_methods(["PUT"])
def day(request, day):
    try:
        return JsonResponse(serialize(services.save_day(date.fromisoformat(day), payload(request))))
    except (ValueError, TypeError, InvalidOperation) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

@require_http_methods(["GET", "POST"])
def attachments(request, day):
    try:
        parsed = date.fromisoformat(day)

        if request.method == "GET":
            return JsonResponse({"attachments": selectors.attachments_for_day(parsed)})

        return JsonResponse(serialize_attachment(services.save_attachment(parsed, request.FILES.get("file"))), status=201)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

@require_http_methods(["GET"])
def attachment_file(request, attachment_id):
    try:
        attachment = selectors.attachment_by_id(attachment_id)
        stream = attachment.file.open("rb")
    except (Attachment.DoesNotExist, FileNotFoundError):
        raise Http404("Attachment file missing")

    response = FileResponse(stream, content_type=attachment.content_type,
                            as_attachment=not attachment.content_type.startswith("image/"), filename=attachment.name)
    response["X-Content-Type-Options"] = "nosniff"

    return response


@require_http_methods(["DELETE"])
def delete_attachment(request, day, attachment_id):
    from django.http import HttpResponse

    try:
        services.delete_attachment(date.fromisoformat(day), attachment_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Attachment.DoesNotExist:
        return JsonResponse({"error": "Attachment not found for this day."}, status=404)
    except OSError:
        return JsonResponse({"error": "The file could not be removed. Please try again."}, status=500)

    return HttpResponse(status=204)

@require_http_methods(["GET", "POST"])
def executions(request):
    from . import executions as engine
    try:
        if request.method == 'GET': return JsonResponse(engine.ledger())
        data = payload(request)
        from .accounts import prepare_import, record_import
        from django.db import transaction
        rows, account = prepare_import(data) if 'csv' in data else ([engine.normalize(data['execution'])], None)
        if data.get('preview'):
            new, duplicates = engine.inspect_batch(rows)
            return JsonResponse({'rows':new,'duplicates':duplicates,'warnings':getattr(rows,'warnings',[]),'dates':sorted({r['session_date'] for r in rows})})
        with transaction.atomic():
            if 'csv' in data:
                from .models import BrokerageAccount
                BrokerageAccount.objects.filter(pk=-1).update(name='')
                rows, account = prepare_import(data)
            result = engine.import_rows(rows)
            record_import(account, rows)
        return JsonResponse({**result,**engine.ledger()}, status=201)
    except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
        return JsonResponse({'error':str(exc)},status=400)


def trade_by_key(key):
    from .executions import ledger
    trade=next((t for t in ledger()['trades'] if t['trade_id']==key),None)
    if trade is None: raise Http404('Trade not found')
    return trade

@require_http_methods(['GET','PUT'])
def trade_journal(request, key):
    from .models import TradeReview
    from apps.core.validation import bounded_text
    trade_by_key(key)
    if request.method=='GET':
        review=TradeReview.objects.filter(pk=key).first()
        return JsonResponse({'notes':review.notes if review else ''})
    try:
        notes=bounded_text(payload(request).get('notes',''),20000)
        TradeReview.objects.update_or_create(trade_key=key,defaults={'notes':notes})
        return JsonResponse({'notes':notes})
    except (ValueError,TypeError) as exc:return JsonResponse({'error':str(exc)},status=400)

@require_http_methods(['GET','POST','DELETE'])
def trade_attachments(request, key, attachment_id=None):
    trade=trade_by_key(key)
    try:
        if request.method=='GET':
            return JsonResponse({'attachments':[serialize_attachment(a) for a in Attachment.objects.filter(trade_key=key).order_by('created_at','id')]})
        if request.method=='DELETE':
            attachment=Attachment.objects.get(pk=attachment_id,trade_key=key)
            services.delete_attachment(attachment.date,attachment.id,trade_key=key)
            return JsonResponse({'deleted':True})
        return JsonResponse(serialize_attachment(services.save_attachment(date.fromisoformat(trade['session_date']),request.FILES.get('file'),trade_key=key)),status=201)
    except Attachment.DoesNotExist:raise Http404('Attachment not found for this trade')
    except ValueError as exc:return JsonResponse({'error':str(exc)},status=400)


@require_http_methods(['POST'])
def manual_trade(request):
    from .manual_trades import save_manual_trade
    from .executions import ledger
    try:
        result=save_manual_trade(payload(request))
        return JsonResponse({**result,**ledger()},status=201)
    except (ValueError,TypeError,KeyError,InvalidOperation) as exc:
        return JsonResponse({'error':str(exc)},status=400)

@require_http_methods(['POST'])
def manual_execution(request):
    from .manual_trades import save_manual_execution
    from .executions import ledger
    try:
        result=save_manual_execution(payload(request))
        return JsonResponse({**result,**ledger()},status=201)
    except (ValueError,TypeError,KeyError,InvalidOperation) as exc:
        return JsonResponse({'error':str(exc)},status=400)

@require_http_methods(['GET', 'PUT'])
def profile(request):
    from .models import Profile
    from apps.core.validation import bounded_text
    if request.method == 'GET':
        record = Profile.objects.filter(pk=1).first()
        return JsonResponse({'display_name': record.display_name if record else '', 'bio': record.bio if record else ''})
    try:
        data = payload(request)
        values = {'display_name': bounded_text(data.get('display_name', ''), 100), 'bio': bounded_text(data.get('bio', ''), 1000)}
        Profile.objects.update_or_create(pk=1, defaults=values)
        return JsonResponse(values)
    except (ValueError, TypeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

@require_http_methods(['DELETE'])
def clear_trading_data(request):
    from .settings_services import clear_trading_data as clear
    try:
        if payload(request).get('confirmation') != 'CLEAR_ALL_TRADE_AND_JOURNAL_DATA':
            return JsonResponse({'error': 'Explicit confirmation is required.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Explicit confirmation is required.'}, status=400)
    return JsonResponse(clear())


@require_http_methods(['DELETE'])
def remove_rules(request):
    from .deletions import delete_rules
    try:return JsonResponse(delete_rules(payload(request)))
    except (ValueError,TypeError) as exc:return JsonResponse({'error':str(exc)},status=400)

@require_http_methods(['DELETE'])
def remove_executions(request):
    from .deletions import delete_executions
    try:return JsonResponse(delete_executions(payload(request)))
    except (ValueError,TypeError) as exc:return JsonResponse({'error':str(exc)},status=400)
