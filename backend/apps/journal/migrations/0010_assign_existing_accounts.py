"""Assign existing data only where its account can be identified unambiguously."""

from django.db import migrations


def assign_accounts(apps, schema_editor) -> None:
    account_model = apps.get_model("journal", "BrokerageAccount")
    execution_model = apps.get_model("journal", "Execution")
    day_model = apps.get_model("journal", "Day")
    attachment_model = apps.get_model("journal", "Attachment")
    accounts = list(account_model.objects.all())
    for execution in execution_model.objects.filter(account=None):
        matches = [a for a in accounts if a.source_identifier == execution.data.get("account")]
        if len(matches) == 1:
            execution.account_id = matches[0].pk
            execution.save(update_fields=["account"])

    for day in day_model.objects.filter(account=None):
        owners = set(
            execution_model.objects.filter(session_date=day.date).values_list(
                "account_id", flat=True
            )
        )
        # A mixed-account review cannot safely be attributed to one account.
        owner = next(iter(owners)) if len(owners) == 1 else None
        if not owners and len(accounts) == 1:
            owner = accounts[0].pk
        if owner is not None:
            day.account_id = owner
            day.save(update_fields=["account"])
            attachment_model.objects.filter(date=day.date, trade_key="").update(account_id=owner)

    for execution in execution_model.objects.exclude(account=None):
        day_model.objects.get_or_create(
            date=execution.session_date,
            account_id=execution.account_id,
            defaults={
                "checks": [
                    dict(r, status="pending")
                    for r in apps.get_model("journal", "Rule")
                    .objects.filter(active=True)
                    .values("id", "text", "weight")
                ]
            },
        )


class Migration(migrations.Migration):
    dependencies = [("journal", "0009_attachment_account_day_account_execution_account_and_more")]
    operations = [migrations.RunPython(assign_accounts, migrations.RunPython.noop)]
