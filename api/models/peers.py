from pydantic import BaseModel


class PeerCreate(BaseModel):
    allowed_ips: str = ""


class PeerCreateResponse(BaseModel):
    public_key: str
    private_key: str
    allowed_ips: str
    address: str


class PeerResponse(BaseModel):
    public_key: str
    allowed_ips: str
    endpoint: str | None = None
    latest_handshake: str | None = None
    transfer_rx: str | None = None
    transfer_tx: str | None = None


class PeerListResponse(BaseModel):
    peers: list[PeerResponse]
    total: int
