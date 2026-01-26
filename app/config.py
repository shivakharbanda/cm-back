"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    app_debug: bool = False
    app_port: int = 8000

    # Frontend URL for CORS
    frontend_url: str = "http://localhost:5173"

    # Database - individual components
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "automation_db"

    @property
    def database_url(self) -> str:
        """Construct async database URL from components."""
        return f"postgresql+psycopg_async://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # JWT Settings
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Instagram OAuth
    instagram_client_id: str = ""
    instagram_client_secret: str = ""
    instagram_redirect_uri: str = "http://localhost:8000/api/v1/instagram/callback"

    # Instagram Graph API
    instagram_graph_api_url: str = "https://graph.instagram.com"

    # Encryption key for storing access tokens
    encryption_key: str = ""

    # Logging
    log_level: str = "INFO"

    # RabbitMQ
    rabbitmq_url: str = "amqp://admin:admin123@localhost:5672/"

    # Link-in-Bio Settings
    bio_page_enabled: bool = True

    # GeoIP
    geoip_database_path: str = "./data/GeoLite2-Country.mmdb"

    # Analytics
    analytics_retention_days: int = 90

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
