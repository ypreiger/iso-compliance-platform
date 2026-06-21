"""Application configuration."""
from __future__ import annotations

import os
from functools import lru_cache

DEFAULT_ADMIN_EMAILS = (
    "yaakov.preiger@think-21.com",
    "yaakovpreiger@gmail.com",
    "valeria.preiger@gmail.com",
)


@lru_cache
def get_settings() -> "Settings":
    return Settings()


class Settings:
    def __init__(self) -> None:
        self.database_host = os.getenv("DATABASE_HOST", "localhost")
        self.database_port = os.getenv("DATABASE_PORT", "5432")
        self.database_user = os.getenv("DATABASE_USER", "iso")
        self.database_password = os.getenv("DATABASE_PASSWORD", "iso")
        self.database_name = os.getenv("DATABASE_NAME", "iso")
        self.jwt_secret = os.getenv("JWT_SECRET", "dev-jwt-secret-change-me")
        self.jwt_ttl_hours = int(os.getenv("JWT_TTL_HOURS", "24"))
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.saml_idp_entity_id = os.getenv("SAML_IDP_ENTITY_ID", "")
        self.saml_idp_sso_url = os.getenv("SAML_IDP_SSO_URL", "")
        self.saml_idp_x509_cert = os.getenv("SAML_IDP_X509_CERT", "")
        self.iso_web_url = os.getenv("ISO_WEB_URL", "http://localhost:5173").rstrip("/")
        self.saml_sp_entity_id = os.getenv(
            "SAML_SP_ENTITY_ID",
            f"{self.iso_web_url}/api/auth/saml/metadata",
        )
        self.saml_sp_acs_url = os.getenv(
            "SAML_SP_ACS_URL",
            f"{self.iso_web_url}/api/auth/saml/acs",
        )
        self.auth_dev_mode = os.getenv("AUTH_DEV_MODE", "0") == "1"
        raw = os.getenv("ADMIN_EMAILS", "")
        self.admin_emails = tuple(
            e.strip().lower()
            for e in (raw.split(",") if raw else DEFAULT_ADMIN_EMAILS)
            if e.strip()
        )
        self.llm_gateway_url = os.getenv("LLM_GATEWAY_URL", "")
        self.llm_api_key = os.getenv("LLM_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        self.llm_model_mapping = os.getenv("LLM_MODEL_MAPPING", "gpt-4-turbo")

    @property
    def dsn(self) -> str:
        return (
            f"host={self.database_host} port={self.database_port} "
            f"dbname={self.database_name} user={self.database_user} "
            f"password={self.database_password}"
        )

    @property
    def google_signin_enabled(self) -> bool:
        """Google Identity Services (any @gmail.com / Google account)."""
        return bool(self.google_client_id)

    @property
    def google_oauth_redirect_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_configured(self) -> bool:
        return self.google_signin_enabled

    @property
    def saml_configured(self) -> bool:
        return bool(
            self.saml_idp_entity_id
            and self.saml_idp_sso_url
            and self.saml_idp_x509_cert.strip()
        )
