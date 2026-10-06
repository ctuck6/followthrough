from django.test import TestCase

from apps.journal.models import Day, Rule
from apps.journal.selectors import journal_state
from apps.journal.services import reorder_rules, save_rule


class RuleOrderTests(TestCase):
    def test_order_persists_with_historical_assessments(self) -> None:
        first = save_rule({"text": "First", "weight": 1})
        second = save_rule({"text": "Second", "weight": 2})
        checks = [{"id": first.id, "text": first.text, "weight": 1, "status": "followed"}]
        day = Day.objects.create(date="2026-10-04", checks=checks)
        revised = save_rule({"id": first.id, "text": "Revised", "weight": 1})
        reorder_rules([second.id, revised.id])
        state = journal_state()
        self.assertEqual([r["id"] for r in state["rules"]], [second.id, revised.id])
        self.assertEqual(state["rule_order"][first.id], state["rule_order"][revised.id])
        day.refresh_from_db()
        self.assertEqual(day.checks, checks)
        appended = save_rule({"text": "Third", "weight": 1})
        self.assertGreater(appended.position, state["rule_order"][revised.id])

    def test_invalid_or_stale_order_is_rejected(self) -> None:
        first = save_rule({"text": "First", "weight": 1})
        second = save_rule({"text": "Second", "weight": 1})

        for ids in ([first.id], [first.id, first.id], [first.id, 999], None):
            response = self.client.post(
                "/api/rules/reorder/", {"ids": ids}, content_type="application/json"
            )
            self.assertEqual(response.status_code, 400)

        self.assertEqual(list(Rule.objects.values_list("id", flat=True)), [first.id, second.id])
        response = self.client.post(
            "/api/rules/reorder/", {"ids": [second.id, first.id]}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rules"][0]["id"], second.id)
