"""Offline deployment contracts; these tests never contact provider accounts."""

import os
import runpy
import ssl
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml
from celery import Celery
from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values
from storages.backends.s3 import S3Storage

from config.connections import database_config, secure_redis_url

ROOT = Path(__file__).resolve().parents[2]
NEON_URL = "postgresql://beta:test-only@ep-example.eu-central-1.aws.neon.tech/beta?sslmode=require&channel_binding=require"
UPSTASH_URL = "rediss://default:test-only@example.upstash.io:6379/0"
EXTERNAL = {
    "DATABASE_URL": NEON_URL,
    "REDIS_URL": UPSTASH_URL,
    "AWS_STORAGE_BUCKET_NAME": "beta-private",
    "AWS_ACCESS_KEY_ID": "test-only-key",
    "AWS_SECRET_ACCESS_KEY": "test-only-secret",
    "AWS_S3_ENDPOINT_URL": "https://example.r2.cloudflarestorage.com",
}


def load_settings(values):
    with patch.dict(os.environ, {**values, "SCANTO_FORMS_ENV_FILE": "/dev/null"}, clear=True):
        return runpy.run_path(str(ROOT / "backend/config/settings.py"), run_name="config._deployment_settings")


def blueprint_services():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    return blueprint, blueprint["projects"][0]["environments"][0]["services"]


def api_environment():
    _, services = blueprint_services()
    api = next(service for service in services if service["name"] == "scantoforms-api")
    values = {item["key"]: str(item.get("value", "test-only")) for item in api["envVars"]}
    return {**values, **EXTERNAL}


def test_neon_url_uses_verified_tls_and_preserves_database_and_channel_binding():
    config = database_config(NEON_URL)
    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert config["HOST"] == "ep-example.eu-central-1.aws.neon.tech"
    assert config["NAME"] == "beta"
    assert config["USER"] == "beta"
    assert config["OPTIONS"]["sslmode"] == "verify-full"
    assert config["OPTIONS"]["channel_binding"] == "require"
    assert config["OPTIONS"]["sslrootcert"]


@pytest.mark.parametrize("mode", ["disable", "allow", "prefer"])
def test_external_database_rejects_tls_downgrades(mode):
    with pytest.raises(ImproperlyConfigured, match="TLS"):
        database_config(NEON_URL.replace("sslmode=require", f"sslmode={mode}"))


def test_external_database_rejects_pooling_and_local_fallback():
    with pytest.raises(ImproperlyConfigured, match="direct URL"):
        database_config(NEON_URL.replace("ep-example.", "ep-example-pooler."))
    with pytest.raises(ImproperlyConfigured, match="PostgreSQL"):
        database_config("sqlite:///db.sqlite3", require_tls=True)
    assert database_config("sqlite:///:memory:")["ENGINE"] == "django.db.backends.sqlite3"
    assert database_config(NEON_URL, ca_file="/custom/ca.pem")["OPTIONS"]["sslrootcert"] == "/custom/ca.pem"


def test_upstash_native_tls_configures_both_celery_connections_without_network():
    config = load_settings(api_environment())
    url = config["CELERY_BROKER_URL"]
    assert url == config["CELERY_RESULT_BACKEND"]
    assert urlsplit(url).hostname == "example.upstash.io"
    params = parse_qs(urlsplit(url).query)
    assert params["ssl_cert_reqs"] == ["required"]
    assert params["ssl_check_hostname"] == ["true"]
    app = Celery("upstash-config-test", broker=url, backend=url)
    try:
        with app.connection_for_read() as connection:
            assert connection.ssl["ssl_cert_reqs"] == ssl.CERT_REQUIRED
            assert connection.ssl["ssl_check_hostname"] is True
        assert app.backend.connparams["ssl_cert_reqs"] == ssl.CERT_REQUIRED
        assert app.backend.connparams["ssl_check_hostname"] is True
    finally:
        app.close()
    assert config["CELERY_RESULT_EXPIRES"] == 3600


@pytest.mark.parametrize("url", [
    "redis://default:password@example.upstash.io:6379/0",
    "https://example.upstash.io",
    "rediss://example.upstash.io:6379/0",
    UPSTASH_URL + "?ssl_cert_reqs=none",
    UPSTASH_URL + "?ssl_check_hostname=false",
])
def test_external_redis_rejects_rest_plaintext_and_unverified_tls(url):
    with pytest.raises(ImproperlyConfigured):
        secure_redis_url(url, require_tls=True)


def test_api_and_worker_templates_select_the_same_external_resources():
    api = load_settings(api_environment())
    worker_values = dict(dotenv_values(ROOT / ".env.worker.example"))
    worker_values.update(EXTERNAL, DJANGO_SECRET_KEY="test-only")
    worker = load_settings(worker_values)
    for key in ["DATABASES", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "STORAGES"]:
        assert api[key] == worker[key], key
    assert api["EXTERNAL_SERVICES_REQUIRED"] and worker["EXTERNAL_SERVICES_REQUIRED"]
    assert api["PROCESSING_MODE"] == worker["PROCESSING_MODE"] == "celery"
    assert not api["CELERY_TASK_ALWAYS_EAGER"] and not worker["CELERY_TASK_ALWAYS_EAGER"]


def test_r2_configuration_uses_private_acl_and_expiring_signed_urls():
    config = load_settings(api_environment())
    options = config["STORAGES"]["default"]["OPTIONS"]
    storage = S3Storage(**options)
    assert storage.default_acl is None
    assert storage.querystring_auth is True
    assert storage.file_overwrite is False
    assert storage.object_parameters == {"CacheControl": "private, no-store"}
    assert storage.region_name == "auto"
    assert storage.addressing_style == "path"
    # Local signing with dummy credentials only; no object is uploaded or requested.
    signed = urlsplit(storage.url("users/example/private.png", expire=60))
    assert signed.scheme == "https"
    assert signed.hostname == "example.r2.cloudflarestorage.com"
    assert signed.path == "/beta-private/users/example/private.png"
    assert parse_qs(signed.query)["X-Amz-Expires"] == ["60"]
    assert "X-Amz-Signature" in parse_qs(signed.query)


@pytest.mark.parametrize("override", [
    {"OBJECT_STORAGE_ENABLED": "false"},
    {"AWS_S3_ENDPOINT_URL": "http://example.r2.cloudflarestorage.com"},
    {"AWS_SECRET_ACCESS_KEY": ""},
    {"DATABASE_URL": ""},
    {"REDIS_URL": ""},
])
def test_beta_fails_closed_on_missing_or_insecure_external_configuration(override):
    with pytest.raises(ImproperlyConfigured):
        load_settings({**api_environment(), **override})


def test_blueprint_creates_only_two_free_application_services():
    blueprint, services = blueprint_services()
    assert {s["name"] for s in services} == {"scantoforms-api", "scantoforms-web"}
    assert all(s["type"] == "web" and s["plan"] == "free" for s in services)
    assert {s["runtime"] for s in services} == {"node", "docker"}

    def check(node):
        if isinstance(node, dict):
            assert not {"databases", "disk", "fromDatabase", "fromService"}.intersection(node)
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(blueprint)
    api = next(s for s in services if s["name"] == "scantoforms-api")
    variables = {item["key"]: item for item in api["envVars"]}
    for key in [*EXTERNAL, "RESEND_API_KEY", "DEFAULT_FROM_EMAIL"]:
        assert variables[key] == {"key": key, "sync": False}
