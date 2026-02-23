"""API Configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiConfig(BaseSettings):
    """Configuration for atlas-api."""

    environment: str = "production"
    log_level: str = "INFO"

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "atlas_db"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_pool_min_size: int = 4
    db_pool_max_size: int = 20

    @property
    def database_url(self) -> str:
        """Get the PostgreSQL connection string."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(
        env_prefix="ATLAS_API_",
        env_file=".env",
        extra="ignore",
    )
