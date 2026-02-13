from pydantic import BaseModel


class PeerCreate(BaseModel):
    name: str
    allowed_ips: str = ""
    dns: str = "1.1.1.1"


class PeerResponse(BaseModel):
    name: str
    public_key: str
    allowed_ips: str
    endpoint: str | None = None
    latest_handshake: str | None = None
    transfer_rx: str | None = None
    transfer_tx: str | None = None
    enabled: bool = True


class PeerListResponse(BaseModel):
    peers: list[PeerResponse]
    total: int
