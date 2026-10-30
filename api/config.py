from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WG_")

    # Required: the API controls the host's WireGuard interfaces, so it never runs unauthenticated.
    api_key: str = Field(min_length=16)
    log_level: str = "INFO"
    cors_origins: str = "*"
    config_dir: Path = Path("/etc/wireguard")


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        errors = "; ".join(
            f"WG_{'_'.join(str(part) for part in error['loc']).upper()}: {error['msg']}" for error in exc.errors()
        )
        raise SystemExit(f"Invalid configuration: {errors}") from None


settings = load_settings()
