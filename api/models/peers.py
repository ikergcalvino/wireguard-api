import re

from pydantic import BaseModel, field_validator

_RE_WG_KEY = re.compile(r"^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=?$")


class Peer(BaseModel):
    public_key: str
    allowed_ips: str | None = None
    endpoint: str | None = None
    preshared_key: str | None = None
    persistent_keepalive: int | None = None
    latest_handshake: int | None = None
    transfer_rx: int | None = None
    transfer_tx: int | None = None

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        if not _RE_WG_KEY.match(v):
            raise ValueError("Invalid WireGuard key format")
        return v

    @field_validator("preshared_key")
    @classmethod
    def validate_preshared_key(cls, v: str | None) -> str | None:
        if v is not None and not _RE_WG_KEY.match(v):
            raise ValueError("Invalid WireGuard key format")
        return v
