from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image


class ProfilePhotoTests(TestCase):
    def test_upload_replace_remove_and_reject_invalid(self) -> None:
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image = BytesIO()
            Image.new("RGB", (800, 600), "green").save(image, format="PNG")

            def upload() -> object:
                return self.client.post(
                    "/api/profile/photo/",
                    {"photo": SimpleUploadedFile("avatar.png", image.getvalue())},
                )

            first = upload()
            self.assertEqual(first.status_code, 200)
            self.assertTrue(first.json()["photo_url"])
            self.assertEqual(len(list(Path(directory).rglob("*.jpg"))), 1)
            self.assertEqual(upload().status_code, 200)
            self.assertEqual(len(list(Path(directory).rglob("*.jpg"))), 1)
            invalid = self.client.post(
                "/api/profile/photo/",
                {"photo": SimpleUploadedFile("bad.png", b"not an image")},
            )
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(len(list(Path(directory).rglob("*.jpg"))), 1)
            self.assertEqual(
                self.client.delete("/api/profile/photo/").json()["photo_url"], ""
            )
            self.assertEqual(len(list(Path(directory).rglob("*.jpg"))), 0)
