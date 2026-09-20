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
