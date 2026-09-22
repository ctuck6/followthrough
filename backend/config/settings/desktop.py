"""Local desktop launcher settings; shares the normal journal database."""
from .local import *  # noqa: F403

CSRF_TRUSTED_ORIGINS = ['http://localhost:5174']
