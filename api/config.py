from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "WG_"}

    api_key: str = ""
    log_level: str = "INFO"
    cors_origins: str = "*"
    config_dir: Path = Path("/etc/wireguard")


settings = Settings()
