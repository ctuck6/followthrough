from django.core.exceptions import ImproperlyConfigured
from .base import *

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
if len(SECRET_KEY) < 50 or SECRET_KEY == "local-only-followthrough-development-key":
    raise ImproperlyConfigured("Production requires DJANGO_SECRET_KEY with at least 50 characters.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production requires explicit DJANGO_ALLOWED_HOSTS.")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
MIDDLEWARE = [*MIDDLEWARE, "django.middleware.clickjacking.XFrameOptionsMiddleware"]
