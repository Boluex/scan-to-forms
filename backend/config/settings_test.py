from .settings import *  # noqa: F403

DATABASES = {"default": dj_database_url.parse(os.environ["TEST_DATABASE_URL"]) if os.getenv("TEST_DATABASE_URL") else {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}  # noqa: F405
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

ENABLE_LEGACY_WORKSPACE = True  # Exercise retained APIs in the legacy regression suite.
ENABLE_PAYSTACK = True
DIGITIZATION_PRICE_PER_RESPONDENT_NGN = "100.00"
SYNTHETIC_PRICE_PER_RESPONSE_NGN = "10.00"
BANK_NAME = "Test Bank"
BANK_ACCOUNT_NAME = "ScanToForms Test"
BANK_ACCOUNT_NUMBER = "0000000000"

MIDDLEWARE = [m for m in MIDDLEWARE if m != "whitenoise.middleware.WhiteNoiseMiddleware"]  # noqa: F405
