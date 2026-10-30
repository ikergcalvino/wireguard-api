import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.services.wireguard import _lifecycle_locks

VALID_KEY = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_lifecycle_locks():
    # asyncio locks are bound to the event loop that first uses them, and every test runs its own loop.
    yield
    _lifecycle_locks.clear()
