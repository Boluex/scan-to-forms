"""Connection configuration shared by local and external workers."""

import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def database_config(url, require_tls=False, ca_file=""):
    """Use direct PostgreSQL sessions and verified TLS for the external beta."""
    parts = urlsplit(url)
    neon = (parts.hostname or "").endswith(".neon.tech")
    if require_tls or neon:
        if parts.scheme not in {"postgres", "postgresql"} or not parts.hostname:
            raise ImproperlyConfigured("Set DATABASE_URL to an external PostgreSQL URL.")
        if neon and "-pooler" in parts.hostname:
            raise ImproperlyConfigured("Use Neon's direct URL: OCR recovery requires session advisory locks.")
        options = dict(parse_qsl(parts.query))
        if options.get("sslmode", "require") not in {"require", "verify-ca", "verify-full"}:
            raise ImproperlyConfigured("PostgreSQL TLS must remain enabled.")
        # Upgrade provider sslmode=require to certificate AND hostname verification.
        options["sslmode"] = "verify-full"
        root = ca_file or options.get("sslrootcert") or ssl.get_default_verify_paths().cafile
        if not root:
            raise ImproperlyConfigured("Set DATABASE_SSL_ROOT_CERT to a trusted CA bundle.")
        options["sslrootcert"] = root
        url = urlunsplit(parts._replace(query=urlencode(options)))
    return dj_database_url.parse(url, conn_max_age=60, conn_health_checks=True)


def secure_redis_url(url, ca_file="", require_tls=False):
    parts = urlsplit(url)
    if require_tls and (parts.scheme != "rediss" or not parts.hostname or not parts.password):
        raise ImproperlyConfigured("Set REDIS_URL to an authenticated rediss:// URL.")
    if parts.scheme != "rediss":
        return url
    options = dict(parse_qsl(parts.query))
    if options.get("ssl_cert_reqs", "required") not in {"required", "CERT_REQUIRED"}:
        raise ImproperlyConfigured("Redis TLS certificate verification must be required.")
    if options.get("ssl_check_hostname", "true").lower() not in {"true", "1"}:
        raise ImproperlyConfigured("Redis TLS hostname verification must remain enabled.")
    options.update(ssl_cert_reqs="required", ssl_check_hostname="true")
    if ca_file:
        options["ssl_ca_certs"] = ca_file
    return urlunsplit(parts._replace(query=urlencode(options)))
