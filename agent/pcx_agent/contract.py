"""Exemplos fixos do protocolo, compartilhados com o app em docs/protocol/fixtures.

Os testes do agente garantem que os arquivos batem com o codigo; os testes do app leem os
mesmos arquivos. Para regenerar: python tools/write_fixtures.py
"""

from datetime import UTC, datetime
from pathlib import Path

from pcx_agent import PROTOCOL
from pcx_agent.api.app import ApiError, _pair_error
from pcx_agent.api.stream import build_hello, build_snapshot_message
from pcx_agent.auth.pairing import PairError
from pcx_agent.sensors.base import METRIC_NAMES, DiskVolume, GpuReading, Snapshot

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "docs" / "protocol" / "fixtures"

AGENT_ID = "8e3c523e-8ee9-4e80-b25f-411510ac887f"
AGENT_NAME = "PC-DEMO"
VERSION = "1.2.3"  # fixa, para os exemplos nao mudarem a cada versao


def example_snapshot() -> Snapshot:
    return Snapshot(
        t=datetime(2026, 11, 1, 3, 2, 24, 88941, tzinfo=UTC),
        cpu_total=13.0,
        ram_percent=43.8,
        ram_used_bytes=15017385984,
        ram_total_bytes=34266001408,
        disks=[
            DiskVolume(mount="C:\\", percent=81.3, used_bytes=811909726208, total_bytes=999243640832),
            DiskVolume(mount="E:\\", percent=55.0, used_bytes=140781154304, total_bytes=255936425984),
        ],
        disk_read_bps=2965907.8,
        disk_write_bps=3423685.9,
        net_down_bps=4099.7,
        net_up_bps=447.9,
        gpus=[
            GpuReading(
                id="luid_0x00000000_0x0000d38e_phys_0",
                name="NVIDIA GeForce RTX 3070",
                usage_percent=17.98,
                vram_used_bytes=2721603584,
                vram_total_bytes=8406433792,
                temp_c=49.0,
                vendor="nvidia",
            )
        ],
        host_name=AGENT_NAME,
        uptime_s=29186.8,
    )


def _error_body(err: ApiError) -> dict:
    return {"code": err.code, "message": err.message, **err.extra}


def build_fixtures() -> dict[str, object]:
    snapshot = example_snapshot()
    agent = {"id": AGENT_ID, "name": AGENT_NAME, "version": VERSION, "protocol": PROTOCOL}
    return {
        "snapshot_message": build_snapshot_message(42, snapshot),
        "hello": build_hello(AGENT_ID, AGENT_NAME, VERSION, {"cpu", "ram", "disk", "net", "gpu", "gpu.temp"}),
        "info": {"agent_id": AGENT_ID, "name": AGENT_NAME, "version": VERSION, "protocol": PROTOCOL, "busy": False},
        "pair": {"device_id": "0b6f4c2e-5d1a-4c3b-9a8e-7f6d5c4b3a21", "token": "x" * 43, "agent": agent},
        "history": {
            "metric": "cpu.total",
            "range": "15m",
            "points": [
                {"t": 1761966139.0, "avg": 12.5, "max": 20.0},
                {"t": 1761966144.0, "avg": 14.0, "max": 31.5},
            ],
        },
        "metrics": {"names": sorted(METRIC_NAMES), "from_snapshot": snapshot.metrics()},
        "error_bad_credentials": _error_body(_pair_error(PairError("bad_credentials", attempts_left=4))),
        "error_session_busy": _error_body(
            ApiError(409, "session_busy", "PC em uso por Moto G.", active_device="Moto G")
        ),
    }
