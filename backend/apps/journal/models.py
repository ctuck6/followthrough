from django.db import models


class Rule(models.Model):
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    text = models.CharField(max_length=300)
    weight = models.PositiveSmallIntegerField(default=1)
    active = models.BooleanField(default=True)


class Day(models.Model):
    date = models.DateField()
    account = models.ForeignKey("BrokerageAccount", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "date"], name="unique_account_day"),
            models.UniqueConstraint(
                fields=["date"],
                condition=models.Q(account__isnull=True),
                name="unique_unassigned_day",
            ),
        ]

    plan = models.TextField(blank=True)
    reflection = models.TextField(blank=True)
    checks = models.JSONField(default=list)
    trades = models.JSONField(default=list)
    draft_trade = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class Attachment(models.Model):
    account = models.ForeignKey("BrokerageAccount", null=True, blank=True, on_delete=models.PROTECT)
    trade_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    date = models.DateField(db_index=True)
    file = models.FileField(upload_to="attachments/%Y/%m/")
    name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, default="application/octet-stream")
    created_at = models.DateTimeField(auto_now_add=True)


class Execution(models.Model):
    account = models.ForeignKey("BrokerageAccount", null=True, blank=True, on_delete=models.PROTECT)
    trade_id = models.CharField(max_length=100, unique=True)
    session_date = models.DateField(db_index=True)
    execution_time = models.CharField(max_length=30, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class TradeReview(models.Model):
    trade_key = models.CharField(max_length=64, primary_key=True)
    notes = models.TextField(blank=True)


class Profile(models.Model):
    photo = models.FileField(upload_to="profiles/", blank=True)
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)


class PendingFileDeletion(models.Model):
    account = models.ForeignKey(
        "BrokerageAccount", null=True, blank=True, on_delete=models.SET_NULL
    )
    name = models.CharField(max_length=500, unique=True)


class Strategy(models.Model):
    name = models.CharField(max_length=100)
    criteria = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class TradeStrategy(models.Model):
    trade_key = models.CharField(max_length=64, primary_key=True)
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE)
    checked = models.JSONField(default=list)


class BrokerageAccount(models.Model):
    name = models.CharField(max_length=100)
    broker = models.CharField(
        max_length=20, choices=[("ibkr", "Interactive Brokers"), ("schwab", "Charles Schwab"), ("tradovate", "Tradovate")]
    )
    source_identifier = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_import_at = models.DateTimeField(null=True, blank=True)


class BrokerSync(models.Model):
    conflicts = models.JSONField(default=list)
    account = models.ForeignKey(BrokerageAccount, null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, default="idle")
    message = models.CharField(max_length=500, blank=True)
    last_attempt = models.DateTimeField(null=True)
    last_success = models.DateTimeField(null=True)
    last_report_date = models.DateField(null=True)
    scheduled_day = models.DateField(null=True)
    retry_at = models.DateTimeField(null=True)
    failures = models.PositiveIntegerField(default=0)
    lease_until = models.DateTimeField(null=True)
    run_id = models.CharField(max_length=40, blank=True)
    requested = models.BooleanField(default=False)
    imported = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
