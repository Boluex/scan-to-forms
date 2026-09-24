import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [v.strip() for v in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if v.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "apps.core",
    "apps.accounts",
    "apps.questionnaires",
    "apps.documents",
    "apps.exports",
    "apps.notifications",
    "apps.billing",
    "apps.botlab",
    "apps.googleforms",
    "apps.orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
        conn_health_checks=True,
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Africa/Lagos")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.ActiveAccountJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {"anon": "60/hour", "user": "1000/hour", "auth": "10/minute", "upload": "30/hour"},
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "CHECK_REVOKE_TOKEN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ScanToForms API",
    "DESCRIPTION": "Questionnaire digitization and review API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "PlanCodeEnum": "apps.billing.models.Plan.Code",
    },
}

CORS_ALLOWED_ORIGINS = [v.strip() for v in os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if v.strip()]
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:3000").split(",") if v.strip()]

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "ScanToForms <noreply@localhost>")

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_SOFT_TIME_LIMIT = 540

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "100"))
OCR_ENGINE = os.getenv("OCR_ENGINE", "auto")
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 1024 * 1024

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
ADMIN_CONTACT_EMAIL = os.getenv("ADMIN_CONTACT_EMAIL", "admin@localhost")
PAYSTACK_BASE_URL = os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_TIMEOUT_SECONDS = int(os.getenv("PAYSTACK_TIMEOUT_SECONDS", "15"))
PAYSTACK_CALLBACK_URL = os.getenv(
    "PAYSTACK_CALLBACK_URL", f"{FRONTEND_URL}/dashboard/billing/callback"
)
PAYSTACK_PLAN_CODES = {
    ("STUDENT", "MONTHLY"): os.getenv("PAYSTACK_STUDENT_MONTHLY_PLAN_CODE", ""),
    ("STUDENT", "YEARLY"): os.getenv("PAYSTACK_STUDENT_YEARLY_PLAN_CODE", ""),
    ("RESEARCHER", "MONTHLY"): os.getenv("PAYSTACK_RESEARCHER_MONTHLY_PLAN_CODE", ""),
    ("RESEARCHER", "YEARLY"): os.getenv("PAYSTACK_RESEARCHER_YEARLY_PLAN_CODE", ""),
    ("ORGANIZATION", "MONTHLY"): os.getenv("PAYSTACK_ORGANIZATION_MONTHLY_PLAN_CODE", ""),
    ("ORGANIZATION", "YEARLY"): os.getenv("PAYSTACK_ORGANIZATION_YEARLY_PLAN_CODE", ""),
}
EXTRA_OCR_PAGES_PRICE_KOBO = int(os.getenv("EXTRA_OCR_PAGES_PRICE_KOBO", "150000"))

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Focused MVP. Legacy customer tools are disabled at the API boundary.
ENABLE_LEGACY_WORKSPACE = env_bool("ENABLE_LEGACY_WORKSPACE", False)
ENABLE_PAYSTACK = env_bool("ENABLE_PAYSTACK", False)
ENABLE_ORGANIZATIONS = False
ENABLE_PUBLIC_BOTLAB = False
ENABLE_GOOGLE_OAUTH = False
ENABLE_WHATSAPP = False
MANUAL_BANK_TRANSFER_ENABLED = env_bool("MANUAL_BANK_TRANSFER_ENABLED", True)
BANK_NAME = os.getenv("BANK_NAME", "")
BANK_ACCOUNT_NAME = os.getenv("BANK_ACCOUNT_NAME", "")
BANK_ACCOUNT_NUMBER = os.getenv("BANK_ACCOUNT_NUMBER", "")
DIGITIZATION_PRICE_PER_RESPONDENT_NGN = os.getenv("DIGITIZATION_PRICE_PER_RESPONDENT_NGN", "0")
SYNTHETIC_PRICE_PER_RESPONSE_NGN = os.getenv("SYNTHETIC_PRICE_PER_RESPONSE_NGN", "0")
MAX_ORDER_RESPONDENTS = int(os.getenv("MAX_ORDER_RESPONDENTS", "1000"))
MAX_ORDER_PAGES = int(os.getenv("MAX_ORDER_PAGES", "5000"))
MAX_SYNTHETIC_RESPONSES = int(os.getenv("MAX_SYNTHETIC_RESPONSES", "1000"))
PROCESSING_MODE = os.getenv("PROCESSING_MODE", "celery")  # celery or manual (real human transcription)
TEST_DEPLOYMENT = env_bool("TEST_DEPLOYMENT", False)
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({"order_upload": "120/minute", "order_create": "20/hour"})
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
