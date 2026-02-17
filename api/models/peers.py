from pydantic import BaseModel


class Peer(BaseModel):
    public_key: str
    allowed_ips: str | None = None
    endpoint: str | None = None
    preshared_key: str | None = None
    persistent_keepalive: int | None = None
    latest_handshake: int | None = None
    transfer_rx: int | None = None
    transfer_tx: int | None = None
