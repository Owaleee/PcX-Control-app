import httpx
import pytest
import pytest_asyncio

from pcx_agent.api.app import AppContext, build_context, create_app
from pcx_agent.config import load_settings
from pcx_agent.sensors.fake import FakeSensorProvider

PASSWORD = "segredo-123"


@pytest.fixture
def ctx(tmp_path) -> AppContext:
    context = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider(seed=1))
    context.passwords.set_password(PASSWORD)
    yield context
    context.db.close()


@pytest_asyncio.fixture
async def client(ctx):
    app = create_app(ctx, run_sampler=False)
    transport = httpx.ASGITransport(app=app, client=("10.0.0.5", 5000))
    async with httpx.AsyncClient(transport=transport, base_url="http://agente") as http:
        yield http


async def pair_device(client: httpx.AsyncClient, ctx: AppContext, name: str = "Moto G") -> str:
    """Pareia um aparelho com um codigo novo e devolve o token."""
    code = ctx.pairing.new_code()
    response = await client.post("/v1/pair", json={"device_name": name, "code": code})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _no_crash_hooks_between_tests():
    """Testes que rodam o main() instalam os ganchos de travamento: desfaz ao fim de cada um."""
    yield
    from pcx_agent import crashlog

    crashlog.uninstall_crash_logging()
