"""Validated profile image uploads, stored outside the database."""

from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Profile


@require_http_methods(["GET", "POST", "DELETE"])
def photo(request: HttpRequest) -> JsonResponse:
    record, _ = Profile.objects.get_or_create(pk=1)

    if request.method == "GET":
        return JsonResponse({"photo_url": record.photo.url if record.photo else ""})

    old_name = record.photo.name
    storage = record.photo.storage

    if request.method == "POST":
        upload = request.FILES.get("photo")

        if not upload or upload.size > 5 * 1024 * 1024:
            return JsonResponse({"error": "Choose an image up to 5 MB."}, status=400)

        try:
            with Image.open(upload) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Choose a JPEG, PNG, or WebP image.")

                if image.width * image.height > 20_000_000:
                    raise ValueError("Choose an image smaller than 20 megapixels.")

                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((512, 512))
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=90)

            record.photo.save(f"{uuid4().hex}.jpg", ContentFile(buffer.getvalue()))
        except (
            ValueError,
            OSError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
        ):
            return JsonResponse(
                {
                    "error": "Choose a valid JPEG, PNG, or WebP image up to 20 megapixels."
                },
                status=400,
            )
    else:
        record.photo = ""
        record.save(update_fields=["photo"])

    if old_name:
        storage.delete(old_name)

    return JsonResponse({"photo_url": record.photo.url if record.photo else ""})
