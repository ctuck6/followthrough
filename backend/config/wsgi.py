import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
application = get_wsgi_application()

# Start only in the serving process, after Django has initialized.
from apps.journal.broker_sync import start_worker  # noqa: E402

start_worker()
