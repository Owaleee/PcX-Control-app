"""Logica da bandeja, sem tkinter: as janelas so chamam este controlador."""

import getpass
import os
import platform
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pcx_agent.api.app import AppContext
from pcx_agent.auth.pairing import Device
from pcx_agent.auth.passwords import MIN_LENGTH
from pcx_agent.config import save_port
from pcx_agent.crashlog import PreviousSession
from pcx_agent.diagnostics import fixes
from pcx_agent.diagnostics.model import CheckResult, Fix
from pcx_agent.diagnostics.report import ReportFacts, build_report
from pcx_agent.diagnostics.runner import ALL_CHECKS, Sources, exe_path, probe_agent, run_all
from pcx_agent.diagnostics.support import build_support_zip, choose_dest
from pcx_agent.diagnostics.windows import read_firewall_rules, read_security_products
from pcx_agent.network import (
    lan_address,
    list_interfaces,
    network_category,
    parse_profiles,
    profile_output_status,
    run_profile_script,
)
from pcx_agent.pairing_uri import local_ipv4, pairing_uri
from pcx_agent.tray import texts
from pcx_agent.winsys import folders

LOOPBACK = "127.0.0.1"
NO_NETWORK_WARNING = (
    "Não encontrei a rede deste PC. Conecte-o ao Wi-Fi ou ao cabo e gere outro código."
)
PUBLIC_NETWORK_WARNING = (
    "A rede deste PC está como Pública: o celular não vai conseguir conectar. "
    "Mude para Privada nas configurações de rede do Windows."
)
DOMAIN_NETWORK_WARNING = (
    "A rede deste PC é de domínio (rede de empresa): a regra do PcX Control vale só para redes "
    "Privadas, então o celular pode não conseguir conectar."
)
MISMATCH_MESSAGE = "As senhas não são iguais."
SHORT_MESSAGE = f"A senha precisa ter pelo menos {MIN_LENGTH} caracteres."


def _can_write(folder: Path) -> bool:
    """Da para criar arquivo na pasta? Testa de verdade: a Area de Trabalho pode estar protegida."""
    probe = folder / f".pcx-{uuid.uuid4().hex}.tmp"
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        return False
    return True


class PasswordInputError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class PairingInfo:
    code: str
    uri: str
    host: str
    port: int
    expires_at: float
    warning: str | None
    interface: str | None = None


@dataclass(frozen=True)
class DeviceRow:
    id: str
    name: str
    last_used: str
    active: bool


def format_last_used(ts: float, now: float) -> str:
    elapsed = now - ts
    if elapsed < 60:
        return "agora"
    if elapsed < 3600:
        return f"há {int(elapsed // 60)} min"
    when, today = time.localtime(ts), time.localtime(now)
    if when[:3] == today[:3]:
        return time.strftime("hoje às %H:%M", when)
    midnight = time.mktime((*today[:3], 0, 0, 0, 0, 0, -1))
    yesterday = time.localtime(midnight - 43200)  # meio-dia de ontem (seguro no horario de verao)
    if when[:3] == yesterday[:3]:
        return time.strftime("ontem às %H:%M", when)
    return time.strftime("%d/%m/%Y", when)


class AgentController:
    def __init__(
        self,
        ctx: AppContext,
        port: int,
        *,
        address_lookup: Callable[[], tuple[str, str | None]] | None = None,
        category_lookup: Callable[[str | None], str | None] | None = None,
        now: Callable[[], float] = time.time,
        diagnostics_sources: Callable[[], Sources] | None = None,
        fix_actions: dict[str, Callable[[], bool]] | None = None,
        server=None,
        previous_session: PreviousSession | None = None,
        autostart_enabled: Callable[[], bool] | None = None,
    ) -> None:
        self._ctx = ctx
        self._port = port
        self._server = server
        self._previous_session = previous_session
        self._autostart_enabled = autostart_enabled
        self.last_fix_message: str | None = None
        self.last_package: Path | None = None
        # Resolvidos na chamada (e nao no padrao do parametro) para os testes trocarem o modulo.
        self._address_lookup = address_lookup or (lambda: lan_address())
        self._category_lookup = category_lookup or (lambda name: network_category(name))
        self._now = now
        self._diagnostics_sources = diagnostics_sources or self._real_sources
        self._fix_actions = fix_actions or {
            "abrir_rede": fixes.open_network_settings,
            "criar_firewall": lambda: fixes.create_firewall_rule(exe_path()),
            "reiniciar_sensores": self._restart_sensors,
            "reiniciar_servidor": self._restart_server,
            "trocar_porta": self._change_port,
            "salvar_pacote": self._save_package_fix,
        }
        self.on_paired: Callable[[str], None] | None = None
        # (resultados, ids que rodaram): alimenta o monitor da bandeja com a rodada da janela.
        self.on_results: Callable[[list[CheckResult], set[str]], None] | None = None
        ctx.pairing.on_pair = self._handle_pair

    @property
    def port(self) -> int:
        """Porta atual: a do servidor, que muda quando a pessoa troca a porta."""
        return self._server.port if self._server is not None else self._port

    def program_path(self) -> str:
        return sys.executable

    def _restart_sensors(self) -> bool:
        reset = getattr(self._ctx.provider, "reset_sensors", None)
        if reset is not None:
            reset()
        return True

    def _restart_server(self) -> bool:
        if self._server is None:
            return False
        self._server.restart()
        return True

    def _change_port(self) -> bool:
        if self._server is None:
            return False
        new = fixes.find_free_port(self._server.port + 1)
        if new is None or not save_port(self._ctx.settings.config_path, new):
            return False  # fica na porta antiga
        self._server.restart(new)
        if self._server.start_error is not None:
            return False  # nem a porta nova subiu: a verificacao do agente mostra o motivo
        self.last_fix_message = texts.DIAG_PORT_CHANGED.format(porta=new)
        return True

    def _handle_pair(self, device: Device) -> None:
        if self.on_paired is not None:
            self.on_paired(device.name)

    def needs_first_run(self) -> bool:
        return not self._ctx.passwords.is_set()

    def set_password(self, new: str, confirm: str) -> None:
        if new != confirm:
            raise PasswordInputError(MISMATCH_MESSAGE)
        if len(new) < MIN_LENGTH:
            raise PasswordInputError(SHORT_MESSAGE)
        self._ctx.passwords.set_password(new)

    def start_pairing(self) -> PairingInfo:
        code = self._ctx.pairing.new_code()
        host, interface = self._address_lookup()
        return PairingInfo(
            code=code,
            uri=pairing_uri(self._ctx.db.agent_id, host, self.port, code),
            host=host,
            port=self.port,
            expires_at=self._now() + self._ctx.pairing.code_ttl_s,
            warning=NO_NETWORK_WARNING if host == LOOPBACK else None,
            interface=interface,
        )

    def public_network_warning(self, info: PairingInfo) -> str | None:
        """Aviso quando a placa do QR esta numa rede Publica. Pode demorar: chame fora da UI."""
        if info.interface is None:
            return None
        # A regra do firewall vale so no perfil Privado: Publica e Dominio bloqueiam o celular.
        category = self._category_lookup(info.interface)
        if category == "public":
            return PUBLIC_NETWORK_WARNING
        if category == "domain":
            return DOMAIN_NETWORK_WARNING
        return None

    def devices(self) -> list[DeviceRow]:
        active = self._ctx.sessions.active()
        active_id = active.device_id if active is not None else None
        now = self._now()
        devices = sorted(
            self._ctx.pairing.list_devices(),
            key=lambda d: (d.id != active_id, -d.last_used_at),
        )
        return [
            DeviceRow(d.id, d.name, format_last_used(d.last_used_at, now), d.id == active_id)
            for d in devices
        ]

    def revoke(self, device_id: str) -> None:
        self._ctx.pairing.revoke(device_id)

    def revoke_all(self) -> None:
        self._ctx.pairing.revoke_all()

    def status_text(self) -> str:
        active = self._ctx.sessions.active()
        if active is None:
            return "PcX Control: aguardando celular"
        return f"PcX Control: conectado a {active.device_name}"

    # Diagnostico ("Verificar conexao"). Roda fora da thread da interface: chama o PowerShell.

    def _real_sources(self) -> Sources:
        def profiles() -> dict[str, str] | None:
            raw = run_profile_script()
            return None if profile_output_status(raw) == "ilegivel" or not raw else parse_profiles(raw)

        def reading():
            snapshot = self._ctx.sampler.latest
            return (snapshot, None) if snapshot is not None else (None, "ainda sem leitura")

        server = self._server

        def server_state() -> tuple[str | None, bool]:
            return (server.start_error, server.running) if server is not None else (None, True)

        return Sources(
            interfaces=list_interfaces,
            route=local_ipv4,
            profiles=profiles,
            firewall_rules=read_firewall_rules,
            exe_path=exe_path,
            security=read_security_products,
            probe=lambda address: probe_agent(address, self._ctx.db.agent_id),
            reading=reading,
            port=self.port,
            server_state=server_state,
            reading_age=self._ctx.sampler.reading_age,
            previous_session=lambda: self._previous_session,
            gpu_failed=lambda: bool(getattr(self._ctx.provider, "gpu_failed", False)),
        )

    def clear_crash_notice(self) -> None:
        """Esconde o aviso de fechamento inesperado (depois que o pacote foi salvo)."""
        self._previous_session = None

    def run_checks(self, ids: set[str] | None) -> list[CheckResult]:
        """Roda so as verificacoes de `ids` (None = todas), sem avisar a bandeja."""
        return run_all(self._diagnostics_sources(), only=ids)

    def run_diagnostics(self) -> list[CheckResult]:
        results = self.run_checks(None)
        hook = self.on_results
        if hook is not None:
            hook(results, set(ALL_CHECKS))
        return results

    def watch_sensor_failures(self, callback: Callable[[], None]) -> None:
        """Liga `callback` as falhas de sensor: o Sampler chama depois de publicar a leitura."""
        self._ctx.sampler.on_sensor_failure = callback

    def diagnostics_report(self, results: list[CheckResult]) -> str:
        sources = self._diagnostics_sources()
        snapshot, _ = sources.reading()
        try:
            interfaces = sources.interfaces()
        except OSError:
            interfaces = []
        facts = ReportFacts(
            agent_version=self._ctx.settings.version,
            windows_version=f"{platform.system()} {platform.release()} ({platform.version()})",
            interfaces=interfaces,
            gpus=snapshot.gpus if snapshot is not None else [],
            pdh_instances=list(getattr(self._ctx.provider, "gpu_instances", [])),
            extra=self._report_extra(snapshot),
        )
        return build_report(results, facts)

    def _report_extra(self, snapshot) -> list[str]:
        """Linhas de [PC e agente]: so contagens e versoes, nunca nomes de aparelhos."""
        provider = self._ctx.provider
        drivers_of = getattr(provider, "adapter_drivers", None)
        drivers = drivers_of() if callable(drivers_of) else {}
        sources = getattr(provider, "temperature_source", {})
        lines = [f"CPU: {platform.processor() or 'desconhecida'}"]
        for gpu in snapshot.gpus if snapshot is not None else []:
            luid = gpu.id.removeprefix("luid_").split("_phys_")[0].lower()
            lines.append(
                f"{gpu.name}: driver {drivers.get(luid) or 'desconhecido'}, "
                f"temperatura por {sources.get(luid, 'desconhecida')}"
            )
        lines.append(f"Porta: {self.port}")
        lines.append(f"Início com o Windows: {self._autostart_text()}")
        lines.append(f"Celulares pareados: {len(self._ctx.pairing.list_devices())}")
        lines.append(f"Celular conectado agora: {'sim' if self._ctx.sessions.active() else 'não'}")
        return lines

    def _autostart_text(self) -> str:
        if self._autostart_enabled is None:
            return "desconhecido"
        try:
            return "sim" if self._autostart_enabled() else "não"
        except Exception:  # noqa: BLE001 - o relatorio sai mesmo sem esta linha
            return "desconhecido"

    def save_support_package(self, results: list[CheckResult], candidates: list[Path] | None = None) -> Path:
        """Grava o zip na Area de Trabalho (ou Documentos, ou logs) e some o aviso de fechamento."""
        log_dir = self._ctx.settings.log_dir
        if candidates is None:
            candidates = [d for d in (folders.desktop_dir(), folders.documents_dir()) if d is not None]
            candidates.append(log_dir)
        dest = choose_dest(candidates, _can_write)
        try:
            home = os.path.expanduser("~")
        except Exception:  # noqa: BLE001
            home = ""
        try:
            user = getpass.getuser()
        except Exception:  # noqa: BLE001
            user = ""
        path = build_support_zip(
            dest, self.diagnostics_report(results), log_dir, self._ctx.settings.config_path,
            datetime.now(), home, user,
        )
        self.clear_crash_notice()
        return path

    def _save_package_fix(self) -> bool:
        self.last_package = self.save_support_package(self.run_diagnostics())
        return True

    def apply_fix(self, fix: Fix) -> bool:
        """Abre a correcao; o diagnostico roda de novo quando a pessoa volta para a janela."""
        return self._fix_actions[fix]()

