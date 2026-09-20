from django.apps import AppConfig

class JournalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.journal"
    # Keep the existing migration identity and journal_* database tables.
    label = "journal"
