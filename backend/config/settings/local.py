from .base import *

DEBUG = True
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-only-followthrough-development-key")
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
