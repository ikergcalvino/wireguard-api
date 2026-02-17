from pydantic import BaseModel


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
