import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    app_name: str = "Aashan"
    environment: str = "development"
    mock_mode: bool = True
    setu_base_url: str = ""
    setu_auth_base_url: str = "https://accountservice.setu.co"
    setu_client_id: str = ""
    setu_client_secret: str = ""
    setu_product_instance_id: str = ""
    setu_auto_fetch: bool = False
    redirect_url: str = ""
    webhook_base_url: str = ""
    aa_webhook_token: str = ""
    aa_webhook_secret: str = ""
    webhook_replay_window_seconds: int = 300
    max_webhook_bytes: int = 1024 * 1024
    rate_limit_enabled: bool = True
    trust_proxy_headers: bool = False
    allowed_hosts: list = field(default_factory=lambda: ["*"])
    database_url: str = "sqlite:///./aashan.db"
    auth_required: bool = False
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_service_role_key: str = ""
    cors_origins: list = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:8501",
        "http://localhost:8000",
    ])

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(Path.cwd() / ".env")
        cors = os.getenv("CORS_ORIGINS", "").strip()
        origins = [item.strip() for item in cors.split(",") if item.strip()] or None
        return cls(
            app_name=os.getenv("APP_NAME", "Aashan"),
            environment=os.getenv("ENVIRONMENT", "development"),
            mock_mode=os.getenv("MOCK_MODE", "true").lower() in {"1", "true", "yes", "on"},
            setu_base_url=os.getenv("SETU_BASE_URL", ""),
            setu_auth_base_url=os.getenv("SETU_AUTH_BASE_URL", "https://accountservice.setu.co"),
            setu_client_id=os.getenv("SETU_CLIENT_ID", ""),
            setu_client_secret=os.getenv("SETU_CLIENT_SECRET", ""),
            setu_product_instance_id=os.getenv("SETU_PRODUCT_INSTANCE_ID", ""),
            setu_auto_fetch=os.getenv("SETU_AUTO_FETCH", "false").lower() in {"1", "true", "yes", "on"},
            redirect_url=os.getenv("REDIRECT_URL", ""),
            webhook_base_url=os.getenv("WEBHOOK_BASE_URL", ""),
            aa_webhook_token=os.getenv("AA_WEBHOOK_TOKEN", ""),
            aa_webhook_secret=os.getenv("AA_WEBHOOK_SECRET", ""),
            webhook_replay_window_seconds=int(os.getenv("WEBHOOK_REPLAY_WINDOW_SECONDS", "300") or 300),
            rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
            trust_proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"},
            allowed_hosts=[h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()] or ["*"],
            database_url=os.getenv("DATABASE_URL", "sqlite:///./aashan.db"),
            auth_required=os.getenv("AUTH_REQUIRED", "").lower() in {"1", "true", "yes", "on"}
                or os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"},
            supabase_url=os.getenv("SUPABASE_URL", "").rstrip("/"),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
            supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", ""),
            supabase_jwt_issuer=os.getenv("SUPABASE_JWT_ISSUER", "").rstrip("/"),
            supabase_jwt_audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated"),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
            cors_origins=origins or cls().cors_origins,
        )


settings = Settings.from_env()
