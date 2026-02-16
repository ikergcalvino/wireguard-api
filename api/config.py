from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    WG_CONFIG_DIR: str = "/etc/wireguard"
    WG_SERVER_ENDPOINT: str = ""
    API_KEY: str = ""

    model_config = {"env_prefix": "WG_API_"}


settings = Settings()
