from django.test import TestCase


class SettingsTests(TestCase):
    def test_profile_roundtrip_and_validation(self):
        response = self.client.put(
            "/api/profile/",
            {"display_name": "New name", "bio": "Trading goals"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get("/api/profile/").json(),
            {"display_name": "New name", "bio": "Trading goals"},
        )
        self.assertEqual(
            self.client.put(
                "/api/profile/",
                {"display_name": "x" * 101},
                content_type="application/json",
            ).status_code,
            400,
        )
