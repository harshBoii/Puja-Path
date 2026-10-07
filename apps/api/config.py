from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", extra="ignore")

    brand: str = "Puja Path"
    app_env: str = "development"  # development | test | staging | production

    database_url: str = "postgresql://postgres:postgres@localhost:5432/pujapath"
    redis_url: str = "redis://localhost:6379/0"  # only used when jobs_mode == "worker"
    # Background jobs: "inline" (inside the API, no Redis), "worker" (Arq + Redis), "manual" (tests only).
    jobs_mode: Literal["inline", "worker", "manual"] = "inline"
    staff_2fa: bool = False  # authenticator code after the password for admin sign-in (off: password only)
    cron_secret: str = ""  # enables POST /v1/internal/cron for external schedulers (serverless hosts)
    jwt_secret: str = "change-me"
    revalidate_secret: str = "change-me"
    next_public_site_url: str = "http://localhost:3000"
    web_internal_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""
    r2_key_prefix: str = ""  # e.g. "pujapath/" when the bucket is shared with another app
    pexels_api_key: str = ""  # only for scripts/fetch_images.py
    cf_stream_account_id: str = ""
    cf_stream_api_token: str = ""
    cf_stream_signing_key_id: str = ""
    cf_stream_signing_key_pem: str = ""

    messaging_provider: str = "fake"
    gupshup_api_key: str = ""
    gupshup_app_name: str = ""
    gupshup_source_number: str = ""
    gupshup_webhook_token: str = ""
    wati_api_endpoint: str = ""
    wati_access_token: str = ""
    wati_webhook_token: str = ""

    payment_provider: str = "fake"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    cashfree_app_id: str = ""
    cashfree_secret_key: str = ""
    cashfree_webhook_secret: str = ""
    cashfree_env: str = "sandbox"
    fake_payment_webhook_secret: str = "fake-webhook-secret"

    shipping_provider: str = "fake"
    shiprocket_email: str = ""
    shiprocket_password: str = ""
    shiprocket_pickup_location: str = ""
    shiprocket_pickup_pincode: str = ""
    shiprocket_webhook_token: str = ""

    sms_otp_provider: str = "fake"  # fake | msg91 | telnyx
    sms_otp_api_key: str = ""
    sms_otp_from: str = ""  # telnyx: sender number in E.164 (or an approved alphanumeric sender ID)
    sms_otp_messaging_profile_id: str = ""  # telnyx: optional, when sending from a number pool

    ops_alert_email: str = ""
    smtp_url: str = ""
    slack_webhook_url: str = ""

    sentry_dsn: str = ""
    posthog_key: str = ""

    admin_email: str = ""
    admin_password: str = ""

    local_media_dir: Path = API_DIR / "var" / "media"

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("development", "test")

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def media_public_base(self) -> str:
        # Without R2, media is proxied through the storefront origin (the browser only talks to Next.js).
        return self.r2_public_base_url or f"{self.next_public_site_url}/media"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
