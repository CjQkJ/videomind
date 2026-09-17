from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "CHANGE_ME_IN_PRODUCTION_videomind_2026"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "VideoMind"
    site_name: str = "VideoMind"
    environment: str = "development"
    secret_key: str = DEFAULT_SECRET_KEY
    database_url: str = "sqlite:///./jobs_data/app.sqlite3"
    cors_origins: str = ""
    allow_dev_codes: bool = True

    jwt_expire_hours: int = 720
    email_code_expire_minutes: int = 10
    email_code_length: int = 6
    email_code_cooldown_seconds: int = 60

    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "VideoMind"
    smtp_use_tls: bool = True

    guest_global_concurrency: int = 1
    user_concurrency: int = 2
    vip_concurrency: int = 4
    global_hard_cap: int = 4
    guest_queue_limit: int = 10
    user_queue_limit: int = 20
    global_queue_limit: int = 200

    jobs_dir: str = "./jobs_data"
    uploads_dir: str = "./uploads_data"
    max_upload_size_bytes: int = 500 * 1024 * 1024

    # Upstream OpenAI-compatible endpoint. Point this at your own provider or
    # gateway; there is intentionally no shared default.
    openai_base_url: str = ""
    openai_api_key: str = ""
    default_model: str = "gemini-3.6-flash-high"
    understand_mode: str = "native"
    max_video_duration_sec: int = 14400
    segment_seconds: int = 12 * 60
    segment_overlap_seconds: int = 30
    segment_threshold_seconds: int = 15 * 60

    worker_poll_seconds: float = 1.5
    worker_count: int = 2
    worker_lease_seconds: int = 3600

    # Email address granted the admin role on login. Leave empty to disable
    # the admin console; set ADMIN_EMAIL to your own address when deploying.
    admin_email: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_security(settings: Settings) -> None:
    if settings.environment.strip().lower() not in {"production", "prod"}:
        return
    if settings.secret_key == DEFAULT_SECRET_KEY:
        raise RuntimeError("生产环境必须配置非默认 SECRET_KEY")
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError("生产环境必须配置 SMTP_USER / SMTP_PASSWORD")
    if "*" in {item.strip() for item in settings.cors_origins.split(",")}:
        raise RuntimeError("生产环境 CORS_ORIGINS 不能包含通配符 *")
