from django.db import models

class Rule(models.Model):
    text = models.CharField(max_length=300)
    weight = models.PositiveSmallIntegerField(default=1)
    active = models.BooleanField(default=True)

class Day(models.Model):
    date = models.DateField(unique=True)
    plan = models.TextField(blank=True)
    reflection = models.TextField(blank=True)
    checks = models.JSONField(default=list)
    trades = models.JSONField(default=list)
    draft_trade = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

class Attachment(models.Model):
    trade_key = models.CharField(max_length=64, blank=True, default='', db_index=True)
    date = models.DateField(db_index=True)
    file = models.FileField(upload_to='attachments/%Y/%m/')
    name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, default='application/octet-stream')
    created_at = models.DateTimeField(auto_now_add=True)

class Execution(models.Model):
    trade_id = models.CharField(max_length=100, unique=True)
    session_date = models.DateField(db_index=True)
    execution_time = models.CharField(max_length=30, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class TradeReview(models.Model):
    trade_key = models.CharField(max_length=64, primary_key=True)
    notes = models.TextField(blank=True)

class Profile(models.Model):
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)

class PendingFileDeletion(models.Model):
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
    broker = models.CharField(max_length=20, choices=[('ibkr', 'Interactive Brokers'), ('schwab', 'Charles Schwab')])
    source_identifier = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_import_at = models.DateTimeField(null=True, blank=True)
