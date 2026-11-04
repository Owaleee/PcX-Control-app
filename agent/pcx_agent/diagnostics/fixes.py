"""Correcoes oferecidas pelo diagnostico. Cada uma so abre algo; a pessoa confirma no Windows."""

import logging
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path, PureWindowsPath

from pcx_agent.server import PortInUseError, _ensure_port_free

logger = logging.getLogger("pcx_agent.diagnostics")
NETWORK_SETTINGS_URI = "ms-settings:network-status"
FIREWALL_SCRIPT = "firewall.cmd"  # instalado ao lado do .exe (packaging/installer.iss)
PORT_ATTEMPTS = 20


def port_is_free(port: int, host: str = "0.0.0.0") -> bool:
    """Mesmo teste de bind que o servidor faz antes de subir."""
    try:
        _ensure_port_free(host, port)
    except PortInUseError:
        return False
    except OSError:
        return False
    return True


def find_free_port(
    start: int, attempts: int = PORT_ATTEMPTS, is_free: Callable[[int], bool] = port_is_free
) -> int | None:
    """Primeira porta livre a partir de `start`; None depois de `attempts` tentativas."""
    for port in range(start, min(start + attempts, 65536)):
        if is_free(port):
            return port
    return None


def open_network_settings() -> bool:
    """Abre Configuracoes > Rede e Internet, onde se troca Publica por Privada."""
    if sys.platform != "win32":
        return False
    os.startfile(NETWORK_SETTINGS_URI)
    return True


def firewall_command(exe_path: str) -> tuple[str, str]:
    """(programa, parametros) para recriar a regra com o mesmo script do instalador."""
    script = PureWindowsPath(exe_path).parent / FIREWALL_SCRIPT
    return "cmd.exe", f'/c ""{script}" add "{exe_path}""'


def create_firewall_rule(exe_path: str | None) -> bool:
    """Pede permissao de administrador e roda o firewall.cmd do instalador.

    Devolve False sem o .exe instalado, sem o script ou se a pessoa recusar o pedido: o
    diagnostico roda de novo e mostra o mesmo problema, sem caixa de erro.
    """
    if sys.platform != "win32" or exe_path is None:
        return False
    if not (Path(exe_path).parent / FIREWALL_SCRIPT).exists():
        logger.warning("firewall.cmd nao encontrado ao lado de %s", exe_path)
        return False
    import ctypes

    program, params = firewall_command(exe_path)
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", program, params, None, 0)
    if result <= 32:  # ShellExecute: ate 32 e erro (inclusive a pessoa recusar)
        logger.info("Criacao da regra do firewall nao concluida (codigo %s)", result)
        return False
    logger.info("Pedido para criar a regra do firewall enviado")
    return wait_for_rule()


def wait_for_rule(timeout_s: float = 20.0, interval_s: float = 1.0) -> bool:
    """O ShellExecute volta antes do netsh terminar: espera a regra aparecer."""
    from pcx_agent.diagnostics.checks import RULE_NAME
    from pcx_agent.diagnostics.windows import read_firewall_rules

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rules = read_firewall_rules()
        if rules and any(rule.name == RULE_NAME for rule in rules):
            return True
        time.sleep(interval_s)
    return False
