import json
from django.test import TestCase, Client
from ..models import Rule, Day
from ..grading import grade

class AttachmentTests(TestCase):
    def test_upload_persists_for_its_date_and_survives_journal_save(self):
        import tempfile
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from ..models import Attachment
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            image = BytesIO()
            Image.new('RGB', (20, 20), 'green').save(image, format='PNG')
            response = self.client.post('/api/days/2026-09-19/attachments/', {'file': SimpleUploadedFile('chart.png', image.getvalue(), content_type='image/png')})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['type'], 'image/png')
            self.assertEqual(len(self.client.get('/api/days/2026-09-19/attachments/').json()['attachments']), 1)
            self.assertEqual(self.client.get('/api/days/2026-09-20/attachments/').json()['attachments'], [])
            self.client.put('/api/days/2026-09-19/', json.dumps({'checks':[]}), content_type='application/json')
            self.assertEqual(Attachment.objects.count(), 1)
            download=self.client.get(response.json()['url'])
            self.assertEqual(b''.join(download.streaming_content), image.getvalue())
            download.close()
            disguised=self.client.post('/api/days/2026-09-19/attachments/', {'file':SimpleUploadedFile('fake.png',b'<script>bad()</script>',content_type='image/png')})
            self.assertEqual(disguised.json()['type'],'application/octet-stream')
            download=self.client.get(disguised.json()['url'])
            self.assertTrue(download['Content-Disposition'].startswith('attachment'))
            download.close()
            self.assertEqual(self.client.post('/api/days/bad/attachments/').status_code,400)
            self.assertEqual(self.client.post('/api/days/2026-09-19/attachments/').status_code,400)

    def test_delete_is_date_scoped_and_removes_file(self):
        import tempfile
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from ..models import Attachment
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            item = self.client.post('/api/days/2026-09-19/attachments/', {'file': SimpleUploadedFile('chart.txt', b'chart notes')}).json()
            attachment = Attachment.objects.get(pk=item['id'])
            storage, name = attachment.file.storage, attachment.file.name
            url = f"/api/days/2026-09-19/attachments/{item['id']}/"
            self.assertEqual(self.client.delete(f"/api/days/2026-09-20/attachments/{item['id']}/").status_code,404)
            self.assertTrue(storage.exists(name))
            self.assertEqual(self.client.get(url).status_code,405)
            secure = Client(enforce_csrf_checks=True)
            self.assertEqual(secure.delete(url).status_code,403)
            token = secure.get('/api/state/').json()['csrfToken']
            self.assertEqual(secure.delete(url, HTTP_X_CSRFTOKEN=token).status_code,204)
            self.assertFalse(storage.exists(name))
            self.assertFalse(Attachment.objects.filter(pk=item['id']).exists())
            self.assertEqual(self.client.get(item['url']).status_code,404)
