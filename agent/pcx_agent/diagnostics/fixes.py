"""Correcoes oferecidas pelo diagnostico. Cada uma so abre algo; a pessoa confirma no Windows."""

import logging
import os
import sys
from pathlib import Path, PureWindowsPath

logger = logging.getLogger("pcx_agent.diagnostics")
NETWORK_SETTINGS_URI = "ms-settings:network-status"
FIREWALL_SCRIPT = "firewall.cmd"  # instalado ao lado do .exe (packaging/installer.iss)


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
    return True
