"""SAML SP settings for Google Workspace IdP."""
from __future__ import annotations

from urllib.parse import urlparse

from onelogin.saml2.settings import OneLogin_Saml2_Settings

from app.config import Settings, get_settings


def _cert_body(pem: str) -> str:
    return (
        pem.strip()
        .replace("-----BEGIN CERTIFICATE-----", "")
        .replace("-----END CERTIFICATE-----", "")
        .replace("\n", "")
        .strip()
    )


def saml_settings_dict(settings: Settings) -> dict:
    return {
        "strict": True,
        "debug": settings.auth_dev_mode,
        "sp": {
            "entityId": settings.saml_sp_entity_id,
            "assertionConsumerService": {
                "url": settings.saml_sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": settings.saml_idp_entity_id,
            "singleSignOnService": {
                "url": settings.saml_idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": _cert_body(settings.saml_idp_x509_cert),
        },
        "security": {
            "wantAssertionsSigned": True,
            "wantMessagesSigned": False,
            "authnRequestsSigned": False,
        },
    }


def build_saml_settings(settings: Settings) -> OneLogin_Saml2_Settings:
    return OneLogin_Saml2_Settings(saml_settings_dict(settings))


def request_dict_from_http(request, *, post_data: dict | None = None) -> dict:
    """Build the request dict expected by python3-saml (proxy-aware)."""
    settings = get_settings()
    parsed = urlparse(settings.saml_sp_acs_url)
    host = parsed.netloc or request.headers.get("host", "localhost")
    path = parsed.path or request.url.path
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    port = parsed.port or (443 if proto == "https" else 80)
    return {
        "https": "on" if proto == "https" else "off",
        "http_host": host,
        "script_name": path,
        "server_port": port,
        "get_data": dict(request.query_params),
        "post_data": post_data or {},
    }
