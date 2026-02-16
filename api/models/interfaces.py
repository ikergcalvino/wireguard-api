from pydantic import BaseModel


class InterfaceCreate(BaseModel):
    name: str
    address: str = "10.0.0.1/24"
    listen_port: int = 51820
    post_up: str = "iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
    post_down: str = "iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"


class InterfaceResponse(BaseModel):
    name: str
    public_key: str
    address: str
    listen_port: int
    status: str
    total_peers: int = 0
    enabled_peers: int = 0


class InterfaceDetailResponse(InterfaceResponse):
    transfer: str | None = None


class InterfaceListResponse(BaseModel):
    interfaces: list[InterfaceResponse]
    total: int
