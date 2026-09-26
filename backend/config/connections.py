"""Connection configuration shared by local and external workers."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.core.exceptions import ImproperlyConfigured


def secure_redis_url(url, ca_file=""):
    parts = urlsplit(url)
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
