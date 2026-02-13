from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    WG_INTERFACE: str = "wg0"
    WG_CONFIG_DIR: str = "/etc/wireguard"
    WG_SERVER_IP: str = "10.0.0.1"
    WG_SUBNET: str = "10.0.0.0/24"
    WG_PORT: int = 51820
    WG_SERVER_ENDPOINT: str = ""
    API_KEY: str = ""

    model_config = {"env_prefix": "WG_API_"}


settings = Settings()
