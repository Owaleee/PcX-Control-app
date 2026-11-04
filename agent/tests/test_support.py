"""Pacote de suporte: zip com relatorio, logs e configuracao, sem banco e sem segredos."""

import dataclasses
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from pcx_agent.api.app import build_context
from pcx_agent.config import load_settings
from pcx_agent.controller import AgentController
from pcx_agent.diagnostics.model import CheckResult
from pcx_agent.diagnostics.support import build_support_zip, choose_dest, scrub
from pcx_agent.sensors.fake import FakeSensorProvider
from pcx_agent.winsys import folders

windows = pytest.mark.skipif(sys.platform != "win32", reason="so no Windows")
NOW = datetime(2026, 11, 3, 14, 5)
HOME = r"C:\Users\Alexandre"
TOKEN = "A" * 22


def _setup(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "agent.log").write_text('{"msg": "ok"}\n', encoding="utf-8")
    (logs / "agent.log.1").write_text("antigo\n", encoding="utf-8")
    (logs / "gpu.log").write_text("gpu\n", encoding="utf-8")
    (logs / "crash.log").write_text("crash\n", encoding="utf-8")
    (logs / "crash-20261103.log").write_text("crash2\n", encoding="utf-8")
    (logs / "pcx.db").write_text("segredo", encoding="utf-8")
    (logs / "pcx.db-wal").write_text("segredo", encoding="utf-8")
    (logs / "pcx.db-shm").write_text("segredo", encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text('{"port": 8765}', encoding="utf-8")
    return logs, config


def test_zip_has_report_logs_config_and_no_db(tmp_path):
    logs, config = _setup(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()
    path = build_support_zip(dest, "relatorio", logs, config, NOW, HOME, "Alexandre")
    assert path.name == "PcXControl-suporte-20261103-1405.zip"
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    assert {"relatorio.txt", "config.json", "logs/agent.log", "logs/agent.log.1", "logs/gpu.log",
            "logs/crash.log", "logs/crash-20261103.log"} <= names
    assert not [n for n in names if ".db" in n]


def test_zip_contents_scrubbed(tmp_path):
    logs, config = _setup(tmp_path)
    (logs / "agent.log").write_text(
        f"token {TOKEN}1 em C:\\Users\\Alexandre\\AppData e c:/users/alexandre/x e Alexandre\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out"
    dest.mkdir()
    path = build_support_zip(dest, f"rel {TOKEN}", logs, config, NOW, HOME, "Alexandre")
    with zipfile.ZipFile(path) as z:
        log = z.read("logs/agent.log").decode()
        rel = z.read("relatorio.txt").decode()
    assert "[oculto]" in log and TOKEN not in log and "[oculto]" in rel
    assert "%USERPROFILE%\\AppData" in log
    assert "%USERPROFILE%/x" in log
    assert "Alexandre" not in log and "alexandre" not in log.lower()


def test_scrub_short_user_is_not_replaced():
    assert scrub("o pc de ab", r"C:\Users\ab", "ab") == "o pc de ab"


def test_unreadable_log_listed_and_zip_still_created(tmp_path, monkeypatch):
    logs, config = _setup(tmp_path)
    real = Path.read_bytes

    def fake(self):
        if self.name == "gpu.log":
            raise PermissionError("em uso")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", fake)
    dest = tmp_path / "out"
    dest.mkdir()
    path = build_support_zip(dest, "rel", logs, config, NOW, HOME, "Alexandre")
    with zipfile.ZipFile(path) as z:
        assert "logs/gpu.log" not in z.namelist()
        rel = z.read("relatorio.txt").decode()
        assert "logs/agent.log" in z.namelist()
    assert "[Arquivos que ficaram de fora]" in rel
    assert "logs/gpu.log" in rel and "em uso" in rel


def test_choose_dest_falls_back_to_documents_then_logs(tmp_path):
    desktop, documents, logs = tmp_path / "d", tmp_path / "doc", tmp_path / "logs"
    assert choose_dest([desktop, documents, logs], lambda p: True) == desktop
    assert choose_dest([desktop, documents, logs], lambda p: p != desktop) == documents
    assert choose_dest([desktop, documents, logs], lambda p: p == logs) == logs
    assert choose_dest([desktop, documents, logs], lambda p: False) == logs


def _controller(tmp_path):
    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())
    ctx.settings.log_dir.mkdir(parents=True, exist_ok=True)
    return ctx, AgentController(ctx, 8765, diagnostics_sources=_sources(), autostart_enabled=lambda: True)


def _sources():
    from pcx_agent.diagnostics.model import AgentProbe
    from pcx_agent.diagnostics.runner import Sources

    return lambda: Sources(
        interfaces=list, route=lambda: None, profiles=dict, firewall_rules=list, exe_path=lambda: None,
        security=list, probe=lambda a: AgentProbe(reachable=True, same_agent=True),
        reading=lambda: (None, "ainda sem leitura"), port=8765,
    )


def test_report_extra_has_no_device_names(tmp_path):
    ctx, controller = _controller(tmp_path)
    try:
        ctx.pairing.pair("Celular do Ze", code=ctx.pairing.new_code(), client_ip="10.0.0.1")
        text = controller.diagnostics_report([])
        assert "Porta: 8765" in text
        assert "Início com o Windows: sim" in text
        assert "Celulares pareados: 1" in text
        assert "Celular conectado agora: não" in text
        assert "Ze" not in text
    finally:
        ctx.db.close()


def test_autostart_unknown_without_callable(tmp_path):
    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())
    try:
        text = AgentController(ctx, 8765, diagnostics_sources=_sources()).diagnostics_report([])
        assert "Início com o Windows: desconhecido" in text
    finally:
        ctx.db.close()


def test_save_package_clears_crash_notice(tmp_path):
    ctx, controller = _controller(tmp_path)
    try:
        controller._previous_session = object()
        path = controller.save_support_package(
            [CheckResult("a", "Agente", "t", "ok", "d")], candidates=[tmp_path]
        )
        assert path.exists() and path.parent == tmp_path
        assert controller._previous_session is None
        with zipfile.ZipFile(path) as z:
            assert "relatorio.txt" in z.namelist()
    finally:
        ctx.db.close()


@windows
def test_desktop_dir_exists():
    assert folders.desktop_dir() is not None and folders.desktop_dir().exists()
    assert folders.documents_dir() is not None


def test_known_folders_none_outside_windows():
    if sys.platform != "win32":
        assert folders.desktop_dir() is None and folders.documents_dir() is None



def test_failed_build_leaves_no_partial_file(tmp_path, monkeypatch):
    from pcx_agent.diagnostics import support

    logs, config = _setup(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()

    def boom(*args):
        raise OSError("disco cheio")

    monkeypatch.setattr(support, "scrub", boom)
    with pytest.raises(OSError):
        build_support_zip(dest, "rel", logs, config, NOW, HOME, "Alexandre")
    assert list(dest.iterdir()) == []


def test_report_extra_driver_and_source_by_luid(tmp_path):
    from pcx_agent.sensors.base import GpuReading, Snapshot

    class Provider(FakeSensorProvider):
        def __init__(self):
            super().__init__()
            self.temperature_source = {"0x0_0x1": "driver"}

        def adapter_drivers(self):
            return {"0x0_0x1": "31.0.101.5"}

    gpu = GpuReading(id="luid_0x0_0x1_phys_0", name="Placa X", usage_percent=1, vram_total_bytes=1, vendor="amd")
    snap = Snapshot(
        t=NOW, cpu_total=1, ram_percent=1, ram_used_bytes=1, ram_total_bytes=2, disks=[], disk_read_bps=0,
        disk_write_bps=0, net_down_bps=0, net_up_bps=0, gpus=[gpu], host_name="PC", uptime_s=1,
    )
    ctx = build_context(load_settings(data_dir=tmp_path), Provider())
    try:
        sources = dataclasses.replace(_sources()(), reading=lambda: (snap, None))
        controller = AgentController(ctx, 8765, diagnostics_sources=lambda: sources)
        assert "Placa X: driver 31.0.101.5, temperatura por driver" in controller.diagnostics_report([])
    finally:
        ctx.db.close()
