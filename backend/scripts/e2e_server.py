"""Disposable local browser-test backend. Never connects to the project database."""
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
with tempfile.TemporaryDirectory(prefix='scantoforms-e2e-') as directory:
    os.environ.update({
        'DJANGO_SETTINGS_MODULE': 'config.settings', 'DJANGO_DEBUG': 'true',
        'DATABASE_URL': f'sqlite:///{directory}/test.sqlite3', 'MEDIA_ROOT': f'{directory}/media',
        'PROCESSING_MODE': 'manual', 'TEST_DEPLOYMENT': 'true', 'USE_S3_STORAGE': 'false',
        'ENABLE_LEGACY_WORKSPACE': 'false', 'ENABLE_PAYSTACK': 'false',
        'BANK_NAME': 'E2E Test Bank', 'BANK_ACCOUNT_NAME': 'Test Only', 'BANK_ACCOUNT_NUMBER': '0000000000',
        'DIGITIZATION_PRICE_PER_RESPONDENT_NGN': '100', 'SYNTHETIC_PRICE_PER_RESPONSE_NGN': '10',
        'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        'DJANGO_CORS_ALLOWED_ORIGINS': 'http://127.0.0.1:3107', 'FRONTEND_URL': 'http://127.0.0.1:3107',
    })
    import django
    django.setup()
    from django.core.management import call_command

    from apps.accounts.models import User
    call_command('migrate', interactive=False, verbosity=0)
    # Test credentials exist only inside this disposable database.
    User.objects.create_user(email='operator@example.test', name='E2E Operator', password='E2E-Operator-43892!', is_staff=True)
    call_command('runserver', '127.0.0.1:8107', use_reloader=False)
