"""Server-only Firebase credentials; never expose these through a public endpoint."""

import json
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=1)
def firebase_app():
    import firebase_admin
    from firebase_admin import credentials

    if not settings.FIREBASE_PROJECT_ID:
        raise ImproperlyConfigured("Firebase is not configured.")
    credential = (
        credentials.Certificate(json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON))
        if settings.FIREBASE_SERVICE_ACCOUNT_JSON
        else credentials.ApplicationDefault()
    )
    return firebase_admin.initialize_app(
        credential,
        {"projectId": settings.FIREBASE_PROJECT_ID, "httpTimeout": 15},
        name="scanforms",
    )
