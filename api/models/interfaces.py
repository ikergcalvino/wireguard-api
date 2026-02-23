from pydantic import BaseModel, field_validator

from api.models.constants import RE_IFACE_NAME, RE_WG_KEY


class Interface(BaseModel):
    name: str
    address: str | None = None
    listen_port: int | None = None
    private_key: str | None = None
    public_key: str | None = None
    post_up: str | None = None
    post_down: str | None = None
    fwmark: str | None = None
    num_peers: int | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not RE_IFACE_NAME.match(v):
            raise ValueError(
                "Interface name must be 1-15 alphanumeric, dash or underscore characters"
            )
        return v

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str | None) -> str | None:
        if v is not None and not RE_WG_KEY.match(v):
            raise ValueError("Invalid WireGuard key format")
        return v
